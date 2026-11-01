说明：本机目录前缀已替换，答复实质及所记录的内容指纹未改。

# v4.4.1 最终候选独立文件评阅

评阅日期：2026-11-02 04:42:12（本机时间）。本次只做维护补丁的文件评阅；未做真实科研、联网、账户操作、发布、安装或情景答复执行。未修改技能源文件；本报告是唯一新增产物。

## 结论与适用边界

在实际读取范围内，未发现需要阻断本次维护补丁的矛盾、授权扩大、科研规则改变或失效链接。建议按“维护前核当前覆盖的澄清 + 可选定向情景补充”处理。原有科研运行原则已覆盖 F1–F3 的实质判断，无须为它们再次添加科研义务。

这是读过维护判据后的独立文档审阅，不是未见判据的独立情景执行，也未审查其他执行者的答复。因此它不能证明真实课题科学有效、该版本因果优于旧版、跨领域普遍有效，或任一情景已通过独立行为评估。主会话应按实际工作范围决定后续处理。

## 实际范围

- 当前候选根目录：<code><candidate-skill>/</code>。
- 基线运行文档快照：<code><baseline-skill>/</code>。
- 正文阅读全文：两版 <code>SKILL.md</code>、两版 <code>references/behavioral-evaluation.md</code>；候选的 <code>workflow.md</code>、<code>public-data-feasibility.md</code>、<code>research.md</code>、<code>research-value-review.md</code>、<code>question-shaping.md</code>、<code>hypothesis-tournament.md</code>、<code>research-types.md</code>、<code>roles-and-checkpoints.md</code>；候选 <code>assets/evaluation/feasibility-order-scenarios.json</code>。
- 为核对运行参考有无变化，对两侧 25 份 references 文件做 SHA256 字节比较。除上述正文范围外，仅计算散列，不解释其正文；其中包括未阅读全文的其他参考文件。
- 没有读取 AUDIT、CHANGELOG、任何之前或中间的评估答复、项目历史结论、记忆库。没有打开既有其他情景的原始 JSON；它们与新情景的交叉程度仅按两版评估页已有判据比较。
- 基线仅有 SKILL.md 与 references；不是完整发布包。本次不据此断言其他脚本、资产、安装副本或已发布版本的差异和可用性。

## 具体发现

### 1. 原科研规则已覆盖，新题面不需要另设规则

| 定向情景 | 已有运行要求与位置（候选及基线字节相同） | 本次判断 |
|---|---|---|
| F1 同规则联合子集 | <code>public-data-feasibility.md:15–19</code> 分开独立单位、配对、目标完整案例、来源条件；<code>:27–32</code> 按目标核人数上限与信息量、不设统一人数门槛；<code>research.md:20–25</code> 核单位、信息量并按致命条件排序 | 联合纳入条件与工程前的上限核查已有覆盖。无需新增“先数人数”的重复通用义务。 |
| F2 工程成功上界 | <code>question-shaping.md:34–42</code> 要求说明能区分或约束什么，不用高总分补偿关键测量缺失；<code>research-value-review.md:9–15</code> 区分技术可信度、科学信息量与下一块投入；<code>workflow.md:11–19</code> 最小探针、投入边界、科学/资源取舍 | 更高处理成功率和更多同类样本不能自动填补题面设定的不可辨识性；这不是新增研究执行原则。 |
| F3 有信息的描述结果 | <code>research-value-review.md:13–15</code> 承认精度充分负结果/解决矛盾的价值，不以显著性或人数决定发表；<code>research-types.md:44</code> 不以有无独立验证统一判探索；<code>public-data-feasibility.md:21</code> 独立验证是否必要取决于目标与设计 | 不因不显著、缺蛋白或独立队列就终止描述研究已有明确要求；F3用于约束过度停止，不能包装为新科学能力。 |

### 2. 维护方法有意复用已有要求，增量有限但清楚

基线 <code>workflow.md:37</code> 已要求技能维护区分“执行未落实、规则缺口和工具缺口”，说明收益、负担和适用范围，并分别核源副本、安装和发布。候选 <code>behavioral-evaluation.md:5–9</code> 没有另加项目台账或研究关口，而是把维护者的核查顺序具体化：先对齐经验发生版本、待改副本和当前有效规则，再区分已有但未落实、后续已修复、表述/触发缺口和工具缺口。它还明确前两类不重复增加义务。

所以这部分是已有维护原则的展开，不能称为填补了 F1–F3 的科研规则空白。新增加的“后续版本已修复”分类、当前覆盖核对和“无需改/实际改变”的维护结论要求有明确用途；短导航与详页的轻度重复没有形成两个相互竞争的权威位置。

两版 SKILL.md 的正文执行原则、范围说明、CP/G表及授权边界保持相同；可见变化是版本号 4.4.0 → 4.4.1 和末段增加“先核当前版本是否已覆盖旧经验，再决定修改”。评估页新增维护前覆盖核对、情景证据小标题及 F1–F3 扩展，既有 S/R/U 判据保留。

### 3. 新题面有交叉，合理用途是定向压力测试和反向对照

按两版评估页的既有判据，F2 与 R1“技术通过而增量/精度弱”有交叉；F3 与 R2“有信息的负结果”、U3“事前描述性估计”有明显交叉。它们没有代表全新的研究能力，不宜按题目数量证明维护收益。

新增定向用途仍可辨认：F1把独立性、年龄、测量和配对放入同一人数条件，并给出大工程无法改变的上限；F2把“工程很可能成功”与“不能区分给定解释”直接对立；F3是前两项旁的避免过度停止对照。候选 <code>behavioral-evaluation.md:51</code> 明确这些不是每个研究必须运行的新关口，且原文 <code>:25</code> 已允许按改动选择相关例。因此未形成重复强制测试负担。是否值得长期保留，仍可由后续真实维护使用反馈判断。

### 4. 题面内部一致，阈值限定于虚构任务

- F1 的 12 名目录记录在给定四项条件的交集中仅 V1 与 V4 合格，共 2 名、每病组 1 名。D1–D6 因与发现集重叠排除；V2/V6 年龄不符，V3 目标细胞数不符，V5 缺功能配对。题面没有给效应/精度目标，不能仅凭“2名”自动宣判一切研究都无效；维护判据 <code>behavioral-evaluation.md:55</code> 已明确防止这一误读。年龄50–79、细胞至少30、12GB只属于该题设，不是技能通用门槛。
- F2 明确限定现有 bulk RNA 上两种解释的预期完全相同，重处理不产生可区分读出或新对照。因此能测试工程上界与目标不变时的资源判断；不能从这道题推出 bulk RNA 或方法工具普遍没有价值。<code>behavioral-evaluation.md:56</code> 明确保留工具价值，且题面没有授权两周工程或转为工具论文。
- F3 的95%区间为 -0.04到0.06，处于事前关注尺度±0.10之内；它提供判断描述性报告价值的具体信息，未授权新实验、联系期刊或发布。整理价值不等于保证接收，也不能仅凭题面升级为因果、机制或正式等效性结论。其判据与原有负结果规则相容。
- JSON可正常解析，恰有3个唯一情景ID F1/F2/F3。内容不依赖真实项目、患者、病种、账户、平台或绝对工程路径。题目集中于生物研究中的特定判断，是补充测试覆盖；没有据此把技能全部研究类型缩成分子/组学要求。

### 5. 授权、适用范围与链接未见变更或冲突

SKILL.md:14 保持单次任务轻量，:23–28 保持范围内执行、事实/建议/决定分开和权限随原任务；:32–43 保持CP/G可合并、可说明不适用以及不设疾病/平台/样本数通用默认。<code>roles-and-checkpoints.md:16,47–49</code> 的决定权、评估不批准执行与连续执行规则在两版相同。维护评估页的隔离、无联网/账户操作/真实患者数据等限制也仍只属于维护情景执行，不是把它们变成科研通用禁令。

对候选实际阅读全文的10份Markdown文件，检查到69个Markdown本地链接，均存在并解析在候选技能根目录内；新链接 <code>../assets/evaluation/feasibility-order-scenarios.json</code> 可打开。这里核的是路径存在性，不代表链接指向的全部正文均已阅读或其论断已证实。基线快照不含USAGE.md及assets，故未以不完整快照的缺文件判为发布包坏链。

未发现需修改源文件的明确问题；无需为本次审阅另行追加运行规则、授权或适用范围。

## 读取文件指纹

SHA256按原始字节计算。下表是本次阅读全文的文件；候选8份运行参考的基线副本另已散列确认相同。报告落盘前重新核对这些指纹，若变化则中止写入；不宣称保存了首次正文读取之前的完整快照。

| 版本 | 相对路径 | 字节数 | SHA256 |
|---|---|---:|---|
| 候选 | <code>SKILL.md</code> | 7163 | <code>45be2d43ce8ce05def4704b5a96e4ab321453f0a9d30c29f3cc8d849f77cad78</code> |
| 候选 | <code>references/behavioral-evaluation.md</code> | 6256 | <code>0eedfe34ffbfa7e87c8f182602f3cdf4e5a2999619dd2e5f81b7b7f409dcccfd</code> |
| 候选 | <code>references/workflow.md</code> | 3501 | <code>56de2b8b5c66bb4122e2a8eb191cc04f79870e34ff318076850f39f86059a3cb</code> |
| 候选 | <code>references/public-data-feasibility.md</code> | 5692 | <code>4f3cac473ef265eed243fb0a036b63b8350476b0349eb92a1f31a78d94572065</code> |
| 候选 | <code>references/research.md</code> | 3937 | <code>4f4dc695934782a18d25b5048be5327931c480d9da24e1e0e4f36fa9fd16ec36</code> |
| 候选 | <code>references/research-value-review.md</code> | 3170 | <code>3a32280cf5242656dce8033512bb18c0d794330baac581afddd5eb1ea934e65b</code> |
| 候选 | <code>references/question-shaping.md</code> | 4842 | <code>525a9e6a7ce7fad7a6ce0496d5ffc49b83eea992b19e87efc001e84f98a240b5</code> |
| 候选 | <code>references/hypothesis-tournament.md</code> | 3453 | <code>d425a15b83741caed41a6ce31fc1cc22cc9f47597d91e21bbf4424380d66661f</code> |
| 候选 | <code>references/research-types.md</code> | 6896 | <code>7cb52ae6061a2daa1a6be4d6c0894646c08408099d03ebd1fed5f218289efad3</code> |
| 候选 | <code>references/roles-and-checkpoints.md</code> | 5308 | <code>e064a4ea423da7693f997a50241b9f7e557737b86a3774d2769495c0aa3a4ed3</code> |
| 候选 | <code>assets/evaluation/feasibility-order-scenarios.json</code> | 3149 | <code>2d22bb8138be4374bff30bc7f0e7e937815ed4e7887d117b338082e4faf64d75</code> |
| 基线 | <code>SKILL.md</code> | 7100 | <code>5151f761cc7a7c75cd8bc1ed34583f0baab4fbcd88be7207cb5b36038a78e693</code> |
| 基线 | <code>references/behavioral-evaluation.md</code> | 4626 | <code>d3f0674ed9a7db214bad196c7c823422c86f845509dd4a23886a507171c1d3bd</code> |

### 仅字节比较的完整参考对照

下表包括25对reference文件。标记“正文”表示本次已阅读全文的候选文件（behavioral两版均已读）；“散列”表示只做字节对比。相同项仅列一份SHA256，该值同时适用于两版。此表不是对未读正文的内容审查结论。

| references下文件 | 范围 | 基线SHA256 | 候选SHA256 |
|---|---|---|---|
| <code>archive.md</code> | 散列 | <code>e1bd0719f1a4a029abf6ef67be061256772412cc79c205523cdd9f9f71148195</code> | 同左 |
| <code>behavioral-evaluation.md</code> | 正文 | <code>d3f0674ed9a7db214bad196c7c823422c86f845509dd4a23886a507171c1d3bd</code> | <code>0eedfe34ffbfa7e87c8f182602f3cdf4e5a2999619dd2e5f81b7b7f409dcccfd</code> |
| <code>capability-registry.md</code> | 散列 | <code>77e7eada1a2445252aeb46c5318ea86deca1fe8469f47db583658ca47d3175bc</code> | 同左 |
| <code>design-lessons.md</code> | 散列 | <code>4a5ab8657d997f281c0312f1b3f80a64333f18a8acc501a12d13cd812d926e03</code> | 同左 |
| <code>evidence-and-materials.md</code> | 散列 | <code>6e31c6c3fd97ba157a368a139f27fe81dc541fca1d9ed1d0c38553a88972e3b6</code> | 同左 |
| <code>governance.md</code> | 散列 | <code>65fe097dc53b5f082196865c123ec94033056a813c72af1f48719029a91f8ec1</code> | 同左 |
| <code>hypothesis-tournament.md</code> | 正文 | <code>d425a15b83741caed41a6ce31fc1cc22cc9f47597d91e21bbf4424380d66661f</code> | 同左 |
| <code>migration.md</code> | 散列 | <code>fbb5c9043dc47002fc5965b28712065faac54cccaa0a480b41e45ebedccfd65d</code> | 同左 |
| <code>narrative-spine.md</code> | 散列 | <code>f91413e790e82734cc5d32f12af7edc808a4cae0f0678ef437c72c246abde841</code> | 同左 |
| <code>portability.md</code> | 散列 | <code>e5b5b9df71f4d94a3426aa10a65171db034bc8c0b7a6fcdb8f97033612e801c6</code> | 同左 |
| <code>project-layout.md</code> | 散列 | <code>8bcc9814f6111c66d38cec0f0a526defac48e7d7910cce3125a75503b2893c2f</code> | 同左 |
| <code>public-data-feasibility.md</code> | 正文 | <code>4f3cac473ef265eed243fb0a036b63b8350476b0349eb92a1f31a78d94572065</code> | 同左 |
| <code>quality-and-change.md</code> | 散列 | <code>3345366f1c4e5d157ac37790f45faabaed6a8c49b606b769913faea73dbd5e17</code> | 同左 |
| <code>question-shaping.md</code> | 正文 | <code>525a9e6a7ce7fad7a6ce0496d5ffc49b83eea992b19e87efc001e84f98a240b5</code> | 同左 |
| <code>release.md</code> | 散列 | <code>038fec70f43359825324decfdd8ac4aa07cc1e7d8fea2e7ad73d4615bc1a2051</code> | 同左 |
| <code>reproducibility.md</code> | 散列 | <code>2fa1296f12edbacaf9234ae390b1b5abb012b0666a35a010c5283133909c74e1</code> | 同左 |
| <code>research-types.md</code> | 正文 | <code>7cb52ae6061a2daa1a6be4d6c0894646c08408099d03ebd1fed5f218289efad3</code> | 同左 |
| <code>research-value-review.md</code> | 正文 | <code>3a32280cf5242656dce8033512bb18c0d794330baac581afddd5eb1ea934e65b</code> | 同左 |
| <code>research.md</code> | 正文 | <code>4f4dc695934782a18d25b5048be5327931c480d9da24e1e0e4f36fa9fd16ec36</code> | 同左 |
| <code>reviewer.md</code> | 散列 | <code>4c123b98ab183817ae6bb0a549ce9077c35070b6efbf73dc66cb60cab094bfe2</code> | 同左 |
| <code>roles-and-checkpoints.md</code> | 正文 | <code>e064a4ea423da7693f997a50241b9f7e557737b86a3774d2769495c0aa3a4ed3</code> | 同左 |
| <code>skill-composition.md</code> | 散列 | <code>43f9efc62ec7b214914e10203a8909c1b2d45d789c94624b378f8b9aed08cd5a</code> | 同左 |
| <code>state-schema-v2.md</code> | 散列 | <code>d25622708dbb1fe6c77ba5099a0dc4cccbb81b32f6f0cc3c2d625935211d4ec3</code> | 同左 |
| <code>tooling.md</code> | 散列 | <code>8ac62df74bad9ff615c81035ff9c96098964f6808279b01764d1e6028c956ea9</code> | 同左 |
| <code>workflow.md</code> | 正文 | <code>56de2b8b5c66bb4122e2a8eb191cc04f79870e34ff318076850f39f86059a3cb</code> | 同左 |

## 未覆盖事项

未查阅完整包的其他脚本/资产差异、运行测试结果、真实研究经历、已安装或已发布版本；未运行独立情景任务，也未建立跨类型真实项目前瞻观察。链接检查、JSON解析与散列比较只验证文件和结构范围，不替代行为或科学有效性证据。
