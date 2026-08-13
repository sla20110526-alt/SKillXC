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
DEFAULT_EXPECTED_STAGE = {
    "导演": "导演与人物调度",
    "摄影指导": "全片摄影基线",
    "美术／Production Design": "美术与 LookDev",
    "编剧／剧作": "剧作与场戏节拍",
    "剪辑": "剪辑与节奏",
}
EVIDENCE_MARKS = {"用户提供", "直接观察", "来源支持", "分析性归纳"}
REPOSITORY_SNAPSHOT_PATTERN = re.compile(r"^- 仓库快照：\[[^]]+\]\(([^)]+\.md)\)", re.M)
PROHIBITED_SOURCE_LOCATORS = ("聊天记录", "生产对话", "Git 历史", "Git历史", "旧提交")
EXPECTED_PHASE_CALLERS = {
    ("导演", "项目风格意图基线"): "style-lock-director",
    ("导演", "导演与人物调度"): "directing-blocking",
    ("摄影指导", "全片摄影基线"): "cinematography-direction",
    ("摄影指导", "用户明确确认的限时场戏摄影例外"): "cinematography-direction",
    ("美术／Production Design", "美术与 LookDev"): "art-lookdev-direction",
    ("编剧／剧作", "剧作与场戏节拍"): "dramaturgy-scene-beats",
    ("剪辑", "剪辑与节奏"): "editing-rhythm",
}


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


def _source_sections(sources_text: str) -> dict[str, str]:
    matches = list(re.finditer(r"^### (SRC-[A-Z0-9-]+)\s*$", sources_text, re.M))
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(sources_text)
        sections[match.group(1)] = sources_text[match.end():end]
    return sections


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


def _parse_phase_routes(text: str) -> tuple[dict[tuple[str, str], str], list[str]]:
    routes: dict[tuple[str, str], str] = {}
    errors: list[str] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.startswith("|") or "`" not in line:
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != 5:
            continue
        department, phase, caller_cell, _, _ = cells
        caller_match = re.search(r"`([^`]+)`", caller_cell)
        if not caller_match:
            continue
        key = (department, phase)
        if key in routes:
            errors.append(f"phase-routing.md: 第 {line_number} 行重复阶段 {key!r}")
        routes[key] = caller_match.group(1)
    return routes, errors


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
    version = record.get("卡片版本", "")
    profile_references = re.findall(r"^- Profile引用：`([^`]+)`\s*$", text, re.M)
    if profile_references != [f"{profile_id}@{version}"]:
        errors.append(f"{label}: 当前项目短执行卡的 Profile引用必须精确等于 {profile_id}@{version}")
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
    expected_stages = contract.get("allowed_stage_by_department", DEFAULT_EXPECTED_STAGE)
    expected_expiry = contract.get("expiry_by_department", {})
    expected_inheritance = contract.get("inheritance_by_department", {})
    if department in expected_stages and record.get("适用阶段") != expected_stages[department]:
        errors.append(f"{label}: {department} 的适用阶段必须为 {expected_stages[department]!r}")
    if department in expected_expiry and record.get("Profile本体失效点") != expected_expiry[department]:
        errors.append(f"{label}: {department} 的 Profile本体失效点必须为 {expected_expiry[department]!r}")
    if department in expected_inheritance and record.get("可跨阶段继承") != expected_inheritance[department]:
        errors.append(f"{label}: {department} 的可跨阶段继承必须为 {expected_inheritance[department]!r}")
    if department in {"导演", "摄影指导"} and "- 双入口分流：" not in text:
        errors.append(f"{label}: {department} Profile 缺少双入口分流说明")

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
    phase_routing_path = references / "phase-routing.md"
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
        phase_routes, phase_errors = _parse_phase_routes(
            phase_routing_path.read_text(encoding="utf-8-sig")
        )
        errors.extend(phase_errors)
    except (OSError, UnicodeDecodeError) as exc:
        phase_routes = {}
        errors.append(f"无法读取 phase-routing.md：{exc}")
    if phase_routes != EXPECTED_PHASE_CALLERS:
        errors.append("phase-routing.md: 部门、允许阶段与责任Skill映射不完整或不一致")
    for (department, phase), caller in EXPECTED_PHASE_CALLERS.items():
        caller_path = library_root.parent / caller / "SKILL.md"
        try:
            caller_text = caller_path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError) as exc:
            errors.append(f"phase-routing.md: 无法读取责任Skill {caller}：{exc}")
            continue
        if phase not in caller_text or "Profile" not in caller_text:
            errors.append(f"phase-routing.md: {department} 的阶段 {phase} 未在责任Skill {caller} 中明确声明")

    try:
        sources_text = sources_path.read_text(encoding="utf-8-sig")
        known_sources, source_errors = _source_ids(sources_text)
        source_sections = _source_sections(sources_text)
        errors.extend(source_errors)
        for value in PROHIBITED_SOURCE_LOCATORS:
            if value in sources_text:
                errors.append(f"sources.md: 仍含外部历史定位要求：{value}")
    except OSError as exc:
        known_sources = set()
        source_sections = {}
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

    used_sources = {
        source_id
        for _, record in cards.values()
        for source_id in filter(None, record.get("来源ID", "").split("、"))
    }
    for source_id in sorted(used_sources):
        section = source_sections.get(source_id, "")
        snapshot_match = REPOSITORY_SNAPSHOT_PATTERN.search(section)
        if not snapshot_match:
            errors.append(f"sources.md: 卡片使用的来源 {source_id} 缺少仓库快照")
            continue
        snapshot_path = (references / snapshot_match.group(1)).resolve()
        try:
            snapshot_path.relative_to(references.resolve())
        except ValueError:
            errors.append(f"sources.md: {source_id} 的仓库快照越出 references 目录")
            continue
        if not snapshot_path.is_file():
            errors.append(f"sources.md: {source_id} 的仓库快照不存在：{snapshot_match.group(1)}")
        bad_locator = next((value for value in PROHIBITED_SOURCE_LOCATORS if value in section), None)
        if bad_locator:
            errors.append(f"sources.md: {source_id} 仍要求外部历史定位：{bad_locator}")

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
        definition_paths = item.get("definition_paths")
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
        if not isinstance(definition_paths, dict) or set(definition_paths) != set(versions):
            errors.append(f"profile-version-history.json: {profile_id} 的每个版本必须有且只有一个 definition_path")
        else:
            for version in versions:
                relative_path = definition_paths.get(version)
                if not isinstance(relative_path, str) or not relative_path:
                    errors.append(f"profile-version-history.json: {profile_id}@{version} 的 definition_path 无效")
                    continue
                definition_path = (references / relative_path).resolve()
                try:
                    definition_path.relative_to(references.resolve())
                except ValueError:
                    errors.append(f"profile-version-history.json: {profile_id}@{version} 的定义越出 references 目录")
                    continue
                if not definition_path.is_file():
                    errors.append(f"profile-version-history.json: {profile_id}@{version} 的定义文件不存在：{relative_path}")
                    continue
                try:
                    definition_text = definition_path.read_text(encoding="utf-8-sig")
                    definition_record, _, definition_errors = _extract_record(
                        definition_text, f"{profile_id}@{version}"
                    )
                except (OSError, UnicodeDecodeError) as exc:
                    errors.append(f"profile-version-history.json: 无法读取 {profile_id}@{version}：{exc}")
                    continue
                errors.extend(definition_errors)
                if definition_record.get("ProfileID") != profile_id:
                    errors.append(f"profile-version-history.json: {profile_id}@{version} 的定义 ProfileID 不一致")
                if definition_record.get("卡片版本") != version:
                    errors.append(f"profile-version-history.json: {profile_id}@{version} 的定义卡片版本不一致")
                definition_references = re.findall(
                    r"^- Profile引用：`([^`]+)`\s*$", definition_text, re.M
                )
                if definition_references != [f"{profile_id}@{version}"]:
                    errors.append(
                        f"profile-version-history.json: {profile_id}@{version} 的短执行卡Profile引用不一致"
                    )
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
        "phase_routes": len(phase_routes),
        "sources": len(known_sources),
        "errors": errors,
    }


def _render_report(result: dict[str, Any]) -> str:
    errors = result["errors"]
    lines = [
        "# Profile 资料库检查报告",
        "",
        "Schema版本：v1.1",
        f"Profile卡片数：{result['profiles']}",
        f"目录记录数：{result['catalog_rows']}",
        f"历史版本记录数：{result.get('history_rows', 0)}",
        f"阶段调用路由数：{result.get('phase_routes', 0)}",
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
            "本检查只证明卡片结构、阶段/失效/继承合同、字段取值、方法ID、成熟度/状态门槛、目录、历史定义和仓库来源快照一致；不证明作品归属、方法归因、创作者意图、AI适配效果或项目创作质量。",
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
