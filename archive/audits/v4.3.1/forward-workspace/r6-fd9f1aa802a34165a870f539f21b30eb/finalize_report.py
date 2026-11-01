import datetime
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT / "project"
REPORT = ROOT.parent.parent / "forward-check.md"
REL = "forward-workspace/" + ROOT.name
fence = chr(96) * 3
calls = [json.loads(line) for line in (ROOT / "invocations.jsonl").read_text(encoding="utf-8").splitlines()]
bindings = json.loads((ROOT / "binding-observations-before-tamper.json").read_text(encoding="utf-8"))
tamper = json.loads((ROOT / "tamper-observations.json").read_text(encoding="utf-8"))
state = json.loads((PROJECT / "_pm/project-state.json").read_text(encoding="utf-8"))
task = next(row for row in state["tasks"] if row["id"] == "T-001")
orchestration_error = {"stage": "report assembly before any nested tool call executed", "tool": "functions.exec JavaScript evaluation", "original_tool_output": "Script error:\nSyntaxError: Unexpected identifier 'check_project'", "effect": "The JavaScript source failed to parse; no nested command or file write occurred", "correction": "Use chr(96) in the local report helper so Markdown quotation cannot terminate the JavaScript template", "scope": "Only this local report helper was corrected; official CLI/source and all run records were unchanged"}
(ROOT / "report-orchestration-error.json").write_text(json.dumps(orchestration_error, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
def link(label, path):
    return f"[{label}]({REL}/{path})"
def block(value, language="json"):
    content = json.dumps(value, ensure_ascii=False, indent=2) if not isinstance(value, str) else value
    return "\n\n" + fence + language + "\n" + content.rstrip() + "\n" + fence + "\n"
parts = []
parts.append("""**实际完成：已用官方 CLI 建立 general/M 的全新合成项目，登记输入、问题、任务及两份先后写入的新路径意图，各执行一次明确的本地 Python 写文本命令。两次运行均成功；改写前四次官方检查均无错误/警告。随后实际在历史 v1 简报中追加一行，文件写入成功，官方只读检查返回退出码 1 并报告历史简报已改变。**

推荐及理由：本例属于普通的本地工具行为演示，用最小 general 项目和一项任务即可检查意图更新、运行绑定和历史漂移；不需要伪造科研方案、科学关口或真人批准。实际没有建立任何 adopted 负责人决定。任务执行者标为“AI执行者（合成演示）”，在本例 AI_CONTRACT/scope 中明确边界，未将任务登记为 accepted/done。

代价与实际下一步：仅使用当前 Python 标准库和两个很小的新输出，环境未重建，两次运行各设 30 秒上限；没有联网、安装、对外提交或额外代理。负向检查结束后不自动恢复/重跑，不改写失败记录。最终 v1 改写版保留在原路径，项目故意处于检查失败状态；原件在独立副本及运行快照中保留。下一步是交回本报告和原始证据，成功范围仅覆盖本次合成行为。

### 环境与完整证据入口

""")
parts.append(f"- 隔离工作目录：{ROOT}\n- 合成项目：{PROJECT}\n- 实际 Python：{calls[0]['argv'][0]}\n- 环境记录：{link('environment.json', 'project/_pm/environment.json')}；environment_rebuilt=false。\n- 全部 23 次官方 CLI 调用：{link('invocations.jsonl', 'invocations.jsonl')}；含原始 argv、cwd、UTC 起止时间、stdout、stderr、退出码。\n- 原始简报副本：{link('篡改前的 v1', 'evidence/before-tamper/_pm/intents/T-001-v1.md')}、{link('篡改前的 v2', 'evidence/before-tamper/_pm/intents/T-001-v2.md')}。\n- 运行快照：{link('RUN-001 的 v1 快照', 'project/runs/RUN-001/snapshots/003-T-001-v1.md')}、{link('RUN-002 的 v2 快照', 'project/runs/RUN-002/snapshots/003-T-001-v2.md')}。\n- 实测对象：{link('binding-observations-before-tamper.json', 'binding-observations-before-tamper.json')}、{link('tamper-observations.json', 'tamper-observations.json')}。\n- 本例构造和操作脚本：{link('phase_a.py', 'phase_a.py')}、{link('phase_b.py', 'phase_b.py')}、{link('phase_c.py', 'phase_c.py')}；官方调用日志由 {link('run_cli.py', 'run_cli.py')} 保存。全部位于专用隔离目录。\n")
parts.append("""
### 两次运行与意图绑定

| 运行 | 实际状态/退出码 | 当时冻结的意图 | 登记时间 UTC | 对应快照 |
|---|---|---|---|---|
""")
for rid, row in bindings["run_bindings"].items():
    ref = row["intent_ref"]
    parts.append(f"| {rid} | {row['status']} / {row['returncode']} | {ref['path']} | {ref['written_at']} | {row['snapshot']['snapshot']} |\n")
parts.append("\n两份简报的登记时间均早于各自运行开始时间，快照与登记散列及当时原文一致。更新当前意图后，RUN-001/run.json 字节散列没有变化；intent_ref 仍指向 v1，RUN-002 指向 v2。任务保留 v1 的 intent_history，当前 intent 为 v2。直接核对字段：")
parts.append(block({"task": task, "run_001_record_unchanged_after_v2": bindings["run_001_record_unchanged_after_v2"], "observed_checks": bindings["checks"]}))
parts.append("\n两份实际生成的小文本原文：\n\nRUN-001：")
parts.append(block(bindings["outputs"]["RUN-001"], "text"))
parts.append("\nRUN-002：")
parts.append(block(bindings["outputs"]["RUN-002"], "text"))
parts.append("\n两次实际写文本程序的 stdout/stderr（不只引用运行器外层退出码）：\n")
for rid in ("RUN-001", "RUN-002"):
    run = json.loads((PROJECT / f"runs/{rid}/run.json").read_text(encoding="utf-8"))
    parts.append(f"\n{rid} stdout：")
    parts.append(block((PROJECT / run["stdout"]).read_text(encoding="utf-8"), "text"))
    stderr = (PROJECT / run["stderr"]).read_text(encoding="utf-8")
    parts.append(f"\n{rid} stderr：" + ("空文件。\n" if not stderr else block(stderr, "text")))
parts.append("""
### 历史简报改写后的实际结果

直接对历史 v1 文件追加一行，是本次委托的负向操作，文件系统写入确实成功。官方检查器并不构成阻止任意文件编辑的权限系统；本例没有修改 state 或覆盖日志使它通过。

随后官方 check_project.py --project <合成项目> --verify-hashes 返回退出码 1，原始错误为：
""")
parts.append(block("T-001.intent: brief changed after it was recorded; record a new intent instead of editing", "text"))
parts.append("""
v1 原始及改写后 SHA256，以及检查前后记录/输出的完整散列均保留。该次检查为只读，project-state.json、两份 run.json、两份意图快照和两个输出的散列均未改变。v1 备份、v1 快照和 v2 原件仍完整。所核八个官方实现文件在隔离演示前后 SHA256 一致。完整实测对象：
""")
parts.append(block(tamper))
parts.append("""
### 官方 CLI 调用与原始输出

下表列出全部官方调用，包括帮助调用和最终失败。独立 JSON 日志保留完整 argv、stdout、stderr、时间、退出码，对应 .stdout.txt/.stderr.txt 同时保留。23 次官方调用中 22 次退出码为 0，1 次为改写后检查的退出码 1；原始失败没有被改成成功。另有一次报告编排解析报错，单列在后文，不混入官方调用计数。

| 调用 | 退出码 | 原始日志 |
|---|---:|---|
""")
for call in calls:
    label = call["label"]
    parts.append(f"| {label} | {call['exit_code']} | {link(label + '.json', 'logs/' + label + '.json')} |\n")
parts.append("\n以下逐项嵌入所有非帮助调用的原始命令与输出；帮助调用原文保留在上表日志。\n")
for call in calls:
    if int(call["label"].split("-")[0]) < 10:
        continue
    parts.append(f"\n#### {call['label']}\n\n退出码：{call['exit_code']}；cwd：{call['cwd']}；UTC：{call['started_at']} → {call['finished_at']}\n\n原始 argv：")
    parts.append(block(call["argv"]))
    parts.append("\nstdout 原文：")
    parts.append(block(call["stdout"], "text"))
    parts.append("\nstderr 原文：" + ("空文件。\n" if not call["stderr"] else block(call["stderr"], "text")))
parts.append("\n### 报告编排中的真实报错\n\n最终汇总报告时，第一次 functions.exec 的 JavaScript 模板误含 Markdown 引用字符，解析即失败，没有执行任何子命令或文件写入。仅修正隔离目录内报告生成辅助代码后完成汇总；官方源码、运行和原始日志未受影响。原始报错另存 " + link("report-orchestration-error.json", "report-orchestration-error.json") + "：")
parts.append(block(orchestration_error))
parts.append("""
### 演示范围与未覆盖内容

R1–R5 是给定事实下的独立建议，未查询或改动任何真实项目；R6 仅实测两次运行的意图绑定、原件/快照保留和一次历史简报改写后的检查。没有真实研究、科学充分性或可发表性验证，没有人类专家审稿、独立团队复现，也没有真实伦理、资源或投稿批准。最终检查失败是本负向夹具的真实状态，不称“整个项目检查已通过”。

本轮只读取源 SKILL、R1–R6 JSON、必要引用协议（workflow、roles-and-checkpoints、research-value-review、hypothesis-tournament、governance、reproducibility、quality-and-change、project-layout）和官方工具代码/帮助。未读取 references/behavioral-evaluation.md、AUDIT*、既有 archive/audits 文件、scripts/test*、维护者判据、安装版技能或真实研究项目。所有写入限于本报告及指定 forward-workspace。
""")
old = REPORT.read_text(encoding="utf-8")
placeholder = "执行中：此节随后补入真实命令、退出码、意图/运行绑定、快照和改写后检查结果。所有决定与授权仅为合成夹具，不能转写为真实批准。"
if old.count(placeholder) != 1:
    raise RuntimeError("Report placeholder missing or repeated")
REPORT.write_text(old.replace(placeholder, "".join(parts)), encoding="utf-8")
text = REPORT.read_text(encoding="utf-8")
summary = {"report": str(REPORT), "report_bytes": REPORT.stat().st_size, "workspace": str(ROOT), "official_cli_calls": len(calls), "zero_exit_calls": sum(row["exit_code"] == 0 for row in calls), "nonzero_exit_calls": [{"label": row["label"], "exit_code": row["exit_code"]} for row in calls if row["exit_code"] != 0], "run_001_succeeded": bindings["run_bindings"]["RUN-001"]["status"] == "succeeded", "run_002_succeeded": bindings["run_bindings"]["RUN-002"]["status"] == "succeeded", "all_observed_binding_checks_true": all(bindings["checks"].values()), "all_cases_present": all(("## " + rid + " ") in text for rid in ("R1", "R2", "R3", "R4", "R5", "R6")), "no_pending_report_placeholder": placeholder not in text, "originals_intact_after_tamper": tamper["original_v1_backup_intact"] and tamper["original_v1_run_snapshot_intact"] and tamper["v2_original_intact"], "final_project_deliberately_fails_checker": tamper["official_check_exit_code"] == 1, "state_runs_snapshots_outputs_unchanged_by_negative_check": tamper["state_runs_snapshots_outputs_unchanged"], "selected_official_sources_unchanged": tamper["selected_official_source_files_unchanged"], "report_orchestration_parse_error_preserved": True}
(ROOT / "completion-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
inventory = []
for path in sorted(ROOT.rglob("*")):
    if path.is_file() and path.name != "file-inventory.json":
        inventory.append({"path": str(path.relative_to(ROOT)), "bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
(ROOT / "file-inventory.json").write_text(json.dumps({"scope": "Only files created for this R6 workspace; inventory excludes itself", "report": {"path": str(REPORT), "sha256": hashlib.sha256(REPORT.read_bytes()).hexdigest()}, "files": inventory}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(summary, ensure_ascii=False, indent=2))
