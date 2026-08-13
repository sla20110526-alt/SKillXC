#!/usr/bin/env python3
"""Atomically version and activate project creative-control index rows."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import re
import shutil
import sys
import uuid
from pathlib import Path
from typing import Any


SKILL_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SKILL_ROOT.parents[1]
VALIDATOR_PATH = SKILL_ROOT.parent / "production-router-handoff/scripts/validate_project_data.py"
SOURCE_CATALOG = SKILL_ROOT / "references/control-source-catalog.json"
PROFILE_CATALOG = SKILL_ROOT.parent / "film-profile-library/references/catalog.md"
PROFILE_HISTORY = SKILL_ROOT.parent / "film-profile-library/references/profile-version-history.json"
VERSION_RE = re.compile(r"^v([0-9]{3,})$")
SOURCE_REF_RE = re.compile(r"^(CCS-[A-Z0-9-]+)@(v[0-9]{3,})$")
PROFILE_REF_RE = re.compile(r"^(FP-[A-Z0-9-]+)@(v[0-9]+\.[0-9]+)$")
TRANSACTION_RE = re.compile(r"^CCV-[A-Z0-9-]+$")
TASK_ARTIFACT_REF_RE = re.compile(r"^[A-Z][A-Z0-9-]+@v[0-9]{3,}$")
BASELINE_INPUTS_BY_SOURCE = {
    "CCS-STYLE-LOCK@v001": (),
    "CCS-STYLE-LOCK@v002": (),
    "CCS-STYLE-LOCK@v003": (),
    "CCS-ART-LOOKDEV@v001": ("项目风格锁定基线",),
    "CCS-ART-LOOKDEV@v002": ("项目风格锁定基线",),
    "CCS-CINEMATOGRAPHY@v001": ("项目风格锁定基线", "美术LookDev基线"),
    "CCS-CINEMATOGRAPHY@v002": ("美术LookDev基线",),
    "CCS-LIGHTING@v001": ("项目风格锁定基线", "美术LookDev基线", "全片摄影规则"),
    "CCS-LIGHTING@v002": ("全片摄影规则",),
}


def _configure_utf8_stdio() -> None:
    """Keep CLI diagnostics machine-readable on Windows without env overrides."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="replace")


KINDS = {
    "baseline": {
        "default_index": "creative-control/项目创作基线索引.csv",
        "template": SKILL_ROOT / "assets/项目创作基线索引模板.csv",
        "schema": SKILL_ROOT / "assets/creative-control-baseline.schema.json",
        "id": "控制卡ID",
        "version": "项目卡版本",
        "previous": "上一项目卡版本",
        "status": "控制卡状态",
        "path": "控制卡路径",
        "source": "源定义引用",
        "profiles": "Profile引用集合",
        "input_refs": "输入控制卡引用集合",
        "fingerprint": "内容指纹SHA256",
        "subject": ("控制类型", "控制对象"),
        "status_label": "控制卡状态",
        "expected_source": {
            "项目风格锁定基线": "CCS-STYLE-LOCK",
            "美术LookDev基线": "CCS-ART-LOOKDEV",
            "全片摄影规则": "CCS-CINEMATOGRAPHY",
            "项目灯光基线": "CCS-LIGHTING",
        },
        "allowed_profile_prefixes": {
            "项目风格锁定基线": ("FP-DIR-",),
            "美术LookDev基线": ("FP-PD-",),
            "全片摄影规则": ("FP-CIN-",),
            "项目灯光基线": (),
        },
        "required_baseline_inputs": {
            "项目风格锁定基线": (),
            "美术LookDev基线": ("项目风格锁定基线",),
            "全片摄影规则": ("美术LookDev基线",),
            "项目灯光基线": ("全片摄影规则",),
        },
    },
    "acting": {
        "default_index": "creative-control/acting/角色表演母档表.csv",
        "template": SKILL_ROOT.parent / "acting-direction/assets/角色表演母档表模板.csv",
        "schema": SKILL_ROOT.parent / "acting-direction/assets/acting-master.schema.json",
        "id": "表演母档ID",
        "version": "母档版本",
        "previous": "上一母档版本",
        "status": "母档状态",
        "path": "母档卡路径",
        "source": "源定义引用",
        "profiles": None,
        "input_refs": None,
        "fingerprint": "内容指纹SHA256",
        "subject": ("角色ID",),
        "status_label": "母档状态",
        "expected_source": "CCS-ACTING-MASTER",
        "allowed_profile_prefixes": None,
        "required_baseline_inputs": None,
    },
    "voice": {
        "default_index": "creative-control/sound/角色声音身份表.csv",
        "template": SKILL_ROOT.parent / "sound-voice-direction/assets/角色声音身份表模板.csv",
        "schema": SKILL_ROOT.parent / "sound-voice-direction/assets/voice-identity.schema.json",
        "id": "声音身份卡ID",
        "version": "身份卡版本",
        "previous": "上一身份卡版本",
        "status": "身份卡状态",
        "path": "身份卡路径",
        "source": "源定义引用",
        "profiles": None,
        "input_refs": None,
        "fingerprint": "内容指纹SHA256",
        "subject": ("说话者ID",),
        "status_label": "身份卡状态",
        "expected_source": "CCS-VOICE-IDENTITY",
        "allowed_profile_prefixes": None,
        "required_baseline_inputs": None,
    },
}


class ControlVersionError(Exception):
    pass


def _load_validator() -> Any:
    spec = importlib.util.spec_from_file_location("validate_project_data", VALIDATOR_PATH)
    if spec is None or spec.loader is None:
        raise ControlVersionError(f"无法加载项目数据检查器：{VALIDATOR_PATH}")
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
        raise ControlVersionError(f"路径越出项目根目录：{resolved}") from exc
    return resolved


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.is_file():
        raise ControlVersionError(f"控制索引不存在：{path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ControlVersionError(f"控制索引缺少表头：{path}")
        return list(reader.fieldnames), [dict(row) for row in reader if any(row.values())]


def _write_csv(path: Path, headers: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers, extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


def _load_payload(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ControlVersionError(f"无法读取操作载荷：{exc}") from exc
    if not isinstance(value, dict):
        raise ControlVersionError("操作载荷顶层必须是对象")
    return value


def _required_text(payload: dict[str, Any], fields: tuple[str, ...]) -> None:
    missing = [field for field in fields if not isinstance(payload.get(field), str) or not payload[field]]
    if missing:
        raise ControlVersionError(f"操作载荷缺少非空字段：{missing}")
    if TRANSACTION_RE.fullmatch(str(payload["事务ID"])) is None:
        raise ControlVersionError("事务ID必须匹配 CCV-[A-Z0-9-]+")


def _version_number(value: str) -> int:
    match = VERSION_RE.fullmatch(value)
    if not match:
        raise ControlVersionError(f"项目控制版本无效：{value}")
    return int(match.group(1))


def _source_catalog() -> dict[str, dict[str, Any]]:
    payload = json.loads(SOURCE_CATALOG.read_text(encoding="utf-8-sig"))
    return {
        str(item["source_id"]): {
            "current": str(item["current_version"]),
            "available": {str(version) for version in item["available_versions"]},
        }
        for item in payload["sources"]
    }


def _profile_versions() -> dict[str, str]:
    result: dict[str, str] = {}
    for line in PROFILE_CATALOG.read_text(encoding="utf-8-sig").splitlines():
        if not line.startswith("| FP-"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) == 7:
            result[cells[0]] = cells[3]
    return result


def _profile_history() -> dict[str, set[str]]:
    payload = json.loads(PROFILE_HISTORY.read_text(encoding="utf-8-sig"))
    return {
        str(item["profile_id"]): {str(version) for version in item["available_versions"]}
        for item in payload["profiles"]
    }


def _split_refs(value: str) -> list[str]:
    if value in {"无", "不适用", ""}:
        return []
    values = value.split("；")
    if len(values) != len(set(values)):
        raise ControlVersionError(f"引用集合含重复值：{value}")
    return values


def _required_baseline_inputs(row: dict[str, str], config: dict[str, Any]) -> tuple[str, ...]:
    source_ref = row[config["source"]]
    required = BASELINE_INPUTS_BY_SOURCE.get(source_ref)
    if required is None:
        raise ControlVersionError(f"未定义该中央源版本的长期基线依赖契约：{source_ref}")
    return required


def _allows_consultant_field(row: dict[str, str]) -> bool:
    return row["源定义引用"] in {
        "CCS-STYLE-LOCK@v003",
        "CCS-ART-LOOKDEV@v002",
        "CCS-CINEMATOGRAPHY@v002",
        "CCS-LIGHTING@v002",
    }


FINGERPRINT_IGNORED_PREFIXES = (
    "项目卡版本：",
    "上一项目卡版本：",
    "母档版本：",
    "上一母档版本：",
    "身份卡版本：",
    "上一身份卡版本：",
    "控制卡状态：",
    "母档状态：",
    "身份卡状态：",
    "当前有效：",
    "内容变更摘要：",
    "状态依据类型：",
    "状态依据原文：",
    "生效依据原文：",
    "记录日期：",
    "生效日期：",
    "控制卡路径：",
    "母档卡路径：",
    "身份卡路径：",
    "项目创作基线索引路径：",
    "表演母档表路径：",
    "声音身份表路径：",
    "内容指纹SHA256：",
    "校验报告路径：",
    "校验结论：",
)


def _semantic_fingerprint(path: Path) -> str:
    lines: list[str] = []
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.rstrip()
        if any(line.startswith(prefix) for prefix in FINGERPRINT_IGNORED_PREFIXES):
            continue
        lines.append(line)
    normalized = "\n".join(lines).strip() + "\n"
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _metadata_values(row: dict[str, str], config: dict[str, Any]) -> dict[str, str]:
    return {
        config["status_label"]: row[config["status"]],
        "当前有效": row["当前有效"],
        "状态依据类型": row["状态依据类型"],
        "状态依据原文": row["状态依据原文"],
        "生效依据原文": row["生效依据原文"],
        "生效日期": row["生效日期"],
    }


def _validate_card_metadata(path: Path, row: dict[str, str], config: dict[str, Any]) -> None:
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    for label, value in _metadata_values(row, config).items():
        matches = [line for line in lines if line.startswith(f"{label}：")]
        if len(matches) != 1:
            raise ControlVersionError(f"{path} 必须且只能包含一行 {label}")
        if matches[0] != f"{label}：{value}":
            raise ControlVersionError(f"{path} 的 {label} 与索引不一致")


def _write_card_metadata(source: Path, target: Path, row: dict[str, str], config: dict[str, Any]) -> None:
    text = source.read_text(encoding="utf-8-sig")
    for label, value in _metadata_values(row, config).items():
        pattern = re.compile(rf"(?m)^{re.escape(label)}：.*$")
        if len(pattern.findall(text)) != 1:
            raise ControlVersionError(f"{source} 必须且只能包含一行 {label}")
        text = pattern.sub(f"{label}：{value}", text)
    target.write_text(text, encoding="utf-8")


def _validate_source_and_profiles(row: dict[str, str], config: dict[str, Any]) -> None:
    source_ref = row[config["source"]]
    match = SOURCE_REF_RE.fullmatch(source_ref)
    if not match:
        raise ControlVersionError(f"中央源引用无效：{source_ref}")
    source_id, version = match.groups()
    known_sources = _source_catalog()
    if version not in known_sources.get(source_id, {}).get("available", set()):
        raise ControlVersionError(f"中央源引用不存在：{source_ref}")
    expected_source = config["expected_source"]
    if isinstance(expected_source, dict):
        expected_source = expected_source.get(row.get("控制类型"))
    if source_id != expected_source:
        raise ControlVersionError(
            f"控制类型与中央源定义不对应：应为 {expected_source}，实际为 {source_id}"
        )
    if config["profiles"]:
        known_profiles = _profile_versions()
        profile_history = _profile_history()
        profile_references = _split_refs(row[config["profiles"]])
        allowed_prefixes = config["allowed_profile_prefixes"].get(row.get("控制类型"), ())
        if profile_references and not allowed_prefixes:
            raise ControlVersionError(f"{row.get('控制类型')} 不允许直接引用Profile")
        for reference in profile_references:
            profile_match = PROFILE_REF_RE.fullmatch(reference)
            if not profile_match:
                raise ControlVersionError(f"Profile引用无效：{reference}")
            profile_id, profile_version = profile_match.groups()
            if allowed_prefixes and not profile_id.startswith(allowed_prefixes):
                raise ControlVersionError(
                    f"{row.get('控制类型')} 的Profile专业部门不匹配：{profile_id}"
                )
            current = known_profiles.get(profile_id)
            if current is None:
                raise ControlVersionError(f"ProfileID不存在：{profile_id}")
            if profile_version not in profile_history.get(profile_id, set()):
                raise ControlVersionError(f"Profile引用的版本没有历史记录（可能尚未发布）：{reference}")
    if config["input_refs"]:
        for reference in _split_refs(row[config["input_refs"]]):
            if re.fullmatch(r"[A-Z][A-Z0-9-]+@v[0-9]{3,}", reference) is None:
                raise ControlVersionError(f"输入控制卡引用必须精确到 ID@v###：{reference}")
        for reference in _split_refs(row["顾问任务成果引用集合"]):
            if TASK_ARTIFACT_REF_RE.fullmatch(reference) is None:
                raise ControlVersionError(f"顾问任务成果引用必须精确到成果 ID@v###：{reference}")


def _validate_business(
    rows: list[dict[str, str]],
    project_id: str,
    config: dict[str, Any],
    check_card_metadata: bool,
) -> None:
    grouped: dict[str, list[dict[str, str]]] = {}
    subject_ids: dict[tuple[str, ...], str] = {}
    subject_active: dict[tuple[str, ...], list[str]] = {}
    for row in rows:
        if row["项目ID"] != project_id:
            raise ControlVersionError(f"发现其他项目数据：{row['项目ID']}")
        _validate_source_and_profiles(row, config)
        if config["required_baseline_inputs"] is not None:
            consultant_refs = row["顾问任务成果引用集合"]
            if _allows_consultant_field(row):
                if not consultant_refs:
                    raise ControlVersionError("当前风格基线源必须填写顾问任务成果引用集合；无顾问时写无")
            elif consultant_refs not in {"", "不适用"}:
                raise ControlVersionError("历史风格基线源版本不能补写当时不存在的顾问任务成果字段")
        if config["id"] == "声音身份卡ID":
            person_reference = row.get("关联人物正式资产ID与版本", "")
            creature_reference = row.get("关联生物怪物正式资产ID与版本", "")
            if person_reference not in {"", "无"} and creature_reference not in {"", "无"}:
                raise ControlVersionError("声音身份卡不能同时关联人物和生物怪物正式资产")
        card_id = row[config["id"]]
        subject = tuple(row[field] for field in config["subject"])
        if subject in subject_ids and subject_ids[subject] != card_id:
            raise ControlVersionError(
                f"同一控制对象使用了不同稳定ID：{subject} -> {subject_ids[subject]} / {card_id}"
            )
        subject_ids[subject] = card_id
        grouped.setdefault(card_id, []).append(row)
        status = row[config["status"]]
        active = row["当前有效"]
        if (status == "已生效") != (active == "是"):
            raise ControlVersionError(f"{card_id}@{row[config['version']]} 的状态与当前有效不一致")
        if active == "是":
            subject_active.setdefault(subject, []).append(f"{card_id}@{row[config['version']]}")
        card_path = _resolve_inside(Path(row["__project_root"]), row[config["path"]]) if "__project_root" in row else None
        if card_path is not None and not card_path.is_file():
            raise ControlVersionError(f"控制卡文件不存在：{card_path}")
        if card_path is not None:
            expected_fingerprint = _semantic_fingerprint(card_path)
            if row[config["fingerprint"]] != expected_fingerprint:
                raise ControlVersionError(
                    f"{card_id}@{row[config['version']]} 的内容指纹与卡片文件不一致"
                )
            if check_card_metadata:
                _validate_card_metadata(card_path, row, config)
    for card_id, versions in grouped.items():
        numbers = sorted(_version_number(row[config["version"]]) for row in versions)
        if numbers != list(range(1, max(numbers) + 1)):
            raise ControlVersionError(f"{card_id} 的项目版本不连续：{numbers}")
        if sum(row["当前有效"] == "是" for row in versions) > 1:
            raise ControlVersionError(f"{card_id} 存在多个当前有效版本")
        by_number = {_version_number(row[config["version"]]): row for row in versions}
        for number, row in by_number.items():
            expected = "不适用" if number == 1 else f"v{number - 1:03d}"
            if row[config["previous"]] != expected:
                raise ControlVersionError(
                    f"{card_id}@{row[config['version']]} 的上一版本应为 {expected}"
                )
    for subject, active_versions in subject_active.items():
        if len(active_versions) > 1:
            raise ControlVersionError(f"同一控制对象存在多个当前有效版本：{subject} -> {active_versions}")
    if config["required_baseline_inputs"] is not None:
        by_reference = {
            f"{row[config['id']]}@{row[config['version']]}": row
            for row in rows
        }
        for row in rows:
            references = _split_refs(row[config["input_refs"]])
            if f"{row[config['id']]}@{row[config['version']]}" in references:
                raise ControlVersionError(f"{row[config['id']]} 不得引用自身")
            linked_baselines = [by_reference[reference] for reference in references if reference in by_reference]
            required_types = _required_baseline_inputs(row, config)
            linked_types = [item["控制类型"] for item in linked_baselines]
            invalid_types = [control_type for control_type in linked_types if control_type not in required_types]
            if invalid_types:
                raise ControlVersionError(
                    f"{row[config['id']]}@{row[config['version']]} 引用了下游或不允许的项目基线：{invalid_types}"
                )
            invalid_counts = [control_type for control_type in required_types if linked_types.count(control_type) != 1]
            if invalid_counts:
                raise ControlVersionError(
                    f"{row[config['id']]}@{row[config['version']]} 的上游基线精确引用数量不为一：{invalid_counts}"
                )
            if row["当前有效"] == "是":
                inactive_links = [
                    f"{item[config['id']]}@{item[config['version']]}"
                    for item in linked_baselines
                    if item["当前有效"] != "是" or item[config["status"]] != "已生效"
                ]
                if inactive_links:
                    raise ControlVersionError(
                        f"当前生效基线引用了非当前生效的上游版本：{inactive_links}"
                    )


def _schema_check(path: Path, schema: Path, project_id: str) -> None:
    result = VALIDATOR._check_pair(path, schema, project_id, None, True)
    if result["errors"]:
        raise ControlVersionError("Schema检查失败：\n" + "\n".join(result["errors"]))


def _validate_index(
    path: Path,
    project_id: str,
    config: dict[str, Any],
    project_root: Path,
    check_card_metadata: bool = True,
) -> None:
    _schema_check(path, config["schema"], project_id)
    _, rows = _read_csv(path)
    working = [dict(row, __project_root=str(project_root)) for row in rows]
    _validate_business(working, project_id, config, check_card_metadata)


def _draft(payload: dict[str, Any], rows: list[dict[str, str]], config: dict[str, Any], project_root: Path) -> dict[str, Any]:
    _required_text(payload, ("项目ID", "事务ID", "操作日期"))
    candidates = payload.get("记录")
    if not isinstance(candidates, list) or not candidates or not all(isinstance(item, dict) for item in candidates):
        raise ControlVersionError("草案载荷的“记录”必须是非空对象数组")
    existing = {(row[config["id"]], row[config["version"]]) for row in rows}
    added: list[str] = []
    for raw in candidates:
        row = {key: str(value) for key, value in raw.items()}
        if row.get("项目ID") != payload["项目ID"]:
            raise ControlVersionError("草案记录项目ID与载荷不一致")
        card_id = row.get(config["id"], "")
        version = row.get(config["version"], "")
        if (card_id, version) in existing:
            raise ControlVersionError(f"项目控制版本已存在：{card_id}@{version}")
        same = [item for item in rows if item[config["id"]] == card_id]
        expected_number = 1 if not same else max(_version_number(item[config["version"]]) for item in same) + 1
        if _version_number(version) != expected_number:
            raise ControlVersionError(f"{card_id} 的新版本必须为 v{expected_number:03d}")
        expected_previous = "不适用" if expected_number == 1 else f"v{expected_number - 1:03d}"
        if row.get(config["previous"]) != expected_previous:
            raise ControlVersionError(f"{card_id}@{version} 的上一版本必须为 {expected_previous}")
        if row.get(config["status"]) != "待确认" or row.get("当前有效") != "否":
            raise ControlVersionError("新项目控制草案必须为 待确认 + 当前有效=否")
        if row.get("状态依据类型") != "系统草案":
            raise ControlVersionError("新项目控制草案的状态依据类型必须为系统草案")
        card_path = _resolve_inside(project_root, row.get(config["path"], ""))
        if not card_path.is_file():
            raise ControlVersionError(f"草案卡片文件不存在：{card_path}")
        fingerprint = _semantic_fingerprint(card_path)
        if row.get(config["fingerprint"]) not in {"", fingerprint}:
            raise ControlVersionError(f"草案载荷中的内容指纹与卡片文件不一致：{card_path}")
        row[config["fingerprint"]] = fingerprint
        latest_existing = (
            max(same, key=lambda item: _version_number(item[config["version"]]))
            if same
            else None
        )
        if latest_existing is not None and fingerprint == latest_existing[config["fingerprint"]]:
            raise ControlVersionError(f"{card_id} 的语义内容未变化，不得建立新项目版本")
        _validate_source_and_profiles(row, config)
        source_match = SOURCE_REF_RE.fullmatch(row[config["source"]])
        assert source_match is not None
        source_id, source_version = source_match.groups()
        if _source_catalog()[source_id]["current"] != source_version:
            raise ControlVersionError(f"新草案必须引用中央目录当前源版本：{row[config['source']]}")
        if config["required_baseline_inputs"] is not None:
            known_rows = {
                f"{item[config['id']]}@{item[config['version']]}": item
                for item in rows
            }
            input_references = _split_refs(row[config["input_refs"]])
            required_types = _required_baseline_inputs(row, config)
            for required_type in required_types:
                matches = [
                    known_rows[reference]
                    for reference in input_references
                    if reference in known_rows and known_rows[reference]["控制类型"] == required_type
                ]
                if len(matches) != 1:
                    raise ControlVersionError(f"新草案必须精确引用一张{required_type}当前生效版")
                if matches[0]["当前有效"] != "是" and matches[0][config["status"]] != "待确认":
                    raise ControlVersionError(f"新草案引用的{required_type}不是当前生效版或待确认新链")
            known_input_references = [reference for reference in input_references if reference in known_rows]
            if len(known_input_references) != len(input_references):
                unknown = [reference for reference in input_references if reference not in known_rows]
                raise ControlVersionError(f"长期基线输入集合只能引用本项目已入表的直接上游控制卡：{unknown}")
        rows.append(row)
        existing.add((card_id, version))
        added.append(f"{card_id}@{version}")
    return {"新增待确认版本": added}


def _targets(payload: dict[str, Any]) -> list[dict[str, str]]:
    raw = payload.get("目标")
    if not isinstance(raw, list) or not raw or not all(isinstance(item, dict) for item in raw):
        raise ControlVersionError("状态操作的“目标”必须是非空对象数组")
    result = [{key: str(value) for key, value in item.items()} for item in raw]
    if any(not item.get("卡片ID") or not item.get("版本") for item in result):
        raise ControlVersionError("每个目标必须包含卡片ID和版本")
    if len({(item["卡片ID"], item["版本"]) for item in result}) != len(result):
        raise ControlVersionError("状态操作目标重复")
    if len({item["卡片ID"] for item in result}) != len(result):
        raise ControlVersionError("一次状态事务不能同时选择同一控制卡的多个版本")
    return result


def _activate(payload: dict[str, Any], rows: list[dict[str, str]], config: dict[str, Any]) -> dict[str, Any]:
    _required_text(payload, ("项目ID", "事务ID", "操作日期", "用户操作原文"))
    targets = _targets(payload)
    index = {(row[config["id"]], row[config["version"]]): row for row in rows}
    selected: list[dict[str, str]] = []
    for target in targets:
        row = index.get((target["卡片ID"], target["版本"]))
        if row is None or row[config["status"]] != "待确认" or row["当前有效"] != "否":
            raise ControlVersionError(f"目标不存在或不是待确认版本：{target}")
        selected.append(row)
    activated: list[str] = []
    replaced: list[str] = []
    changed: list[tuple[str, str]] = []
    for target in selected:
        card_id = target[config["id"]]
        for row in rows:
            if row[config["id"]] == card_id and row["当前有效"] == "是":
                row[config["status"]] = "已替代"
                row["当前有效"] = "否"
                row["状态依据类型"] = "版本替代"
                row["状态依据原文"] = f"被 {card_id}@{target[config['version']]} 替代；事务 {payload['事务ID']}"
                replaced.append(f"{card_id}@{row[config['version']]}")
                changed.append((card_id, row[config["version"]]))
        target[config["status"]] = "已生效"
        target["当前有效"] = "是"
        target["状态依据类型"] = "用户明确确认"
        target["状态依据原文"] = str(payload["用户操作原文"])
        target["生效依据原文"] = str(payload["用户操作原文"])
        target["生效日期"] = str(payload["操作日期"])
        activated.append(f"{card_id}@{target[config['version']]}")
        changed.append((card_id, target[config["version"]]))
    return {"已生效版本": activated, "已替代版本": replaced, "_changed": changed}


def _would_break_active_dependents(
    rows: list[dict[str, str]],
    target_keys: set[tuple[str, str]],
    config: dict[str, Any],
) -> list[str]:
    if config["required_baseline_inputs"] is None:
        return []
    target_references = {f"{card_id}@{version}" for card_id, version in target_keys}
    broken: list[str] = []
    for row in rows:
        key = (row[config["id"]], row[config["version"]])
        if key in target_keys or row["当前有效"] != "是":
            continue
        if target_references.intersection(_split_refs(row[config["input_refs"]])):
            broken.append(f"{row[config['id']]}@{row[config['version']]}")
    return broken


def _invalidate(payload: dict[str, Any], rows: list[dict[str, str]], config: dict[str, Any]) -> dict[str, Any]:
    _required_text(payload, ("项目ID", "事务ID", "操作日期", "用户操作原文"))
    targets = _targets(payload)
    index = {(row[config["id"]], row[config["version"]]): row for row in rows}
    target_keys = {(target["卡片ID"], target["版本"]) for target in targets}
    broken = _would_break_active_dependents(rows, target_keys, config)
    if broken:
        raise ControlVersionError(f"停用会留下引用已失效上游的当前生效下游；必须把完整受影响链一起停用：{broken}")
    invalidated: list[str] = []
    changed: list[tuple[str, str]] = []
    for target in targets:
        row = index.get((target["卡片ID"], target["版本"]))
        if row is None or row[config["status"]] in {"已替代", "已失效"}:
            raise ControlVersionError(f"目标不存在或已不可停用：{target}")
        row[config["status"]] = "已失效"
        row["当前有效"] = "否"
        row["状态依据类型"] = "用户明确停用"
        row["状态依据原文"] = str(payload["用户操作原文"])
        invalidated.append(f"{target['卡片ID']}@{target['版本']}")
        changed.append((target["卡片ID"], target["版本"]))
    return {"已失效版本": invalidated, "自动恢复旧版": [], "_changed": changed}


def _write_transaction(
    project_root: Path,
    index_path: Path,
    headers: list[str],
    rows: list[dict[str, str]],
    project_id: str,
    transaction_id: str,
    config: dict[str, Any],
    changed_keys: list[tuple[str, str]],
) -> Path:
    token = uuid.uuid4().hex
    temp = index_path.with_name(f".{index_path.stem}.{token}.tmp{index_path.suffix}")
    staged_cards: dict[Path, Path] = {}
    backup_dir = project_root / "creative-control/backups" / transaction_id
    try:
        _write_csv(temp, headers, rows)
        _validate_index(temp, project_id, config, project_root, check_card_metadata=False)
        row_index = {(row[config["id"]], row[config["version"]]): row for row in rows}
        for key in set(changed_keys):
            row = row_index[key]
            original_card = _resolve_inside(project_root, row[config["path"]])
            staged_card = original_card.with_name(f".{original_card.stem}.{token}.tmp{original_card.suffix}")
            _write_card_metadata(original_card, staged_card, row, config)
            if _semantic_fingerprint(staged_card) != row[config["fingerprint"]]:
                raise ControlVersionError(f"卡片状态更新意外改变了语义内容：{original_card}")
            staged_cards[original_card] = staged_card
        if backup_dir.exists():
            raise ControlVersionError(f"备份目录已存在，事务ID必须唯一：{backup_dir}")
        backup_dir.mkdir(parents=True)
        backup = backup_dir / index_path.name
        shutil.copyfile(index_path, backup)
        card_backups: dict[Path, Path] = {}
        for original_card in staged_cards:
            relative = original_card.relative_to(project_root)
            card_backup = backup_dir / relative
            card_backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(original_card, card_backup)
            card_backups[original_card] = card_backup
        replaced_paths: list[Path] = []
        try:
            temp.replace(index_path)
            replaced_paths.append(index_path)
            for original_card, staged_card in staged_cards.items():
                staged_card.replace(original_card)
                replaced_paths.append(original_card)
            _validate_index(index_path, project_id, config, project_root)
        except Exception:
            if index_path in replaced_paths:
                shutil.copyfile(backup, index_path)
            for original_card, card_backup in card_backups.items():
                if original_card in replaced_paths:
                    shutil.copyfile(card_backup, original_card)
            raise
        return backup_dir
    finally:
        temp.unlink(missing_ok=True)
        for staged_card in staged_cards.values():
            staged_card.unlink(missing_ok=True)


def _run(args: argparse.Namespace) -> dict[str, Any]:
    config = KINDS[args.kind]
    project_root = Path(args.project_root).resolve()
    if not project_root.is_dir():
        raise ControlVersionError(f"项目数据根目录不存在：{project_root}")
    index_path = _resolve_inside(project_root, args.index or config["default_index"])
    if args.command == "init":
        if index_path.exists():
            _validate_index(index_path, args.project_id, config, project_root)
            return {
                "项目ID": args.project_id,
                "索引种类": args.kind,
                "初始化结论": "已存在并通过检查",
            }
        index_path.parent.mkdir(parents=True, exist_ok=True)
        temp = index_path.with_name(f".{index_path.stem}.{uuid.uuid4().hex}.tmp{index_path.suffix}")
        try:
            shutil.copyfile(config["template"], temp)
            _validate_index(temp, args.project_id, config, project_root)
            temp.replace(index_path)
            _validate_index(index_path, args.project_id, config, project_root)
        finally:
            temp.unlink(missing_ok=True)
        return {
            "项目ID": args.project_id,
            "索引种类": args.kind,
            "初始化结论": "已初始化空索引",
            "索引路径": str(index_path),
        }
    headers, rows = _read_csv(index_path)
    if args.command == "check":
        _validate_index(index_path, args.project_id, config, project_root)
        return {"项目ID": args.project_id, "索引种类": args.kind, "检查结论": "通过"}
    payload = _load_payload(Path(args.payload).resolve())
    project_id = str(payload.get("项目ID", ""))
    _validate_index(index_path, project_id, config, project_root)
    if args.command == "draft":
        result = _draft(payload, rows, config, project_root)
    elif args.command == "activate":
        result = _activate(payload, rows, config)
    else:
        result = _invalidate(payload, rows, config)
    changed_keys = list(result.pop("_changed", []))
    backup_dir = _write_transaction(
        project_root,
        index_path,
        headers,
        rows,
        project_id,
        str(payload["事务ID"]),
        config,
        changed_keys,
    )
    return {
        "项目ID": project_id,
        "索引种类": args.kind,
        **result,
        "备份目录": str(backup_dir),
        "写入结论": "通过",
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="原子更新项目创作控制版本与生效状态")
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("init", "check", "draft", "activate", "invalidate"):
        sub = commands.add_parser(command)
        sub.add_argument("--kind", required=True, choices=sorted(KINDS))
        sub.add_argument("--project-root", required=True)
        sub.add_argument("--index")
        if command in {"init", "check"}:
            sub.add_argument("--project-id", required=True)
        else:
            sub.add_argument("--payload", required=True)
    return parser.parse_args()


def main() -> int:
    _configure_utf8_stdio()
    try:
        result = _run(_parse_args())
    except (ControlVersionError, OSError, csv.Error, json.JSONDecodeError) as exc:
        print(f"创作控制版本事务失败：{exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
