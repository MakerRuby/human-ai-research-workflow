# 问题与假设的论证：{{PROJECT_NAME}}

- **作用**：写清每个问题和项目级假设的论证，包括为什么这样问、机制推理、判别性预测的依据和证据摘要。
- **不负责**：不保存当前表述、澄清度、状态和链接；这些以 `_pm/project-state.json` 的 `questions` 和 `hypotheses` 为准，用 `research_tree.py` 维护。不保存锦标赛原始记录，那些在 `_pm/research/tournaments/`。
- **读者**：负责人、统筹 AI、方法与实验执行者。
- **更新触发**：新增或拆分问题；CP3 选定假设；检验结果改变解释；问题被搁置或放弃，此时要写明原因。
- **相邻文档**：证据地图见 `references/EVIDENCE_MAP.md`；研究设计见 `RESEARCH_PLAN.md`；论文主线见 `manuscript/NARRATIVE.md`。

本页按编号组织。编号对应的状态从 state 读取（`check_project.py` 的 research_model 摘要，或审阅页），这里不抄写状态。

## Q-001

- 为什么这样问；答案为“是”或“否”时，各自会采取什么不同的行动：
- 杀死条件：
- 研究类型选择的理由：
- 关键反对意见与回应：

## H-001

- 机制推理（引用 `REF-*`、`F-*`）：
- 判别性预测为什么能区分它与竞争假设：
- 最省力的判别分析或实验，以及操作定义：
- 发现集与验证集的安排（对应 state 中的 `derived_from`、`validated_on`）：
- 检验后的解释（引用 `F-*`；状态在 state 中更新）：
