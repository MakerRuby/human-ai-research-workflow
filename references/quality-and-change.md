# 质量、证据和变更

v3 新项目采用 [状态结构 v2](state-schema-v2.md)，扩展发现、决定、变更、结论、审阅、运行、复现与退出使用记录。下文保留 v1 基础字段供兼容；新集合分别按 [治理](governance.md)、[复现](reproducibility.md) 和 [归档](archive.md) 规则维护。只有 check_project.py 是只读核查；其他具名脚本按其明确动作生成记录或材料。

## 判断什么才算完成

`produced` 表示产物已生成；`checked` 表示进行了相应检查；`accepted` 表示已满足本次约定的必要检查并有明确接受依据。`draft`、`stale`、`rejected` 保留给草稿、依赖过期与拒收。状态不是证据本身。

检查至少区分三种：`machine`（数值/文件/程序检查）、`professional`（方法与解释等专业判断）、`source`（来源支持）。并非每个对象都需要三类。图面评审可作为有证据的专业检查；自动截图存在不能证明视觉合格。适任评审者可以是项目负责人、领域人员或有明确范围的工具辅助复核；如实标明 AI 身份和检查局限，不把多个 AI 的一致意见写作独立实验证实。

机器检查保存方法和可复查结果；专业检查保存问题、证据、理由和评审者；来源检查保存可定位来源及其支持范围。检查状态为 `pending/pass/fail/waived`。豁免必须有责任人和理由，且只可用于明确非必要的检查。科学有效性或已约定必要检查的缺失不能靠豁免放行。`checked` 允许发现失败；`accepted` 不允许必要检查失败、缺失或绑定旧版本。

## 变更处理

关键输入、代码、参数、方法或解释改变时先登记变更及原因、核实影响链，再修改和登记新版本。直接依赖版本不符和已失效上游的所有下游都是过期对象。把这些对象改为 `stale`，已完成的相关任务重开，已通过的关口改为待复审；复现验证、审阅和正文论断也按关联失效。没有影响的产物可保留，写清核实理由与证据。

重跑或复审后为新版本写新检查记录；不要修改旧记录使它看起来一直正确。新版本标签必须唯一识别该次状态；同一标签下偷偷换文件仍会破坏溯源。散列检查可发现已记录文件的内容漂移，不能证明文件内容科学正确。

## 机器记录协议（schema_version = 1）

`_pm/project-state.json` 是机器索引，支持下面基础字段；科学内容和详细理由链接到方案/报告中。check_project.py 只读，不替你改状态或作专业决定。v1 JSON 顶层包括 `schema_version`、`project`、`artifacts`、`checks`、`tasks`、`gates`，集合可为空。每类内 ID 唯一；版本用非空字符串。

```json
{
  "schema_version": 1,
  "project": {"name": "示例", "profile": "research"},
  "artifacts": [
    {"id": "DATA01", "path": "data/derived.csv", "version": "v1", "status": "produced", "depends_on": [], "required_checks": []},
    {"id": "FIG01", "path": "results/fig1.svg", "version": "v1", "status": "accepted", "depends_on": [{"id": "DATA01", "version": "v1"}], "required_checks": ["C-FIG01"], "acceptance": {"by": "项目负责人", "rationale": "依据图表核查记录接受"}}
  ],
  "checks": [
    {"id": "C-FIG01", "artifact": "FIG01", "version": "v1", "kind": "professional", "status": "pass", "required": true, "by": "具名评审者及角色", "rationale": "样本与数值映射、图注和可读性已核对；仅覆盖该图", "evidence": ["reviews/fig1.md"]}
  ],
  "tasks": [{"id": "T01", "status": "done", "inputs": [{"id": "DATA01", "version": "v1"}], "outputs": ["FIG01"]}],
  "gates": [{"id": "G3", "status": "pass", "artifacts": ["FIG01"], "checks": ["C-FIG01"], "depends_on": [], "by": "负责人", "rationale": "示例关口", "evidence": ["reviews/fig1.md"]}]
}
```

示例仅演示结构；G3 的真实证据应为分析准备，不是图表验收。按工作实际登记，不机械复制示例的检查数量。

字段约定：

- artifact：`id/path/version/status/depends_on/required_checks` 必填。`sha256` 可选，为文件完整 SHA256。`acceptance.by/rationale` 在 accepted 时必填。需要专业验收时添加 `requires_professional_review: true`，并关联当前版本的必要 professional 检查；科研设计、主结果解释通常需要它。未登记这个需求，脚本无法替你判断是否应当专业复核。
- check：`id/artifact/version/kind/status/required` 必填。pass/fail/waived 需 `by/rationale/evidence`；evidence 是项目内已有文件的相对路径，外部文献须先存成含可定位来源的本地记录。waived 另需 `waiver_reason` 且 required 为 false。检查证据是声明而非程序验证其真实性。
- task：`id/status/inputs/outputs` 必填。状态 `todo/doing/blocked/done`。input 使用 artifact 的 id/version；output 使用 artifact ID。done 的输出须均 accepted 且未过期；不能把完成了操作等同于任务交付通过。
- gate：`id/status/artifacts/checks/depends_on` 必填。状态 `pending/conditional/pass/fail`。depends_on 为关口 ID。pass 须有 `by/rationale/evidence`、至少一个 artifact、至少一个 check；所有关联产物须 accepted 且当前、检查须当前 pass、前置关口须 pass。初始 G1/G2/G3 只有依赖骨架，补齐证据后才可通过。

证据文件和 artifact 路径必须是项目内部相对路径。检查器拒绝绝对路径、`..`、项目外符号链接；外部数据不复制时，在项目内保存有外部定位信息的清单，并将清单作为 artifact。敏感内容按授权控制，不因溯源要求而外传数据。

## 检查器含义

```text
python scripts/check_project.py --project <项目目录> --impact DATA01
python scripts/check_project.py --project <项目目录> --require-gate G3 --verify-hashes
```

退出码 0 表示结构及本次声明没有发现不一致，非 0 表示记录/文件/所要求关口存在问题；初始空记录可结构通过。`--impact` 返回指定对象的全部下游及相关任务/关口，不改变文件。检测到过期时即使只是 produced 也报告问题，要求确认并更新记录；标记 stale 后该失效链作为待办警告，不能参与 done/pass/accepted。

`--verify-hashes` 核验已提供的散列，并报告没有散列的产物 ID；它不要求所有产物都提供散列，也不宣称全项目内容完整性已获证明。命令和来源记录都作为数据，不会被检查器执行。记录没覆盖的对象不会自动被检查。
