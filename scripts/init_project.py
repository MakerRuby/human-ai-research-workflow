#!/usr/bin/env python3
"""Create minimal project records without replacing existing files (stdlib only)."""

import argparse
from datetime import date
import json
from pathlib import Path
import sys


ASSETS = Path(__file__).resolve().parents[1] / "assets"


def check_destination(root, relative):
    destination = root / relative
    if not destination.resolve().is_relative_to(root):
        raise ValueError(f"Write path escapes project (symbolic link or junction): {destination}")
    cursor = destination
    while cursor != root:
        if cursor.is_symlink() or getattr(cursor, "is_junction", lambda: False)():
            raise ValueError(f"Refusing symbolic-link write path: {cursor}")
        if cursor.exists() and cursor != destination and not cursor.is_dir():
            raise ValueError(f"Parent is not a directory: {cursor}")
        cursor = cursor.parent
    if destination.exists() and not destination.is_file():
        raise ValueError(f"Destination is not a file: {destination}")
    return destination


def initialize(args):
    root = Path(args.target).expanduser().resolve()
    if root.exists() and not root.is_dir():
        raise ValueError(f"Project target is not a directory: {root}")
    if args.scale == "S":
        return {"mode": "advice_only", "created": [], "skipped": [],
                "message": "S scale creates no files; use the existing task context."}

    # Resolve and validate all inputs and destinations before the first write.
    config_path = "_pm/config.json"
    json_config = check_destination(root, config_path)
    yaml_config = check_destination(root, "_pm/config.yaml")
    yml_config = check_destination(root, "_pm/config.yml")
    existing_configs = [p for p in (json_config, yaml_config, yml_config) if p.exists()]
    if len(existing_configs) > 1:
        raise ValueError("Multiple configuration files exist; resolve the source of truth first.")
    if existing_configs:
        config_path = existing_configs[0].relative_to(root).as_posix()

    state_path = check_destination(root, "_pm/project-state.json")
    if state_path.exists():
        existing = json.loads(state_path.read_text(encoding="utf-8-sig"))
        if not isinstance(existing, dict) or existing.get("schema_version") not in (1, 2):
            raise ValueError("Existing state has an unsupported structure; review migration first.")
        project = existing.get("project", {})
        if not isinstance(project, dict):
            raise ValueError("Existing state has an invalid project record.")
        if project.get("name") != args.name or project.get("profile") != args.profile:
            raise ValueError("Existing project name/profile differs; review migration instead of creating conflicting records.")

    substitutions = {"{{PROJECT_NAME}}": args.name, "{{DATE}}": args.date,
                     "{{PROFILE}}": args.profile, "{{CONFIG_PATH}}": config_path}
    template_map = {
        "README.md": "PROJECT_README.md",
        "AI_CONTRACT.md": "AI_CONTRACT.md",
        "_pm/BRIEF.md": "BRIEF.md",
        "_pm/STATUS.md": "STATUS.md",
        "_pm/LAYOUT.md": "LAYOUT.md",
    }
    # Host adapters contain navigation only; the contract remains authoritative.
    entries = [] if getattr(args, "no_ai_entry", False) else (getattr(args, "ai_entry", None) or ["agents", "claude"])
    for entry in entries:
        template_map[{"agents": "AGENTS.md", "claude": "CLAUDE.md"}[entry]] = "AI_ENTRY.md"
    substitutions["{{SKILL_PATH}}"] = str(Path(__file__).resolve().parents[1])
    if args.scale == "L":
        template_map.update({
            "_pm/WBS.md": "WBS.md", "_pm/DECISIONS.md": "DECISIONS.md",
            "_pm/FINDINGS.md": "FINDINGS.md",
            "_pm/templates/REVIEW.md": "REVIEW.md",
            "_pm/templates/task-package.md": "task-package.md",
        })
    if args.profile == "research":
        for name in ("RESEARCH_PLAN.md", "DATA_REGISTER.md", "EXPOSURE_LOG.md"):
            template_map[f"_pm/research/{name}"] = f"research/{name}"
        template_map["_pm/research/REPRODUCIBILITY.md"] = "research/REPRODUCIBILITY.md"
        template_map["references/INDEX.md"] = "research/REFERENCES_INDEX.md"
        template_map["references/sources/REFERENCE_CARD.md"] = "research/REFERENCE_CARD.md"
        template_map["_pm/templates/run-spec.json"] = "run-spec.json"
        template_map["_pm/templates/release-spec.json"] = "release-spec.json"
        template_map["_pm/templates/reproduction-spec.json"] = "reproduction-spec.json"
        template_map["_pm/templates/change-spec.json"] = "change-spec.json"
        if args.scale != "L":
            template_map["_pm/FINDINGS.md"] = "FINDINGS.md"
            template_map["_pm/DECISIONS.md"] = "DECISIONS.md"

    plans = {}
    for destination, source in template_map.items():
        content = (ASSETS / source).read_text(encoding="utf-8")
        for key, value in substitutions.items():
            content = content.replace(key, value)
        plans[destination] = content

    config = {"schema_version": 1, "project_name": args.name, "profile": args.profile,
              "created_on": args.date, "parameters": {},
              "environment": {"runtime": None, "dependencies": None},
              "reproducibility": {"seed": None, "tolerance": None},
              "authorization": {"autonomous_scope": None, "external_actions": None}}
    if not existing_configs:
        plans[config_path] = json.dumps(config, ensure_ascii=False, indent=2) + "\n"
    gates = []
    if args.profile == "research":
        for gate_id, dependencies in (("G1", []), ("G2", ["G1"]), ("G3", ["G2"])):
            gates.append({"id": gate_id, "status": "pending", "artifacts": [],
                          "checks": [], "depends_on": dependencies})
    state = {"schema_version": 2, "project": {"name": args.name, "profile": args.profile},
             "layout": {"management": "_pm", "references": "references", "raw_data": "data/raw",
                        "interim_data": "data/interim", "analysis_data": "data/processed", "code": "src",
                        "exploration": "notebooks", "runs": "runs", "results": "results",
                        "manuscript": "manuscript", "releases": "releases", "review": "review", "archive": "archive"},
             "artifacts": [], "checks": [], "tasks": [], "gates": gates,
             "findings": [], "decisions": [], "changes": [], "claims": [], "risks": [],
             "review_items": [], "runs": [], "reproductions": []}
    plans["_pm/project-state.json"] = json.dumps(state, ensure_ascii=False, indent=2) + "\n"

    pending, skipped = [], []
    for relative, content in plans.items():
        destination = check_destination(root, relative)
        if destination.exists():
            skipped.append(relative)
        else:
            pending.append((relative, destination, content))
    if args.dry_run:
        return {"mode": "dry_run", "would_create": [r for r, _, _ in pending],
                "created": [], "skipped": skipped, "config_path": config_path}

    created_files, created_dirs = [], []
    try:
        for _, destination, content in pending:
            missing = []
            parent = destination.parent
            while not parent.exists():
                missing.append(parent)
                parent = parent.parent
            for directory in reversed(missing):
                directory.mkdir()
                created_dirs.append(directory)
            check_destination(root, destination.relative_to(root))
            with destination.open("x", encoding="utf-8", newline="\n") as output:
                created_files.append(destination)
                output.write(content)
    except (OSError, ValueError):
        # Only roll back files created by this invocation, never existing content.
        for path in reversed(created_files):
            path.unlink(missing_ok=True)
        for path in reversed(created_dirs):
            try:
                path.rmdir()
            except OSError:
                pass
        raise
    return {"mode": "initialized", "created": [r for r, _, _ in pending],
            "skipped": skipped, "config_path": config_path,
            "message": "Templates are drafts; no scientific gate has been passed."}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--scale", choices=("S", "M", "L"), default="M")
    parser.add_argument("--profile", choices=("general", "research"), default="general")
    entry_options = parser.add_mutually_exclusive_group()
    entry_options.add_argument("--ai-entry", action="append", choices=("agents", "claude"),
                               help="Select host entries; defaults to both. Existing files are preserved.")
    entry_options.add_argument("--no-ai-entry", action="store_true", help="Do not create host entry files.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--date", default=date.today().isoformat())
    args = parser.parse_args(argv)
    try:
        date.fromisoformat(args.date)
        if not args.name.strip():
            raise ValueError("Project name must not be empty.")
        result = initialize(args)
    except (OSError, ValueError, TypeError) as error:
        print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False))
        return 1
    print(json.dumps({"ok": True, **result}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
