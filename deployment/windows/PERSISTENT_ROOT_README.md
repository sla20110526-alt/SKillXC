# Codex 用户级 Skill 持久化目录

本目录保存重装 Windows 后仍需保留的 Codex 用户级 Skill、个人插件清单和恢复工具。C 盘只保留指向本目录的 `.agents` 入口链接。

在 Codex 正在运行、无法替换 `.agents` 根目录时，允许保留 `.agents` 空壳，并让其中的 `skills` 与 `plugins` 分别链接到本目录；恢复脚本会识别两种等效结构。

## 目录职责

- `skills/`：26 个 SKillXC Skill 的中央仓库链接，以及两个小云雀本地 Skill 的实体文件。
- `plugins/marketplace.json`：个人插件市场清单。
- `plugins/plugins/skillxc`：指向 SKillXC 中央仓库的插件入口。
- `plugins/plugins/cowart`：Cowart 的持久化插件源，供系统重装后重新安装。
- `recovery/`：恢复脚本、安装清单与恢复说明。

不要在 `skills/` 中复制或直接改写 SKillXC 的 26 个 Skill。应修改中央 Git 仓库，再由链接自动生效。

## 重装 Windows 后

1. 确保保存本目录的磁盘仍连接到电脑。
2. 安装并登录 Codex。
3. 双击 `recovery/Restore-CodexUserAssets.cmd`；如需从 PowerShell 启动，使用 `powershell.exe -NoProfile -ExecutionPolicy Bypass -File "recovery/Restore-CodexUserAssets.ps1"`。
4. 脚本会逐文件核验两个小云雀 Skill 和 Cowart；看到 `Recovery validation passed.` 后重启 Codex。
5. 在个人插件市场重新安装 Cowart；SKillXC 已通过用户级 Skill 链接生效，不要再同时安装同名插件。

恢复脚本自动识别当前 Windows 用户名。若新系统已经存在包含文件或链接的 `%USERPROFILE%\.agents` 实体目录，脚本会停止，不会覆盖其中内容；仅含空目录时可以安全接管。

## 边界

- 格式化 C 盘不会删除本目录。
- 本目录无法防护保存它的磁盘自身损坏；SKillXC 另有 GitHub 远端备份。
- 两个小云雀 Skill 和 Cowart 的当前本地副本依赖本目录保存，应另行备份整个目录以防磁盘损坏。
