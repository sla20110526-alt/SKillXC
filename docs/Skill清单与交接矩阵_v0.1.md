# Skill 清单与交接矩阵 v0.1

## 使用原则

- 控制类 Skill 管理事实、版本、计划、批准和就绪，不代替创作判断。
- 创作类 Skill 生产方案和候选，不宣布资产已登记。
- 进入任何通用创作 Skill 前先说明用途并询问用户是否确认使用。
- 进入导演、美术、编剧/剧作、剪辑的方法建立阶段时，再询问是否从 Profile 资料库调取谁。摄影只在建立或重建全片摄影基线时常规询问一次；后续继承摄影规则卡。
- 分镜表只有 `shot-visual-design` 可以写入；摄影指导的逐镜意见经审核卡返回，由镜头视觉设计写回。
- Prompt 放行与生成结果可用分开记录；生产对话只回显轻量检查点，独立记录对话按用户明确授权同步项目进度。
- 下游只读取当前任务需要的最小数据切片。
- 中央源定义、Profile 与项目重要创作控制卡使用相互独立的版本；中央源或 Profile 升级不自动改写既有项目卡。
- 项目数据使用人读 Markdown 卡、CSV 多行记录和 JSON Schema 检查；单次创作短卡由任务索引追踪，不重复制造专用 CSV。
- 每次结构化数据交接附校验报告；结构通过不替代用户批准、正式登记和业务复核。

## 生产控制类

| Skill | 主要输入 | 核心输出 | 下游 |
|---|---|---|---|
| `project-category-lock` | 剧本、参考、用户问答 | 项目锁定卡、项目锁定索引、校验报告 | 剧本事实索引 |
| `script-truth-index` | 项目锁定卡、锁定剧本 | 事实索引卡、场次/事实索引、校验报告 | 资产拆解、场戏分析 |
| `asset-demand-plan` | 候选资产、预留正式资产ID、剧本事实 | 批次计划、需求/依赖表、校验报告 | 路由交接 |
| `production-router-handoff` | 当前阶段、项目绑定、任务和缺口 | Skill确认、任务单、任务索引、激活指令、校验报告 | 对应创作 Skill |
| `approval-asset-registry` | 项目绑定；用户明确登记指令；唯一候选 | 绑定卡/索引、登记回执、正式/可调用表、校验报告 | 就绪审计、分镜 |
| `creative-control-versioning` | 专业Skill产生的项目控制卡草案；中央源/Profile精确引用；用户确认原文 | 项目基线/表演母档/声音身份的版本与生效事务、备份和校验 | 专业生产、就绪审计；不生产创作内容 |
| `generation-version-log` | 用户明确同步或详细记录要求 | 镜头生产进度表；按需生成/失败详表；校验报告 | 项目进度、复盘；不进入资产登记 |
| `continuity-readiness-audit` | 正式登记与调用表、剧本状态 | 审计卡、场次/生成单元表、校验报告 | 分镜或返回补资产 |

## 资产与风格生产类

| Skill | 用户确认点 | 核心输出 | 下游 |
|---|---|---|---|
| `script-asset-breakdown` | 是否使用通用拆解 Skill | 拆解卡、候选/缺口表、预留正式资产ID、校验报告 | 资产需求计划 |
| `style-lock-director` | 使用哪些专业 Skill；是否加载 Profile | 完整风格包、分类短执行卡 | 各资产/分镜 Skill |
| `art-lookdev-direction` | 是否使用；是否加载美术 Profile | 世界、美术、材质、色彩规则 | 风格总控、资产生产 |
| `cinematography-direction` | 是否使用；全片基线时是否加载摄影 Profile | 全片摄影规则卡；场戏摄影约束卡；逐镜摄影审核卡 | 镜头设计；摄影审核写回 |
| `lighting-direction` | 是否使用 | 光源地图、受光与曝光卡 | 场景资产、镜头 Prompt |
| `specialist-consultant-router` | 是否使用；准确与艺术化边界 | 最小顾问问题与结论卡 | 美术、资产、调度 |
| `character-asset-production` | 是否使用；当前人物工作模式；每次候选是否明确登记 | 脸母图、单张五视图卡、服装/状态/交互继承卡、Prompt输入与候选验收 | 图片Prompt；明确登记后转登记 |
| `location-spatial-production` | 是否使用；场景工作模式；母图构图子模式；每张候选是否明确登记 | 母图、空间圣经、锚点/投影表、场景状态、多视图与光影状态 | 图片Prompt；明确登记后转登记；导演/分镜读取空间数据 |
| `world-asset-production` | 混合/类别不清时是否使用；下游生产Skill是否确认 | 资产身份拆分、唯一责任Skill、依赖与生产顺序；不产候选 | 对应分类资产Skill |
| `prop-vehicle-production` | 是否使用；对象工作模式与交付形态；候选是否明确登记 | 对象生产卡、部件/交互锚点、对象总览卡、图案文字校对、载具舱内接口与候选验收 | 图片Prompt；明确登记后转登记；人物/生物组合或场景空间读取接口 |
| `creature-monster-production` | 是否使用；生命体工作模式；父/附加版本；候选是否明确登记 | 生命体生产卡、形态定义、解剖锚点、运动约束集、单张总览卡、转化/VFX交接与候选验收 | 图片Prompt；明确登记后转登记；表演/调度/分镜读取运动切片 |
| `vfx-asset-production` | 是否需要独立资产；是否使用；候选是否明确登记 | VFX视觉母版定义、时序/环境接触卡与候选验收 | 图片/镜头Prompt；明确登记后转登记 |
| `image-prompt-production` | 是否使用 | GPT Image 2 Prompt与修订 | 外部生成；再回资产 Skill |

## 场戏与镜头创作类

| Skill | 用户确认点 | 核心输出 | 下游 |
|---|---|---|---|
| `acting-direction` | 是否使用；母档模式或场戏适配模式；母档版本是否确认生效 | 角色表演母档表/卡；场戏表演卡与下游短切片 | 母档先交剧作/导演；场戏卡交摄影、镜头、声音、Prompt |
| `dramaturgy-scene-beats` | 是否使用；是否加载剧作 Profile；表演母档版本 | 戏剧目标、信息、潜台词和节拍 | 导演、场戏表演适配 |
| `directing-blocking` | 是否使用；是否加载导演 Profile；表演母档版本 | 观众视点、人物调度和空间关系 | 场戏表演适配 |
| `shot-visual-design` | 是否使用；继承哪些摄影规则卡 | 带分镜组/镜头稳定ID与版本的分镜表；剪辑与摄影审核写回；校验报告 | 剪辑节奏、逐镜摄影审核、Prompt生产 |
| `editing-rhythm` | 是否使用；是否加载剪辑 Profile | 时长、切点、动作接点、生成单元修订 | 镜头设计写回后转逐镜摄影审核 |
| `sound-voice-direction` | 是否使用；身份建档/独立候选/场戏适配；缺失正式声音时选择补资产或临时声音 | 声音身份卡、独立音频候选卡、场戏声音卡 | 明确登记后转登记；场戏卡转就绪审计和Prompt生产 |
| `video-prompt-production` | 是否使用；分镜与摄影审核是否完成 | 带稳定ID/版本的Seedance正式Prompt；轻量状态检查点；按需同步包 | 外部人工生成；独立进度同步 |

## 独立资料与审查类

| Skill | 触发 | 输出 |
|---|---|---|
| `film-profile-library` | 对应专业阶段中用户明确选择 | 当前阶段方法卡；完整Profile不下传 |
| `video-qc-review` | 用户要求检查、查询或项目复盘 | 默认只分析；明确要求后写QC记录卡、表和校验报告 |

## 关键返工路由

| 问题 | 返回 Skill |
|---|---|
| 剧本出处或状态不清 | `script-truth-index` |
| 项目目录未绑定或跨项目数据混用 | `approval-asset-registry` 重建或复核绑定卡 |
| 项目重要创作控制卡版本、中央源/Profile引用或生效状态冲突 | 内容返回责任专业Skill；版本和状态交 `creative-control-versioning` |
| 缺少资产或父子版本错误 | `asset-demand-plan` / 对应资产生产 Skill |
| 人脸或人物身份错误 | `character-asset-production` + `image-prompt-production` |
| 场景构造或视图错误 | `location-spatial-production` + `image-prompt-production` |
| 道具、载具、图案文字本体错误 | `prop-vehicle-production` + `image-prompt-production` |
| 生物/怪物解剖、身份或运动约束错误 | `creature-monster-production` + `image-prompt-production` |
| VFX视觉身份、发光、接触或时序错误 | `vfx-asset-production`；静帧返回图片Prompt，镜头执行返回视频Prompt |
| 混合资产未拆分、责任不清或生产顺序冲突 | `world-asset-production` 重新路由；缺槽位时返回 `asset-demand-plan` |
| 缺少场景机位视图 | `location-spatial-production` 补做 SV3 |
| 戏剧目标或信息顺序错误 | `dramaturgy-scene-beats` |
| 人物走位或观众视点错误 | `directing-blocking` |
| 表演僵硬、夸张或缺少反应 | `acting-direction` |
| 角色声音身份漂移或缺少稳定边界 | `sound-voice-direction` 模式 A 建档或更新身份卡 |
| 发声角色缺少正式声音资产 | `sound-voice-direction` 模式 B 补做/上传候选，或由用户明确选择模式 C 的Seedance临时声音 |
| 声音可以但来自Seedance可用镜头，想跨镜复用 | 先提取独立音频文件，再经 `sound-voice-direction` 模式 B 核对并明确登记 |
| 重要角色没有当前有效表演母档，或下游临时编写人物性格 | `acting-direction` 先建立/更新母档，再重做场戏表演卡 |
| 构图、景别、机位或运镜平庸 | `shot-visual-design` |
| 视场/透视、物理距离、景深/焦点、曝光、支撑或运动物理实现冲突 | `cinematography-direction` 逐镜摄影审核；由 `shot-visual-design` 写回技术修正 |
| 运镜无法在既定时长或生成单元内完成 | `editing-rhythm` 修订；由 `shot-visual-design` 写回后重新做逐镜摄影审核 |
| 已定场戏需要突破全片摄影规则 | `cinematography-direction` 先说明冲突并请求用户确认限时场戏例外 |
| 时长、切点或动作衔接错误 | `editing-rhythm` |
| 设计正确但 Seedance 未执行 | `video-prompt-production` 精简或拆单元 |
| 需要系统诊断视频问题 | `video-qc-review` |

