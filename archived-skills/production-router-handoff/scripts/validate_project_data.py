#!/usr/bin/env python3
"""Validate project CSV/JSON records against the repository's JSON Schema subset."""

from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CONTRACT_VERSION = "v0.1"
SUPPORTED_TOP_LEVEL_KEYS = {
    "$schema",
    "title",
    "description",
    "type",
    "required",
    "properties",
    "additionalProperties",
}
SUPPORTED_PROPERTY_KEYS = {
    "type",
    "enum",
    "minLength",
    "pattern",
    "minimum",
    "exclusiveMinimum",
    "description",
}
SUPPORTED_TYPES = {"null", "string", "boolean", "integer", "number", "object", "array"}


def _configure_utf8_stdio() -> None:
    """Keep CLI diagnostics machine-readable on Windows without env overrides."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="replace")


def _schema_types(spec: dict[str, Any]) -> list[str]:
    value = spec.get("type")
    if isinstance(value, str):
        return [value]
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return value
    return []


def _coerce_csv_value(raw: str, spec: dict[str, Any]) -> Any:
    types = _schema_types(spec)
    if raw == "" and "null" in types:
        return None
    if "integer" in types and re.fullmatch(r"[-+]?\d+", raw):
        return int(raw)
    if "number" in types:
        try:
            return float(raw)
        except ValueError:
            pass
    if "boolean" in types and raw.lower() in {"true", "false"}:
        return raw.lower() == "true"
    return raw


def _type_matches(value: Any, expected: str) -> bool:
    if expected == "null":
        return value is None
    if expected == "string":
        return isinstance(value, str)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    return False


def _validate_schema_shape(schema: dict[str, Any], label: str) -> list[str]:
    errors: list[str] = []
    unknown_top_level = set(schema) - SUPPORTED_TOP_LEVEL_KEYS
    if unknown_top_level:
        errors.append(f"{label}: 检查器不支持顶层关键字 {sorted(unknown_top_level)!r}")
    if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
        errors.append(f"{label}: $schema 必须为 Draft 2020-12")
    if schema.get("type") != "object":
        errors.append(f"{label}: 顶层 type 必须为 object")
    properties = schema.get("properties")
    if not isinstance(properties, dict) or not properties:
        errors.append(f"{label}: properties 必须是非空对象")
        return errors
    required = schema.get("required", [])
    if not isinstance(required, list) or any(item not in properties for item in required):
        errors.append(f"{label}: required 含有未知字段或不是数组")
    if schema.get("additionalProperties") is not False:
        errors.append(f"{label}: additionalProperties 必须为 false")
    for field, spec in properties.items():
        if not isinstance(spec, dict):
            errors.append(f"{label}.{field}: 字段定义必须是对象")
            continue
        unknown_property = set(spec) - SUPPORTED_PROPERTY_KEYS
        if unknown_property:
            errors.append(f"{label}.{field}: 检查器不支持关键字 {sorted(unknown_property)!r}")
        types = _schema_types(spec)
        if not types or any(item not in SUPPORTED_TYPES for item in types):
            errors.append(f"{label}.{field}: type 缺失或包含不支持的类型")
        if "pattern" in spec:
            try:
                re.compile(spec["pattern"])
            except (re.error, TypeError) as exc:
                errors.append(f"{label}.{field}: pattern 无效：{exc}")
    return errors


def _validate_value(value: Any, spec: dict[str, Any], location: str) -> list[str]:
    errors: list[str] = []
    types = _schema_types(spec)
    if types and not any(_type_matches(value, item) for item in types):
        return [f"{location}: 类型应为 {'/'.join(types)}，实际为 {type(value).__name__}"]
    if value is None:
        return errors
    if "enum" in spec and value not in spec["enum"]:
        errors.append(f"{location}: 值 {value!r} 不在允许集合 {spec['enum']!r}")
    if isinstance(value, str):
        if "minLength" in spec and len(value) < spec["minLength"]:
            errors.append(f"{location}: 字符长度小于 {spec['minLength']}")
        if "pattern" in spec and re.search(spec["pattern"], value) is None:
            errors.append(f"{location}: 值 {value!r} 不匹配 {spec['pattern']!r}")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in spec and value < spec["minimum"]:
            errors.append(f"{location}: 数值必须大于等于 {spec['minimum']}")
        if "exclusiveMinimum" in spec and value <= spec["exclusiveMinimum"]:
            errors.append(f"{location}: 数值必须大于 {spec['exclusiveMinimum']}")
    return errors


def _validate_record(record: dict[str, Any], schema: dict[str, Any], location: str) -> list[str]:
    errors: list[str] = []
    properties = schema["properties"]
    for field in schema.get("required", []):
        if field not in record:
            errors.append(f"{location}.{field}: 缺少必填字段")
    if schema.get("additionalProperties") is False:
        for field in record:
            if field not in properties:
                errors.append(f"{location}.{field}: Schema 未定义此字段")
    for field, value in record.items():
        if field in properties:
            errors.extend(_validate_value(value, properties[field], f"{location}.{field}"))
    return errors


def _validate_csv(
    path: Path,
    schema: dict[str, Any],
    expected_project_id: str | None,
    require_project_id: bool,
) -> tuple[int, int, list[str]]:
    errors: list[str] = []
    failed_rows = 0
    properties = schema["properties"]
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        try:
            headers = next(reader)
        except StopIteration:
            return 0, 0, [f"{path}: CSV 为空，缺少表头"]
        if len(headers) != len(set(headers)):
            errors.append(f"{path}: CSV 表头存在重复字段")
        expected_headers = list(properties)
        if headers != expected_headers:
            errors.append(
                f"{path}: 表头与 Schema properties 的名称或顺序不一致；"
                f"期望 {expected_headers!r}，实际 {headers!r}"
            )
        if require_project_id and "项目ID" not in headers:
            errors.append(f"{path}: 项目数据 CSV 缺少 项目ID 列")
        row_count = 0
        for line_number, values in enumerate(reader, start=2):
            if not values or all(value == "" for value in values):
                continue
            row_count += 1
            if len(values) != len(headers):
                errors.append(f"{path}: 第 {line_number} 行列数为 {len(values)}，表头列数为 {len(headers)}")
                failed_rows += 1
                continue
            raw_record = dict(zip(headers, values))
            record = {
                field: _coerce_csv_value(raw, properties.get(field, {}))
                for field, raw in raw_record.items()
            }
            row_errors = _validate_record(record, schema, f"{path}:第{line_number}行")
            if expected_project_id is not None and "项目ID" in record:
                if record["项目ID"] != expected_project_id:
                    row_errors.append(
                        f"{path}:第{line_number}行.项目ID: "
                        f"应为 {expected_project_id!r}，实际为 {record['项目ID']!r}"
                    )
            if row_errors:
                failed_rows += 1
                errors.extend(row_errors)
    return row_count, failed_rows, errors


def _validate_json(
    path: Path,
    schema: dict[str, Any],
    expected_project_id: str | None,
    require_project_id: bool,
) -> tuple[int, int, list[str]]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    records = payload if isinstance(payload, list) else [payload]
    errors: list[str] = []
    failed_rows = 0
    for index, record in enumerate(records, start=1):
        record_errors: list[str] = []
        if not isinstance(record, dict):
            errors.append(f"{path}:记录{index}: 必须是对象")
            failed_rows += 1
            continue
        record_errors.extend(_validate_record(record, schema, f"{path}:记录{index}"))
        if require_project_id and "项目ID" not in record:
            record_errors.append(f"{path}:记录{index}: 项目数据缺少 项目ID")
        if expected_project_id is not None and "项目ID" in record:
            if record["项目ID"] != expected_project_id:
                record_errors.append(f"{path}:记录{index}.项目ID 与 --project-id 不一致")
        if record_errors:
            failed_rows += 1
            errors.extend(record_errors)
    return len(records), failed_rows, errors


def _resolve(path_value: str, root: Path) -> Path:
    path = Path(path_value)
    return path if path.is_absolute() else (root / path).resolve()


def _check_pair(
    input_path: Path,
    schema_path: Path,
    project_id: str | None,
    card_path: Path | None = None,
    require_project_id: bool = False,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "input": str(input_path),
        "schema": str(schema_path),
        "card": str(card_path) if card_path else None,
        "rows": 0,
        "passed_rows": 0,
        "failed_rows": 0,
        "errors": [],
    }
    if card_path is not None:
        if not card_path.is_file():
            result["errors"].append(f"Markdown 卡片模板不存在：{card_path}")
        else:
            try:
                card_text = card_path.read_text(encoding="utf-8-sig")
            except (OSError, UnicodeDecodeError) as exc:
                result["errors"].append(f"无法读取 Markdown 卡片模板 {card_path}: {exc}")
            else:
                for marker in ("对应Schema", "数据契约版本", "校验报告"):
                    if marker not in card_text:
                        result["errors"].append(f"{card_path}: 缺少三层契约标记 {marker}")
                if schema_path.name not in card_text:
                    result["errors"].append(f"{card_path}: 未引用对应 Schema {schema_path.name}")
    if not input_path.is_file():
        result["errors"].append(f"输入文件不存在：{input_path}")
        return result
    if not schema_path.is_file():
        result["errors"].append(f"Schema 不存在：{schema_path}")
        return result
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        result["errors"].append(f"无法读取 Schema {schema_path}: {exc}")
        return result
    shape_errors = _validate_schema_shape(schema, str(schema_path))
    if shape_errors:
        result["errors"].extend(shape_errors)
        return result
    try:
        if input_path.suffix.lower() == ".csv":
            rows, failed_rows, errors = _validate_csv(input_path, schema, project_id, require_project_id)
        elif input_path.suffix.lower() == ".json":
            rows, failed_rows, errors = _validate_json(input_path, schema, project_id, require_project_id)
        else:
            rows, failed_rows, errors = 0, 0, [f"不支持的输入格式：{input_path.suffix}"]
        result["rows"] = rows
        result["failed_rows"] = failed_rows
        result["passed_rows"] = rows - failed_rows
        result["errors"].extend(errors)
    except (OSError, csv.Error, json.JSONDecodeError) as exc:
        result["errors"].append(f"无法读取输入 {input_path}: {exc}")
    return result


def _render_report(
    results: list[dict[str, Any]],
    project_id: str | None,
    pair_count: int | None = None,
) -> str:
    total_rows = sum(item["rows"] for item in results)
    passed_rows = sum(item["passed_rows"] for item in results)
    failed_rows = sum(item["failed_rows"] for item in results)
    errors = [error for item in results for error in item["errors"]]
    lines = [
        "# 数据校验报告",
        "",
        f"数据契约版本：{CONTRACT_VERSION}",
        f"检查时间（UTC）：{datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        f"项目ID：{project_id or '模板检查/未指定'}",
        f"输入数据文件数：{len(results)}",
        f"检查配对数：{pair_count or len(results)}",
        f"数据行数：{total_rows}",
        f"通过行数：{passed_rows}",
        f"失败行数：{failed_rows}",
        f"结论：{'通过' if not errors else '未通过'}",
        "",
        "## 文件结果",
        "",
    ]
    for item in results:
        lines.extend(
            [
                f"- 输入：`{item['input']}`",
                f"  - Markdown卡片：`{item['card']}`" if item["card"] else "  - Markdown卡片：由当前任务提供",
                f"  - Schema：`{item['schema']}`",
                f"  - 数据行：{item['rows']}",
                f"  - 通过行：{item['passed_rows']}",
                f"  - 失败行：{item['failed_rows']}",
                f"  - 结果：{'通过' if not item['errors'] else '未通过'}",
            ]
        )
    lines.extend(["", "## 错误", ""])
    lines.extend([f"- {error}" for error in errors] or ["- 无"])
    lines.extend(
        [
            "",
            "## 未覆盖的业务复核",
            "",
            "本报告只验证结构、字段取值和可选的项目 ID 一致性；不代替批准授权、跨表引用、父子依赖、版本有效性和创作质量复核。",
            "",
        ]
    )
    return "\n".join(lines)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="检查项目 CSV/JSON 与 JSON Schema 的一致性")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--manifest", help="仓库数据契约映射 JSON")
    mode.add_argument("--input", help="待检查的项目 CSV 或 JSON")
    parser.add_argument("--schema", help="与 --input 配套的 JSON Schema")
    parser.add_argument("--root", help="manifest 相对路径的根目录；默认自动定位仓库根目录")
    parser.add_argument("--project-id", help="要求所有含 项目ID 的数据行与此值一致")
    parser.add_argument("--report", help="将 Markdown 检查报告写入此路径")
    parser.add_argument(
        "--pair",
        action="append",
        nargs=2,
        metavar=("INPUT", "SCHEMA"),
        help="追加同项目 CSV/JSON 与 Schema 配对；仅与首个 --input 一起使用",
    )
    return parser.parse_args()


def main() -> int:
    _configure_utf8_stdio()
    args = _parse_args()
    default_root = Path(__file__).resolve().parents[3]
    root = Path(args.root).resolve() if args.root else default_root
    pairs: list[tuple[Path, Path, Path | None, bool]] = []
    if args.manifest:
        manifest_path = _resolve(args.manifest, Path.cwd())
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"无法读取 manifest：{exc}", file=sys.stderr)
            return 2
        if manifest.get("contract_version") != CONTRACT_VERSION:
            print("manifest 数据契约版本与检查器不一致", file=sys.stderr)
            return 2
        manifest_pairs = manifest.get("pairs", [])
        if not isinstance(manifest_pairs, list):
            print("manifest pairs 必须是数组", file=sys.stderr)
            return 2
        templates = [item.get("template") for item in manifest_pairs if isinstance(item, dict)]
        schemas = [item.get("schema") for item in manifest_pairs if isinstance(item, dict)]
        if len(templates) != len(set(templates)) or len(schemas) != len(set(schemas)):
            print("manifest 存在重复 template 或 schema 映射", file=sys.stderr)
            return 2
        actual_templates = {
            path.relative_to(root).as_posix() for path in (root / "skills").rglob("*.csv")
        }
        actual_schemas = {
            path.relative_to(root).as_posix() for path in (root / "skills").rglob("*.schema.json")
        }
        if set(templates) != actual_templates or set(schemas) != actual_schemas:
            print("manifest 未完整覆盖仓库中的 CSV 或 Schema", file=sys.stderr)
            return 2
        for item in manifest_pairs:
            if not isinstance(item, dict) or not all(key in item for key in ("template", "schema", "card")):
                print("manifest 每个映射必须包含 template、schema、card", file=sys.stderr)
                return 2
            card = _resolve(item["card"], root) if item.get("card") else None
            pairs.append((_resolve(item["template"], root), _resolve(item["schema"], root), card, True))
    else:
        if not args.schema:
            print("使用 --input 时必须同时提供 --schema", file=sys.stderr)
            return 2
        if not args.project_id:
            print("检查真实项目数据时必须提供 --project-id；模板检查请使用 --manifest", file=sys.stderr)
            return 2
        pairs.append((_resolve(args.input, Path.cwd()), _resolve(args.schema, Path.cwd()), None, True))
        for input_value, schema_value in args.pair or []:
            pairs.append((_resolve(input_value, Path.cwd()), _resolve(schema_value, Path.cwd()), None, True))

    if not pairs:
        print("没有可检查的数据契约映射", file=sys.stderr)
        return 2
    results = [
        _check_pair(input_path, schema_path, args.project_id, card_path, require_project_id)
        for input_path, schema_path, card_path, require_project_id in pairs
    ]
    report = _render_report(results, args.project_id, len(pairs))
    print(report)
    if args.report:
        report_path = _resolve(args.report, Path.cwd())
        report_path.parent.mkdir(parents=True, exist_ok=True)
        temp_report_path = report_path.with_name(f".{report_path.name}.tmp")
        temp_report_path.write_text(report, encoding="utf-8")
        try:
            temp_report_path.replace(report_path)
        except OSError:
            shutil.copyfile(temp_report_path, report_path)
            temp_report_path.unlink(missing_ok=True)
    return 1 if any(item["errors"] for item in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
