#!/usr/bin/env python3
"""Validate the central creative-control source catalog and definition links."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SKILL_ROOT.parents[1]
CATALOG = SKILL_ROOT / "references/control-source-catalog.json"
SOURCE_ID_RE = re.compile(r"^CCS-[A-Z0-9-]+$")
VERSION_RE = re.compile(r"^v([0-9]{3,})$")


def validate() -> list[str]:
    errors: list[str] = []
    try:
        payload = json.loads(CATALOG.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"无法读取源定义目录：{exc}"]
    if not isinstance(payload, dict) or not isinstance(payload.get("sources"), list):
        return ["源定义目录顶层必须包含 sources 数组"]
    seen: set[str] = set()
    for index, item in enumerate(payload["sources"], start=1):
        label = f"sources[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{label}: 必须是对象")
            continue
        required = (
            "source_id",
            "current_version",
            "available_versions",
            "control_type",
            "owner_skill",
            "definition_paths",
            "available_versions_policy",
            "change_summary",
        )
        missing = [field for field in required if field not in item]
        if missing:
            errors.append(f"{label}: 缺少字段 {missing}")
            continue
        source_id = str(item["source_id"])
        if SOURCE_ID_RE.fullmatch(source_id) is None:
            errors.append(f"{label}: source_id 无效：{source_id}")
        if source_id in seen:
            errors.append(f"{label}: source_id 重复：{source_id}")
        seen.add(source_id)
        versions = item["available_versions"]
        if item["available_versions_policy"] != "append-only":
            errors.append(f"{label}: available_versions_policy 必须为 append-only")
        if not isinstance(versions, list) or not versions:
            errors.append(f"{label}: available_versions 必须是非空数组")
            continue
        numbers: list[int] = []
        for version in versions:
            match = VERSION_RE.fullmatch(str(version))
            if not match:
                errors.append(f"{label}: 版本格式无效：{version}")
                continue
            numbers.append(int(match.group(1)))
        if numbers and sorted(numbers) != list(range(1, max(numbers) + 1)):
            errors.append(f"{label}: 可用版本必须从 v001 连续：{versions}")
        current = str(item["current_version"])
        if current not in {str(value) for value in versions}:
            errors.append(f"{label}: current_version 不在 available_versions 中")
        if numbers and current != f"v{max(numbers):03d}":
            errors.append(f"{label}: current_version 必须是最大可用版本")
        owner = REPO_ROOT / "skills" / str(item["owner_skill"]) / "SKILL.md"
        if not owner.is_file():
            errors.append(f"{label}: owner_skill 不存在：{owner}")
        paths = item["definition_paths"]
        if not isinstance(paths, list) or not paths:
            errors.append(f"{label}: definition_paths 必须是非空数组")
            continue
        current_ref = f"{source_id}@{current}"
        reference_found = False
        for value in paths:
            path = (REPO_ROOT / str(value)).resolve()
            try:
                path.relative_to(REPO_ROOT)
            except ValueError:
                errors.append(f"{label}: definition_path 越出仓库：{value}")
                continue
            if not path.is_file():
                errors.append(f"{label}: definition_path 不存在：{value}")
                continue
            if current_ref in path.read_text(encoding="utf-8-sig"):
                reference_found = True
        if not reference_found:
            errors.append(f"{label}: 定义文件中没有当前源引用 {current_ref}")
    return errors


def main() -> int:
    errors = validate()
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print("创作控制中央源目录检查通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
