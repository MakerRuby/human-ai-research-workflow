# 一轮固定交付与投稿前材料

一轮一编号，默认 `releases/<ID>/`：`upload/` 保存本轮拟提交文件；`internal_review/` 保存检查、状态快照及复现比较报告；根目录有 README 和 manifest。保留正文/代码等工作源文件，交付目录保存固定副本。根项目 README 链接当前候选包，旧包保留生成时状态。

先核对实际收件方要求。研究项目记录目标期刊官方要求的来源、访问时间、文章类型与本轮条件；通用项目记录客户或交付验收要求。脚本不会自动获取期刊要求或判断文件是否符合全部要求。

复制 `assets/release-spec.json` 并填写：编号、标题、交付对象（研究项目用 `journal`，普通项目用 `recipient`）、阶段、`requirements_record`、必要关口/成果/复现编号、关键结果 `critical_results`、本轮文件清单和确认依据。每个文件绑定 `artifact`、`version`、`destination`；destination 必须在 upload/ 或 internal_review/。模板按科研项目提供，普通项目同时按下文更换确认项。

```text
python <skill>/scripts/build_release.py --project <project> --spec _pm/release-spec.json --mode draft
python <skill>/scripts/build_release.py --project <project> --spec _pm/release-ready-spec.json --mode ready
python <skill>/scripts/build_release.py --project <project> --verify releases/<ID>
python <skill>/scripts/build_release.py --project <project> --verify releases/<ID> --against-current
```

draft 仍要求文件与版本真实存在，可以带明确阻塞供审阅；ready 拒绝结构错误、未闭环变更、未接受的阻塞审阅、未验收或过期的必要成果和未满足的必要关口。研究项目必须明确关键结果和完整范围复现验证，确保声明的覆盖连接到对应结果。普通项目不强制研究关口和复现。

研究项目必须逐项记录作者、声明、期刊要求和跨文档一致性；普通项目采用交付授权、交付要求和跨文档一致性。确认项结构为 `id/status/by/rationale/evidence`，status 为 confirmed 或有依据的 not_applicable。只能登记实际获得的确认；不适用也要有理由，不能用 AI 猜测合作者已同意。

manifest 保存来源路径、版本、哈希、生成时阻塞、范围、确认与状态指纹。内部保留要求和确认依据文件。仅拟上传目录供后续外发范围核对；内部记录可能含不宜提交的信息。

生成脚本不覆盖已有编号。verify 核查固定包内容；against-current 另报当前源文件偏离，历史包完好与源文件已变化可以同时成立。校验和防止无意损坏，不是签名，也不能证明证据真实。ready 是声明范围内的记录与检查满足，不等于科学结论被证明、文件已实际提交或期刊会接收。
