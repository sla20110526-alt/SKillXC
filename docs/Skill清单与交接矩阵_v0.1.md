# Skill 清单与交接矩阵 v0.1

## 使用原则

- 控制类 Skill 管理事实、版本、计划、批准和就绪，不代替创作判断。
- 创作类 Skill 生产方案和候选，不宣布资产已登记。
- 进入任何通用创作 Skill 前先说明用途并询问用户是否确认使用。
- 进入导演、摄影、美术、编剧/剧作、剪辑阶段时，再询问是否从 Profile 资料库调取谁。
- 下游只读取当前任务需要的最小数据切片。

## 生产控制类

| Skill | 主要输入 | 核心输出 | 下游 |
|---|---|---|---|
| `project-category-lock` | 剧本、参考、用户问答 | 项目锁定卡 | 剧本事实索引 |
| `script-truth-index` | 项目锁定卡、锁定剧本 | 场次与事实索引 | 资产拆解、场戏分析 |
| `asset-demand-plan` | 候选资产、预留正式资产ID、剧本事实 | 独立需求槽位、依赖、批次 | 路由交接 |
| `production-router-handoff` | 当前阶段、项目绑定、任务和缺口 | Skill确认、任务单、激活指令 | 对应创作 Skill |
| `approval-asset-registry` | 项目绑定；用户明确登记指令；唯一候选 | 项目数据绑定卡、正式资产登记、可调用映射 | 就绪审计、分镜 |
| `generation-version-log` | 用户明确记录要求 | 可选生成/失败记录 | 复盘；不进入登记 |
| `continuity-readiness-audit` | 正式登记与调用表、剧本状态 | 场次/生成单元就绪结论 | 分镜或返回补资产 |

## 资产与风格生产类

| Skill | 用户确认点 | 核心输出 | 下游 |
|---|---|---|---|
| `script-asset-breakdown` | 是否使用通用拆解 Skill | 候选资产、预留正式资产ID、变体、缺口 | 资产需求计划 |
| `style-lock-director` | 使用哪些专业 Skill；是否加载 Profile | 完整风格包、分类短执行卡 | 各资产/分镜 Skill |
| `art-lookdev-direction` | 是否使用；是否加载美术 Profile | 世界、美术、材质、色彩规则 | 风格总控、资产生产 |
| `cinematography-direction` | 是否使用；是否加载摄影 Profile | 项目/场戏摄影策略卡 | 镜头设计、Prompt |
| `lighting-direction` | 是否使用 | 光源地图、受光与曝光卡 | 场景资产、镜头 Prompt |
| `specialist-consultant-router` | 是否使用；准确与艺术化边界 | 最小顾问问题与结论卡 | 美术、资产、调度 |
| `character-asset-production` | 是否使用；每次候选是否明确登记 | 选脸、单张五视图总览卡、人物变体 | 正式登记 |
| `location-spatial-production` | 是否使用；母图/视图是否明确登记 | 母图、空间圣经、光源图、多视图 | 正式登记、导演调度 |
| `world-asset-production` | 是否使用；候选是否明确登记 | 道具、载具、生物、怪物、VFX资产 | 正式登记 |
| `image-prompt-production` | 是否使用 | GPT Image 2 Prompt与修订 | 外部生成；再回资产 Skill |

## 场戏与镜头创作类

| Skill | 用户确认点 | 核心输出 | 下游 |
|---|---|---|---|
| `dramaturgy-scene-beats` | 是否使用；是否加载剧作 Profile | 戏剧目标、信息、潜台词和节拍 | 导演、表演 |
| `directing-blocking` | 是否使用；是否加载导演 Profile | 观众视点、人物调度和空间关系 | 镜头设计 |
| `acting-direction` | 是否使用 | 目标、策略、倾听、眼神和身体行为 | 镜头设计、Prompt |
| `shot-visual-design` | 是否使用；是否加载摄影 Profile | 有叙事理由的分镜表 | 剪辑、用户确认 |
| `editing-rhythm` | 是否使用；是否加载剪辑 Profile | 时长、切点、动作接点、生成单元 | 分镜定稿 |
| `sound-voice-direction` | 是否使用 | 声音身份、对白、环境和声音桥 | Prompt生产 |
| `video-prompt-production` | 是否使用；分镜是否确认 | Seedance 2.0正式Prompt | 外部生成可用镜头 |

## 独立资料与审查类

| Skill | 触发 | 输出 |
|---|---|---|
| `film-profile-library` | 对应专业阶段中用户明确选择 | 当前阶段方法卡；完整Profile不下传 |
| `video-qc-review` | 用户要求检查、查询或项目复盘 | 默认只分析；明确要求后才写QC记录 |

## 关键返工路由

| 问题 | 返回 Skill |
|---|---|
| 剧本出处或状态不清 | `script-truth-index` |
| 项目目录未绑定或跨项目数据混用 | `approval-asset-registry` 重建或复核绑定卡 |
| 缺少资产或父子版本错误 | `asset-demand-plan` / 对应资产生产 Skill |
| 人脸、场景、道具本体错误 | 对应资产生产 Skill + `image-prompt-production` |
| 缺少场景机位视图 | `location-spatial-production` 补做 SV3 |
| 戏剧目标或信息顺序错误 | `dramaturgy-scene-beats` |
| 人物走位或观众视点错误 | `directing-blocking` |
| 表演僵硬、夸张或缺少反应 | `acting-direction` |
| 构图、景别、机位或运镜平庸 | `shot-visual-design` |
| 时长、切点或动作衔接错误 | `editing-rhythm` |
| 设计正确但 Seedance 未执行 | `video-prompt-production` 精简或拆单元 |
| 需要系统诊断视频问题 | `video-qc-review` |

