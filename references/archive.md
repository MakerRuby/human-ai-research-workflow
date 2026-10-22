# 退出使用与归档

设 `archive/`，按实际需要建立。它保存明确不再进入当前路线的材料，而非所有中间文件。建议：`archive/retired/<ARCH-ID>/` 放已登记成果的退出快照；`archive/exploratory/` 可放明确不用且需要保留的探索材料；原始运行、失败日志和固定投稿包仍保留在原职责目录。

成果当前质量 `status` 与使用生命周期 `lifecycle` 分开。默认 active；退出时为 retired。原因类型 `disposition` 分为 invalid（错误被否定）、superseded（已被替代）、out_of_scope（有效但不属本次范围）、exploratory_unused（探索未采用）。不应把所有未使用结果都写为错误，也不应只因结果不显著而隐藏它们。

退出需要实际责任角色、时间、原因、决定/核查证据、原位置、版本、文件哈希、替代成果（如有）和关联变更。依赖它的分析、图表、正文、复现和审阅先进入变更闭环。保留负结果与选择原因，避免选择性报告。

可从 `assets/archive-spec.json` 复制规范到项目管理目录，替换占位值；无关联变更或替代成果时可省略这两个字段。

```json
{
  "id":"ARCH-001","artifacts":["RESULT-OLD"],
  "disposition":"superseded","reason":"经核查采用更新方法；详见决定",
  "by":"实际责任人或授权执行角色","evidence":["_pm/DECISIONS.md"],
  "change":"CH-001","replacement":"RESULT-NEW"
}
```

```text
python <skill>/scripts/archive_artifacts.py --project <project> --spec _pm/archive-spec.json
```

脚本为登记成果建立不覆盖的归档副本与 manifest，标记 retired，并核对已登记依赖。原文件保留以维持历史证据链接；副本明确是历史快照，不建立第二份当前成果。retired 输入不能被运行和比较脚本用于新的分析，新交付包也拒绝包含它们。核查器会阻止接受仍使用已退出输入的当前成果。

对于无需保持原位置的未登记探索文件，可在明确范围和授权后迁入归档并保留清单。对于已被引用的大文件，如确需迁移，先逐一更新路径引用与恢复说明并验证；本脚本不自动搬动或删除原件。归档不等于删除，也不能用移目录绕过变更审阅。重新采用时须有新的决定、重新核验和明确版本，不通过静默去掉 retired 恢复旧结论。
