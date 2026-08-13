# SKillXC 仓库规则

## 仓库定位

- 本仓库是 AI 影视生产 Skill 的中央源仓库，不是具体影视项目，也不是项目数据目录。
- `skills/` 是 30 个生产 Skill 的唯一内容源；安装位置只允许链接到这里，不得维护副本。
- `.codex-plugin/plugin.json` 是整套 Skill 的插件清单。
- 具体项目的数据、资产登记表、脚本事实索引和生成记录不得写入本仓库。

## 调用规则

- 生产任务先进入 `production-router-handoff`，由它判断当前阶段和最小调用集合。
- 混合或类别不清的世界资产需求由 `world-asset-production` 二级路由拆分；它不生产候选。道具/载具、生物/怪物、VFX 分别由 `prop-vehicle-production`、`creature-monster-production`、`vfx-asset-production` 唯一负责。
- 除总路由入口外，专业 Skill 和通用 Skill 必须在向用户说明用途并获得确认后显式调用。
- 每次只加载当前阶段真正需要的 Skill；不得一次加载全部 Skill 或全部大师 Profile。
- 大师 Profile 只在用户明确选择后调取，并且只在指定阶段和作用域内生效。摄影 Profile 只在建立/重建全片摄影基线时常规询问；后续继承摄影规则卡，除非用户明确确认限时场戏例外。
- `shot-visual-design` 是分镜表唯一写入者；`cinematography-direction` 先建立全片/场戏摄影规则，后做逐镜摄影审核，不直接改分镜表或重新决定叙事功能。
- `acting-direction` 是角色表演母档和场戏表演卡的唯一写入者；重要角色在剧作/导演场戏工作前按项目建立一份当前有效母档，逐场只做适配，不把母档当作人物或声音资产。
- `sound-voice-direction` 是角色声音身份卡、独立声音候选卡和场戏声音卡的唯一写入者。只有台词、独白或持续画外发声角色才按需建立独立声音资产；身份卡不是资产，环境/动作声与Seedance临时镜头内声音默认不登记。发声角色缺少正式声音资产时必须询问用户选择补做候选或临时声音，不得自行决定。
- 中央源定义、Profile卡版本和项目控制卡版本必须分离。专业Skill写控制内容，`creative-control-versioning` 唯一写项目长期创作基线、表演母档与声音身份索引的版本和状态；中央源/Profile升级不得自动改写既有项目卡。
- 分镜组、镜头和正式 Prompt 使用稳定 ID 与独立版本；Prompt“已放行生成”和生成结果“可用”不得合并为一个“通过”。生产对话只维护轻量检查点，明确同步后由 `generation-version-log` 专用记录对话写项目进度表。
- 没有具体项目或项目数据目录时，只维护工作流，不创建虚构项目数据。
- 具体项目必须先由 `approval-asset-registry` 确认项目 ID、项目数据根目录和绑定卡；所有项目数据读写必须解析到绑定目录内，禁止跨项目串表。
- 项目数据默认遵循 `skills/production-router-handoff/references/project-data-contract.md`：人读卡、CSV 行数据、JSON Schema 检查三层分工；结构检查不得替代批准和业务复核。

## 维护边界

- 用户要求按优先级一次修复一项时，只修改当前确认项；完成逐文件检查后停止，等待下一次确认。
- 修改 Skill 前遵循 Codex 的 `skill-creator` 规范；修改插件结构前遵循 `plugin-creator` 规范。
- 修改源文件后必须检查 UTF-8、YAML/JSON 语法、内部链接、目录结构和调用边界。
- 修改数据模板或 Schema 后必须更新 `skills/production-router-handoff/assets/data-contract-map.json`，并运行 `validate_project_data.py --manifest`；不得只增加 Schema 而不执行检查。
- `ARCHIVE_EXPLICIT_ONLY`：历史讨论、聊天转录和接续记录不属于本仓库、插件或任何 Skill 的引用图。未收到用户在当前指令中明确提供的归档路径和“读取／核对／比较历史”要求时，禁止从外部目录、Git 历史、旧提交、远端旧版本或缓存中搜索、读取或引用这些内容。
- 新任务的现行入口及其加载策略以 `active-rule-sources.json` 为准；列入清单不代表一次加载全部内容，Skill 正文仍须遵守“元数据发现后、用户确认再激活”的抽屉式边界。当前规则以用户最新明确指令、正式 Skill 和现行流程文件为准。
- 提交前运行 `python deployment/validate_active_rule_boundary.py`；不得把历史正文、历史文件链接或通向外部归档的目录链接重新放入现行仓库。

## 安装拓扑

- 用户级 `.agents` 的持久化根目录位于 `D:\Ai影视制作\2026项目\006-skills`；Windows 用户目录使用指向它的根入口链接，或在应用占用根目录时使用分别指向 D 盘的 `skills`、`plugins` 子入口链接。
- 30 个 SKillXC Skill 使用持久化根目录中的目录链接，目标必须指向本仓库 `skills/` 下的对应 Skill。
- 个人插件市场中的 `skillxc` 入口指向本仓库根目录；不得复制整个仓库形成第二份内容源。
- 重装恢复工具的仓库源位于 `deployment/windows/`，D 盘运行副本位于持久化根目录的 `recovery/`。
- 直接链接安装和插件安装不得同时启用，以免同名 Skill 重复发现。
- 更新 Skill 时编辑中央源仓库，再运行验证；不要在安装链接位置建立独立版本。
