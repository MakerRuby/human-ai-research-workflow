# 假设锦标赛

> 作用：把一个已塑形的研究问题（澄清度至少 L2）展开成多个竞争假设，经评审、两两比较、进化和元评审，得到排序后的假设池和判别性预测，供负责人在 CP3 选择。不负责：问题塑形（见 [问题塑形](question-shaping.md)）、设计与样本量（见 `experimental-design`、`statistical-power`）。机制借鉴 Google AI co-scientist（Gottweis et al.，arXiv 2502.18864；Nature 2026）后重写，来源与差异见 [外部经验](design-lessons.md)。

## 0. 触发与跳过登记

以下任一情况出现，就是在做 CP3 决定，必须二选一：开一轮锦标赛，或在 `D-*` 中登记跳过理由。

- 准备从多个过程、通路、机制或细胞类型中选一个作为主线；
- 准备锁定要用实验（qPCR、敲低等）检验的候选；
- 文献检索发现已有多个相互竞争的解释，而本研究要在其中站队。

允许跳过的理由：备选只有一两个且显而易见（附竞争解释表，必须包含“最无聊解释”）；问题仍停在 L0–L1（先回到问题塑形）；负责人明确不需要（记录原话）。“时间紧”“AI 已经想清楚了”不是跳过理由。选定之后，`HYPOTHESES.md` 要写清选择依据和被放弃的备选；所依据的文献论断须经全文核对（见 [资料与证据](evidence-and-materials.md)），不能只凭摘要。

## 1. 何时用，何时不用

适用于机制尚不明确、存在多种合理解释，而选错方向代价很大的问题。问题本身还停留在 L0–L1 时不要用，先回到问题塑形。只有一两个显而易见的备选时也不必用，直接写竞争解释表即可。

锦标赛的输出是“值得优先检验的假设”，不是“正确的假设”。Elo 排名是 AI 内部的相对偏好，不是证据，不能写进论文作为支持。Co-Scientist 的作者自己也说明，Elo 是基于自评的有限指标，三个湿实验验证都有专家在环筛选。

## 2. 文件与状态

一轮锦标赛对应一个目录 `_pm/research/tournaments/<TID>/`，由 `scripts/tournament.py` 管理：

| 文件 | 内容 | 写入方式 |
|---|---|---|
| `config.json` | 研究目标、所属 `Q-*`、评价标准与权重、约束、是否只要新假设、预算、Elo 参数、冻结状态 | `init` 生成；负责人确认后 `freeze` |
| `hypotheses.jsonl` | 每行一个假设：`id`、`statement`、`mechanism`、`predictions`（判别性预测）、`strategy`、`origin`（ai/human）、`parents`、`refs`、`status` | `add`，只追加 |
| `reviews.jsonl` | 每行一条评审：假设、评审类型、各标准评分、致命缺陷、结论、评审者 | `review`，只追加 |
| `matches.jsonl` | 每行一场比较：a、b、winner（a/b/tie）、`order`（ab/ba）、理由、评委（`ai:<上下文>` 或 `human:<姓名>`） | `match`，只追加 |
| `META_REVIEW.md` | 反复出现的问题与下一轮要求 | 主会话编写，带轮次编号 |
| `ranking.json` / `REPORT.md` | 重放全部比较后得到的排名、各策略统计、人机一致率、建议的下一批对阵 | `rank` 生成，可重建 |

只追加、不改写：被淘汰的假设改记一条状态变更，原记录保留；改进后的假设作为新条目，用 `parents` 指向前身。排名随时可以从原始比较记录重放出来，所以评委和规则都可以复核。

## 3. 流程

1. **配置（人机检查点 T1）**：AI 起草 `config.json`，包括目标、评价标准（默认：可检验性、生物学合理性、新颖性、对结论的影响、可行性）、约束（可用模型、样本、预算、伦理）和本轮预算（假设数、比较场数）。负责人确认后执行 `freeze`；之后再改，要登记 `D-*`。
2. **并行生成**：宿主允许时，用多个独立上下文的子代理，每个采用不同的生成策略：
   - `literature`：从检索到的证据出发；
   - `debate`：模拟几位持不同立场的专家辩论；
   - `decompose`：先找出可检验的中间环节，再组装成假设；
   - `analogy`：借用其他系统、组织或疾病中的已知机制；
   - `contrarian`：刻意反主流；
   - `null`：最无聊的解释（混杂、伪影、反向因果），作为基准假设必须入池。
   
   负责人的假设以 `origin: human` 入池（T2），与 AI 的假设同等竞争。子代理只写到自己的输出位置，由主会话统一编号后执行 `add`。可调用 `hypothesis-generation`、`scientific-brainstorming` 技能。
3. **分层评审**：
   - 初审（不联网，快速淘汰明显不可检验或违背已知事实的假设）；
   - 全审（联网检索，评价正确性和新颖性，引用要标 `REF-*`）；
   - 深度验证（把假设拆成子论断逐条判断，区分致命缺陷和可修补的缺陷）；
   - 模拟评审（逐步推演机制或实验，找出会失败的场景）。
   
   评审者与生成者用不同的上下文。新颖性一定要联网判断：Co-Scientist 的消融实验显示，评审不联网时，会把已发表的想法评为高度新颖。
4. **两两比较**：优先安排排名相近、内容相似或比较次数少的假设对阵。每对比较 A/B 和 B/A 两种顺序，以减轻位置偏差。评委要写出理由，比较依据是事先冻结的标准，而不是文采。`rank` 输出的 `next_pairs` 给出建议的下一批对阵。
5. **进化**：对排名靠前的假设，可以补充依据、提升可行性、组合、简化或刻意发散。产出新条目并重新参赛，不覆盖原条目。
6. **元评审**：把评审和比较中反复出现的问题，写入 `META_REVIEW.md`，在下一轮生成和评审时附在提示里，并注明轮次。
7. **停止**：满足任一条件就停：Top-k 的 Elo 进入平台期（`rank` 报告 `plateau`）；预算用完；负责人叫停。
8. **人评与交付（T3，即 CP3）**：负责人对 Top 3–5 盲评，或至少做一轮两两判断，结果以 `human:` 评委写入比较记录。报告给出人与 Elo 排序的一致率。一致率低，说明标准或评委有偏差，要先查原因，再决定是否继续。交付物包括：排序后的假设池、每个假设的判别性预测、最省力的判别实验或分析、主要风险，以及 NIH Specific Aims 式的一页摘要（可选）。

## 4. 命令

先用 `research_tree.py question add` 登记问题，`init` 要求问题已存在。

```text
python <skill>/scripts/tournament.py --project <project> init --id T01 --question Q-001 --goal "…"
python <skill>/scripts/tournament.py --project <project> freeze --id T01 --by "负责人"
python <skill>/scripts/tournament.py --project <project> add --id T01 --spec <hypothesis.json>
python <skill>/scripts/tournament.py --project <project> review --id T01 --spec <review.json>
python <skill>/scripts/tournament.py --project <project> blind --id T01 --a T01-H001 --b T01-H004 --order ba
python <skill>/scripts/tournament.py --project <project> match --id T01 --spec <match.json>
python <skill>/scripts/tournament.py --project <project> status --id T01 --hypothesis T01-H002 --status eliminated --reason "…"
python <skill>/scripts/tournament.py --project <project> rank --id T01
python <skill>/scripts/tournament.py --project <project> promote --id T01 --hypothesis T01-H003 --to H-002 --decision D-005
```

- `blind` 生成单场比较的评委材料，只包含表述、机制、预测和参考文献，并按 `--order` 展示。
- `status` 把假设标为淘汰、撤回或恢复。`null` 基准假设要离开候选池，必须附一项已采纳的负责人决定（`--decision`）。
- `promote` 把选定的假设登记为项目级假设 `H-*`，附上来源锦标赛和排名快照。它要求附一项已采纳的 CP3 决定，因为只有负责人在 CP3 选定的假设才能提升。之后的检验状态用 `research_tree.py hypothesis set` 更新。脚本只用标准库，不调用任何模型。生成、评审和比较由宿主中的 AI 或人完成，脚本只负责记录、校验和计算。

## 5. 防偏差

- 评价标准在看到假设之前冻结；中途要改，就登记 `D-*`，并说明对已有比较的影响（必要时重开一轮）。
- 评委不知道假设来源：给评委的材料用 `blind` 生成，只保留表述、机制、预测和参考文献，隐去 `origin`、`strategy`、`parents`，按指定顺序展示。
- `null` 假设必须入池。它排在前列是重要信号，不能静默删掉；只有负责人做出已登记的决定，它才能离开候选池。
- 小样本时 Elo 波动大。报告每个假设的比较场数；场数不足的排名，标为不稳定。
- 不追求“看起来新”：只有可检验性和判别性预测清楚的假设，才能进入 CP3 的推荐。
