#!/usr/bin/env python3
"""Validate the single-source SKillXC installation and invocation contract."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


IMPLICIT_PATTERN = re.compile(
    r"(?m)^\s*allow_implicit_invocation:\s*(true|false)\s*$", re.IGNORECASE
)


def _configure_utf8_stdio() -> None:
    """Keep CLI diagnostics machine-readable on Windows without env overrides."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="replace")


def _read_json(path: Path, errors: list[str]) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        errors.append(f"JSON读取失败：{path}：{exc}")
        return {}
    if not isinstance(data, dict):
        errors.append(f"JSON根节点必须是对象：{path}")
        return {}
    return data


def validate(root: Path) -> list[str]:
    root = root.resolve()
    errors: list[str] = []
    manifest = _read_json(root / "deployment/windows/install-manifest.json", errors)
    activation = manifest.get("skillxc_activation")
    if not isinstance(activation, dict):
        errors.append("安装清单缺少skillxc_activation对象")
        return errors

    if activation.get("mode") != "direct-skill-links":
        errors.append("开发态激活模式必须是direct-skill-links")
    if activation.get("plugin_id") != "skillxc@personal":
        errors.append("插件保护对象必须是skillxc@personal")
    if activation.get("plugin_must_be_installed") is not False:
        errors.append("直接Skill链接生效时skillxc插件必须保持未安装")

    expected = activation.get("central_skill_names")
    implicit = activation.get("implicit_skill_names")
    explicit = activation.get("explicit_only_skill_names")
    for label, value in (
        ("central_skill_names", expected),
        ("implicit_skill_names", implicit),
        ("explicit_only_skill_names", explicit),
    ):
        if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
            errors.append(f"{label}必须是非空字符串数组")

    if errors:
        return errors

    expected_set = set(expected)
    implicit_set = set(implicit)
    explicit_set = set(explicit)
    for label, values in (
        ("central_skill_names", expected),
        ("implicit_skill_names", implicit),
        ("explicit_only_skill_names", explicit),
    ):
        if len(values) != len(set(values)):
            errors.append(f"{label}存在重复名称")
    if int(manifest.get("central_skill_count", -1)) != len(expected):
        errors.append("central_skill_count与中央Skill名称清单不一致")
    if implicit_set != {"production-router-handoff"}:
        errors.append("只能允许production-router-handoff隐式调用")
    if implicit_set & explicit_set:
        errors.append("隐式Skill与仅显式Skill清单不得重叠")
    if implicit_set | explicit_set != expected_set:
        errors.append("隐式与仅显式Skill清单的并集必须等于中央Skill清单")

    marketplace = activation.get("marketplace")
    expected_marketplace = {
        "name": "personal",
        "source": "local",
        "path": "./plugins/skillxc",
        "installation_policy": "AVAILABLE",
    }
    if marketplace != expected_marketplace:
        errors.append("skillxc个人市场合同不符合AVAILABLE且不安装的开发态约束")

    skills_root = root / "skills"
    actual_names = sorted(path.name for path in skills_root.iterdir() if path.is_dir()) if skills_root.is_dir() else []
    if actual_names != sorted(expected):
        missing = sorted(expected_set - set(actual_names))
        extra = sorted(set(actual_names) - expected_set)
        errors.append(f"中央Skill目录与清单不一致；缺失={missing}；多余={extra}")

    for name in sorted(expected_set & set(actual_names)):
        skill_root = skills_root / name
        skill_file = skill_root / "SKILL.md"
        agent_file = skill_root / "agents/openai.yaml"
        if not skill_file.is_file():
            errors.append(f"缺少SKILL.md：{name}")
        if not agent_file.is_file():
            errors.append(f"缺少agents/openai.yaml：{name}")
            continue
        try:
            agent_text = agent_file.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError) as exc:
            errors.append(f"无法按UTF-8读取agents/openai.yaml：{name}：{exc}")
            continue
        matches = IMPLICIT_PATTERN.findall(agent_text)
        if len(matches) != 1:
            errors.append(f"allow_implicit_invocation必须且只能声明一次：{name}")
            continue
        actual_implicit = matches[0].lower() == "true"
        if actual_implicit != (name in implicit_set):
            errors.append(f"隐式调用策略与清单不一致：{name}")

    plugin = _read_json(root / ".codex-plugin/plugin.json", errors)
    if plugin and (plugin.get("name") != "skillxc" or plugin.get("skills") != "./skills/"):
        errors.append("插件清单必须以skillxc命名并直接引用./skills/")
    return errors


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="检查SKillXC单一内容源和调用策略合同")
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    return parser.parse_args()


def main() -> int:
    _configure_utf8_stdio()
    errors = validate(Path(_parse_args().root))
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print("SKillXC安装与调用合同检查通过：30个中央Skill，1个隐式路由，29个仅显式Skill")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
