# 项目数据三层契约

本契约规定项目数据的默认结构。用户明确指定其他格式时服从用户，并在任务卡的“格式例外”中写明；不得为了形式完整而把同一段长文本机械复制三份。

## 三层职责

1. **Markdown 卡片**：供人阅读和确认。记录范围、结论、关键决策、缺口、输入版本、输出文件与下游动作。
2. **CSV 表格**：作为多条记录和索引的结构化事实源。每张项目表必须带 `项目ID`，UTF-8 编码，第一行为唯一表头；一个单元格只承载一个字段，多个值用统一分隔符并在卡片中说明。
3. **JSON Schema 检查**：每份纳入契约的 CSV 必须映射到一份 Draft 2020-12 Schema。Schema 描述单行对象；CSV 表头必须与 `properties` 完全一致，数据行逐行检查。

Markdown 不由 JSON Schema 直接解析。Markdown 卡片应引用对应 CSV、Schema、数据契约版本和检查报告，避免人读结论与结构化数据失联。只有一张说明卡、没有多行数据的创作产物，以该成果的一行任务成果索引承担 CSV 与 Schema 层，不另造一张重复表；任务索引只承载任务调度，不承载成果版本、路径或依赖。

## 权威关系

- `tasks/任务索引.csv` 是任务身份、任务单版本与调度状态的权威源；`tasks/任务成果索引.csv` 是无专用权威表任务产物的稳定 ID、独立版本、路径、指纹、上游引用与可交接状态的权威源。两表通过来源任务 ID/版本形成一对多关系。

- 项目锁定、路由任务、资产拆解、索引、计划、正式登记、就绪审计、分镜设计和按需记录都按本契约输出。
- CSV 是逐条记录的权威源；Markdown 是对该批数据的范围、结论和例外说明。
- Schema 是结构与取值约束，不是项目数据，也不能证明创作结果已经批准或资产已经登记。
- 正式资产是否可调用仍只由 `approval-asset-registry` 的明确登记门决定；Schema 通过不改变候选、失败或未批准结果的身份。
- Schema 只验证单表结构与单行约束。跨表 ID、父子依赖、版本引用和批准授权仍由对应 Skill 复核，不得把“结构通过”写成“业务通过”。

## 检查门

每次把项目数据交给下游前：

1. 使用绑定卡确认项目 ID 和项目数据根目录。
2. 运行 `scripts/validate_project_data.py` 检查相关 CSV 与 Schema；真实项目必须传入 `--project-id`。
3. 在项目数据目录生成 `数据校验报告.md`，或把同等内容写入本批 Markdown 卡片。
4. 报告为“未通过”时暂停交接，修正数据后重新检查；不得跳过错误或用文字声称通过。

单表示例：

```powershell
python "<production-router-handoff Skill目录>\scripts\validate_project_data.py" --input "<项目CSV绝对路径>" --schema "<Schema绝对路径>" --project-id "<项目ID>" --report "<项目数据根目录>\validation\数据校验报告.md"
```

同一批有多张表时，在首对 `--input/--schema` 后为每一张追加 `--pair "<CSV>" "<Schema>"`，一次生成覆盖整批的报告；不要让后一张表的单独报告覆盖前一张结果。

仓库模板完整性检查：

```powershell
python skills/production-router-handoff/scripts/validate_project_data.py --manifest skills/production-router-handoff/assets/data-contract-map.json
```

检查器实现本仓库 Schema 使用的确定性关键字子集，并对未支持的关键字直接报错，不静默跳过。当前支持类型、`required`、`additionalProperties: false`、`enum`、`minLength`、`pattern`、`minimum` 和 `exclusiveMinimum`；新增其他约束时必须先扩展检查器和回归测试。

## 检查报告最小字段

- 数据契约版本、检查时间、项目 ID
- 输入 CSV 与所用 Schema
- 表头检查、数据行数、通过行数、失败行数
- 精确到行号和字段的错误
- 最终结论：`通过 / 未通过`
- 结构检查未覆盖的业务复核项

检查报告属于具体项目数据，不写入 SKillXC 中央仓库。中央仓库只保存模板、Schema、契约映射和检查器。
