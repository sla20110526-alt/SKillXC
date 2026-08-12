# 真人写实 AI 影视生产总流程 v0.1

状态：首轮可执行结构；以各 Skill 内规则为准。系统只处理已有剧本或生产内容明确的项目，终点为正式 Seedance 2.0 镜头 Prompt 与生成可用镜头。

## 总循环

```text
控制类发任务单
→ 用户确认准备使用的通用 Skill 及可选 Profile
→ 创作类生产候选
→ 用户明确登记
→ 正式登记并进入可调用表
→ 就绪检查
→ 下一生产单元
```

## 主流程

1. `project-category-lock`：问答锁定真人写实、GPT Image 2、Seedance 2.0、画幅和参考用途。
2. `approval-asset-registry`：为具体项目确认项目 ID 和项目数据根目录，建立项目数据绑定卡；没有具体项目时只提醒，不建虚构目录。
3. `script-truth-index`：建立不含创作建议的剧本事实索引。
4. `script-asset-breakdown`：识别候选资产与状态变化，并预留项目内稳定正式资产 ID；预留不等于登记。
5. `asset-demand-plan`：沿用预留正式资产 ID，建立独立需求槽位、依赖与生产批次；需求不是正式资产版本。
6. `style-lock-director`：用户确认专业 Skill 与可选 Profile 后完成风格测试和短执行卡。
7. 分类资产生产：人物、场景或世界资产 + `image-prompt-production`。
8. `approval-asset-registry`：只有“登记这张”“确认登记”等明确指令才把预留 ID 的正式版本写入绑定项目的登记表和可调用表；正式名称采用用户指定名称。
9. `continuity-readiness-audit`：分镜前只核对当前绑定项目的正式可调用资产。
10. `dramaturgy-scene-beats` → `directing-blocking` → `acting-direction`。
11. `shot-visual-design` → `cinematography-direction` → `editing-rhythm` → `sound-voice-direction`。
12. 用户确认分镜后，`video-prompt-production` 装配 Seedance 2.0 Prompt 并生成可用镜头。
13. 用户需要时调用 `video-qc-review` 独立诊断；默认只分析，明确要求后才登记 QC 记录。

## 硬规则

- 候选、失败、用户仅表示喜欢或准备继续修改的结果都不登记。
- 每个项目使用独立项目数据根目录和绑定卡；生产对话只提交登记申请，登记对话只写绑定项目的表。
- 正式资产 ID 在资产拆解时预留，登记时沿用并增加版本；正式资产名称以用户明确指定的名称为准。
- 失败原因只在用户明确要求时由 `generation-version-log` 记录。
- 人物采用一张五视图总览卡：左1/3为正面特写和3/4侧面特写，右2/3为正面、侧面、背面全身。
- 人物资产画幅按排版需要，不跟随成片画幅。
- 大师 Profile 独立存放；对应阶段询问用户后才调取，用完只下传短执行卡。
- 项目数据默认：Markdown 卡片供人确认，CSV 保存多行权威记录，JSON Schema 检查表头和逐行结构；所有项目 CSV 行携带项目 ID，检查报告写入绑定项目目录。用户指定特定格式时记录例外并服从用户。
- 结构检查通过不等于用户批准、正式登记、业务引用或创作质量通过；对应责任 Skill 仍须完成业务复核。
- 分镜每镜必须解释“为什么需要本镜”与“为什么选择本机位和运镜”。
