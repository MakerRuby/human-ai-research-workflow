import datetime
import hashlib
import json
import platform
from pathlib import Path
import shutil
import sys
from run_cli import invoke

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT / "project"
EVIDENCE = ROOT / "evidence"
EVIDENCE.mkdir(exist_ok=True)
events = []
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
def write_new(relative, content):
    target = PROJECT / relative
    if target.exists():
        raise FileExistsError(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8", newline="\n")
    events.append({"action": "write_new_fixture", "path": str(target), "sha256": sha(target), "at": datetime.datetime.now(datetime.timezone.utc).isoformat()})
def official(label, tool, args):
    result = invoke(label, tool, args)
    if result != 0:
        raise RuntimeError(label + " failed; preserved log must be inspected")
def dump(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

for relative in ("README.md", "AI_CONTRACT.md", "_pm/BRIEF.md", "_pm/STATUS.md", "_pm/LAYOUT.md", "_pm/config.json", "_pm/project-state.json"):
    target = EVIDENCE / "initialized" / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(PROJECT / relative, target)

contract = PROJECT / "AI_CONTRACT.md"
contract.write_text(contract.read_text(encoding="utf-8") + """
## 本例的合成隔离执行范围（覆盖模板占位）

本目录是 R6 行为演示，非真实科研项目。实际执行者是 AI 代理；不存在真实课题负责人对科研方案的批准。
本轮委托仅允许在本隔离目录写文件、用官方 CLI 登记合成问题/任务/输入/意图、执行两次明确的本地 Python 写文本命令，并故意改写第一份意图作负向检查。
禁止联网、安装、对外提交、接触真实项目/账户或新增代理。所有授权表述仅作为合成夹具，不能移用于真实项目。
普通项目使用 general 配置；本例不适用科研假设锦标赛、伦理/注册或科学关口，也不登记虚构真人批准。
原始输入、两份简报、运行快照和全部成功/失败日志保留；失败不改成通过；不以人工改写状态文件修复。
""" , encoding="utf-8")
events.append({"action": "append_scope_to_synthetic_contract", "path": str(contract), "sha256": sha(contract)})
(PROJECT / "_pm/BRIEF.md").write_text("""# R6 合成文本运行与意图绑定演示

- 作用：定义本例交付物和边界；不负责科研方案或批准。
- 读者：评估执行者与维护者；更新触发：本例范围改变；相邻：AI_CONTRACT、STATUS、LAYOUT。
- 目标：用官方 CLI 登记同一任务的 v1/v2 意图，各运行一次写新文本，检查历史绑定；再故意改写 v1 并记录拒绝/报错。
- 完成定义：保留两份原始简报、两次运行、快照、命令和 stdout/stderr/退出码；如实报告篡改后检查结果。
- 输入、配置和命令均为合成夹具，无真实研究、真人批准或外部行动；不使用网络或安装依赖。
- 实际执行者：AI 前向行为演示代理；运行环境沿用当前 Python，未重建环境。
""", encoding="utf-8")

write_new("scope.md", """# R6 执行边界
- 作用：保存本例委托的隔离范围；不负责真实批准或科学结论。
- 读者：AI 执行者及维护者；更新触发：本例范围变更；相邻：AI_CONTRACT、_pm/BRIEF.md。
- 任务只生成两份很小的合成文本，随后以改写旧简报为负向检查。
- 全部输入、选择和配置均属合成演示；实际执行者是 AI，不是真实课题负责人。
- 仅在本 forward-workspace 和指定 forward-check.md 写入，不联网、不安装、不对外提交。
""")
write_new("data/raw/fixture.txt", "synthetic fixture only; no real research data\n")
write_new("_pm/text-config.json", json.dumps({"fixture": "R6", "encoding": "utf-8", "note": "synthetic only; no scientific approval"}, ensure_ascii=False, indent=2) + "\n")
write_new("_pm/environment.json", json.dumps({"python_executable": sys.executable, "python_version": sys.version, "platform": platform.platform(), "environment_rebuilt": False, "dependencies": "Python standard library only", "bytecode_writes": False}, ensure_ascii=False, indent=2) + "\n")
writer = """import argparse
import hashlib
import json
from pathlib import Path

parser = argparse.ArgumentParser(description="Write one fresh synthetic text file.")
parser.add_argument("--input", required=True)
parser.add_argument("--config", required=True)
parser.add_argument("--output", required=True)
parser.add_argument("--label", required=True)
args = parser.parse_args()
root = Path.cwd().resolve()
source = (root / args.input).resolve()
configuration = (root / args.config).resolve()
output = (root / args.output).resolve()
for path in (source, configuration, output):
    if root not in path.parents:
        raise ValueError("Path must remain inside the synthetic project")
config = json.loads(configuration.read_text(encoding="utf-8"))
text = f"fixture={config['fixture']}\\nlabel={args.label}\\n" + source.read_text(encoding="utf-8")
output.parent.mkdir(parents=True, exist_ok=True)
with output.open("x", encoding="utf-8", newline="\\n") as stream:
    stream.write(text)
print(json.dumps({"written": args.output, "sha256": hashlib.sha256(output.read_bytes()).hexdigest(), "synthetic_only": True}, ensure_ascii=False))
"""
write_new("src/write_text.py", writer)
write_new("_pm/intents/T-001-v1.md", """任务：T-001，显式本地 Python 命令生成第一份小文本；仅合成夹具。
服务于：Q-001，检查同一任务的运行是否保存各自的冻结意图绑定。
为什么现在做：先取得 v1 运行证据；否则不能判断更新意图是否误回绑旧运行。
证据阶梯：文件与登记准备 → 一次实际小文本运行；不涉及科研证据。
预期结果及含义：成功且快照/绑定一致 → 本次路径可用；失败/不一致 → 保留日志定位；无结论 → 不扩展声称。
投入上限与停止条件：一次小文件、30 秒上限；官方登记失败则不启动依赖运行。
产出位置与登记编号：outputs/run-001.txt；RUN-001；不覆盖旧文件。
文档职责：冻结意图；不代表批准或结果；读者为执行者/维护者；实质更新另路径；相邻为任务/运行记录。
""")
spec1 = {"id": "RUN-001", "task": "T-001", "stage": "analysis", "purpose": "Synthetic first text run with v1 intent; no research data", "inputs": [{"id": "INPUT-001", "version": "v1"}], "code": ["src/write_text.py"], "config": "_pm/text-config.json", "environment": "_pm/environment.json", "environment_rebuilt": False, "cache_policy": "No cache used; explicit Python -B; existing environment, not rebuilt", "outputs": ["outputs/run-001.txt"]}
write_new("_pm/run-001.json", json.dumps(spec1, ensure_ascii=False, indent=2) + "\n")
dump(ROOT / "fixture-write-events-a.json", events)
selected = ["init_project.py", "research_tree.py", "record.py", "run_project.py", "check_project.py", "research_model.py", "project_io.py", "lifecycle.py"]
dump(EVIDENCE / "official-source-hashes-before.json", {name: sha(Path(r"D:\桌面\skill_barn\sci_skill\human-ai-research-workflow") / "scripts" / name) for name in selected})

p = ["--project", str(PROJECT)]
official("11-input-register", "record.py", p + ["artifact", "--id", "INPUT-001", "--path", "data/raw/fixture.txt", "--version", "v1"])
official("12-question-register", "research_tree.py", p + ["question", "add", "--id", "Q-001", "--statement", "合成两次小文本运行能否各自保留当时的冻结任务意图，并显露旧简报改写？", "--clarity", "2"])
official("13-task-register", "research_tree.py", p + ["task", "add", "--id", "T-001", "--title", "合成文本运行与意图绑定演示", "--serves", "Q-001", "--input", "INPUT-001@v1"])
official("14-task-doing", "research_tree.py", p + ["task", "set", "--id", "T-001", "--status", "doing", "--by", "AI执行者（合成演示）", "--rationale", "执行已委托的隔离小文本演示，非科研批准", "--evidence", "scope.md"])
official("15-intent-v1-register", "research_tree.py", p + ["task", "intent", "--id", "T-001", "--path", "_pm/intents/T-001-v1.md"])
official("16-pre-run-check", "check_project.py", p + ["--verify-hashes"])
official("17-run-001", "run_project.py", p + ["--spec", "_pm/run-001.json", "--timeout", "30", "--", sys.executable, "-X", "utf8", "-B", "src/write_text.py", "--input", "data/raw/fixture.txt", "--config", "_pm/text-config.json", "--output", "outputs/run-001.txt", "--label", "first"])
official("18-post-run-001-check", "check_project.py", p + ["--verify-hashes"])
for relative in ("_pm/project-state.json", "runs/RUN-001/run.json", "outputs/run-001.txt", "_pm/intents/T-001-v1.md"):
    target = EVIDENCE / "after-first-run" / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(PROJECT / relative, target)
dump(ROOT / "phase-a-observations.json", {"run": json.loads((PROJECT / "runs/RUN-001/run.json").read_text(encoding="utf-8")), "output": (PROJECT / "outputs/run-001.txt").read_text(encoding="utf-8")})
