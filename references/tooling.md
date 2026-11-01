# 辅助工具：按动作选用

仅在使用文件型管理工具时读取。Python 3.9+、标准库；脚本只实现已声明的动作，不授予权限或判断科学充分性。默认不执行历史记录中的命令，不自动迁移旧state；一个state由单写入者维护。普通读文件、帮助和局部修复不用包装成科研运行。

## 1. 工具分工

| 动作 | 工具与权威说明 |
|---|---|
| 新建/补缺、预览 | `init_project.py`；[使用](../USAGE.md)、[迁移](migration.md) |
| 只读核记录/哈希/影响/关口 | `check_project.py`；[质量](quality-and-change.md) |
| 问题、假设、任务创建/状态/意图 | `research_tree.py`；[状态结构](state-schema-v2.md) |
| 决定、发现、成果、check/accept及执行控制 | `record.py`；[治理](governance.md) |
| 实际执行并保留快照/日志 | `run_project.py`；[复现](reproducibility.md) |
| 实际输出比较 | `verify_reproduction.py`；同上 |
| 关键变更影响及关闭 | `manage_change.py`；[治理](governance.md) |
| 只读审阅页/固定包/归档 | `render_review.py`、`build_release.py`、`archive_artifacts.py`；各对应协议 |
| 可选锦标赛/能力短名单 | `tournament.py`、`registry_search.py`；[竞争解释](hypothesis-tournament.md)、[注册表](capability-registry.md) |

用相应脚本`--help`查实际参数，不从文档推测新子命令。常见入口：

```text
python <skill>/scripts/init_project.py --target <project> --name <name> --scale M --profile research --no-research-folders --dry-run
python <skill>/scripts/research_tree.py --project <project> question add --id Q-001 --statement "实际问题" --clarity 2
python <skill>/scripts/research_tree.py --project <project> task add --id T-001 --title "实际工作包" --serves Q-001
python <skill>/scripts/research_tree.py --project <project> task intent --id T-001 --path _pm/intents/T-001.md
python <skill>/scripts/check_project.py --project <project> --require-gate G3 --verify-hashes
```

`--design`可重复指定研究类型，适用时生成实验登记及E1/R1；不是伦理或注册已完成。S级初始化不写文件；M/L仅补缺，不覆盖原件。`--no-research-folders`只跳过默认目录README占位，不自动映射业务路径。

## 2. 元数据探针的合法启动输入

首次公开资源盘点尚无分析数据时，不为满足inputs而绑定无关旧成果：

1. 将本轮**实际**官方URL或本地文件、访问范围/日期及用途写成项目内来源清单，如`references/probe-input.json`；计划访问与已取得文件分别标明。
2. 用`record.py artifact --id META-001 --path references/probe-input.json --version v1`登记清单。它是请求来源证据，不证明远端数据已取得或核验。
3. 使用独立探针配置、实际代码和环境记录。run-spec的inputs引用META-001@v1，task关联已登记任务；其他必填项按`assets/run-spec.json`填真实值，新输出路径不得覆盖旧文件。
4. 仅身份/文件目录核查可标stage为metadata；若需QC结构或目标读出，按实际接触声明analysis/validation及接触记录。标签不证明盲法。
5. 用本次明确提供的argv调用run_project，核实际文件与日志；不把失败或占位清单记成数据可行。

持续变化的授权/state不作冻结分析输入。登记拒绝后先定位原因，不继续依赖运行；工具未覆盖的少量字段按项目约定做可审查补丁，再核检查器，不能整体重写或伪造批准。

## 3. 维护而非日常科研的验证

```text
python -B -m unittest discover -s <skill>/scripts -p "test_*.py" -v
```

测试使用合成夹具；跳过、失败及覆盖范围如实报告。基础技能校验按宿主实际可用工具运行，不能假设某个绝对安装路径。结构测试不判断科学价值，实质流程变更另按[情景评估](behavioral-evaluation.md)核可观察行为。
