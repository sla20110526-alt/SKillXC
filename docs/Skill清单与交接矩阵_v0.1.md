# Skill 清单与交接矩阵 v0.1

## 使用原则

- 默认轻量生产：后台保留完整任务单、ID/版本、索引与校验，用户只看当前结果、必要缺口、一个确认点和下一步。切换对话用短交接包定位完整任务单，不在聊天中展开整张任务卡。
- 项目绑定、正式登记、控制版本、进度/失败记录、正式审计、正式 QC 与复盘为严格记录模式；只有用户明确要求后才进入相应专用数据对话。
- 控制类 Skill 管理事实、版本、计划、批准和就绪，不代替创作判断。
- 创作类 Skill 生产方案和候选，不宣布资产已登记。
- 进入任何通用创作 Skill 前先说明用途并询问用户是否确认使用。
- 只在 Profile 阶段合同允许的责任 Skill 中询问调取谁。导演在项目风格意图和场戏调度分别询问；美术、编剧/剧作、剪辑各在本部门阶段询问。摄影只在建立或重建全片摄影基线时常规询问一次；后续继承摄影规则卡，只有用户确认的限时场戏例外可重新调取。
- 分镜表只有 `shot-visual-design` 可以写入；摄影指导的逐镜意见经审核卡返回，由镜头视觉设计写回。
- 场戏剧作先形成逐节拍权威数据 `BDT@版本`，再形成引用它的场戏节拍卡 `DSB@版本`；只向导演调度和场戏表演适配下传戏剧切片，不预设镜头、摄影或剪辑决定。
- 场戏导演先形成逐调度单元数据 `DBD@版本`，再形成引用它的调度卡 `DBC@版本`；人物移动必须有触发、目的、路径和结束，轴线/越轴必须可重建空间，缺失正式空间依据时回传 SV3 视图缺口。
- Prompt 放行与生成结果可用分开记录；生产对话只回显轻量检查点，独立记录对话按用户明确授权同步项目进度。
- 下游只读取当前任务需要的最小数据切片。
- 中央源定义、Profile 与项目重要创作控制卡使用相互独立的版本；中央源或 Profile 升级不自动改写既有项目卡，也不静默替换项目固定引用。
- 项目数据使用人读 Markdown 卡、CSV 多行记录和 JSON Schema 检查；任务索引只追踪任务调度，单次创作短卡由任务成果索引追踪，不重复制造专用 CSV。
- 每次结构化数据交接附校验报告；结构通过不替代用户批准、正式登记和业务复核。

## 生产控制类

| Skill | 主要输入 | 核心输出 | 下游 |
|---|---|---|---|
| `project-category-lock` | 剧本、参考、用户问答 | 项目锁定卡、项目锁定索引、校验报告 | 剧本事实索引 |
| `script-truth-index` | 项目锁定卡、锁定剧本 | 事实索引卡、场次/事实索引、校验报告 | 资产拆解、场戏分析 |
| `asset-demand-plan` | 候选资产、预留正式资产ID、剧本事实 | 批次计划、需求/依赖表、校验报告 | 路由交接 |
| `production-router-handoff` | 当前阶段、项目绑定、任务和缺口 | 面向用户的轻量回显/短交接包；后台完整任务单、任务索引、任务成果索引和校验依据 | 对应创作 Skill或严格记录对话 |
| `approval-asset-registry` | 项目绑定；用户明确登记指令；唯一候选 | 绑定卡/索引、登记回执、正式/可调用表、校验报告 | 就绪审计、分镜 |
| `creative-control-versioning` | 专业Skill产生的项目控制卡草案；中央源/Profile精确引用；用户确认原文 | 项目基线/表演母档/声音身份的版本与生效事务、备份和校验 | 专业生产、就绪审计；不生产创作内容 |
| `generation-version-log` | 用户明确同步或详细记录要求 | 镜头生产进度表；按需生成/失败详表；校验报告 | 项目进度、复盘；不进入资产登记 |
| `continuity-readiness-audit` | 正式登记与调用表、剧本状态 | 默认只回显结论/阻断缺口；明确正式审计时写审计卡、场次/生成单元表和校验报告 | 分镜、Prompt或返回补资产 |

## 资产与风格生产类

| Skill | 用户确认点 | 核心输出 | 下游 |
|---|---|---|---|
| `script-asset-breakdown` | 是否使用通用拆解 Skill | 拆解卡、候选/缺口表、预留正式资产ID、校验报告 | 资产需求计划 |
| `style-lock-director` | 四种工作模式；相应专业Skill；对应阶段是否加载Profile | 项目风格意图基线、唯一直接上游四卡状态、P0审查记录、风格包组合快照与三个资产短切片 | 专业基线Skill；任务成果索引；分类资产与图片Prompt |
| `art-lookdev-direction` | 是否使用；长期基线时是否加载美术 Profile；长期基线/资产类别交接/场次状态/兼容复核模式 | 可追溯美术长期基线；建筑陈设、服装妆造、道具、材料工艺、老化污迹、固有色与母题规则；美术执行交接包和GPT Image 2短切片 | 风格总控组装P0/风格包；摄影基线；分类资产生产 |
| `cinematography-direction` | 是否使用；全片基线时是否加载摄影 Profile | 全片摄影规则卡；场戏摄影约束卡；逐镜摄影审核卡 | 镜头设计；摄影审核写回 |
| `lighting-direction` | 是否使用；项目基线/场景光源地图/人物受光/多视图继承/镜头短执行模式 | 项目灯光长期基线；场景光源地图；人物受光、多视图继承和镜头灯光短执行卡 | 风格总控、场景资产、图片/视频Prompt；不改摄影机、空间或VFX本体 |
| `specialist-consultant-router` | 是否使用；专业点等级；唯一主领域；危险内容边界 | 带稳定版本的顾问问题包、逐主张证据集、结论卡及“可靠可采用/有条件采用/暂不可裁决”状态 | 美术、资产、调度、镜头按 `CCR@版本 + 主张ID/采用字段` 精确引用 |
| `character-asset-production` | 是否使用；当前人物工作模式；每次候选是否明确登记 | 脸母图、单张五视图卡、服装/状态/交互继承卡、Prompt输入与候选验收 | 图片Prompt；明确登记后转登记 |
| `location-spatial-production` | 是否使用；场景工作模式；母图构图子模式；每张候选是否明确登记 | 母图、空间圣经、锚点/投影表、场景状态、多视图与光影状态 | 图片Prompt；明确登记后转登记；导演/分镜读取空间数据 |
| `world-asset-production` | 混合/类别不清时是否使用；下游生产Skill是否确认 | 资产身份拆分、唯一责任Skill、依赖与生产顺序；不产候选 | 对应分类资产Skill |
| `prop-vehicle-production` | 是否使用；对象工作模式与交付形态；候选是否明确登记 | 对象生产卡、部件/交互锚点、对象总览卡、图案文字校对、载具舱内接口与候选验收 | 图片Prompt；明确登记后转登记；人物/生物组合或场景空间读取接口 |
| `creature-monster-production` | 是否使用；生命体工作模式；父/附加版本；候选是否明确登记 | 生命体生产卡、形态定义、解剖锚点、运动约束集、单张总览卡、转化/VFX交接与候选验收 | 图片Prompt；明确登记后转登记；表演/调度/分镜读取运动切片 |
| `vfx-asset-production` | 独立资产判定；工作模式；正式父/来源/接触版本；候选是否明确登记 | VFX生产卡、定义、时序/接触表、视觉母版/状态变体/接触参考或单镜执行条款、候选验收与登记回执绑定 | 图片Prompt或分镜/镜头Prompt；明确登记后转登记 |
| `image-prompt-production` | 是否使用；新生成/参考编辑；图片Prompt ID/版本 | 带稳定ID/版本的GPT Image 2完整Prompt、参考映射、轻量检查点与返工分流 | 外部人工生成或按明确任务调用图片能力；结果回唯一责任资产Skill复核 |

## 场戏与镜头创作类

| Skill | 用户确认点 | 核心输出 | 下游 |
|---|---|---|---|
| `acting-direction` | 是否使用；母档模式或场戏适配模式；母档版本是否确认生效 | 角色表演母档表/卡；场戏表演卡与下游短切片 | 母档先交剧作/导演；场戏卡交摄影、镜头、声音、Prompt |
| `dramaturgy-scene-beats` | 是否使用；场戏节拍建立/换版兼容复核；是否加载剧作 Profile；剧本版本/原文定位；表演母档版本 | 带稳定版本的逐节拍数据与场戏节拍卡；锁定台词/顺序/因果保护；导演/表演最小切片 | 仅导演调度、场戏表演适配 |
| `directing-blocking` | 是否使用；调度建立/重设计或换版复核；本阶段是否加载导演 Profile；节拍/母档/空间版本 | `DBD`逐调度单元数据与`DBC`场戏调度卡；观众知情、位置、距离、朝向、视线、遮挡、出入场、移动触发、权力、轴线及SV3缺口 | 场戏表演适配；场戏摄影约束；逐镜设计 |
| `shot-visual-design` | 是否使用；继承哪些摄影规则卡 | 带分镜组/镜头稳定ID与版本的分镜表；剪辑与摄影审核写回；校验报告 | 剪辑节奏、逐镜摄影审核、Prompt生产 |
| `editing-rhythm` | 是否使用；节奏审查/重设计或换版复核；是否加载剪辑 Profile；分镜/调度/表演/摄影约束版本 | `ERT`逐镜关系数据与`ERC`节奏卡；顺序、时长、切点、动作/声音接点、相邻状态和生成单元替代提案 | `shot-visual-design`唯一写回新分镜快照后转逐镜摄影审核 |
| `sound-voice-direction` | 是否使用；身份建档/独立候选/场戏适配；缺失正式声音时选择补资产或临时声音 | 声音身份卡、独立音频候选卡、场戏声音卡 | 明确登记后转登记；场戏卡转就绪审计和Prompt生产 |
| `video-prompt-production` | 是否使用；分镜与摄影审核是否完成 | 带稳定ID/版本的Seedance正式Prompt；轻量状态检查点；按需同步包 | 外部人工生成；独立进度同步 |

## 独立资料与审查类

| Skill | 触发 | 输出 |
|---|---|---|
| `film-profile-library` | 阶段合同允许且用户本次明确选择 | 当前阶段方法短卡；阶段交付后关闭本体，只下传已转译项目规则切片 |
| `video-qc-review` | 用户要求检查、查询或项目复盘 | 默认只分析；明确要求后写QC记录卡、表和校验报告 |

## 关键返工路由

| 问题 | 返回 Skill |
|---|---|
| 剧本出处或状态不清 | `script-truth-index` |
| 专业事实缺口、来源冲突或顾问结论超出适用范围 | `specialist-consultant-router`；无可靠来源时保持“暂不可裁决”，危险内容只保留非操作性后果与安全边界 |
| 项目目录未绑定或跨项目数据混用 | `approval-asset-registry` 重建或复核绑定卡 |
| 项目重要创作控制卡版本、中央源/Profile引用或生效状态冲突 | 内容返回责任专业Skill；版本和状态交 `creative-control-versioning` |
| 风格四卡直接上游链未闭合、P0测试未通过或旧风格包引用已替代来源 | `style-lock-director` 返回唯一责任专业层；受影响的当前评审和旧快照标记待复核，修复后建立下一评审/快照版本 |
| 缺少资产或父子版本错误 | `asset-demand-plan` / 对应资产生产 Skill |
| 人脸或人物身份错误 | `character-asset-production` + `image-prompt-production` |
| 场景构造或视图错误 | `location-spatial-production` + `image-prompt-production` |
| 光源角色、人物受光、阴影、反射、曝光灯光实现或换角度灯光继承错误 | `lighting-direction`；空间锚点错误返回 `location-spatial-production`，相机侧曝光目标错误返回 `cinematography-direction` |
| 道具、载具、图案文字本体错误 | `prop-vehicle-production` + `image-prompt-production` |
| 生物/怪物解剖、身份或运动约束错误 | `creature-monster-production` + `image-prompt-production` |
| VFX视觉身份、来源/路径、阶段、发光、接触或残留错误 | 图片资产定义/候选返回 `vfx-asset-production` + `image-prompt-production`；逐镜Prompt漏译返回 `video-prompt-production`；场景受光规则错误返回 `lighting-direction` |
| 混合资产未拆分、责任不清或生产顺序冲突 | `world-asset-production` 重新路由；缺槽位时返回 `asset-demand-plan` |
| 缺少场景机位视图 | `location-spatial-production` 补做 SV3 |
| 戏剧目标、节拍触发、潜台词或信息/权力变化错误；锁定台词、顺序或因果被改 | `dramaturgy-scene-beats`；若确需改剧本，先由 `script-truth-index` 建立新内容版本 |
| 人物走位或观众视点错误 | `directing-blocking` |
| 表演僵硬、夸张或缺少反应 | `acting-direction` |
| 角色声音身份漂移或缺少稳定边界 | `sound-voice-direction` 模式 A 建档或更新身份卡 |
| 发声角色缺少正式声音资产 | `sound-voice-direction` 模式 B 补做/上传候选，或由用户明确选择模式 C 的Seedance临时声音 |
| 声音可以但来自Seedance可用镜头，想跨镜复用 | 先提取独立音频文件，再经 `sound-voice-direction` 模式 B 核对并明确登记 |
| 重要角色没有当前有效表演母档，或下游临时编写人物性格 | `acting-direction` 先建立/更新母档，再重做场戏表演卡 |
| 人物走位没有戏剧触发、权力关系没有落到空间、轴线/出入方向混乱 | `directing-blocking` 模式 A 重设计；先建立下一 `DBD/DBC` 版本，再重做场戏表演适配 |
| 调度成立但现有场景图看不到必要通道、遮挡或锚点 | `directing-blocking` 提出 SV3 缺口 → `asset-demand-plan` → `location-spatial-production` |
| 构图、景别、机位或运镜平庸 | `shot-visual-design` |
| 视场/透视、物理距离、景深/焦点、曝光、支撑或运动物理实现冲突 | `cinematography-direction` 逐镜摄影审核；由 `shot-visual-design` 写回技术修正 |
| 运镜无法在既定时长或生成单元内完成 | `editing-rhythm` 修订；由 `shot-visual-design` 写回后重新做逐镜摄影审核 |
| 已定场戏需要突破全片摄影规则 | `cinematography-direction` 先说明冲突并请求用户确认限时场戏例外 |
| 时长、切点或动作衔接错误 | `editing-rhythm` |
| 设计正确但 Seedance 未执行 | `video-prompt-production` 精简或拆单元 |
| 需要系统诊断视频问题 | `video-qc-review` |

