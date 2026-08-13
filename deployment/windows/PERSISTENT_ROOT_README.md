# Codex 用户级 Skill 持久化目录

本目录保存重装 Windows 后仍需保留的 Codex 用户级 Skill、个人插件清单和恢复工具。C 盘只保留指向本目录的 `.agents` 入口链接。

在 Codex 正在运行、无法替换 `.agents` 根目录时，允许保留 `.agents` 空壳，并让其中的 `skills` 与 `plugins` 分别链接到本目录；恢复脚本会识别两种等效结构。

## 目录职责

- `skills/`：30 个 SKillXC Skill 的中央仓库链接，以及两个小云雀本地 Skill 的实体文件。
- `plugins/marketplace.json`：个人插件市场清单。
- `plugins/plugins/skillxc`：指向 SKillXC 中央仓库的插件入口。
- `plugins/plugins/cowart`：Cowart 的持久化插件源，供系统重装后重新安装。
- `recovery/`：恢复脚本、安装清单与恢复说明。

不要在 `skills/` 中复制或直接改写 SKillXC 的 30 个 Skill。应修改中央 Git 仓库，再由链接自动生效。

## 重装 Windows 后

1. 确保保存本目录的磁盘仍连接到电脑。
2. 安装并登录 Codex，安装 Python 3，并至少启动一次 Codex。
3. 双击 `recovery/Restore-CodexUserAssets.cmd`；如需从 PowerShell 启动，使用 `powershell.exe -NoProfile -ExecutionPolicy Bypass -File "recovery/Restore-CodexUserAssets.ps1"`。
4. 脚本会核验中央仓库、30 个目录链接、两个小云雀 Skill、Cowart、个人插件市场、同名插件未安装状态，以及 Codex 实际发现的 30 项运行时目录；看到 `Recovery validation passed.` 后退出并重新启动 Codex。
5. 在重启后的新对话发送“请使用生产路由与交接，告诉我当前任务应进入哪个阶段；未经我确认不要调用其他 SKillXC Skill。”总路由应被发现并先询问确认，其他 29 个专业/通用 Skill 不应自动展开。
6. 在个人插件市场重新安装 Cowart；SKillXC 已通过用户级 Skill 链接生效，`skillxc@personal` 必须继续显示为 `not installed`。

恢复脚本自动识别当前 Windows 用户名。若新系统已经存在包含文件或链接的 `%USERPROFILE%\.agents` 实体目录，脚本会停止，不会覆盖其中内容；仅含空目录时可以安全接管。

## 边界

- 格式化 C 盘不会删除本目录。
- 运行时目录检查需要 Python 3；恢复脚本会在缺少 Python 或 Codex 命令时停止并说明原因，不会把“磁盘文件存在”误报成“Codex 已加载”。
- 本目录无法防护保存它的磁盘自身损坏；SKillXC 另有 GitHub 远端备份。
- 两个小云雀 Skill 和 Cowart 的当前本地副本依赖本目录保存，应另行备份整个目录以防磁盘损坏。
