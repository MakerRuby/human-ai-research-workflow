import datetime
import hashlib
import json
from pathlib import Path
import shutil
import sys
from run_cli import invoke

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT / "project"
EVIDENCE = ROOT / "evidence"
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
def official(label, tool, args):
    code = invoke(label, tool, args)
    if code != 0:
        raise RuntimeError(label + " failed; preserved log must be inspected")
def write_new(path, content):
    if path.exists():
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")

first_run_hash = sha(PROJECT / "runs/RUN-001/run.json")
original_first = json.loads((PROJECT / "runs/RUN-001/run.json").read_text(encoding="utf-8"))
intent2 = """任务：T-001，沿用合成输入/代码，新路径登记第二份意图后生成第二份文本。
服务于：Q-001，检查当前意图更新不会回绑第一遍运行。
为什么现在做：第一遍运行已留存；现在才能检查新旧意图与运行的区分。
证据阶梯：单次实际运行 → 两次运行的版本绑定检查；非科研或独立复现。
预期结果及含义：v2绑定RUN-002且v1仍绑定RUN-001 → 本次记录一致；任一回绑/快照偏离 → 保留原件报告。
投入上限与停止条件：一次小文件、30秒；登记或预检查失败则不启动第二遍。
产出位置与登记编号：outputs/run-002.txt；RUN-002；保留v1及第一遍全部原件。
文档职责：第二版冻结意图；不代表真人批准/结果；读者为执行者/维护者；更新另路径；相邻为任务/运行记录。
"""
write_new(PROJECT / "_pm/intents/T-001-v2.md", intent2)
spec = {"id": "RUN-002", "task": "T-001", "stage": "analysis", "purpose": "Synthetic second text run with new-path v2 intent; no research data", "inputs": [{"id": "INPUT-001", "version": "v1"}], "code": ["src/write_text.py"], "config": "_pm/text-config.json", "environment": "_pm/environment.json", "environment_rebuilt": False, "cache_policy": "No cache used; explicit Python -B; existing environment, not rebuilt", "outputs": ["outputs/run-002.txt"]}
write_new(PROJECT / "_pm/run-002.json", json.dumps(spec, ensure_ascii=False, indent=2) + "\n")
dump(ROOT / "fixture-write-events-b.json", {"intent_v2_created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(), "intent_v2_sha256": sha(PROJECT / "_pm/intents/T-001-v2.md"), "run_spec_sha256": sha(PROJECT / "_pm/run-002.json"), "run_001_hash_before_update": first_run_hash})
p = ["--project", str(PROJECT)]
official("19-intent-v2-register", "research_tree.py", p + ["task", "intent", "--id", "T-001", "--path", "_pm/intents/T-001-v2.md"])
official("20-after-intent-update-check", "check_project.py", p + ["--verify-hashes"])
official("21-run-002", "run_project.py", p + ["--spec", "_pm/run-002.json", "--timeout", "30", "--", sys.executable, "-X", "utf8", "-B", "src/write_text.py", "--input", "data/raw/fixture.txt", "--config", "_pm/text-config.json", "--output", "outputs/run-002.txt", "--label", "second"])
official("22-post-run-002-check", "check_project.py", p + ["--verify-hashes"])

state = json.loads((PROJECT / "_pm/project-state.json").read_text(encoding="utf-8"))
task = next(row for row in state["tasks"] if row["id"] == "T-001")
runs = {rid: json.loads((PROJECT / f"runs/{rid}/run.json").read_text(encoding="utf-8")) for rid in ("RUN-001", "RUN-002")}
observations = {"current_task_intent": task["intent"], "intent_history": task.get("intent_history"), "run_001_record_unchanged_after_v2": sha(PROJECT / "runs/RUN-001/run.json") == first_run_hash, "run_bindings": {}, "checks": {}, "outputs": {}}
observations["checks"]["old_run_not_rebound"] = runs["RUN-001"]["intent_ref"] == original_first["intent_ref"]
observations["checks"]["history_has_v1"] = len(task.get("intent_history", [])) == 1 and task["intent_history"][0] == runs["RUN-001"]["intent_ref"]
observations["checks"]["current_is_v2"] = task["intent"] == runs["RUN-002"]["intent_ref"]
for rid, record in runs.items():
    intent = record["intent_ref"]
    snap = next(row for row in record["snapshots"] if row["role"] == "intent")
    before_start = datetime.datetime.fromisoformat(intent["written_at"]) <= datetime.datetime.fromisoformat(record["started_at"])
    snap_matches = sha(PROJECT / snap["snapshot"]) == intent["sha256"] == sha(PROJECT / intent["path"])
    observations["run_bindings"][rid] = {"intent_ref": intent, "snapshot": snap, "intent_before_run_start": before_start, "snapshot_matches_original": snap_matches, "status": record["status"], "returncode": record["returncode"]}
    observations["outputs"][rid] = (PROJECT / record["outputs"][0]["path"]).read_text(encoding="utf-8")
    observations["checks"][rid + "_intent_before_run"] = before_start
    observations["checks"][rid + "_intent_snapshot_matches"] = snap_matches
    observations["checks"][rid + "_actual_stdout_read"] = bool((PROJECT / record["stdout"]).read_text(encoding="utf-8").strip())
    observations["checks"][rid + "_actual_stderr_empty"] = not (PROJECT / record["stderr"]).read_text(encoding="utf-8")
observations["checks"]["first_output_exact"] = observations["outputs"]["RUN-001"] == "fixture=R6\nlabel=first\nsynthetic fixture only; no real research data\n"
observations["checks"]["second_output_exact"] = observations["outputs"]["RUN-002"] == "fixture=R6\nlabel=second\nsynthetic fixture only; no real research data\n"
for relative in ("_pm/project-state.json", "_pm/intents/T-001-v1.md", "_pm/intents/T-001-v2.md", "runs/RUN-001/run.json", "runs/RUN-002/run.json", "outputs/run-001.txt", "outputs/run-002.txt"):
    target = EVIDENCE / "before-tamper" / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(PROJECT / relative, target)
dump(ROOT / "binding-observations-before-tamper.json", observations)
print(json.dumps({"binding_observations": observations}, ensure_ascii=False, indent=2))
