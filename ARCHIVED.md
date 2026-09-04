# SKillXC 旧版 Skill 封存说明

封存日期：2026-09-05
状态：30 个旧版生产与控制 Skill 全部封存。

## 封存边界

- 旧源码、参考资料、模板、脚本和 Git 历史全部保留。
- 旧源码目录由 `skills/` 改名为 `archived-skills/`；30 个入口文件的文件名与正文保持不变，但整个目录不再被 Codex 自动发现。
- `.codex-plugin/plugin.json` 不再声明 `skills/`，旧仓库不再作为可安装生产插件发布。
- 本机全局 Junction 已移出 `.agents/skills` 自动发现目录并保持为失效占位；同时保留 `config.toml` 的显式停用条目，若旧目录以后被误恢复仍会继续阻断发现。
- GitHub 仓库完成最终封存提交后设置为 Archive，只读保存。

## 后继系统

新的影视生产工作统一使用：[小虫的影视生产流](https://github.com/sla20110526-alt/XiaoC-YingShiGongZuo)。

共享能力库中已经独立收存并标注准确版本的 Profile 与专业 Skill 由新系统按其冻结规范调用，不因本仓库封存而删除。

## 恢复限制

只有用户以后明确要求恢复旧版 SKillXC，并指定恢复范围时，才能解除 GitHub Archive、恢复默认发现目录、重建本机发现链接或重新发布插件。不得因兼容、排错或历史引用自行恢复。
