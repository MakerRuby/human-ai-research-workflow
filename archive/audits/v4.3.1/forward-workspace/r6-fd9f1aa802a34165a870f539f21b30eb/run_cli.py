import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
SKILL = Path(r"D:\桌面\skill_barn\sci_skill\human-ai-research-workflow")
ALLOWED = {"init_project.py", "research_tree.py", "run_project.py", "check_project.py", "record.py"}
LOGS = ROOT / "logs"
LOGS.mkdir(exist_ok=True)
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
os.environ["PYTHONUTF8"] = "1"

def invoke(label, tool, arguments):
    if tool not in ALLOWED:
        raise ValueError("Only explicit official tools are allowed")
    log_path = LOGS / (label + ".json")
    if log_path.exists():
        raise FileExistsError(log_path)
    command = [sys.executable, "-X", "utf8", "-B", str(SKILL / "scripts" / tool), *arguments]
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    result = subprocess.run(command, cwd=ROOT, env=os.environ.copy(), capture_output=True, text=True, encoding="utf-8", errors="replace")
    finished = datetime.datetime.now(datetime.timezone.utc).isoformat()
    record = {"label": label, "argv": command, "cwd": str(ROOT), "started_at": started, "finished_at": finished, "exit_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr}
    log_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (LOGS / (label + ".stdout.txt")).write_text(result.stdout, encoding="utf-8")
    (LOGS / (label + ".stderr.txt")).write_text(result.stderr, encoding="utf-8")
    with (ROOT / "invocations.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, ensure_ascii=False) + "\n")
    print(json.dumps(record, ensure_ascii=False, indent=2))
    return result.returncode

if __name__ == "__main__":
    if sys.argv[1] == "help":
        jobs = [
            ("01-init-help", "init_project.py", ["--help"]),
            ("02-tree-help", "research_tree.py", ["--help"]),
            ("03-question-help", "research_tree.py", ["--project", str(ROOT / "project"), "question", "add", "--help"]),
            ("04-task-help", "research_tree.py", ["--project", str(ROOT / "project"), "task", "add", "--help"]),
            ("05-intent-help", "research_tree.py", ["--project", str(ROOT / "project"), "task", "intent", "--help"]),
            ("06-run-help", "run_project.py", ["--help"]),
            ("07-check-help", "check_project.py", ["--help"]),
            ("08-decision-help", "record.py", ["--project", str(ROOT / "project"), "decision", "--help"]),
        ]
        failures = [invoke(label, tool, args) for label, tool, args in jobs]
        raise SystemExit(any(failures))
    raise SystemExit(invoke(sys.argv[1], sys.argv[2], sys.argv[3:]))
