"""Validate that the legacy SKillXC repository is sealed and non-discoverable."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_COUNT = 30


def main() -> int:
    errors: list[str] = []
    archived_root = ROOT / "archived-skills"

    if (ROOT / "skills").exists():
        errors.append("默认发现目录 skills/ 仍然存在")
    if not archived_root.is_dir():
        errors.append("封存源码目录 archived-skills/ 不存在")

    all_skill_files = list(ROOT.rglob("SKILL.md"))
    archived_entries = list(archived_root.rglob("SKILL.md")) if archived_root.exists() else []
    exposed_entries = [path for path in all_skill_files if archived_root not in path.parents]
    if exposed_entries:
        errors.append(f"封存目录外仍存在 {len(exposed_entries)} 个 SKILL.md")
    if len(archived_entries) != EXPECTED_COUNT:
        errors.append(f"封存入口应为 {EXPECTED_COUNT} 个，实际 {len(archived_entries)} 个")

    plugin_path = ROOT / ".codex-plugin" / "plugin.json"
    try:
        plugin = json.loads(plugin_path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - diagnostic path
        plugin = {}
        errors.append(f"插件清单不可读：{exc}")
    if "skills" in plugin:
        errors.append("插件清单仍声明 skills 分发入口")

    rules_path = ROOT / "active-rule-sources.json"
    try:
        rules = json.loads(rules_path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - diagnostic path
        rules = {}
        errors.append(f"封存规则清单不可读：{exc}")
    if rules.get("archive_status") != "sealed":
        errors.append("封存规则清单未标记 sealed")
    for item in rules.get("authority_order", []):
        if item.get("path") in {"archived-skills", ".codex-plugin/plugin.json"} and item.get("load_policy") != "disabled-archive-only":
            errors.append(f"{item.get('path')} 未设置 disabled-archive-only")

    result = {
        "archive_status": "sealed" if not errors else "invalid",
        "discoverable_skill_files": len(exposed_entries),
        "archived_skill_files": len(archived_entries),
        "plugin_exports_skills": "skills" in plugin,
        "errors": errors,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
