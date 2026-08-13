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

- 30 个 AI 影视生产 Skill：通过目录链接读取 SKillXC 中央仓库。
- 两个小云雀 Skill：D 盘实体副本。
- `skillxc` 插件：通过目录链接读取中央仓库。
- Cowart 插件：D 盘实体副本；重装系统后需要从个人插件市场重新安装。
- Codex 自带系统 Skill：由 Codex 安装程序恢复，不进入备份。

开发态只启用“30 个用户级 Skill 目录链接”。个人插件市场保留 `skillxc` 入口是为了以后发布和查看清单，但该插件必须保持未安装；若同时安装，会形成同名 Skill 的第二个发现来源。

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

脚本会核验：

- SKillXC 中央仓库是唯一内容源，中央目录名称与安装清单中的 30 项完全一致；
- D 盘 30 个用户级入口全部是指向中央源的目录链接，没有多出的复制目录；
- 两个小云雀 Skill 与 Cowart 持久化副本的逐文件完整性；
- `skillxc` 个人市场入口存在且状态为 `AVAILABLE`，但 `skillxc@personal` 没有安装、没有插件缓存；
- Codex、Python 3 和插件查询命令可运行；Codex 后端实际发现 30/30 个 SKillXC Skill，路径全部指向中央源且没有重名；
- 新对话初始提示中只公开总路由 `production-router-handoff`，其余 29 项保持显式调用。

它只会自动接管不存在或仅含空目录的 `%USERPROFILE%\.agents`；已经正确采用两个子目录链接时直接通过；遇到包含其他文件的实体目录或指向其他位置的链接时会停止。验证过程不会安装 `skillxc` 插件，也不会建立第二份中央源。

当前恢复包需要以下 6 个文件一起保存，缺一即停止：`Restore-CodexUserAssets.cmd`、`Restore-CodexUserAssets.ps1`、`Test-CodexSkillRuntime.ps1`、`validate_codex_runtime.py`、`install-manifest.json` 与 `README.md`。

## 重启后的新对话验收

恢复脚本中的运行时检查使用 Codex 后端强制重新扫描，能证明 30 项目录已经被实际发现；它不能代替桌面应用重启后的交互验收。完成恢复后：

1. 完全退出并重新启动 Codex。
2. 新建一个对话，发送：`请使用生产路由与交接，告诉我当前任务应进入哪个阶段；未经我确认不要调用其他 SKillXC Skill。`
3. 通过标准：Codex 能读取总路由，先核对项目绑定/当前阶段并征求确认；没有自动读取其余专业 Skill。
4. 若失败，先在 PowerShell 运行 `recovery\Test-CodexSkillRuntime.ps1`，把完整输出带回排查；不要改成安装 `skillxc@personal` 规避问题。

## 灾难边界

- 仅格式化 C 盘：运行恢复脚本即可。
- D 盘盘符改变：脚本从自身位置推导持久化根目录，并按相对路径重建中央 Skill 链接。
- D 盘中 SKillXC 仓库缺失：从 `https://github.com/sla20110526-alt/SKillXC.git` 恢复到安装清单约定的相对位置，再运行脚本。
- Python 3 缺失：先安装 Python 3 再运行恢复验证；这只是运行时验收工具的依赖，不会改变 Skill 内容源。
- 整个 D 盘损坏：GitHub 只能恢复 SKillXC；小云雀 Skill 与 Cowart 还需要独立磁盘备份。
