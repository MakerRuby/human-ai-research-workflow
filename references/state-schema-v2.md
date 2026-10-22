# 状态结构 v2

文件 `_pm/project-state.json`，UTF-8 JSON。`schema_version: 2`；`project` 含 name、profile（general/research）。`layout` 是非空的职责到项目相对目录的映射；路径用 `/`，禁止绝对路径、`..` 和链接逃逸。management 固定 `_pm`。同一个集合内编号唯一，版本为非空字符串。

所有集合即使为空也保留数组：artifacts/checks/tasks/gates/findings/decisions/changes/claims/risks/review_items/runs/reproductions。v1 基础字段与规则继续适用，详见 [质量与变更](quality-and-change.md)。v1 不执行扩展规则，不能因此声称扩展治理已通过。

## 基础集合

- artifacts：id/path/version/status/depends_on/required_checks。depends_on 为 `[{"id":"上游编号","version":"v1"}]`。状态 draft/produced/checked/accepted/stale/rejected。accepted 需 acceptance.by/rationale 与当前必需检查通过。可加 sha256、requires_professional_review、requires_reproduction（布尔值）。
- artifacts 可选 lifecycle 为 active/retired；retired 需 retirement.by/at/reason/disposition/manifest/snapshot/evidence。disposition 与操作见 [归档协议](archive.md)。当前质量状态与是否还被采用分别表达。
- checks：id/artifact/version/kind/status/required；kind 为 machine/professional/source，status 为 pending/pass/fail/waived。完成检查需 by/rationale/evidence 文件列表。waived 仅用于非必要检查并有 waiver_reason；命令字段只是记录，核查器不执行。
- tasks：id/status/inputs/outputs；inputs 为版本引用，outputs 为成果编号列表。状态 todo/doing/blocked/done。
- gates：id/status/artifacts/checks/depends_on；列表使用编号，状态 pending/conditional/pass/fail。pass 需 by/rationale/evidence，且必要前置与证据满足。

## 新集合

| 集合 | 必需信息 | 状态 |
|---|---|---|
| findings | id/title/observed_at/by/observation/interpretation/record/evidence/inputs/decisions/changes | observed/under_review/supported/refuted/superseded |
| decisions | id/title/record/findings；采用或被替代的决定还需 by/decided_at/authorization/evidence | proposed/adopted/superseded/withdrawn |
| changes | id/title/opened_at/reason/sources/findings/decisions/items；关闭还需 closed_at/by/closure_rationale | open/blocked/closed |
| claims | id/statement/strength/results/locations/findings；supported 还需 evidence | draft/supported/stale/withdrawn |
| risks | id/title/impact/next_action/owner | open/mitigated/closed |
| review_items | id/title/question/recommendation/alternatives/consequences/inputs/evidence；正式答复需 by/response/responded_at；可选 blocking 布尔 | pending/commented/needs_evidence/conditional/accepted/rejected/stale |
| runs | id/status/path 指向实际 run.json | running/succeeded/failed/timed_out/interrupted |
| reproductions | id/title/scope/required/inputs；通过还需 run/report/by/rationale/evidence | pending/running/pass/fail/blocked/stale |

inputs/results 是成果版本引用；sources 是成果编号；findings/decisions/changes 为相应编号列表。record/evidence/locations/report/path 使用实际项目文件路径。scope 为 full/partial/smoke；required 为布尔值。findings 的 record 指向详细论据，state 中 observation/interpretation 是可检索摘要，不复制整段研究记录。

示例（各相关编号和文件必须先存在）：

```json
{
  "id":"F-001","title":"发现重复样本","status":"observed",
  "observed_at":"2026-10-23T09:00:00+08:00","by":"AI 数据检查执行者",
  "observation":"样本映射检查提示重复；具体数量见证据",
  "interpretation":"需要核实是否为技术重复，尚不能决定排除",
  "record":"_pm/FINDINGS.md","evidence":["results/sample-check.json"],
  "inputs":[{"id":"DATA-001","version":"v1"}],"decisions":[],"changes":[]
}
```

`changes.items` 字段及操作见 [治理协议](governance.md)。closed 记录是历史处理结果，保留当时版本；open 清单必须覆盖当前已登记影响。脚本计算只能覆盖注册的关系，人工审阅补全语义影响。

run.json 和 comparison 报告由实际运行/比较脚本产生，详细字段由其输出定义；勿手工捏造通过。state 中索引与详细证据必须对齐。结构合法不证明内容真实；环境重建与独立复现需要额外实际证据。
