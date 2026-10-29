# 外部系统的经验与本技能的取舍

> 作用：记录 v4 从 AI 科学家系统中借鉴了什么、落在哪里、刻意没借鉴什么，以及这些判断依据的来源。不负责：操作规则（各协议文件）。读者：技能维护者和想了解设计来由的负责人。调研日期为 2026-10-29；来源由调研子代理检索并汇总，部分数字只读到摘要或新闻稿，已标“未核实”，引用前应回到原文核对。

## 1. 总判断

这些系统都显示 AI 能加速假设生成、文献综合和计算分析，但验证仍是瓶颈。三个 Co-Scientist 的湿实验都有专家在环筛选；有批评意见认为，其中部分“新发现”是把已发表的碎片重新组合。Kosmos 的独立评估中，综合解释类陈述的准确率明显低于数据分析类和文献类。因此本技能把 AI 定位为“放大器 + 书记官 + 红队”，验证与价值判断交给人和外部判据。

## 2. 借鉴清单

| 机制 | 来源系统 | 本技能中的位置 | 改写方式 |
|---|---|---|---|
| 研究目标解析为计划配置，人确认后冻结 | Co-Scientist | [假设锦标赛](hypothesis-tournament.md) T1、`tournament.py freeze` | 改动登记 `D-*` |
| 多策略并行生成，人的假设同等入池 | Co-Scientist | 锦标赛第 3 节 | 必须有 `null` 基准；`origin` 字段 |
| 分层评审，新颖性必须联网 | Co-Scientist（消融：离线评审会高估已发表想法的新颖性） | 锦标赛第 3 节 | 全审必须引用来源 |
| 两两比较 + Elo，双向顺序减轻位置偏差 | Co-Scientist | `tournament.py match/rank` | 从只追加的比较记录重放；Elo 明确不作为证据 |
| 只追加的进化，元评审回灌提示 | Co-Scientist | 锦标赛第 3 节、`META_REVIEW.md` | 进化产物带 `parents` 重新参赛 |
| 人评覆盖与一致率 | Co-Scientist（作者承认 Elo 是自评指标） | `rank` 的人机一致率（Kendall τ） | 一致率低时先查偏差 |
| 从真实文献整理行动空间；描述与实现分离；准入需测试 | Biomni | [能力注册表](capability-registry.md) | 种子注册表全部是 `candidate`；冒烟测试后才算 `verified` |
| 两段式检索（先摘要短名单，再加载全文） | Biomni | `registry_search.py` | 短名单设上限，避免上下文被撑满 |
| know-how 文档：元数据 + 固定章节 | Biomni | `assets/capabilities/know-how/` | 加入许可证与本项目教训 |
| 编号计划清单：打勾、标叉、插入修正 | Biomni A1 | 能力注册表第 5 节 | 打勾必须附 `RUN-*` |
| 超时与输出截断，完整日志落盘 | Biomni A1 | `run_project.py`（已有） | 回传开头、结尾和报错行 |
| 结构化世界模型 / 周期摘要 | Kosmos | `STATUS.md` 素材摘要、问题树、检索日志 | 检索前先查日志，命中就复用 |
| 论断逐句溯源；论断按依据分型 | Kosmos、PaperQA2 | CLAIM 的 `basis`（data/literature/synthesis）；synthesis 类强制人审 | `check_project.py` 校验 |
| 允许“证据不足” | PaperQA2 | 检索日志的结论字段；解释简报 | — |
| PI + 专家 + 独立批评者；先发散后合并 | Virtual Lab | 六角色；生成者与评审者用不同上下文 | 同源一致不算独立证据 |
| 阶段闸门，人随时可介入 | Agent Laboratory（co-pilot 模式优于全自主） | CP0–CP9 与一页决策卡 | 不把检查点变成逐步批准；防止负责人只点头 |
| 阴性结果登记 | AgentRxiv 等 | `F-*` 记录负结果；检索日志记录“走不通”的方向 | — |

## 3. 刻意没有借鉴的

- **全自主的端到端运行**：Kosmos 作者承认运行中途无法人工干预，多次运行结论不收敛，有时会漂移到意外方向；AI Scientist 的独立评测中有编造数值、把已知方法判为新颖，还出现过修改自身超时限制的情况。本技能坚持设置检查点，并要求每个任务挂到问题树上。
- **直接集成 Biomni**：开源版已近乎停更，完整环境数十 GB，安装超过 10 小时，需要 LLM API key，执行代码时没有沙箱，数据湖中还有仅限非商用的数据。只把它作为可选的 `tool` 条目，默认关闭（见能力注册表第 6 节）。
- **AI 自动评审代替人评**：Agent Laboratory 的自动评审分数明显高于人评。模拟审稿意见只作为待核实的提示。
- **以 Elo 或评审分数宣称“新颖”或“重要”**：这些指标只用于内部排序。

## 4. 主要来源

- Gottweis et al. Towards an AI co-scientist. arXiv:2502.18864；Nature 2026，doi:10.1038/s41586-026-10644-y（正式版数字以原文为准）。
- Huang et al. Biomni. bioRxiv 10.1101/2025.05.30.656746；Science 2026，doi:10.1126/science.adz4351（正式版未读到，未核实）。GitHub snap-stanford/Biomni（Apache-2.0）。
- Kosmos：arXiv 2511.02824。PaperQA2：arXiv 2409.13740。Virtual Lab：Nature 2025，doi:10.1038/s41586-025-09442-9。Agent Laboratory：arXiv 2501.04227。AI Scientist 独立评测：arXiv 2502.14297。
- 开源复现参考：llnl/open-ai-co-scientist（MIT），只借鉴结构，未复制代码。
- 关于 AI 加速材料发现的 Toner-Rodgers 论文：MIT 已声明对其数据无信心，arXiv 已撤回，不能作为证据。
