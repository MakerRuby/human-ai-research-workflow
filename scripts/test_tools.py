#!/usr/bin/env python3
"""Behavior tests in disposable projects; no live project or original ZIP is edited."""

from argparse import Namespace
import contextlib
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import check_project
import init_project


class ProjectToolsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ai-blueprint-test-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "project"

    def args(self, **overrides):
        values = dict(target=str(self.root), name="测试项目", scale="M", profile="general",
                      dry_run=False, date="2026-10-23")
        values.update(overrides)
        return Namespace(**values)

    def init(self, **overrides):
        return init_project.initialize(self.args(**overrides))

    def write(self, relative, text="evidence\n"):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def save_state(self, state):
        self.write("_pm/project-state.json", json.dumps(state, ensure_ascii=False))

    def fixture(self):
        self.init(profile="research")
        artifacts, checks = [], []
        for identity, file, parents in (
            ("DATA", "data/source.csv", []),
            ("RESULT", "results/model.json", [{"id": "DATA", "version": "v1"}]),
            ("FIG", "results/fig.svg", [{"id": "RESULT", "version": "v1"}]),
            ("TEXT", "manuscript.md", [{"id": "FIG", "version": "v1"}]),
        ):
            self.write(file, identity + "\n")
            evidence = f"reviews/{identity}.md"
            self.write(evidence)
            artifacts.append({"id": identity, "path": file, "version": "v1", "status": "accepted",
                              "depends_on": parents, "required_checks": [f"C-{identity}"],
                              "sha256": hashlib.sha256((self.root / file).read_bytes()).hexdigest(),
                              "acceptance": {"by": "owner", "rationale": "reviewed"}})
            checks.append({"id": f"C-{identity}", "artifact": identity, "version": "v1", "kind": "professional",
                           "status": "pass", "required": True, "by": "reviewer", "rationale": "scope-specific review",
                           "evidence": [evidence]})
        gates = [
            {"id": "G1", "status": "pass", "artifacts": ["DATA"], "checks": ["C-DATA"], "depends_on": [],
             "by": "owner", "rationale": "fixture only", "evidence": ["reviews/DATA.md"]},
            {"id": "G2", "status": "pass", "artifacts": ["RESULT"], "checks": ["C-RESULT"], "depends_on": ["G1"],
             "by": "owner", "rationale": "fixture only", "evidence": ["reviews/RESULT.md"]},
            {"id": "G3", "status": "pass", "artifacts": ["TEXT"], "checks": ["C-TEXT"], "depends_on": ["G2"],
             "by": "owner", "rationale": "fixture only", "evidence": ["reviews/TEXT.md"]},
        ]
        state = {"schema_version": 1, "project": {"name": "fixture", "profile": "research"},
                 "artifacts": artifacts, "checks": checks,
                 "tasks": [{"id": "T-TEXT", "status": "done", "inputs": [{"id": "FIG", "version": "v1"}], "outputs": ["TEXT"]}],
                 "gates": gates}
        self.save_state(state)
        return state

    def audit(self, **kwargs):
        return check_project.check_project(self.root, **kwargs)

    def test_small_scale_does_not_create_target(self):
        self.assertEqual(self.init(scale="S")["created"], [])
        self.assertFalse(self.root.exists())

    def test_dry_run_does_not_create_target(self):
        result = self.init(scale="L", profile="research", dry_run=True)
        self.assertIn("_pm/research/RESEARCH_PLAN.md", result["would_create"])
        self.assertFalse(self.root.exists())

    def test_medium_layout_and_unicode_name(self):
        name = '研究: "糖尿病" \\ cohort'
        result = self.init(name=name)
        self.assertIn("_pm/LAYOUT.md", result["created"])
        self.assertNotIn("references/INDEX.md", result["created"])
        config = json.loads((self.root / "_pm/config.json").read_text(encoding="utf-8"))
        self.assertEqual(config["project_name"], name)
        self.assertIsNone(config["reproducibility"]["seed"])
        self.assertFalse((self.root / "_pm/WBS.md").exists())
        self.assertTrue(self.audit()["ok"])

    def test_initialized_project_documents_state_roles_and_triggers(self):
        self.init()
        for relative in ("README.md", "AI_CONTRACT.md", "_pm/BRIEF.md", "_pm/STATUS.md", "_pm/LAYOUT.md"):
            with self.subTest(relative=relative):
                content = (self.root / relative).read_text(encoding="utf-8")
                self.assertIn("**作用**", content)
                self.assertIn("**不负责**", content)
                self.assertIn("**读者**", content)
                self.assertIn("**更新触发**", content)
                self.assertIn("**相邻文档**", content)

    def test_large_research_layout_and_initial_gate(self):
        result = self.init(scale="L", profile="research")
        self.assertIn("references/INDEX.md", result["created"])
        self.assertIn("references/sources/REFERENCE_CARD.md", result["created"])
        self.assertIn("_pm/research/EXPOSURE_LOG.md", result["created"])
        self.assertTrue((self.root / "_pm/templates/task-package.md").is_file())
        self.assertTrue((self.root / "references/INDEX.md").is_file())
        self.assertTrue((self.root / "references/sources/REFERENCE_CARD.md").is_file())
        self.assertTrue(self.audit()["ok"])
        self.assertFalse(self.audit(require_gate="G3")["ok"])

    def test_medium_research_initializes_source_index_and_card(self):
        result = self.init(profile="research")
        self.assertIn("references/INDEX.md", result["created"])
        self.assertIn("references/sources/REFERENCE_CARD.md", result["created"])
        index = (self.root / "references/INDEX.md").read_text(encoding="utf-8")
        card = (self.root / "references/sources/REFERENCE_CARD.md").read_text(encoding="utf-8")
        self.assertIn("candidate", index)
        self.assertIn("准确位置", card)
        self.assertTrue(self.audit()["ok"])

    def test_research_reference_templates_preserve_existing_files(self):
        self.write("references/INDEX.md", "project-owned index\n")
        result = self.init(profile="research")
        self.assertIn("references/INDEX.md", result["skipped"])
        self.assertEqual((self.root / "references/INDEX.md").read_text(encoding="utf-8"), "project-owned index\n")
        self.assertTrue((self.root / "references/sources/REFERENCE_CARD.md").is_file())

    def test_rerun_preserves_modified_records(self):
        self.init()
        self.write("AI_CONTRACT.md", "custom contract")
        before = {p.relative_to(self.root).as_posix(): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        result = self.init()
        after = {p.relative_to(self.root).as_posix(): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual(result["created"], [])
        self.assertEqual(before, after)

    def test_existing_yaml_remains_source_of_truth(self):
        self.write("_pm/config.yaml", "name: existing\n")
        result = self.init()
        self.assertEqual(result["config_path"], "_pm/config.yaml")
        self.assertFalse((self.root / "_pm/config.json").exists())
        self.assertIn("_pm/config.yaml", (self.root / "AI_CONTRACT.md").read_text(encoding="utf-8"))

    def test_conflicting_configs_fail_before_writes(self):
        self.write("_pm/config.yaml")
        self.write("_pm/config.json", "{}")
        with self.assertRaises(ValueError):
            self.init()
        self.assertFalse((self.root / "AI_CONTRACT.md").exists())

    def test_changed_profile_requires_migration(self):
        self.init()
        with self.assertRaises(ValueError):
            self.init(profile="research")
        self.assertFalse((self.root / "_pm/research").exists())

    def test_missing_template_preflight_leaves_no_project(self):
        copied = self.base / "templates"
        shutil.copytree(init_project.ASSETS, copied)
        (copied / "STATUS.md").unlink()
        with patch.object(init_project, "ASSETS", copied):
            with self.assertRaises(OSError):
                self.init()
        self.assertFalse(self.root.exists())

    def test_write_failure_rolls_back_only_new_files(self):
        self.write("AI_CONTRACT.md", "preserve")
        actual_open = Path.open

        def controlled_open(path, mode="r", *args, **kwargs):
            if path.name == "STATUS.md" and mode == "x":
                raise OSError("simulated failure")
            return actual_open(path, mode, *args, **kwargs)

        with patch.object(Path, "open", controlled_open):
            with self.assertRaises(OSError):
                self.init()
        self.assertEqual((self.root / "AI_CONTRACT.md").read_text(), "preserve")
        self.assertFalse((self.root / "_pm").exists())

    def test_symlink_write_escape_is_rejected(self):
        outside = self.base / "outside"
        outside.mkdir()
        self.root.mkdir()
        try:
            (self.root / "_pm").symlink_to(outside, target_is_directory=True)
        except OSError as error:
            self.skipTest(f"OS did not allow symlink creation: {error}")
        with self.assertRaises(ValueError):
            self.init()
        self.assertEqual(list(outside.iterdir()), [])
        self.assertFalse((self.root / "AI_CONTRACT.md").exists())

    @unittest.skipUnless(os.name == "nt", "Windows junction behavior")
    def test_windows_junction_write_escape_is_rejected(self):
        outside = self.base / "outside"
        outside.mkdir()
        self.root.mkdir()
        link = self.root / "_pm"
        result = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(outside)], capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        try:
            with self.assertRaises(ValueError):
                self.init()
            self.assertEqual(list(outside.iterdir()), [])
            self.assertFalse((self.root / "AI_CONTRACT.md").exists())
        finally:
            link.rmdir()

    @unittest.skipUnless(os.name == "nt", "Windows junction behavior")
    def test_windows_junction_evidence_escape_is_rejected(self):
        self.fixture()
        outside = self.base / "outside"
        outside.mkdir()
        (outside / "DATA.md").write_text("external evidence", encoding="utf-8")
        link = self.root / "external"
        result = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(outside)], capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        try:
            state_path = self.root / "_pm/project-state.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["checks"][0]["evidence"] = ["external/DATA.md"]
            self.save_state(state)
            report = self.audit()
            self.assertFalse(report["ok"])
            self.assertTrue(any("escapes the project" in e for e in report["errors"]), report)
        finally:
            link.rmdir()

    def test_valid_evidence_chain_and_read_only_impact(self):
        self.fixture()
        before = {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        report = self.audit(impact="DATA", require_gate="G3", verify_hashes=True)
        self.assertTrue(report["ok"], report)
        self.assertEqual(report["impact"]["artifacts"], ["FIG", "RESULT", "TEXT"])
        self.assertEqual(report["impact"]["tasks"], ["T-TEXT"])
        self.assertEqual(report["impact"]["gates"], ["G1", "G2", "G3"])
        self.assertEqual(before, {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()})

    def test_version_change_reaches_all_descendants_tasks_and_gates(self):
        state = self.fixture()
        state["artifacts"][0]["version"] = "v2"
        self.save_state(state)
        report = self.audit(impact="DATA")
        self.assertFalse(report["ok"])
        self.assertEqual(report["stale_artifacts"], ["FIG", "RESULT", "TEXT"])
        self.assertTrue(any("T-TEXT" in e and "reopen" in e for e in report["errors"]))
        self.assertTrue(any("G3" in e and "reopen" in e for e in report["errors"]))

    def test_marking_stale_reopening_tasks_and_gates_is_consistent(self):
        state = self.fixture()
        state["artifacts"][0]["version"] = "v2"
        state["artifacts"][0]["status"] = "produced"
        for row in state["artifacts"][1:]:
            row["status"] = "stale"
        state["tasks"][0]["status"] = "todo"
        for gate in state["gates"]:
            gate["status"] = "pending"
        self.save_state(state)
        report = self.audit()
        self.assertTrue(report["ok"], report)
        self.assertEqual(len(report["warnings"]), 3)

    def test_acceptance_without_checks_or_reviewer_fails(self):
        state = self.fixture()
        state["artifacts"][1]["required_checks"] = []
        state["artifacts"][1].pop("acceptance")
        self.save_state(state)
        report = self.audit()
        self.assertFalse(report["ok"])
        self.assertTrue(any("acceptance" in e for e in report["errors"]))

    def test_required_check_cannot_be_waived(self):
        state = self.fixture()
        state["checks"][1]["status"] = "waived"
        state["checks"][1]["waiver_reason"] = "not available"
        self.save_state(state)
        self.assertFalse(self.audit()["ok"])

    def test_optional_waiver_does_not_replace_required_review(self):
        state = self.fixture()
        row = copy.deepcopy(state["checks"][0])
        row.update(id="OPTIONAL", required=False, status="waived", waiver_reason="out of scope")
        state["checks"].append(row)
        self.save_state(state)
        self.assertTrue(self.audit()["ok"])

    def test_professional_review_is_enforced_when_required(self):
        state = self.fixture()
        state["artifacts"][0]["requires_professional_review"] = True
        state["checks"][0]["kind"] = "machine"
        self.save_state(state)
        self.assertFalse(self.audit()["ok"])

    def test_missing_evidence_file_fails(self):
        self.fixture()
        (self.root / "reviews/FIG.md").unlink()
        self.assertFalse(self.audit()["ok"])

    def test_hash_tampering_fails_when_requested(self):
        self.fixture()
        self.write("results/fig.svg", "changed content")
        self.assertTrue(self.audit()["ok"])
        report = self.audit(verify_hashes=True)
        self.assertFalse(report["ok"])
        self.assertTrue(any("sha256 mismatch" in e for e in report["errors"]))

    def test_unrecorded_hashes_are_reported(self):
        state = self.fixture()
        del state["artifacts"][0]["sha256"]
        self.save_state(state)
        report = self.audit(verify_hashes=True)
        self.assertTrue(report["ok"])
        self.assertEqual(report["hashes_not_recorded"], ["DATA"])

    def test_dependency_cycle_fails(self):
        state = self.fixture()
        state["artifacts"][0]["depends_on"] = [{"id": "TEXT", "version": "v1"}]
        self.save_state(state)
        self.assertTrue(any("cycle" in e for e in self.audit()["errors"]))

    def test_gate_cycle_and_nonpass_prerequisite_fail(self):
        state = self.fixture()
        state["gates"][0]["depends_on"] = ["G3"]
        state["gates"][1]["status"] = "conditional"
        self.save_state(state)
        report = self.audit(require_gate="G3")
        self.assertFalse(report["ok"])
        self.assertTrue(any("cycle" in e for e in report["errors"]))
        self.assertTrue(any("prerequisite" in e for e in report["errors"]))

    def test_invalid_records_and_path_escape_fail(self):
        state = self.fixture()
        state["artifacts"][0]["path"] = "../outside.csv"
        state["artifacts"].append(copy.deepcopy(state["artifacts"][1]))
        state["tasks"][0]["inputs"] = [{"id": "UNKNOWN", "version": "v1"}]
        self.save_state(state)
        report = self.audit()
        self.assertFalse(report["ok"])
        for text in ("within the project", "duplicate", "unknown artifact"):
            self.assertTrue(any(text in e for e in report["errors"]), report)

    def test_malformed_json_and_top_level_are_errors(self):
        for content in ("{broken", "[]", '{"schema_version":true}'):
            self.write("_pm/project-state.json", content)
            self.assertFalse(self.audit()["ok"])

    def test_recorded_command_is_never_executed(self):
        state = self.fixture()
        state["checks"][0]["command"] = "create forbidden-sentinel.txt"
        self.save_state(state)
        self.assertTrue(self.audit()["ok"])
        self.assertFalse((self.root / "forbidden-sentinel.txt").exists())

    def test_cli_exit_codes_and_json(self):
        self.init(profile="research")
        script = Path(check_project.__file__)
        success = subprocess.run([sys.executable, str(script), "--project", str(self.root)], capture_output=True, text=True, encoding="utf-8")
        failed = subprocess.run([sys.executable, str(script), "--project", str(self.root), "--require-gate", "G3"], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(success.returncode, 0, success.stderr)
        self.assertTrue(json.loads(success.stdout)["ok"])
        self.assertEqual(failed.returncode, 1, failed.stderr)
        self.assertFalse(json.loads(failed.stdout)["ok"])

    def test_invalid_date_cli_does_not_write(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = init_project.main(["--target", str(self.root), "--name", "project", "--date", "2026-99-99"])
        self.assertEqual(result, 1)
        self.assertFalse(self.root.exists())


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    unittest.main(verbosity=2)
