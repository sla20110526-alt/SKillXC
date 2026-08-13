# Codex 用户级 Skill 重装恢复

## 目标结构

```text
%USERPROFILE%\.agents
        ↓ Windows 目录链接
D:\Ai影视制作\2026项目\006-skills
├─ skills
├─ plugins
├─ recovery
└─ README.md
```

Codex 仍从标准用户入口 `%USERPROFILE%\.agents\skills` 发现 Skill，实际持久化内容位于 D 盘。Windows 用户名改变时，只需重新运行恢复脚本。

若迁移时 Codex 正在运行并占用 `.agents` 根目录，可以采用等效结构：保留 `.agents` 空壳，把其中的 `skills` 与 `plugins` 分别链接到 D 盘。恢复脚本同时支持两种布局。

## 内容来源

- 27 个 AI 影视生产 Skill：通过目录链接读取 SKillXC 中央仓库。
- 两个小云雀 Skill：D 盘实体副本。
- `skillxc` 插件：通过目录链接读取中央仓库。
- Cowart 插件：D 盘实体副本；重装系统后需要从个人插件市场重新安装。
- Codex 自带系统 Skill：由 Codex 安装程序恢复，不进入备份。

## 恢复

最简单的方式是双击：

```text
D:\Ai影视制作\2026项目\006-skills\recovery\Restore-CodexUserAssets.cmd
```

也可以在 PowerShell 中显式绕过本机脚本执行策略运行：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "D:\Ai影视制作\2026项目\006-skills\recovery\Restore-CodexUserAssets.ps1"
```

只检查、不修改：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "D:\Ai影视制作\2026项目\006-skills\recovery\Restore-CodexUserAssets.ps1" -ValidateOnly
```

脚本会逐文件核验持久化的两个小云雀 Skill 和 Cowart。它只会自动接管不存在或仅含空目录的 `%USERPROFILE%\.agents`；已经正确采用两个子目录链接时直接通过；遇到包含其他文件的实体目录或指向其他位置的链接时会停止。

## 灾难边界

- 仅格式化 C 盘：运行恢复脚本即可。
- D 盘盘符改变：脚本从自身位置推导持久化根目录，并按相对路径重建中央 Skill 链接。
- D 盘中 SKillXC 仓库缺失：从 `https://github.com/sla20110526-alt/SKillXC.git` 恢复到安装清单约定的相对位置，再运行脚本。
- 整个 D 盘损坏：GitHub 只能恢复 SKillXC；小云雀 Skill 与 Cowart 还需要独立磁盘备份。
