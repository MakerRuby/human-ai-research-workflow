# 发现、决策与变更

## 发现与决定

重要发现用 F 编号；包括负结果、错误、来源冲突和可行性失败。记录实际时间、观察者、原始观察、解释、输入版本、可打开的证据、相反证据、限制与下一步。`observed` 表示记录了观察；`supported` 也不自动等于研究最终成立。被推翻时保留原记录并说明替代关系。

决策用 D 编号。详细记录候选方案、权衡、结论、责任和授权来源。AI 可以在授权范围内作技术决定，`by` 必须写清真实角色；需要负责人判断的事项保持提议，不能以“建议采纳”代替实际同意。

外部来源使用 `REF-*`，数据来源使用 `DATA-*`，运行使用 `RUN-*`，重要论断使用 `CLAIM-*`，变更使用 `CH-*`。来源入口为 `references/INDEX.md`；只有影响重要判断、分析、图表、论断或正文的来源才需要独立证据卡。候选来源只需最小出处和暂定用途，普通搜索结果不必归档。

来源、发现、决定、运行和论断之间可记录带类型的关系，例如 `supports`、`refutes`、`defines`、`motivates`、`justifies`、`observed_in`、`used_in`、`changes` 和 `supersedes`。AI 可以提出关联；主会话核对编号、版本和证据位置后写入正式记录。影响方向、核心方法或结论强度的关联仍需负责人确认。

## 变更事务

### 事务式常用操作

以下操作只登记已经发生的检查或决定，不执行检查、不判断科学充分性、不授予权限。`--by` 写实际角色，`--evidence` 为已存在的项目相对文件；不要把模板/合成例子当真实批准。AI在项目允许范围内做内容验收时，明确其范围及非独立专业审稿身份。

```text
python <skill>/scripts/record.py --project <project> check --id C-001 --artifact DOC-001 --version v1 --kind professional --status pass --required --by <实际核对者> --rationale <核对范围> --evidence _pm/checks/C-001.md
python <skill>/scripts/record.py --project <project> accept --id DOC-001 --check C-001 --by <实际接受者> --rationale <接受范围> --evidence _pm/checks/C-001.md
python <skill>/scripts/research_tree.py --project <project> task set --id T-001 --status done --output DOC-001 --by <实际执行者> --rationale <完成范围> --evidence _pm/checks/C-001.md
python <skill>/scripts/record.py --project <project> decision-set --id D-002 --status withdrawn --by <实际撤回者> --rationale <未采用/撤回理由> --evidence _pm/DECISIONS.md
```

必要检查未通过、目标内容被修改、输入/输出过期或验收字段缺失时，操作拒绝并保持原状态；检查失败不能用一个新通过记录掩盖原必要失败。更改检查要求或版本须按真实评审/变更处理。

### 暂停、停止与恢复

先登记真实的 adopted D 决定，再控制执行。以下 D 编号只是用法占位，不是任何项目的授权：

```text
python <skill>/scripts/record.py --project <project> project --status stopped --decision D-003 --objective-achieved no --by <实际登记者> --rationale <负责人停止及目标未达成> --evidence _pm/DECISIONS.md
python <skill>/scripts/record.py --project <project> project --status active --decision D-004 --by <实际登记者> --rationale <真实重启范围> --evidence _pm/DECISIONS.md
python <skill>/scripts/research_tree.py --project <project> task set --id T-001 --status doing --decision D-004 --by <实际登记者> --rationale <真实重启该任务> --evidence _pm/DECISIONS.md
```

项目状态可用 paused/stopped，任务也可 cancelled。停止本身不设置目标成功；目标未评估可不传 objective-achieved，已有评估不被默默清空；明确声明 yes 另需 `--objective-evidence`。恢复须新的实际决定，不能复用停止授权，也不自动重开所有任务。只做仍获授权的收尾可继续登记来源、检查和总结，但不以收尾名义运行新研究。旧项目的自定义停止字段和根目录约定先人工核对，再显式登记新字段；不自动迁移真实项目。

已采用决定被实际替代时使用 `decision-set --status superseded --superseded-by D-004`；保留原批准证据。提案未获采用不写成曾被批准。项目只使用一个状态写入者，事务指单次校验后原子写文件，不是并发数据库或权限系统。

### 变更清单

修改数据、排除标准、方法、代码、关键结果、图表或核心论断前，识别影响并登记 CH 编号。一个变更可以关联多项发现和决定。示例规格：

```json
{"id":"CH-001","title":"校正样本映射","reason":"发现重复样本","sources":["DATA-001"],"findings":["F-001"],"decisions":["D-001"]}
```

`manage_change.py open --spec <项目相对路径>` 建立清单并将已登记链条的下游成果标为 stale、任务重开、关口待复审、关联复现/正文结论/审阅标为 stale。先开变更再修改源文件，便于保留完整上下文。

影响清单的 `kind` 为 artifact/task/gate/reproduction/claim/review；每项 `status` 为 pending/blocked/updated/unchanged。处理后写清 `rationale`、实际 `evidence` 文件，成果项还写处理后的 `version`。`unchanged` 表示已核实不用修改，不是略过；例如校正仅涉及未纳入的样本也必须有核验依据。

历史复现、审阅等记录不可覆盖时，为新验证分配新编号，将原影响项标为 updated 并填 `replacement` 指向同类新记录。关闭会核查替代记录的当前状态；原记录继续保留过期或失败状态，不能把旧报告改写成新报告。

```text
python <skill>/scripts/manage_change.py --project <project> close --id CH-001 --by <实际责任角色> --rationale <闭环理由>
```

未决项不能关闭；全部处理后还要检查当前版本、验证状态与证据。保留历史闭环时间和当时版本，后来新变更不能回写旧决定。单文件原子写入不等于跨程序并发事务：由一个统筹写入者合并更新，处理失败保持变更打开。

脚本只能追踪明确登记的依赖。人工补查摘要、正文、图题、补充材料、代码说明和投稿信中的隐含影响；新增依赖后重新审视打开的变更清单。claim 记录把具体论断连接到结果版本和实际正文文件，`strength` 说明解释强度；需要逐处语义核对，脚本不自动读取并证明整篇论文一致。

每次续接先看未关闭变更、过期成果、待决问题，再选可继续任务；结束时登记本轮处理项和余下影响。不要只更新 STATUS 或单张图后宣布项目已同步。
