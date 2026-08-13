#!/usr/bin/env python3
"""Validate film Profile Markdown cards, catalog and source references."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


PROFILE_GLOBS = (
    "director-*.md",
    "cinematographer-*.md",
    "production-designer-*.md",
    "writer-*.md",
    "editor-*.md",
)
DEPARTMENT_PREFIX = {
    "导演": "DIR",
    "摄影指导": "CIN",
    "美术／Production Design": "PD",
    "编剧／剧作": "WRI",
    "剪辑": "EDI",
}
EXPECTED_STAGE = {
    "导演": "导演与人物调度",
    "摄影指导": "全片摄影基线",
    "美术／Production Design": "美术与 LookDev",
    "编剧／剧作": "剧作与场戏节拍",
    "剪辑": "剪辑与节奏",
}
EVIDENCE_MARKS = {"用户提供", "直接观察", "来源支持", "分析性归纳"}


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: Schema 顶层必须是对象")
    return payload


def _profile_files(references: Path) -> list[Path]:
    files: set[Path] = set()
    for pattern in PROFILE_GLOBS:
        files.update(references.glob(pattern))
    return sorted(files, key=lambda item: item.name)


def _extract_record(text: str, label: str) -> tuple[dict[str, str], list[str], list[str]]:
    errors: list[str] = []
    match = re.search(r"^## Profile 记录\s*$\n(?P<body>.*?)(?=^## |\Z)", text, re.M | re.S)
    if not match:
        return {}, [], [f"{label}: 缺少 `## Profile 记录`"]
    record: dict[str, str] = {}
    order: list[str] = []
    for line_number, line in enumerate(match.group("body").splitlines(), start=1):
        if not line.strip():
            continue
        field_match = re.match(r"^- ([^：]+)：(.+)$", line.strip())
        if not field_match:
            errors.append(f"{label}: Profile 记录含无法解析的行：{line!r}")
            continue
        field, value = field_match.groups()
        field = field.strip()
        value = value.strip()
        if field in record:
            errors.append(f"{label}: Profile 记录字段重复：{field}")
        record[field] = value
        order.append(field)
    return record, order, errors


def _schema_types(spec: dict[str, Any]) -> list[str]:
    value = spec.get("type")
    return [value] if isinstance(value, str) else list(value or [])


def _validate_scalar(value: str, spec: dict[str, Any], location: str) -> list[str]:
    errors: list[str] = []
    if "string" not in _schema_types(spec):
        return [f"{location}: Profile 元数据检查器只支持字符串字段"]
    if "enum" in spec and value not in spec["enum"]:
        errors.append(f"{location}: 值 {value!r} 不在允许集合 {spec['enum']!r}")
    if len(value) < int(spec.get("minLength", 0)):
        errors.append(f"{location}: 值不能为空")
    if "pattern" in spec and re.fullmatch(spec["pattern"], value) is None:
        errors.append(f"{location}: 值 {value!r} 不匹配 {spec['pattern']!r}")
    return errors


def _extract_methods(text: str, label: str) -> tuple[list[tuple[str, str]], list[str]]:
    methods: list[tuple[str, str]] = []
    errors: list[str] = []
    section = re.search(r"^## 可观察方法与证据\s*$\n(?P<body>.*?)(?=^## |\Z)", text, re.M | re.S)
    if not section:
        return methods, [f"{label}: 缺少可观察方法表"]
    for line in section.group("body").splitlines():
        match = re.match(r"^\|\s*([A-Z0-9-]+-M\d{2})\s*\|\s*([^|]+?)\s*\|", line)
        if match:
            method_id, evidence = match.groups()
            methods.append((method_id, evidence))
            if evidence not in EVIDENCE_MARKS:
                errors.append(f"{label}: {method_id} 使用未知证据标记 {evidence!r}")
    return methods, errors


def _source_ids(sources_text: str) -> tuple[set[str], list[str]]:
    ids = re.findall(r"^### (SRC-[A-Z0-9-]+)\s*$", sources_text, re.M)
    duplicates = sorted({item for item in ids if ids.count(item) > 1})
    return set(ids), [f"sources.md: 来源ID重复：{item}" for item in duplicates]


def _parse_catalog(text: str) -> tuple[list[dict[str, str]], list[str]]:
    records: list[dict[str, str]] = []
    errors: list[str] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.startswith("| FP-"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != 7:
            errors.append(f"catalog.md: 第 {line_number} 行应为 7 列，实际 {len(cells)} 列")
            continue
        profile_id, subject, works, version, maturity_status, evidence, link = cells
        link_match = re.fullmatch(r"\[打开\]\(([^)]+\.md)\)", link)
        if not link_match:
            errors.append(f"catalog.md: 第 {line_number} 行卡片链接无效：{link!r}")
            continue
        if "／" not in maturity_status:
            errors.append(f"catalog.md: 第 {line_number} 行成熟度／状态无法解析")
            continue
        maturity, status = maturity_status.split("／", 1)
        records.append(
            {
                "ProfileID": profile_id,
                "主体名称": subject,
                "代表作品": works,
                "卡片版本": version,
                "资料成熟度": maturity,
                "当前状态": status,
                "方法证据状态": evidence,
                "文件": link_match.group(1),
            }
        )
    return records, errors


def _validate_card(
    path: Path,
    schema: dict[str, Any],
    known_sources: set[str],
) -> tuple[dict[str, str], list[str]]:
    text = path.read_text(encoding="utf-8-sig")
    label = path.name
    record, field_order, errors = _extract_record(text, label)
    properties = schema.get("properties", {})
    required = schema.get("required", [])
    if field_order != required:
        errors.append(f"{label}: Profile 记录字段名称或顺序与 Schema required 不一致")
    missing = [field for field in required if field not in record]
    unknown = [field for field in record if field not in properties]
    if missing:
        errors.append(f"{label}: 缺少字段 {missing!r}")
    if unknown:
        errors.append(f"{label}: 存在 Schema 未定义字段 {unknown!r}")
    for field, value in record.items():
        if field in properties:
            errors.extend(_validate_scalar(value, properties[field], f"{label}.{field}"))

    contract = schema.get("x-profile-contract", {})
    required_sections = contract.get("required_sections", [])
    actual_sections = re.findall(r"^## (.+?)\s*$", text, re.M)
    if actual_sections != required_sections:
        errors.append(f"{label}: 二级章节名称或顺序与 Profile Schema 不一致")

    methods, method_errors = _extract_methods(text, label)
    errors.extend(method_errors)
    minimum_methods = int(contract.get("minimum_methods", 3))
    if len(methods) < minimum_methods:
        errors.append(f"{label}: 方法条目少于 {minimum_methods} 条")
    method_ids = [method_id for method_id, _ in methods]
    if len(method_ids) != len(set(method_ids)):
        errors.append(f"{label}: 方法ID重复")
    profile_id = record.get("ProfileID", "")
    expected_method_prefix = profile_id.removeprefix("FP-") + "-M"
    for method_id in method_ids:
        if not method_id.startswith(expected_method_prefix):
            errors.append(f"{label}: 方法ID {method_id} 与 ProfileID 不一致")

    evidence_values = {evidence for _, evidence in methods}
    declared_evidence = record.get("方法证据状态")
    if len(evidence_values) == 1 and declared_evidence not in evidence_values:
        errors.append(f"{label}: 方法证据状态与逐条证据标记不一致")
    if len(evidence_values) > 1 and declared_evidence != "混合证据":
        errors.append(f"{label}: 多种逐条证据必须声明为 `混合证据`")

    maturity = record.get("资料成熟度")
    status = record.get("当前状态")
    allowed_statuses = contract.get("maturity_status_rules", {}).get(maturity, [])
    if maturity and status not in allowed_statuses:
        errors.append(f"{label}: 成熟度 {maturity!r} 不允许状态 {status!r}")
    if maturity in {"已核验", "项目验证"}:
        weak = [method_id for method_id, evidence in methods if evidence in {"用户提供", "分析性归纳"}]
        if weak:
            errors.append(f"{label}: {maturity} 仍含未核验方法 {weak!r}")
        source_values = set(record.get("来源ID", "").split("、"))
        if source_values <= {"SRC-USER-001", "SRC-DRAFT-001"}:
            errors.append(f"{label}: {maturity} 缺少外部具体来源或项目验证来源")

    for source_id in filter(None, record.get("来源ID", "").split("、")):
        if source_id not in known_sources:
            errors.append(f"{label}: 来源ID未在 sources.md 登记：{source_id}")

    department = record.get("专业部门")
    expected_prefix = DEPARTMENT_PREFIX.get(department or "")
    if expected_prefix and not profile_id.startswith(f"FP-{expected_prefix}-"):
        errors.append(f"{label}: ProfileID 部门前缀与专业部门不一致")
    if department in EXPECTED_STAGE and record.get("适用阶段") != EXPECTED_STAGE[department]:
        errors.append(f"{label}: {department} 的适用阶段必须为 {EXPECTED_STAGE[department]!r}")
    if department == "摄影指导" and record.get("Profile本体失效点") != "全片摄影规则卡交付后":
        errors.append(f"{label}: 摄影 Profile 必须在全片摄影规则卡交付后失效")

    if "- 禁止下传：" not in text:
        errors.append(f"{label}: 当前项目短执行卡缺少“禁止下传”")
    if "升级缺口：" not in text:
        errors.append(f"{label}: 缺少升级缺口")
    return record, errors


def validate_library(library_root: Path) -> dict[str, Any]:
    references = library_root / "references"
    schema_path = references / "profile-card-schema.json"
    catalog_path = references / "catalog.md"
    sources_path = references / "sources.md"
    history_path = references / "profile-version-history.json"
    errors: list[str] = []
    try:
        schema = _read_json(schema_path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return {"profiles": 0, "catalog_rows": 0, "sources": 0, "errors": [str(exc)]}
    if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
        errors.append("profile-card-schema.json: $schema 必须为 Draft 2020-12")
    if schema.get("type") != "object" or schema.get("additionalProperties") is not False:
        errors.append("profile-card-schema.json: 顶层必须为封闭 object")

    try:
        sources_text = sources_path.read_text(encoding="utf-8-sig")
        known_sources, source_errors = _source_ids(sources_text)
        errors.extend(source_errors)
    except OSError as exc:
        known_sources = set()
        errors.append(f"无法读取 sources.md：{exc}")

    cards: dict[str, tuple[Path, dict[str, str]]] = {}
    all_method_ids: list[str] = []
    files = _profile_files(references)
    for path in files:
        try:
            record, card_errors = _validate_card(path, schema, known_sources)
        except (OSError, UnicodeDecodeError) as exc:
            record, card_errors = {}, [f"{path.name}: 无法读取：{exc}"]
        errors.extend(card_errors)
        profile_id = record.get("ProfileID")
        if profile_id:
            if profile_id in cards:
                errors.append(f"ProfileID重复：{profile_id}")
            cards[profile_id] = (path, record)
        try:
            text = path.read_text(encoding="utf-8-sig")
            all_method_ids.extend(method_id for method_id, _ in _extract_methods(text, path.name)[0])
        except OSError:
            pass
    duplicate_methods = sorted({item for item in all_method_ids if all_method_ids.count(item) > 1})
    errors.extend(f"方法ID全库重复：{item}" for item in duplicate_methods)

    try:
        catalog_records, catalog_errors = _parse_catalog(catalog_path.read_text(encoding="utf-8-sig"))
        errors.extend(catalog_errors)
    except OSError as exc:
        catalog_records = []
        errors.append(f"无法读取 catalog.md：{exc}")
    catalog_ids = [item["ProfileID"] for item in catalog_records]
    if len(catalog_ids) != len(set(catalog_ids)):
        errors.append("catalog.md: ProfileID重复")
    catalog_files = [item["文件"] for item in catalog_records]
    if len(catalog_files) != len(set(catalog_files)):
        errors.append("catalog.md: 卡片文件链接重复")
    if set(catalog_ids) != set(cards):
        errors.append("catalog.md: ProfileID 集合与实际卡片不一致")
    if set(catalog_files) != {path.name for path in files}:
        errors.append("catalog.md: 文件链接集合与实际卡片不一致")
    for item in catalog_records:
        card = cards.get(item["ProfileID"])
        if not card:
            continue
        path, record = card
        if path.name != item["文件"]:
            errors.append(f"catalog.md: {item['ProfileID']} 的文件链接与卡片不一致")
        for field in ("主体名称", "代表作品", "卡片版本", "资料成熟度", "当前状态", "方法证据状态"):
            if record.get(field) != item[field]:
                errors.append(f"catalog.md: {item['ProfileID']} 的 {field} 与卡片不一致")

    history_count = 0
    try:
        history_payload = _read_json(history_path)
        history_records = history_payload.get("profiles")
        if not isinstance(history_records, list):
            errors.append("profile-version-history.json: profiles 必须是数组")
            history_records = []
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        history_records = []
        errors.append(f"无法读取 profile-version-history.json：{exc}")
    history: dict[str, list[str]] = {}
    for index, item in enumerate(history_records):
        if not isinstance(item, dict):
            errors.append(f"profile-version-history.json: 第 {index + 1} 项必须是对象")
            continue
        profile_id = item.get("profile_id")
        versions = item.get("available_versions")
        if not isinstance(profile_id, str) or not profile_id:
            errors.append(f"profile-version-history.json: 第 {index + 1} 项缺少 profile_id")
            continue
        if profile_id in history:
            errors.append(f"profile-version-history.json: ProfileID重复：{profile_id}")
            continue
        if not isinstance(versions, list) or not versions or not all(isinstance(value, str) for value in versions):
            errors.append(f"profile-version-history.json: {profile_id} 的 available_versions 必须是非空字符串数组")
            continue
        if len(versions) != len(set(versions)):
            errors.append(f"profile-version-history.json: {profile_id} 的历史版本重复")
        if any(re.fullmatch(r"v[0-9]+\.[0-9]+", value) is None for value in versions):
            errors.append(f"profile-version-history.json: {profile_id} 含无效版本号")
        else:
            ordered = sorted(versions, key=lambda value: tuple(int(part) for part in value[1:].split(".")))
            if versions != ordered:
                errors.append(f"profile-version-history.json: {profile_id} 的历史版本必须按升序排列")
        history[profile_id] = versions
    history_count = len(history)
    if set(history) != set(cards):
        errors.append("profile-version-history.json: ProfileID 集合与实际卡片不一致")
    for profile_id, (_, record) in cards.items():
        versions = history.get(profile_id, [])
        current = record.get("卡片版本")
        if versions and current != versions[-1]:
            errors.append(f"profile-version-history.json: {profile_id} 的最后版本必须等于当前卡片版本 {current}")

    return {
        "profiles": len(files),
        "catalog_rows": len(catalog_records),
        "history_rows": history_count,
        "sources": len(known_sources),
        "errors": errors,
    }


def _render_report(result: dict[str, Any]) -> str:
    errors = result["errors"]
    lines = [
        "# Profile 资料库检查报告",
        "",
        "Schema版本：v1.0",
        f"Profile卡片数：{result['profiles']}",
        f"目录记录数：{result['catalog_rows']}",
        f"历史版本记录数：{result.get('history_rows', 0)}",
        f"来源ID数：{result['sources']}",
        f"结论：{'通过' if not errors else '未通过'}",
        "",
        "## 错误",
        "",
    ]
    lines.extend([f"- {error}" for error in errors] or ["- 无"])
    lines.extend(
        [
            "",
            "## 证据边界",
            "",
            "本检查只证明卡片结构、字段取值、方法ID、成熟度/状态门槛、目录和来源ID引用一致；不证明作品归属、方法归因、创作者意图、AI适配效果或项目创作质量。",
            "",
        ]
    )
    return "\n".join(lines)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="检查影视 Profile 资料库")
    parser.add_argument(
        "--root",
        help="film-profile-library 目录；默认使用脚本上一级目录",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    root = Path(args.root).resolve() if args.root else Path(__file__).resolve().parents[1]
    result = validate_library(root)
    print(_render_report(result))
    return 1 if result["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
