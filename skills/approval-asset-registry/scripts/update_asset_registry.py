#!/usr/bin/env python3
"""Atomically register asset versions and propagate dependency state changes."""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import re
import shutil
import sys
import uuid
from collections import deque
from pathlib import Path
from typing import Any


SKILL_ROOT = Path(__file__).resolve().parents[1]
ASSETS = SKILL_ROOT / "assets"
VALIDATOR_PATH = SKILL_ROOT.parent / "production-router-handoff/scripts/validate_project_data.py"
ASSET_RESPONSIBILITY_MAP_PATH = (
    SKILL_ROOT.parent / "world-asset-production/assets/asset-responsibility-map.json"
)
DEPENDENCY_FIELDS = (
    "生产依据父资产ID与版本",
    "生产依据附加资产ID与版本",
)
PAIR_FIELDS = (
    "项目ID",
    "绑定卡版本",
    "正式资产ID",
    "版本",
    "资产类型",
    "资产名称",
    "资产角色",
    "文件路径",
    "生产依据父资产ID与版本",
    "生产依据附加资产ID与版本",
    "当前兼容依赖资产ID与版本",
    "声音类别",
    "关联说话者ID",
    "关联声音身份卡ID与版本",
    "音频污染与限制",
    "状态",
    "状态依据",
    "状态更新时间",
)
DEPENDENT_ROLES = {"五视图基础卡", "服装妆造", "状态变体", "交互组合", "场景视图", "光影状态", "对象表面应用", "对象装配"}
VERSION_RE = re.compile(r"^v([0-9]{3,})$")
REFERENCE_RE = re.compile(r"^([^@；]+)@(v[0-9]{3,})$")
EVENT_RE = re.compile(r"^ASP-[A-Z0-9-]+$")


class RegistryError(Exception):
    pass


def _load_asset_responsibility_map() -> dict[str, str]:
    try:
        document = json.loads(ASSET_RESPONSIBILITY_MAP_PATH.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RegistryError(f"无法读取资产责任映射：{exc}") from exc
    router = document.get("secondary_router") if isinstance(document, dict) else None
    if (
        not isinstance(router, dict)
        or router.get("skill") != "world-asset-production"
        or router.get("may_produce_candidates") is not False
    ):
        raise RegistryError("资产责任映射必须把world-asset-production锁定为不产候选的二级路由")
    routes = document.get("asset_type_routes") if isinstance(document, dict) else None
    if not isinstance(routes, dict) or not routes:
        raise RegistryError("资产责任映射缺少非空 asset_type_routes")
    normalized: dict[str, str] = {}
    for asset_type, skill in routes.items():
        if not isinstance(asset_type, str) or not asset_type:
            raise RegistryError("资产责任映射包含空资产类型")
        if not isinstance(skill, str) or not skill:
            raise RegistryError(f"资产责任映射缺少责任Skill：{asset_type!r}")
        if skill == "world-asset-production":
            raise RegistryError(f"二级路由不得成为正式资产生产者：{asset_type!r}")
        normalized[asset_type] = skill
    return normalized


ASSET_RESPONSIBILITY = _load_asset_responsibility_map()


def _load_validator() -> Any:
    spec = importlib.util.spec_from_file_location("validate_project_data", VALIDATOR_PATH)
    if spec is None or spec.loader is None:
        raise RegistryError(f"无法加载项目数据检查器：{VALIDATOR_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VALIDATOR = _load_validator()


def _resolve_inside(root: Path, value: str) -> Path:
    candidate = Path(value)
    resolved = candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise RegistryError(f"项目数据路径越出根目录：{resolved}") from exc
    return resolved


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.is_file():
        raise RegistryError(f"项目表不存在：{path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise RegistryError(f"项目表缺少表头：{path}")
        return list(reader.fieldnames), [dict(row) for row in reader if any(row.values())]


def _write_csv(path: Path, headers: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers, extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


def _load_payload(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RegistryError(f"无法读取操作载荷：{exc}") from exc
    if not isinstance(payload, dict):
        raise RegistryError("操作载荷顶层必须是对象")
    return payload


def _key(row: dict[str, str]) -> tuple[str, str, str]:
    return row["项目ID"], row["正式资产ID"], row["版本"]


def _reference(row: dict[str, str]) -> str:
    return f"{row['正式资产ID']}@{row['版本']}"


def _version_number(value: str) -> int:
    match = VERSION_RE.fullmatch(value)
    if not match:
        raise RegistryError(f"资产版本格式无效：{value!r}")
    return int(match.group(1))


def _split_references(value: str) -> list[str]:
    if value == "不适用":
        return []
    if not value:
        raise RegistryError("依赖版本不得留空；无依赖时写“不适用”")
    references = value.split("；")
    if len(references) != len(set(references)):
        raise RegistryError(f"依赖版本重复：{value}")
    for reference in references:
        if REFERENCE_RE.fullmatch(reference) is None:
            raise RegistryError(f"依赖必须精确写为 正式资产ID@版本：{reference!r}")
    return references


def _join_references(values: list[str]) -> str:
    return "；".join(values) if values else "不适用"


def _production_dependencies(row: dict[str, str]) -> list[str]:
    result: list[str] = []
    for field in DEPENDENCY_FIELDS:
        result.extend(_split_references(row[field]))
    if len(result) != len(set(result)):
        raise RegistryError(f"{_reference(row)} 的生产依据重复")
    return result


def _index(rows: list[dict[str, str]], label: str) -> dict[tuple[str, str, str], dict[str, str]]:
    result: dict[tuple[str, str, str], dict[str, str]] = {}
    for row in rows:
        key = _key(row)
        if key in result:
            raise RegistryError(f"{label}存在重复资产版本：{key}")
        result[key] = row
    return result


def _validate_pair_business(
    formal_rows: list[dict[str, str]],
    callable_rows: list[dict[str, str]],
    project_id: str,
) -> None:
    formal = _index(formal_rows, "正式资产登记表")
    callable_map = _index(callable_rows, "可调用资产表")
    if set(formal) != set(callable_map):
        missing_callable = sorted(set(formal) - set(callable_map))
        missing_formal = sorted(set(callable_map) - set(formal))
        raise RegistryError(
            f"正式/可调用表版本集合不一致；缺可调用={missing_callable!r}，缺正式={missing_formal!r}"
        )
    active_by_asset: dict[tuple[str, str], list[str]] = {}
    reference_states: dict[tuple[str, str], str] = {}
    rows_by_reference = {
        (row["项目ID"], _reference(row)): row for row in formal_rows
    }
    for key, formal_row in formal.items():
        callable_row = callable_map[key]
        if key[0] != project_id:
            raise RegistryError(f"发现其他项目数据：{key}")
        for field in PAIR_FIELDS:
            if formal_row[field] != callable_row[field]:
                raise RegistryError(f"{key} 的正式/可调用字段不一致：{field}")
        production = _production_dependencies(formal_row)
        compatible = _split_references(formal_row["当前兼容依赖资产ID与版本"])
        if formal_row["资产角色"] in DEPENDENT_ROLES and not production:
            raise RegistryError(f"{_reference(formal_row)} 是派生资产但缺少生产依据版本")
        if formal_row["状态"] == "可调用":
            active_by_asset.setdefault((key[0], key[1]), []).append(key[2])
        reference_states[(key[0], _reference(formal_row))] = formal_row["状态"]
        if len(compatible) != len(set(compatible)):
            raise RegistryError(f"{_reference(formal_row)} 当前兼容依赖重复")
    for asset_key, versions in active_by_asset.items():
        if len(versions) > 1:
            raise RegistryError(f"同一正式资产ID存在多个可调用版本：{asset_key} -> {versions}")
    for row in formal_rows:
        self_reference = _reference(row)
        production_dependencies = _production_dependencies(row)
        parent_dependencies = _split_references(row["生产依据父资产ID与版本"])
        extra_dependencies = _split_references(row["生产依据附加资产ID与版本"])
        if row["资产角色"] == "脸母图":
            if row["资产类型"] != "人物":
                raise RegistryError(f"人物脸母图必须登记为人物资产：{self_reference}")
            if production_dependencies or _split_references(row["当前兼容依赖资产ID与版本"]):
                raise RegistryError(f"人物脸母图不得带生产依据或当前兼容依赖：{self_reference}")
        if row["资产角色"] == "五视图基础卡":
            if row["资产类型"] != "人物" or len(parent_dependencies) != 1 or extra_dependencies:
                raise RegistryError(
                    f"人物五视图基础卡必须是人物资产，只依赖一个脸母图父版本：{self_reference}"
                )
            face_row = rows_by_reference.get((project_id, parent_dependencies[0]))
            if face_row is None or face_row["资产类型"] != "人物" or face_row["资产角色"] != "脸母图":
                raise RegistryError(
                    f"人物五视图基础卡的父版本必须是已登记脸母图：{self_reference} -> {parent_dependencies[0]}"
                )
            if face_row["正式资产ID"] == row["正式资产ID"]:
                raise RegistryError(f"人物脸母图与五视图基础卡必须使用不同正式资产ID：{self_reference}")
        if row["资产角色"] == "场景母图":
            if row["资产类型"] != "场景":
                raise RegistryError(f"场景母图必须登记为场景资产：{self_reference}")
            if parent_dependencies:
                raise RegistryError(f"场景母图不得带父资产生产依据：{self_reference}")
        if row["资产类型"] == "场景视图" and row["资产角色"] != "场景视图":
            raise RegistryError(f"场景视图资产必须使用场景视图角色：{self_reference}")
        if row["资产类型"] == "光影" and row["资产角色"] != "光影状态":
            raise RegistryError(f"光影资产必须使用光影状态角色：{self_reference}")
        if row["资产类型"] == "场景" and row["资产角色"] == "状态变体":
            if len(parent_dependencies) != 1:
                raise RegistryError(f"场景状态变体必须只依赖一个场景母图或上一状态版本：{self_reference}")
            state_parent = rows_by_reference.get((project_id, parent_dependencies[0]))
            if state_parent is None or state_parent["资产类型"] != "场景" or state_parent["资产角色"] not in {"场景母图", "状态变体"}:
                raise RegistryError(
                    f"场景状态变体的父版本必须是已登记场景母图或场景状态：{self_reference} -> {parent_dependencies[0]}"
                )
            if state_parent["正式资产ID"] == row["正式资产ID"]:
                raise RegistryError(f"场景母图/上一状态与场景状态变体必须使用不同正式资产ID：{self_reference}")
        if row["资产角色"] == "场景视图":
            if row["资产类型"] != "场景视图" or len(parent_dependencies) != 1:
                raise RegistryError(f"场景视图必须是场景视图资产并只依赖一个空间父版本：{self_reference}")
            spatial_parent = rows_by_reference.get((project_id, parent_dependencies[0]))
            if spatial_parent is None or spatial_parent["资产类型"] != "场景" or spatial_parent["资产角色"] not in {"场景母图", "状态变体"}:
                raise RegistryError(
                    f"场景视图的父版本必须是已登记场景母图或场景状态：{self_reference} -> {parent_dependencies[0]}"
                )
            if spatial_parent["正式资产ID"] == row["正式资产ID"]:
                raise RegistryError(f"场景母图/状态与场景视图必须使用不同正式资产ID：{self_reference}")
        if row["资产角色"] == "光影状态":
            if row["资产类型"] != "光影" or len(parent_dependencies) != 1:
                raise RegistryError(f"光影状态必须是光影资产并只依赖一个空间图父版本：{self_reference}")
            light_parent = rows_by_reference.get((project_id, parent_dependencies[0]))
            allowed_light_parents = {
                ("场景", "场景母图"),
                ("场景", "状态变体"),
                ("场景视图", "场景视图"),
            }
            if light_parent is None or (light_parent["资产类型"], light_parent["资产角色"]) not in allowed_light_parents:
                raise RegistryError(
                    f"光影状态的父版本必须是已登记场景母图、场景状态或场景视图：{self_reference} -> {parent_dependencies[0]}"
                )
            if light_parent["正式资产ID"] == row["正式资产ID"]:
                raise RegistryError(f"空间图与光影状态必须使用不同正式资产ID：{self_reference}")
        object_types = {"道具", "载具"}
        object_parent_roles = {"独立对象", "状态变体", "对象表面应用", "对象装配"}
        if row["资产类型"] in object_types and row["资产角色"] not in object_parent_roles:
            raise RegistryError(f"道具/载具资产角色不符合对象生产链：{self_reference}")
        if row["资产角色"] == "独立对象" and row["资产类型"] in object_types:
            if production_dependencies:
                raise RegistryError(f"基础道具/载具不得带生产依据：{self_reference}")
        if row["资产角色"] == "图案文字母版":
            if row["资产类型"] != "图案文字" or production_dependencies:
                raise RegistryError(f"图案文字母版必须是无依赖的图案文字资产：{self_reference}")
        if row["资产类型"] == "图案文字" and row["资产角色"] != "图案文字母版":
            raise RegistryError(f"图案文字资产必须使用图案文字母版角色：{self_reference}")
        if row["资产类型"] in object_types and row["资产角色"] == "状态变体":
            if len(parent_dependencies) != 1 or extra_dependencies:
                raise RegistryError(f"对象状态变体必须只依赖一个同类型对象父版本：{self_reference}")
            object_parent = rows_by_reference.get((project_id, parent_dependencies[0]))
            if object_parent is None or object_parent["资产类型"] != row["资产类型"] or object_parent["资产角色"] not in object_parent_roles:
                raise RegistryError(f"对象状态变体的父版本必须是已登记同类型对象：{self_reference} -> {parent_dependencies[0]}")
            if object_parent["正式资产ID"] == row["正式资产ID"]:
                raise RegistryError(f"对象父版本与状态变体必须使用不同正式资产ID：{self_reference}")
        if row["资产角色"] == "对象表面应用":
            if row["资产类型"] not in object_types or len(parent_dependencies) != 1 or not extra_dependencies:
                raise RegistryError(f"对象表面应用必须有一个同类型对象父版本和至少一个图案文字母版：{self_reference}")
            surface_parent = rows_by_reference.get((project_id, parent_dependencies[0]))
            if surface_parent is None or surface_parent["资产类型"] != row["资产类型"] or surface_parent["资产角色"] not in object_parent_roles:
                raise RegistryError(f"对象表面应用的父版本必须是已登记同类型对象：{self_reference} -> {parent_dependencies[0]}")
            if surface_parent["正式资产ID"] == row["正式资产ID"]:
                raise RegistryError(f"对象父版本与表面应用必须使用不同正式资产ID：{self_reference}")
            for graphic_dependency in extra_dependencies:
                graphic_row = rows_by_reference.get((project_id, graphic_dependency))
                if graphic_row is None or (graphic_row["资产类型"], graphic_row["资产角色"]) != ("图案文字", "图案文字母版"):
                    raise RegistryError(f"对象表面应用的附加版本必须全部是图案文字母版：{self_reference} -> {graphic_dependency}")
        if row["资产角色"] == "对象装配":
            if row["资产类型"] not in object_types or len(parent_dependencies) != 1 or not extra_dependencies:
                raise RegistryError(f"对象装配必须有一个同类型主承载对象父版本和至少一个装配件：{self_reference}")
            assembly_parent = rows_by_reference.get((project_id, parent_dependencies[0]))
            if assembly_parent is None or assembly_parent["资产类型"] != row["资产类型"] or assembly_parent["资产角色"] not in object_parent_roles:
                raise RegistryError(f"对象装配的父版本必须是已登记同类型主承载对象：{self_reference} -> {parent_dependencies[0]}")
            if assembly_parent["正式资产ID"] == row["正式资产ID"]:
                raise RegistryError(f"主承载对象与对象装配必须使用不同正式资产ID：{self_reference}")
            for object_dependency in extra_dependencies:
                component_row = rows_by_reference.get((project_id, object_dependency))
                if component_row is None or component_row["资产类型"] not in object_types or component_row["资产角色"] not in object_parent_roles:
                    raise RegistryError(f"对象装配的附加版本必须全部是已登记道具/载具：{self_reference} -> {object_dependency}")
        for dependency in production_dependencies:
            if dependency == self_reference:
                raise RegistryError(f"资产不能把自身列为生产依据：{self_reference}")
            if (project_id, dependency) not in reference_states:
                raise RegistryError(f"{self_reference} 引用了不存在的生产依据：{dependency}")
        compatible_dependencies = _split_references(row["当前兼容依赖资产ID与版本"])
        for dependency in compatible_dependencies:
            if dependency == self_reference:
                raise RegistryError(f"资产不能把自身列为当前兼容依赖：{self_reference}")
            if (project_id, dependency) not in reference_states:
                raise RegistryError(f"{self_reference} 引用了不存在的当前兼容依赖：{dependency}")
        if row["状态"] != "可调用":
            continue
        for dependency in compatible_dependencies:
            state = reference_states.get((project_id, dependency))
            if state != "可调用":
                raise RegistryError(
                    f"可调用资产 {_reference(row)} 依赖非可调用版本 {dependency}（{state or '缺失'}）"
                )

    graph = {
        _reference(row): _split_references(row["当前兼容依赖资产ID与版本"])
        for row in formal_rows
        if row["项目ID"] == project_id
    }
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(reference: str) -> None:
        if reference in visiting:
            raise RegistryError(f"当前兼容依赖存在循环：{reference}")
        if reference in visited:
            return
        visiting.add(reference)
        for dependency in graph.get(reference, []):
            visit(dependency)
        visiting.remove(reference)
        visited.add(reference)

    for reference in graph:
        visit(reference)


def _validate_propagation_business(
    formal_rows: list[dict[str, str]],
    propagation_rows: list[dict[str, str]],
    project_id: str,
) -> None:
    formal = _index(formal_rows, "正式资产登记表")
    seen: set[tuple[str, str, str, str, str]] = set()
    latest: dict[tuple[str, str, str], str] = {}
    unresolved: set[tuple[str, str, str]] = set()
    for row in propagation_rows:
        if row["项目ID"] != project_id:
            raise RegistryError(f"状态传播表发现其他项目数据：{row['项目ID']}")
        key = (project_id, row["受影响正式资产ID"], row["受影响版本"])
        if key not in formal:
            raise RegistryError(f"状态传播行引用不存在的正式资产版本：{key}")
        unique = (
            row["传播事件ID"],
            row["传播对象"],
            row["受影响正式资产ID"],
            row["受影响版本"],
            row["依赖路径"],
        )
        if unique in seen:
            raise RegistryError(f"状态传播行重复：{unique}")
        seen.add(unique)
        latest[key] = row["传播后状态"]
        if row["传播处理状态"] == "待复核":
            unresolved.add(key)
    for key, row in formal.items():
        if row["项目ID"] != project_id:
            continue
        if key in latest and latest[key] != row["状态"]:
            raise RegistryError(
                f"{key} 当前状态与最后一条传播结果不一致：{row['状态']} != {latest[key]}"
            )
        if row["状态"] == "待复核" and latest.get(key) != "待复核":
            raise RegistryError(f"待复核资产缺少对应传播结果：{key}")
        if row["状态"] == "待复核" and key not in unresolved:
            raise RegistryError(f"待复核资产缺少未处理传播事件：{key}")
        if row["状态"] != "待复核" and key in unresolved:
            raise RegistryError(f"非待复核资产仍有未处理传播事件：{key}")


def _schema_validate(
    path: Path,
    schema: Path,
    project_id: str,
) -> list[str]:
    result = VALIDATOR._check_pair(path, schema, project_id, None, True)
    return list(result["errors"])


def _validate_staged(
    paths: dict[str, Path],
    project_id: str,
) -> None:
    schema_map = {
        "formal": ASSETS / "formal-asset.schema.json",
        "callable": ASSETS / "callable-asset.schema.json",
        "propagation": ASSETS / "asset-state-propagation.schema.json",
    }
    errors: list[str] = []
    for name, path in paths.items():
        errors.extend(_schema_validate(path, schema_map[name], project_id))
    if errors:
        raise RegistryError("Schema检查失败：\n" + "\n".join(errors))
    _, formal_rows = _read_csv(paths["formal"])
    _, callable_rows = _read_csv(paths["callable"])
    _, propagation_rows = _read_csv(paths["propagation"])
    _validate_pair_business(formal_rows, callable_rows, project_id)
    _validate_propagation_business(formal_rows, propagation_rows, project_id)


def _write_transaction(
    root: Path,
    originals: dict[str, Path],
    headers: dict[str, list[str]],
    rows: dict[str, list[dict[str, str]]],
    project_id: str,
    event_id: str,
) -> Path:
    staged: dict[str, Path] = {}
    token = uuid.uuid4().hex
    try:
        for name, original in originals.items():
            temp = original.with_name(f".{original.stem}.{token}.tmp{original.suffix}")
            _write_csv(temp, headers[name], rows[name])
            staged[name] = temp
        _validate_staged(staged, project_id)
        backup_dir = root / "registry/backups" / event_id
        if backup_dir.exists():
            raise RegistryError(f"备份目录已存在，传播事件ID必须唯一：{backup_dir}")
        backup_dir.mkdir(parents=True)
        for name, original in originals.items():
            shutil.copyfile(original, backup_dir / original.name)
        replaced: list[str] = []
        try:
            for name, original in originals.items():
                staged[name].replace(original)
                replaced.append(name)
            _validate_staged(originals, project_id)
        except Exception:
            for name in replaced:
                shutil.copyfile(backup_dir / originals[name].name, originals[name])
            raise
        return backup_dir
    finally:
        for path in staged.values():
            path.unlink(missing_ok=True)


def _responsible_skill(row: dict[str, str]) -> str:
    asset_type = row["资产类型"]
    try:
        return ASSET_RESPONSIBILITY[asset_type]
    except KeyError as exc:
        raise RegistryError(f"资产类型没有唯一责任生产Skill：{asset_type!r}") from exc


def _propagation_row(
    payload: dict[str, Any],
    trigger_action: str,
    old_version: str,
    new_version: str,
    object_type: str,
    affected: dict[str, str],
    dependency_path: str,
    old_state: str,
    new_state: str,
    processing_state: str,
    basis: str,
    user_text: str = "",
    process_date: str = "",
) -> dict[str, str]:
    return {
        "项目ID": str(payload["项目ID"]),
        "绑定卡版本": affected["绑定卡版本"],
        "传播事件ID": str(payload["传播事件ID"]),
        "触发动作": trigger_action,
        "触发正式资产ID": str(payload["触发正式资产ID"]),
        "被替代版本": old_version,
        "当前新版本": new_version,
        "传播对象": object_type,
        "受影响正式资产ID": affected["正式资产ID"],
        "受影响版本": affected["版本"],
        "受影响需求槽位ID": affected["需求槽位ID"],
        "依赖路径": dependency_path,
        "原状态": old_state,
        "传播后状态": new_state,
        "影响场次": affected["关联场次"] or "不适用",
        "下游复核范围": (
            "登记与可调用映射"
            if object_type in {"新登记版本", "被替代旧版本"}
            else "场次就绪；生成单元；分镜；正式Prompt"
        ),
        "传播处理状态": processing_state,
        "责任Skill": _responsible_skill(affected),
        "传播依据": basis,
        "用户处理原文": user_text,
        "处理日期": process_date,
        "记录日期": str(payload["记录日期"]),
    }


def _require_fields(payload: dict[str, Any], fields: tuple[str, ...]) -> None:
    missing = [field for field in fields if not isinstance(payload.get(field), str) or not payload[field]]
    if missing:
        raise RegistryError(f"操作载荷缺少非空字段：{missing}")
    if EVENT_RE.fullmatch(str(payload.get("传播事件ID", ""))) is None:
        raise RegistryError("传播事件ID必须匹配 ASP-[A-Z0-9-]+")


def _register(
    payload: dict[str, Any],
    formal_rows: list[dict[str, str]],
    callable_rows: list[dict[str, str]],
    propagation_rows: list[dict[str, str]],
) -> dict[str, Any]:
    _require_fields(payload, ("项目ID", "传播事件ID", "记录日期"))
    if any(row["传播事件ID"] == payload["传播事件ID"] for row in propagation_rows):
        raise RegistryError("传播事件ID已存在")
    formal_new = payload.get("正式登记行")
    callable_new = payload.get("可调用行")
    if not isinstance(formal_new, dict) or not isinstance(callable_new, dict):
        raise RegistryError("登记载荷必须包含“正式登记行”和“可调用行”对象")
    formal_new = {key: str(value) for key, value in formal_new.items()}
    callable_new = {key: str(value) for key, value in callable_new.items()}
    project_id = str(payload["项目ID"])
    payload["触发正式资产ID"] = formal_new.get("正式资产ID", "")
    if formal_new.get("项目ID") != project_id or callable_new.get("项目ID") != project_id:
        raise RegistryError("登记行项目ID与载荷不一致")
    for field in PAIR_FIELDS:
        if formal_new.get(field) != callable_new.get(field):
            raise RegistryError(f"新登记行正式/可调用字段不一致：{field}")
    if formal_new.get("状态") != "可调用":
        raise RegistryError("新登记版本初始状态必须为可调用")
    production = _production_dependencies(formal_new)
    compatible = _split_references(formal_new["当前兼容依赖资产ID与版本"])
    if set(production) != set(compatible):
        raise RegistryError("首次登记的当前兼容依赖必须等于全部生产依据版本")

    formal_index = _index(formal_rows, "正式资产登记表")
    callable_index = _index(callable_rows, "可调用资产表")
    new_key = _key(formal_new)
    if new_key in formal_index or new_key in callable_index:
        raise RegistryError(f"资产版本已存在：{new_key}")
    same_asset = [row for row in formal_rows if row["项目ID"] == project_id and row["正式资产ID"] == formal_new["正式资产ID"]]
    expected_version = 1 if not same_asset else max(_version_number(row["版本"]) for row in same_asset) + 1
    if _version_number(formal_new["版本"]) != expected_version:
        raise RegistryError(f"新版本必须为 v{expected_version:03d}")
    state_by_reference = {
        _reference(row): row["状态"] for row in formal_rows if row["项目ID"] == project_id
    }
    for dependency in compatible:
        if state_by_reference.get(dependency) != "可调用":
            raise RegistryError(f"新登记版本依赖非可调用资产：{dependency}")

    formal_rows.append(formal_new)
    callable_rows.append(callable_new)
    affected: list[str] = []
    old_row: dict[str, str] | None = None
    if same_asset:
        old_row = max(same_asset, key=lambda row: _version_number(row["版本"]))
        old_key = _key(old_row)
        old_callable = callable_index[old_key]
        old_state = old_row["状态"]
        basis = f"{formal_new['正式资产ID']} 登记 {formal_new['版本']}，替代 {old_row['版本']}"
        for event in propagation_rows:
            if (
                event["受影响正式资产ID"] == old_row["正式资产ID"]
                and event["受影响版本"] == old_row["版本"]
                and event["传播处理状态"] == "待复核"
            ):
                event["传播处理状态"] = "已重新登记"
                event["用户处理原文"] = formal_new["登记指令原文"]
                event["处理日期"] = str(payload["记录日期"])
        for row in (old_row, old_callable):
            row["状态"] = "历史"
            row["状态依据"] = basis
            row["状态更新时间"] = str(payload["记录日期"])
        propagation_rows.append(
            _propagation_row(
                payload,
                "登记新版本",
                old_row["版本"],
                formal_new["版本"],
                "被替代旧版本",
                old_row,
                "自身版本替代",
                old_state,
                "历史",
                "已完成",
                basis,
                formal_new["登记指令原文"],
                str(payload["记录日期"]),
            )
        )
        old_reference = _reference(old_row)
        reverse: dict[str, list[dict[str, str]]] = {}
        for row in formal_rows:
            if row["项目ID"] != project_id or row is formal_new or row["状态"] not in {"可调用", "待复核"}:
                continue
            for dependency in _split_references(row["当前兼容依赖资产ID与版本"]):
                reverse.setdefault(dependency, []).append(row)
        queue: deque[tuple[str, list[str]]] = deque([(old_reference, [old_reference])])
        expanded: set[tuple[str, str, str]] = set()
        recorded: set[tuple[tuple[str, str, str], str]] = set()
        while queue:
            dependency, path = queue.popleft()
            for dependent in reverse.get(dependency, []):
                dependent_key = _key(dependent)
                record_key = (dependent_key, dependency)
                if record_key in recorded or dependent_key == old_key:
                    continue
                recorded.add(record_key)
                dependent_callable = callable_index[dependent_key]
                previous_state = dependent["状态"]
                propagation_basis = f"当前兼容依赖 {dependency} 已被新版本替代"
                for row in (dependent, dependent_callable):
                    row["状态"] = "待复核"
                    row["状态依据"] = propagation_basis
                    row["状态更新时间"] = str(payload["记录日期"])
                chain = path + [_reference(dependent)]
                propagation_rows.append(
                    _propagation_row(
                        payload,
                        "登记新版本",
                        old_row["版本"],
                        formal_new["版本"],
                        "派生资产",
                        dependent,
                        " -> ".join(chain),
                        previous_state,
                        "待复核",
                        "待复核",
                        propagation_basis,
                    )
                )
                if dependent_key not in expanded:
                    expanded.add(dependent_key)
                    affected.append(_reference(dependent))
                    queue.append((_reference(dependent), chain))
        propagation_rows.append(
            _propagation_row(
                payload,
                "登记新版本",
                old_row["版本"],
                formal_new["版本"],
                "新登记版本",
                formal_new,
                "自身新版本登记",
                "未登记",
                "可调用",
                "已完成",
                basis,
                formal_new["登记指令原文"],
                str(payload["记录日期"]),
            )
        )
    else:
        payload["触发正式资产ID"] = formal_new["正式资产ID"]
        basis = f"{_reference(formal_new)} 首次正式登记"
        propagation_rows.append(
            _propagation_row(
                payload,
                "登记新版本",
                "不适用",
                formal_new["版本"],
                "新登记版本",
                formal_new,
                "自身首次登记",
                "未登记",
                "可调用",
                "已完成",
                basis,
                formal_new["登记指令原文"],
                str(payload["记录日期"]),
            )
        )
    return {
        "项目ID": project_id,
        "正式资产": _reference(formal_new),
        "被替代版本": _reference(old_row) if old_row else "不适用",
        "待复核派生资产": sorted(affected),
        "传播事件ID": payload["传播事件ID"],
    }


def _confirm_compatible(
    payload: dict[str, Any],
    formal_rows: list[dict[str, str]],
    callable_rows: list[dict[str, str]],
    propagation_rows: list[dict[str, str]],
) -> dict[str, Any]:
    _require_fields(
        payload,
        (
            "项目ID",
            "传播事件ID",
            "记录日期",
            "触发正式资产ID",
            "被替代版本",
            "当前新版本",
            "受影响正式资产ID",
            "受影响版本",
            "用户处理原文",
            "处理日期",
            "复核结论",
            "复核依据",
        ),
    )
    if payload["复核结论"] != "可继续":
        raise RegistryError("只有复核结论为“可继续”才能解除待复核")
    if any(row["传播事件ID"] == payload["传播事件ID"] for row in propagation_rows):
        raise RegistryError("传播事件ID已存在")
    project_id = str(payload["项目ID"])
    formal_index = _index(formal_rows, "正式资产登记表")
    callable_index = _index(callable_rows, "可调用资产表")
    target_key = (project_id, str(payload["受影响正式资产ID"]), str(payload["受影响版本"]))
    target = formal_index.get(target_key)
    target_callable = callable_index.get(target_key)
    if target is None or target_callable is None:
        raise RegistryError("待复核资产版本不存在")
    if target["状态"] != "待复核" or target_callable["状态"] != "待复核":
        raise RegistryError("指定资产当前不是待复核状态")
    old_reference = f"{payload['触发正式资产ID']}@{payload['被替代版本']}"
    new_reference = f"{payload['触发正式资产ID']}@{payload['当前新版本']}"
    new_parent_key = (project_id, str(payload["触发正式资产ID"]), str(payload["当前新版本"]))
    if formal_index.get(new_parent_key, {}).get("状态") != "可调用":
        raise RegistryError("确认兼容所指的新依赖版本不是可调用状态")
    unresolved_events = [
        row
        for row in propagation_rows
        if (
        row["受影响正式资产ID"] == target["正式资产ID"]
        and row["受影响版本"] == target["版本"]
        and row["传播处理状态"] == "待复核"
        and len(row["依赖路径"].split(" -> ")) >= 2
        and row["依赖路径"].split(" -> ")[-2] == old_reference
        )
    ]
    if not unresolved_events:
        raise RegistryError("状态传播表中没有与指定直接依赖相符的待复核事件")
    compatible = _split_references(target["当前兼容依赖资产ID与版本"])
    if old_reference in compatible:
        compatible = [new_reference if value == old_reference else value for value in compatible]
    elif old_reference == new_reference and new_reference in compatible:
        compatible = list(compatible)
    else:
        raise RegistryError(f"待复核资产当前兼容依赖中没有 {old_reference}")
    remaining: list[str] = []
    for dependency in compatible:
        match = REFERENCE_RE.fullmatch(dependency)
        assert match is not None
        dependency_key = (project_id, match.group(1), match.group(2))
        if formal_index.get(dependency_key, {}).get("状态") != "可调用":
            remaining.append(dependency)
    other_unresolved = [
        row
        for row in propagation_rows
        if (
            row["受影响正式资产ID"] == target["正式资产ID"]
            and row["受影响版本"] == target["版本"]
            and row["传播处理状态"] == "待复核"
            and row not in unresolved_events
        )
    ]
    updated_dependencies = _join_references(compatible)
    restored = not remaining and not other_unresolved
    new_state = "可调用" if restored else "待复核"
    object_type = "复核解除" if restored else "兼容确认"
    processing_state = "已复核继续" if restored else "待复核"
    basis = f"用户明确确认兼容 {new_reference}；复核依据：{payload['复核依据']}"
    if remaining:
        basis += f"；仍有非可调用依赖：{'；'.join(remaining)}"
    if other_unresolved:
        pending_paths = sorted({row["依赖路径"] for row in other_unresolved})
        basis += f"；仍有未确认传播路径：{'；'.join(pending_paths)}"
    for row in (target, target_callable):
        row["当前兼容依赖资产ID与版本"] = updated_dependencies
        row["状态"] = new_state
        row["状态依据"] = basis
        row["状态更新时间"] = str(payload["处理日期"])
    for event in unresolved_events:
        event["传播处理状态"] = "已复核继续"
        event["用户处理原文"] = str(payload["用户处理原文"])
        event["处理日期"] = str(payload["处理日期"])
    propagation_rows.append(
        _propagation_row(
            payload,
            "确认继续可用",
            str(payload["被替代版本"]),
            str(payload["当前新版本"]),
            object_type,
            target,
            f"{_reference(target)}：{old_reference} -> {new_reference}",
            "待复核",
            new_state,
            "已复核继续",
            basis,
            str(payload["用户处理原文"]),
            str(payload["处理日期"]),
        )
    )
    return {
        "项目ID": project_id,
        "资产版本": _reference(target),
        "当前状态": new_state,
        "仍待处理依赖": remaining,
        "当前兼容依赖": updated_dependencies,
        "传播事件ID": payload["传播事件ID"],
    }


def _table_paths(args: argparse.Namespace) -> tuple[Path, dict[str, Path]]:
    root = Path(args.project_root).resolve()
    if not root.is_dir():
        raise RegistryError(f"项目数据根目录不存在：{root}")
    paths = {
        "formal": _resolve_inside(root, args.formal_table),
        "callable": _resolve_inside(root, args.callable_table),
        "propagation": _resolve_inside(root, args.propagation_table),
    }
    if len(set(paths.values())) != 3:
        raise RegistryError("三张项目表路径不得重复")
    return root, paths


def _run(args: argparse.Namespace) -> dict[str, Any]:
    root, originals = _table_paths(args)
    headers: dict[str, list[str]] = {}
    rows: dict[str, list[dict[str, str]]] = {}
    for name, path in originals.items():
        headers[name], rows[name] = _read_csv(path)
    if args.command == "check":
        _validate_staged(originals, args.project_id)
        return {"项目ID": args.project_id, "检查结论": "通过"}
    payload = _load_payload(Path(args.payload).resolve())
    _validate_staged(originals, str(payload.get("项目ID", "")))
    if args.command == "register":
        result = _register(payload, rows["formal"], rows["callable"], rows["propagation"])
    else:
        result = _confirm_compatible(payload, rows["formal"], rows["callable"], rows["propagation"])
    backup_dir = _write_transaction(
        root,
        originals,
        headers,
        rows,
        str(payload["项目ID"]),
        str(payload["传播事件ID"]),
    )
    result["备份目录"] = str(backup_dir)
    result["写入结论"] = "通过"
    return result


def _add_table_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--project-root", required=True, help="已绑定项目数据根目录")
    parser.add_argument("--formal-table", default="registry/正式资产登记表.csv")
    parser.add_argument("--callable-table", default="registry/可调用资产表.csv")
    parser.add_argument("--propagation-table", default="registry/资产状态传播表.csv")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="原子更新正式资产、可调用映射和状态传播表")
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("check", help="只检查三表结构与跨表业务关系")
    _add_table_args(check)
    check.add_argument("--project-id", required=True)
    register = commands.add_parser("register", help="登记新正式版本并传播旧版本影响")
    _add_table_args(register)
    register.add_argument("--payload", required=True, help="登记操作JSON")
    confirm = commands.add_parser("confirm-compatible", help="按用户明确确认解除一个待复核版本")
    _add_table_args(confirm)
    confirm.add_argument("--payload", required=True, help="兼容确认操作JSON")
    return parser.parse_args()


def main() -> int:
    try:
        result = _run(_parse_args())
    except (RegistryError, OSError, csv.Error) as exc:
        print(f"资产登记事务失败：{exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
