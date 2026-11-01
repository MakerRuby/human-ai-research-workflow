import datetime
import hashlib
import json
from pathlib import Path
import shutil
from run_cli import invoke

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT / "project"
EVIDENCE = ROOT / "evidence"
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

relative_paths = ["_pm/project-state.json", "runs/RUN-001/run.json", "runs/RUN-002/run.json", "runs/RUN-001/snapshots/003-T-001-v1.md", "runs/RUN-002/snapshots/003-T-001-v2.md", "outputs/run-001.txt", "outputs/run-002.txt"]
before_hashes = {rel: sha(PROJECT / rel) for rel in relative_paths}
v1 = PROJECT / "_pm/intents/T-001-v1.md"
original = v1.read_bytes()
preserved = EVIDENCE / "before-tamper/_pm/intents/T-001-v1.md"
if original != preserved.read_bytes():
    raise RuntimeError("Preserved original differs before the deliberate write; stop")
tampered = original + "\n负向夹具：此行是在两次运行完成后追加，用于检查历史简报改写是否被识别。\n".encode("utf-8")
v1.write_bytes(tampered)
event = {"action": "direct local write to a previously registered historical brief", "at": datetime.datetime.now(datetime.timezone.utc).isoformat(), "path": "_pm/intents/T-001-v1.md", "write_succeeded": v1.read_bytes() == tampered, "original_sha256": hashlib.sha256(original).hexdigest(), "changed_sha256": sha(v1), "original_preserved_at": str(preserved.relative_to(ROOT)), "note": "Deliberate synthetic negative fixture; no attempt to treat changed text as original or approved"}
dump(ROOT / "deliberate-tamper-event.json", event)
target = EVIDENCE / "after-tamper/_pm/intents/T-001-v1.md"
target.parent.mkdir(parents=True, exist_ok=True)
shutil.copyfile(v1, target)
check_code = invoke("23-after-v1-tamper-check", "check_project.py", ["--project", str(PROJECT), "--verify-hashes"])
after_hashes = {rel: sha(PROJECT / rel) for rel in relative_paths}
source_before = json.loads((EVIDENCE / "official-source-hashes-before.json").read_text(encoding="utf-8"))
skill = Path(r"D:\桌面\skill_barn\sci_skill\human-ai-research-workflow")
source_after = {name: sha(skill / "scripts" / name) for name in source_before}
dump(EVIDENCE / "official-source-hashes-after.json", source_after)
facts = {"deliberate_tamper": event, "official_check_exit_code": check_code, "preserved_record_hashes_before": before_hashes, "preserved_record_hashes_after": after_hashes, "state_runs_snapshots_outputs_unchanged": before_hashes == after_hashes, "original_v1_backup_intact": sha(preserved) == event["original_sha256"], "original_v1_run_snapshot_intact": sha(PROJECT / "runs/RUN-001/snapshots/003-T-001-v1.md") == event["original_sha256"], "v2_original_intact": sha(PROJECT / "_pm/intents/T-001-v2.md") == sha(EVIDENCE / "before-tamper/_pm/intents/T-001-v2.md"), "selected_official_source_files_unchanged": source_before == source_after, "modified_v1_left_in_place": v1.read_bytes() == tampered, "check_scope": "A single synthetic intent-history/file-consistency case; not scientific validation"}
dump(ROOT / "tamper-observations.json", facts)
(PROJECT / "_pm/STATUS.md").write_text("""# 当前状态：R6 合成行为演示

- 作用：恢复本例结束状态；不负责真实项目授权或科学结论。
- 读者：执行者与维护者；更新触发：本例另有明确后续委托；相邻：AI_CONTRACT、BRIEF、project-state。
- 当前阶段：委托的两次写文本及历史改写负向演示已实际执行。
- 已完成：v1/v2 分别绑定 RUN-001/RUN-002；两次运行成功；改写前四次官方检查无错误/警告。
- 最后检查：故意在 v1 追加说明后，官方检查的真实退出码与报错见 ../logs/23-after-v1-tamper-check.json；此处相对路径从项目根参照。
- 原件：../evidence/before-tamper/ 和运行快照保留原始简报、运行与输出；篡改版留在原路径以保留负向状态。
- 未完成/限制：任务未登记 accepted/done，最终项目处于故意不一致状态；这不否定改写前两次历史运行的实际成功，也不构成科研批准。
- 下一动作：无自动后续；交回本轮 forward-check.md 和原始证据，不修复或掩盖本次负向状态。
""", encoding="utf-8")
layout = PROJECT / "_pm/LAYOUT.md"
layout.write_text(layout.read_text(encoding="utf-8") + "\n## 本例额外文件\n\n| 路径 | 唯一职责 |\n|---|---|\n| scope.md | 本合成演示的授权边界说明；不代表真人批准 |\n| outputs/run-001.txt、outputs/run-002.txt | 两次官方运行生成的合成小文本；非研究结果 |\n\n完整本轮证据、调用日志和保留副本在项目的上级专用隔离工作目录；报告统一索引。\n", encoding="utf-8")
print(json.dumps({"tamper_observations": facts}, ensure_ascii=False, indent=2))
