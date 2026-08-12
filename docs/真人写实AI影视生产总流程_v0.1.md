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
2. `script-truth-index`：建立不含创作建议的剧本事实索引。
3. `script-asset-breakdown`：识别候选资产与状态变化。
4. `asset-demand-plan`：建立需求槽位、依赖与生产批次；需求不是正式资产。
5. `style-lock-director`：用户确认专业 Skill 与可选 Profile 后完成风格测试和短执行卡。
6. 分类资产生产：人物、场景或世界资产 + `image-prompt-production`。
7. `approval-asset-registry`：只有“登记这张”“确认登记”等明确指令才登记并进入可调用表。
8. `continuity-readiness-audit`：分镜前只核对正式可调用资产。
9. `dramaturgy-scene-beats` → `directing-blocking` → `acting-direction`。
10. `shot-visual-design` → `cinematography-direction` → `editing-rhythm` → `sound-voice-direction`。
11. 用户确认分镜后，`video-prompt-production` 装配 Seedance 2.0 Prompt 并生成可用镜头。
12. 用户需要时调用 `video-qc-review` 独立诊断；默认只分析，明确要求后才登记 QC 记录。

## 硬规则

- 候选、失败、用户仅表示喜欢或准备继续修改的结果都不登记。
- 失败原因只在用户明确要求时由 `generation-version-log` 记录。
- 人物采用一张五视图总览卡：左1/3为正面特写和3/4侧面特写，右2/3为正面、侧面、背面全身。
- 人物资产画幅按排版需要，不跟随成片画幅。
- 大师 Profile 独立存放；对应阶段询问用户后才调取，用完只下传短执行卡。
- 项目数据默认：Markdown 卡片 + CSV 表格 + JSON Schema 检查；用户指定特定格式时服从用户。
- 分镜每镜必须解释“为什么需要本镜”与“为什么选择本机位和运镜”。
