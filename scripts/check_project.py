#!/usr/bin/env python3
"""Read-only consistency and transitive-impact checks; never validate scientific truth."""

import argparse
from collections import deque
import hashlib
import json
from pathlib import Path, PureWindowsPath
import re
import sys


ARTIFACT_STATUSES = {"draft", "produced", "checked", "accepted", "stale", "rejected"}
CHECK_STATUSES = {"pending", "pass", "fail", "waived"}
TASK_STATUSES = {"todo", "doing", "blocked", "done"}
GATE_STATUSES = {"pending", "conditional", "pass", "fail"}


class Audit:
    def __init__(self, root, state, verify_hashes=False):
        self.root = root.resolve()
        self.state = state
        self.verify_hashes = verify_hashes
        self.errors = []
        self.warnings = []
        self.unhashed = []
        self.stale = set()

    def error(self, message):
        self.errors.append(message)

    def index(self, key, statuses):
        rows = self.state.get(key)
        if not isinstance(rows, list):
            self.error(f"{key}: expected a list")
            return {}
        indexed = {}
        for row in rows:
            if not isinstance(row, dict) or not self.nonempty(row.get("id")):
                self.error(f"{key}: each record needs a nonempty string id")
                continue
            identity = row["id"]
            if identity in indexed:
                self.error(f"{key}: duplicate id {identity}")
                continue
            indexed[identity] = row
            if row.get("status") not in statuses:
                self.error(f"{identity}: invalid status")
        return indexed

    @staticmethod
    def nonempty(value):
        return isinstance(value, str) and bool(value.strip())

    def ids(self, row, key):
        value = row.get(key)
        if not isinstance(value, list) or any(not self.nonempty(v) for v in value):
            self.error(f"{row.get('id', '?')}.{key}: expected a list of ids")
            return []
        if len(set(value)) != len(value):
            self.error(f"{row.get('id', '?')}.{key}: duplicate references")
        return value

    def version_refs(self, row, key, artifacts):
        value = row.get(key)
        if not isinstance(value, list):
            self.error(f"{row['id']}.{key}: expected a list")
            return []
        result, seen = [], set()
        for dep in value:
            if not isinstance(dep, dict) or not self.nonempty(dep.get("id")) or not self.nonempty(dep.get("version")):
                self.error(f"{row['id']}.{key}: expected id/version records")
                continue
            if dep["id"] in seen:
                self.error(f"{row['id']}.{key}: duplicate reference {dep['id']}")
            seen.add(dep["id"])
            if dep["id"] not in artifacts:
                self.error(f"{row['id']}.{key}: unknown artifact {dep['id']}")
                continue
            result.append(dep)
        return result

    def file(self, value, label):
        if not self.nonempty(value):
            self.error(f"{label}: expected a project-relative file path")
            return None
        windows = PureWindowsPath(value)
        path = Path(value)
        if path.is_absolute() or windows.drive or windows.root or ".." in windows.parts or ".." in path.parts:
            self.error(f"{label}: path must stay within the project")
            return None
        try:
            resolved = (self.root / path).resolve()
            if not resolved.is_relative_to(self.root):
                self.error(f"{label}: symbolic link escapes the project")
                return None
            if not resolved.is_file():
                self.error(f"{label}: missing file {value}")
                return None
            return resolved
        except (OSError, ValueError, RuntimeError) as error:
            self.error(f"{label}: invalid path: {error}")
            return None

    def evidence(self, row):
        for key in ("by", "rationale"):
            if not self.nonempty(row.get(key)):
                self.error(f"{row['id']}: completed review requires {key}")
        paths = row.get("evidence")
        if not isinstance(paths, list) or not paths:
            self.error(f"{row['id']}: completed review requires evidence files")
        else:
            for path in paths:
                self.file(path, f"{row['id']}.evidence")

    def cycles(self, graph, label):
        degrees = {key: len(set(values)) for key, values in graph.items()}
        children = {key: [] for key in graph}
        for child, parents in graph.items():
            for parent in set(parents):
                children[parent].append(child)
        queue = deque(key for key, count in degrees.items() if count == 0)
        while queue:
            for child in children[queue.popleft()]:
                degrees[child] -= 1
                if degrees[child] == 0:
                    queue.append(child)
        unresolved = sorted(key for key, count in degrees.items() if count)
        if unresolved:
            self.error(f"{label}: dependency cycle or blocked descendant: {', '.join(unresolved)}")
        return children

    @staticmethod
    def descendants(seeds, children):
        reached = set(seeds)
        queue = deque(seeds)
        while queue:
            for child in children.get(queue.popleft(), []):
                if child not in reached:
                    reached.add(child)
                    queue.append(child)
        return reached

    def run(self, impact=None, require_gate=None):
        if type(self.state.get("schema_version")) is not int or self.state.get("schema_version") not in (1, 2):
            self.error("Unsupported schema_version; expected integer 1 or 2")
        project = self.state.get("project")
        if not isinstance(project, dict) or not self.nonempty(project.get("name")) or project.get("profile") not in {"general", "research"}:
            self.error("project: name and general/research profile are required")
        artifacts = self.index("artifacts", ARTIFACT_STATUSES)
        checks = self.index("checks", CHECK_STATUSES)
        tasks = self.index("tasks", TASK_STATUSES)
        gates = self.index("gates", GATE_STATUSES)

        graph, direct_stale = {}, set()
        for identity, row in artifacts.items():
            if row.get('lifecycle', 'active') not in {'active', 'retired'}:
                self.error(f"{identity}: lifecycle must be active or retired")
            if row.get('lifecycle') == 'retired':
                retirement = row.get('retirement')
                if not isinstance(retirement, dict):
                    self.error(f"{identity}: retired artifact needs retirement record")
                else:
                    for field in ('by', 'at', 'reason', 'disposition'):
                        if not self.nonempty(retirement.get(field)):
                            self.error(f"{identity}: retirement needs {field}")
                    manifest_file = self.file(retirement.get('manifest'), identity + '.retirement')
                    snapshot_file = self.file(retirement.get('snapshot'), identity + '.snapshot')
                    evidence = retirement.get('evidence')
                    if not isinstance(evidence, list) or not evidence:
                        self.error(f"{identity}: retirement needs evidence")
                    else:
                        for path in evidence:
                            self.file(path, identity + '.retirement.evidence')
                    if manifest_file and snapshot_file:
                        manifest = json.loads(manifest_file.read_text(encoding='utf-8-sig'))
                        entry = next((e for e in manifest.get('files', []) if e.get('id') == identity), None)
                        if not entry or entry.get('version') != row.get('version'):
                            self.error(f"{identity}: retirement manifest does not match artifact version")
                        elif self.verify_hashes:
                            hasher = hashlib.sha256()
                            with snapshot_file.open('rb') as source:
                                for chunk in iter(lambda: source.read(1024*1024), b''):
                                    hasher.update(chunk)
                            if hasher.hexdigest() != entry.get('sha256'):
                                self.error(f"{identity}: archived snapshot hash mismatch")
            if not self.nonempty(row.get("version")):
                self.error(f"{identity}: version must be a nonempty string")
            file = self.file(row.get("path"), identity)
            digest = row.get("sha256")
            if "requires_reproduction" in row and type(row["requires_reproduction"]) is not bool:
                self.error(f"{identity}: requires_reproduction must be boolean")
            if digest is not None and (not isinstance(digest, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", digest)):
                self.error(f"{identity}: invalid sha256")
            elif self.verify_hashes:
                if digest is None:
                    self.unhashed.append(identity)
                elif file:
                    hasher = hashlib.sha256()
                    with file.open("rb") as source:
                        for chunk in iter(lambda: source.read(1024 * 1024), b""):
                            hasher.update(chunk)
                    if hasher.hexdigest().lower() != digest.lower():
                        self.error(f"{identity}: sha256 mismatch")
            dependencies = self.version_refs(row, "depends_on", artifacts)
            if row.get('lifecycle', 'active') == 'active' and row.get('status') == 'accepted' and any(artifacts[d['id']].get('lifecycle') == 'retired' for d in dependencies):
                self.error(f"{identity}: active accepted artifact uses retired input; open change and re-evaluate")
            graph[identity] = [dep["id"] for dep in dependencies]
            if row.get("status") == "stale" or any(artifacts[d["id"]].get("version") != d["version"] for d in dependencies):
                direct_stale.add(identity)
        children = self.cycles(graph, "artifacts")
        self.stale = self.descendants(direct_stale, children)
        for identity in sorted(self.stale):
            if artifacts[identity].get("status") != "stale":
                self.error(f"{identity}: stale input or transitive dependency; mark stale and reopen downstream work")
            else:
                self.warnings.append(f"{identity}: stale; rerun/review is pending")

        for identity, row in checks.items():
            artifact = artifacts.get(row.get("artifact")) if isinstance(row.get("artifact"), str) else None
            if artifact is None:
                self.error(f"{identity}: unknown check artifact")
            if not self.nonempty(row.get("version")):
                self.error(f"{identity}: missing check version")
            if row.get("kind") not in {"machine", "professional", "source"}:
                self.error(f"{identity}: invalid check kind")
            if type(row.get("required")) is not bool:
                self.error(f"{identity}: required must be boolean")
            if row.get("status") in {"pass", "fail", "waived"}:
                self.evidence(row)
            if row.get("status") == "waived" and (row.get("required") is not False or not self.nonempty(row.get("waiver_reason"))):
                self.error(f"{identity}: only nonrequired checks with waiver_reason may be waived")

        for identity, row in artifacts.items():
            required = self.ids(row, "required_checks")
            if "requires_professional_review" in row and type(row["requires_professional_review"]) is not bool:
                self.error(f"{identity}: requires_professional_review must be boolean")
            for check_id in required:
                check = checks.get(check_id)
                if check is None or check.get("artifact") != identity:
                    self.error(f"{identity}: missing or unrelated required check {check_id}")
                elif check.get("required") is not True:
                    self.error(f"{identity}: required check {check_id} must set required=true")
            current_checks = [c for c in checks.values() if c.get("artifact") == identity and c.get("version") == row.get("version")]
            if row.get("status") == "checked" and not any(c.get("status") in {"pass", "fail", "waived"} for c in current_checks):
                self.error(f"{identity}: checked status needs a current completed check")
            if row.get("status") != "accepted":
                continue
            acceptance = row.get("acceptance")
            if not isinstance(acceptance, dict) or not all(self.nonempty(acceptance.get(k)) for k in ("by", "rationale")):
                self.error(f"{identity}: accepted status requires acceptance.by and rationale")
            if not required:
                self.error(f"{identity}: accepted status requires at least one necessary check")
            for check in current_checks:
                if check.get("required") is True and check["id"] not in required:
                    self.error(f"{identity}: necessary check {check['id']} is not linked")
            for check_id in required:
                check = checks.get(check_id, {})
                if check.get("version") != row.get("version") or check.get("status") != "pass":
                    self.error(f"{identity}: required check {check_id} is not current pass")
            if row.get("requires_professional_review") is True and not any(
                c.get("kind") == "professional" and c.get("status") == "pass" and c["id"] in required for c in current_checks
            ):
                self.error(f"{identity}: current necessary professional review is missing")

        task_refs = {}
        for identity, row in tasks.items():
            inputs = self.version_refs(row, "inputs", artifacts)
            outputs = self.ids(row, "outputs")
            for output in outputs:
                if output not in artifacts:
                    self.error(f"{identity}: unknown output {output}")
            task_refs[identity] = {d["id"] for d in inputs} | set(outputs)
            if row.get("status") == "done":
                if any(artifacts[d['id']].get('lifecycle') == 'retired' for d in inputs):
                    self.error(f"{identity}: done task uses retired input")
                if not outputs:
                    self.error(f"{identity}: done needs an accepted output")
                if any(d["id"] in self.stale or artifacts[d["id"]].get("version") != d["version"] for d in inputs):
                    self.error(f"{identity}: done task has stale inputs; reopen it")
                if any(o in self.stale or artifacts.get(o, {}).get("status") != "accepted" for o in outputs):
                    self.error(f"{identity}: done task outputs must be current and accepted")

        gate_graph, gate_refs = {}, {}
        for identity, row in gates.items():
            parents = self.ids(row, "depends_on")
            for parent in parents:
                if parent not in gates:
                    self.error(f"{identity}: unknown prerequisite gate {parent}")
            gate_graph[identity] = [p for p in parents if p in gates]
            outputs = self.ids(row, "artifacts")
            check_ids = self.ids(row, "checks")
            gate_refs[identity] = set(outputs)
            for output in outputs:
                if output not in artifacts:
                    self.error(f"{identity}: unknown artifact {output}")
            for check_id in check_ids:
                check = checks.get(check_id)
                if check is None:
                    self.error(f"{identity}: unknown check {check_id}")
                else:
                    gate_refs[identity].add(check.get("artifact"))
            if row.get("status") != "pass":
                continue
            self.evidence(row)
            if not outputs or not check_ids:
                self.error(f"{identity}: passed gate needs artifacts and checks")
            if any(gates.get(p, {}).get("status") != "pass" for p in parents):
                self.error(f"{identity}: prerequisite gate is not pass")
            for output in outputs:
                if output in self.stale or artifacts.get(output, {}).get("status") != "accepted" or artifacts.get(output, {}).get('lifecycle') == 'retired':
                    self.error(f"{identity}: passed gate artifact {output} must be current and accepted")
            for check_id in check_ids:
                check = checks.get(check_id, {})
                artifact = artifacts.get(check.get("artifact"), {}) if isinstance(check.get("artifact"), str) else {}
                if check.get("status") != "pass" or check.get("version") != artifact.get("version") or check.get("artifact") in self.stale:
                    self.error(f"{identity}: gate check {check_id} is not current pass")
                if check.get("artifact") not in outputs:
                    self.error(f"{identity}: gate check {check_id} must cover a listed artifact")
        gate_children = self.cycles(gate_graph, "gates")
        invalid_gates = {g for g, refs in gate_refs.items() if refs & self.stale}
        invalid_gates = self.descendants(invalid_gates, gate_children)
        for identity in sorted(invalid_gates):
            if gates[identity].get("status") == "pass":
                self.error(f"{identity}: upstream evidence changed; reopen gate")

        if require_gate is not None and (require_gate not in gates or gates[require_gate].get("status") != "pass"):
            self.error(f"Required gate {require_gate} is absent or not pass")
        impact_result = None
        if impact is not None:
            if impact not in artifacts:
                self.error(f"Unknown impact artifact {impact}")
            else:
                affected = self.descendants({impact}, children)
                affected_gates = {g for g, refs in gate_refs.items() if refs & affected}
                affected_gates = self.descendants(affected_gates, gate_children)
                impact_result = {"source": impact, "artifacts": sorted(affected - {impact}),
                                 "tasks": sorted(t for t, refs in task_refs.items() if refs & affected),
                                 "gates": sorted(affected_gates)}
        extended = {}
        if self.state.get("schema_version") == 2:
            from governance import validate
            extended = validate(self, artifacts, tasks, gates, children, impact)
        if self.unhashed:
            self.warnings.append("Hash verification not available for: " + ", ".join(sorted(self.unhashed)))
        return {"ok": not self.errors, "errors": self.errors, "warnings": self.warnings,
                "counts": {"artifacts": len(artifacts), "checks": len(checks), "tasks": len(tasks), "gates": len(gates)},
                "stale_artifacts": sorted(self.stale), "impact": impact_result,
                "hashes_not_recorded": sorted(self.unhashed),
                "governance": extended,
                "scope": "Read-only record/file consistency; scientific validity and evidence truth are not verified."}


def check_project(project, impact=None, require_gate=None, verify_hashes=False):
    root = Path(project).expanduser().resolve()
    try:
        state_file = root / "_pm/project-state.json"
        if not state_file.resolve().is_relative_to(root):
            raise ValueError("State path escapes the project")
        state = json.loads(state_file.read_text(encoding="utf-8-sig"))
        if not isinstance(state, dict):
            raise ValueError("State must be a JSON object")
        return Audit(root, state, verify_hashes).run(impact, require_gate)
    except (OSError, ValueError, TypeError, RuntimeError, RecursionError, KeyError, AttributeError) as error:
        return {"ok": False, "errors": [f"Cannot validate project: {error}"], "warnings": [],
                "scope": "Read-only consistency check; no scientific validation."}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--impact")
    parser.add_argument("--require-gate")
    parser.add_argument("--verify-hashes", action="store_true")
    args = parser.parse_args(argv)
    report = check_project(args.project, args.impact, args.require_gate, args.verify_hashes)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
