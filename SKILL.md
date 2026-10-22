---
name: human-ai-research-workflow
description: 管理人与 AI 从研究构想到投稿前材料的科研协作，支持研究规划、数据可行性核实、分析执行、决策留痕、变更闭环、负责人审阅、成果归档、可复现性与固定交付；按需调用专项技能。尤其适合公开数据和代码分析为主的跨阶段研究，也可调整用于其他复杂项目。简单独立任务不必建立项目脚手架。
metadata:
  version: "3.0.0"
---

# 人与 AI 科研协作工作流

这是通用技能：核心规则不依赖某一 AI 产品、会话系统或工具名称。参见 [跨平台使用说明](USAGE.md)。宿主不支持执行脚本时，按同一规则维护普通文件，并明确哪些检查尚未执行。科研是可选流程，普通项目无需经过科学研究关口。

帮助负责人把目标变成可验收的交付物，让执行、证据、版本和决策能够衔接。保留探索空间，把会影响下游的选择和检查记录清楚。项目管理流程随风险、复杂度和用户要求调整。

## 1. 先识别本次任务

- **讨论**：用户要求分析、设计或“先不做”时，提供建议与待决项，不初始化项目。
- **启动**：目标与工作目录已知且用户要求实施时，检查现有材料，再建立最小必要记录。
- **续接**：读取现有入口、状态与本次相关约定，复述当前目标后继续已授权的工作。
- **评审 / 诊断 / 变更**：围绕指定交付物和受影响依赖开展检查，不重建整个项目。

不要因单个入口文件缺失就认定是新项目。先检查现有 README、项目规则、任务记录、方案和成果。目录已由会话明确提供时直接使用；仅在目标范围会实质改变时提问。现有项目适配见 [迁移规则](references/migration.md)。

## 2. 启动与滚动规划

读取 [工作流程](references/workflow.md)，按需要完成以下动作，可合并或跳过已有答案的部分：

1. 明确问题、预期用途、交付物、边界、资源和主要未知。
2. 优先安排最可能推翻当前路径的可行性检查；提前写明投入上限和转向条件。
3. 为近期交付物定义检查对象、判据、方法和检查责任。探索任务的交付可以是“不确定性得到怎样的澄清”。
4. 拆分近期任务与依赖，远期保留里程碑；按上下游关系和风险确定顺序。
5. 明确执行权限、重要决定的责任人和必要检查，开始首个可验收任务。

可以合并澄清问题；优先使用已有上下文。可逆、低风险的实施细节自行判断并说明假设。缺失数据、科学事实或授权不能靠默认值补齐。遇到阻塞，只暂停依赖该信息的部分，继续独立工作。

## 3. 按需调用专项技能

本技能可以作为统筹入口调用其他技能；专项技能负责领域工作，本技能负责目标、接口、证据和集成验收。**技能调用不等同于开设新会话、创建子代理或获得额外权限。**

遇到领域方法、文献检索、统计分析、代码、科学绘图、文档或投稿材料等专项任务时，读取 [技能协作协议](references/skill-composition.md)。按实际技能目录、技能文件或宿主提供的发现工具确认能力，不能假设某个名称对应的技能已安装。

调用前只读所选技能的必要说明，传入最小相关任务包。优先保留现有授权，不为普通技能切换反复请求确认。缺少技能时使用可验证的现有工具，或明确缺少的关键能力；不自行安装插件、上传数据或发布内容。

## 4. 公开数据科研流程

项目以科学研究为目标时，读取 [科研流程](references/research.md)，按实际设计调整：

- **G1 立项**：问题、价值、最接近证据、候选数据与关键反对意见。
- **G2 数据可行性**：实际文件、样本单位、变量、质量、信息量、来源关系、计算条件与接触记录。
- **G3 分析准备**：主分析、验证、缺失处理、多重分析、解释规则和技术试跑。
- 后续衔接正式分析、结论挑战、图表与论文整合、投稿前发布检查。

区分探索与正式分析；如实记录看过的数据和结果。显著性、预期方向、某个性能数值或期刊接收不作为项目完成的通用条件。方法学判断由适任评审者作出，不能以程序检查替代。

## 5. 验收、证据与变更

读取 [质量与变更规则](references/quality-and-change.md)。同时考虑科学或业务有效性、计算与内容正确性、表达与交付、来源与可重复性；只选择本任务适用的检查。

- 区分 `produced`、`checked` 与 `accepted`。实际检查记录是依据；自述、另一模型同意、清单有勾选均不足以独立证明正确。
- 可程序化的项目执行检查；需要专业判断的项目记录理由、证据和评审者。允许 `pending`、`fail` 及说明适用范围的 `waived`，不得静默当作通过。
- 批量操作按返工成本和不确定性选择代表件及边界件；检查通过且权限已覆盖时直接继续。高风险事项采用项目约定的放行方式。
- 输出绑定输入、代码、参数和环境版本；容差和随机性按任务设定，不保证固定种子即可逐字节重现。
- 关键版本变化后，追踪所有下游成果；将需重跑的成果标为 `stale`，相关任务重开、关口待复审。

## 6. 记录、发现与变更闭环

先读 [目录与唯一事实源](references/project-layout.md)。根目录 `README.md` 是负责人的导航入口，`AI_CONTRACT.md` 是 AI 的执行约定，`STATUS.md` 只保留续接上下文；各类当前状态与版本统一由 `_pm/project-state.json` 管理。目录按需创建，既有项目保留原路径，通过 `layout` 映射职责。不为状态变化移动文件。

重要新发现、负结果、矛盾和会改变后续路线的观察，按 [治理记录协议](references/governance.md) 分配稳定编号。区分观察与解释、发现与决策、决定与变更；记录证据、输入版本、责任和授权来源，保留被推翻的记录。不得把模型建议登记成负责人已批准。

决定不再使用的文件和结果按 [退出与归档规则](references/archive.md) 管理：明确原因及替代关系，使用独立 lifecycle 标记，归档有编号的历史快照，先处理依赖影响，保留被引用原件。不得把归档结果重新混入当前分析或投稿包。

发生关键变化时，先登记变更及完整影响清单，再处理成果、任务、关口、复现验证、正文结论和审阅事项。每项必须明确“已更新”或“核实无需改动”，附版本、理由和证据；有未决项就保持未关闭。`manage_change.py open` 会传播失效状态，`close` 核查处理清单；它不能发现未登记的语义依赖，应人工补充。详见 [状态结构 v2](references/state-schema-v2.md)。

记录按信息类型分工，不把所有事实复制进状态页：

| 记录 | 负责的信息 |
|---|---|
| `AI_CONTRACT.md` | 工作入口、授权边界和记录位置 |
| `_pm/BRIEF.md` | 目标、范围、完成定义和主要约束 |
| `_pm/STATUS.md` | 当前阶段、阻塞、下一动作和记录索引 |
| `_pm/config.json` 或项目既有配置 | 共享且经过确认的参数；未知值留空 |
| `_pm/project-state.json` | 交付物版本与依赖、任务、检查记录和关口状态 |
| `_pm/FINDINGS.md` | 观察、解释、矛盾、限制与发现详述；按需建立 |
| `_pm/DECISIONS.md` | 方案比较、决定理由和授权依据；按需建立 |

科研的方案、数据登记和接触记录使用 `assets/research/` 模板。模板是草稿，不代表任务已完成或关口已通过。存在既有等价记录时优先复用，不建立第二套事实源。

续接时读取入口、状态、相关方案与任务，核对关键版本和未决问题；已授权的工作继续执行，只有目标冲突、关键科学选择或权限不足时才询问。结束前记录完成及证据、阻塞与影响、下一具体动作。不得把失败、未执行或未核查写成通过。

## 7. 可复现、负责人审阅与固定交付

研究计算按 [复现协议](references/reproducibility.md) 保存实际输入、代码、参数、环境、执行日志和输出指纹。`run_project.py` 执行本次明确提供的命令，保留成功和失败；`verify_reproduction.py` 比较新输出并记录范围。区分材料齐全、小规模试跑、部分重跑、完整范围重跑和独立复现；计算一致不代表科学结论成立。按具体分析制定容差，记录缓存和环境重建情况，冻结进入正式分析的 AI 生成材料，不要求保存模型内部思维过程。

负责人审阅使用 [审阅协议](references/reviewer.md)：提供问题、建议、备选、影响、证据和所审版本。`render_review.py` 生成离线只读页面，分六个视图展示；正式答复在真实获得后登记。页面是快照，源记录更新后检查并重新生成；文件差异基线不能冒充实际审阅记录。

按 [固定交付协议](references/release.md) 将一轮投稿或交付材料集中在一个新编号目录：`upload/` 放拟提交文件，`internal_review/` 放内部依据。区分 `draft` 与 `ready`，检查未闭环变更、当前验收、复现覆盖、负责人决定和实际适用要求；历史包不覆盖。科研项目应在执行时核对目标期刊的现行要求。生成包不等于实际投稿或发布。

## 8. 初始化与脚本

`S` 用于单次小任务，初始化脚本只给建议且不写文件；`M` 建立最小记录；`L` 增加任务分解、决策、评审和交接模板。风险和依赖比固定天数更重要；用户可以要求其他布局。

```text
python <skill>/scripts/init_project.py --target <project> --name <name> --scale M --profile general --dry-run
python <skill>/scripts/init_project.py --target <project> --name <name> --scale L --profile research
python <skill>/scripts/check_project.py --project <project>
python <skill>/scripts/check_project.py --project <project> --impact DATA01
python <skill>/scripts/check_project.py --project <project> --require-gate G3 --verify-hashes
python <skill>/scripts/manage_change.py --project <project> open --spec _pm/change-spec.json
python <skill>/scripts/run_project.py --project <project> --spec _pm/run-spec.json -- <executable> <arguments>
python <skill>/scripts/verify_reproduction.py --project <project> --spec _pm/reproduction-spec.json
python <skill>/scripts/render_review.py --project <project>
python <skill>/scripts/render_review.py --project <project> --check
python <skill>/scripts/build_release.py --project <project> --spec _pm/release-spec.json --mode draft
python <skill>/scripts/archive_artifacts.py --project <project> --spec _pm/archive-spec.json
```

初始化不覆盖已有文件，拒绝将写入导向项目外的符号链接；不安装依赖。结构检查器只验证记录一致性、文件、依赖和声明的检查状态，不能判定科学成立或报告真实。默认检查不会执行记录中的命令，也不会改变项目状态。

辅助脚本使用 Python 3.9 及以上版本，仅依赖标准库；研究程序可以使用 R、Python、Julia 或其他环境。新项目采用状态结构 v2；旧结构 v1 保持可读，不自动迁移，也不自动补齐复现或批准证据。同一项目安排一个状态写入者，避免并发更新相互覆盖。脚本不是任意研究代码的沙箱。

## 9. 按需读取的资源

- [工作流程](references/workflow.md)：启动、续接、任务粒度、风险探针和工作周期。
- [科研流程](references/research.md)：G1/G2/G3 细则及分析到投稿前衔接。
- [技能协作](references/skill-composition.md)：发现、调用、权限、冲突、集成和回退。
- [质量与变更](references/quality-and-change.md)：验收、证据、状态结构和影响追踪。
- [迁移规则](references/migration.md)：旧包缺陷、兼容和渐进采用。
- [目录职责](references/project-layout.md)、[治理协议](references/governance.md)、[状态结构](references/state-schema-v2.md)。
- [复现管理](references/reproducibility.md)、[审阅页面](references/reviewer.md)、[固定交付](references/release.md)。
- [宿主适配](references/portability.md)：能力发现、执行方式和降级。
- `assets/task-package.md`、`assets/REVIEW.md`：任务交接与可审查记录。
- `scripts/test_tools.py`：在临时目录验证脚本行为；技能维护时运行。
- `scripts/test_v3.py`：治理、实际运行、比较、审阅快照与固定包行为验证。

初始化时将本技能的位置及持续使用规则写入 `AI_CONTRACT.md`；按宿主需要使用 `--ai-entry agents` / `--ai-entry claude` 创建仅含导航的入口。已有入口保留并最小合并，不复制管理规则。按 [使用说明](USAGE.md) 验证新会话恢复；不保证所有平台自动加载。
