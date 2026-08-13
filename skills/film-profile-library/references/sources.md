# Profile 来源索引

来源索引只说明一项资料能支持什么，不能支持什么。通用机构首页是检索入口，不等于某张 Profile 的方法证据；没有逐条引用的方法一律按“分析性归纳”处理。

## 已登记来源

### SRC-USER-001

- 类型：用户提供。
- 内容：用户在本工作流讨论中指定的导演、摄影指导、Production Design、编剧／剧作与剪辑候选及代表作品清单；其中两项只给出作品未写主体姓名，另有一项剪辑条目重复且作品关系需后续核对。
- 可支持：Profile 候选范围、用户希望优先建设的部门与大部分主体/代表作清单。
- 不可支持：创作者本人意图、具体方法归因、作品场景观察、AI 模型适配结论。
- 定位：当前仓库所关联的生产系统设计对话；后续迁移时应补项目外可保存的来源副本或摘要。

### SRC-DRAFT-001

- 类型：系统工作初稿。
- 内容：本资料库 v1.0 迁移前的 27 张初版 Profile 卡；包含对缺失主体的工作性补全、作品关系整理和方法分析性归纳。
- 可支持：追溯当前初版方法、主体补全与代表作品写法从何而来。
- 不可支持：任何外部事实核验、创作者本人意图、具体作品场景证据或“已核验”成熟度。
- 定位：仓库版本历史中 v1.0 结构迁移之前的 `skills/film-profile-library/references/`。

## 资料发现入口（尚未作为卡片证据）

### SRC-DISCOVERY-DIRECTING-001

- 类型：行业机构检索入口。
- 入口：[BAFTA Film / Directing](https://www.bafta.org/awards/film/director/)、[BFI Sight and Sound](https://www.bfi.org.uk/sight-and-sound/directors-100-greatest-films-all-time)。
- 用途：查找导演、作品和后续访谈线索；引用具体页面后才能建立新的来源 ID。

### SRC-DISCOVERY-CINEMATOGRAPHY-001

- 类型：专业协会检索入口。
- 入口：[American Society of Cinematographers](https://theasc.com/)。
- 用途：查找摄影指导访谈和制作资料；协会首页本身不支持具体方法归因。

### SRC-DISCOVERY-PRODUCTION-DESIGN-001

- 类型：专业协会检索入口。
- 入口：[Art Directors Guild](https://adg.org/)。
- 用途：查找 Production Design 人员、作品与制作资料。

### SRC-DISCOVERY-WRITING-001

- 类型：工会检索入口。
- 入口：[Writers Guild of America](https://www.wga.org/writers-room/101-best-lists)。
- 用途：查找编剧、剧本与访谈线索。

### SRC-DISCOVERY-EDITING-001

- 类型：行业机构检索入口。
- 入口：[American Cinema Editors](https://americancinemaeditors.org/)、[Academy Awards Database](https://awardsdatabase.oscars.org/search/)。
- 用途：查找剪辑人员、作品、访谈和奖项资料。

## 新来源登记规则

1. 每个具体访谈、讲座、制作特辑、文章或作品观察建立独立 `SRC-...` ID；不得只保存搜索结果页。
2. 保存标题、主体、发布者、日期、链接或本地定位、访问日期、可支持主张和不可支持范围。
3. 引文与转述分开；无法确认原文时只写转述，不制造引语。
4. 作品观察必须写作品、场景和可定位时间点；观察到的结果不自动等于创作者意图。
5. AI 适配和失败样本属于项目验证来源，必须有用户明确记录，不从普通反馈自动推断。
