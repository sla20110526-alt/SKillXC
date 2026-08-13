#!/usr/bin/env python3
"""Atomically maintain the project task-artifact index."""

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
VALIDATOR_PATH = SKILL_ROOT / "scripts/validate_project_data.py"
TEMPLATE_PATH = SKILL_ROOT / "assets/任务成果索引模板.csv"
SCHEMA_PATH = SKILL_ROOT / "assets/task-artifact.schema.json"
TASK_SCHEMA_PATH = SKILL_ROOT / "assets/handoff-task.schema.json"
DEFAULT_INDEX = "tasks/任务成果索引.csv"
DEFAULT_TASK_INDEX = "tasks/任务索引.csv"
VERSION_RE = re.compile(r"^v([0-9]{3,})$")
REFERENCE_RE = re.compile(r"^[^@；]+@v(?:[0-9]{3,}|[0-9]+\.[0-9]+)$")
TRANSACTION_RE = re.compile(r"^TAI-[A-Z0-9-]+$")
ALLOWED_SOURCE_TASK_STATUSES = {"已激活", "执行中", "已返回"}


class TaskArtifactError(Exception):
    pass


def _load_validator() -> Any:
    spec = importlib.util.spec_from_file_location("validate_project_data", VALIDATOR_PATH)
    if spec is None or spec.loader is None:
        raise TaskArtifactError(f"无法加载项目数据检查器：{VALIDATOR_PATH}")
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
        raise TaskArtifactError(f"路径越出项目数据根目录：{resolved}") from exc
    return resolved


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.is_file():
        raise TaskArtifactError(f"索引不存在：{path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise TaskArtifactError(f"索引缺少表头：{path}")
        return list(reader.fieldnames), [dict(row) for row in reader if any(row.values())]


def _write_csv(path: Path, headers: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers, extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


def _schema_check(path: Path, schema: Path, project_id: str) -> None:
    result = VALIDATOR._check_pair(path, schema, project_id, None, True)
    if result["errors"]:
        raise TaskArtifactError("Schema检查失败：\n" + "\n".join(result["errors"]))


def _version_number(value: str) -> int:
    match = VERSION_RE.fullmatch(value)
    if match is None:
        raise TaskArtifactError(f"成果版本无效：{value}")
    return int(match.group(1))


def _split_refs(value: str) -> list[str]:
    if value in {"无", "不适用"}:
        return []
    values = value.split("；")
    if any(REFERENCE_RE.fullmatch(item) is None for item in values):
        raise TaskArtifactError(f"上游引用必须为以中文分号分隔的 ID@版本：{value}")
    if len(values) != len(set(values)):
        raise TaskArtifactError(f"上游引用存在重复：{value}")
    return values


def _fingerprint(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _task_pairs(task_index: Path, project_id: str) -> set[tuple[str, str]]:
    _schema_check(task_index, TASK_SCHEMA_PATH, project_id)
    _, tasks = _read_csv(task_index)
    pairs: set[tuple[str, str]] = set()
    seen: set[tuple[str, str]] = set()
    for row in tasks:
        if row["项目ID"] != project_id:
            raise TaskArtifactError(f"任务索引发现其他项目数据：{row['项目ID']}")
        pair = (row["任务ID"], row["任务单版本"])
        if pair in seen:
            raise TaskArtifactError(f"任务索引存在重复任务版本：{pair}")
        seen.add(pair)
        if row["任务状态"] in ALLOWED_SOURCE_TASK_STATUSES:
            pairs.add(pair)
    return pairs


def _validate_business(
    rows: list[dict[str, str]],
    project_id: str,
    project_root: Path,
    task_pairs: set[tuple[str, str]],
) -> None:
    grouped: dict[str, list[dict[str, str]]] = {}
    seen: set[tuple[str, str]] = set()
    local_references = {f"{row['成果ID']}@{row['成果版本']}" for row in rows}
    for row in rows:
        if row["项目ID"] != project_id:
            raise TaskArtifactError(f"任务成果索引发现其他项目数据：{row['项目ID']}")
        key = (row["成果ID"], row["成果版本"])
        if key in seen:
            raise TaskArtifactError(f"任务成果版本重复：{key}")
        seen.add(key)
        if (row["来源任务ID"], row["来源任务单版本"]) not in task_pairs:
            raise TaskArtifactError(
                f"成果来源任务不存在或版本不匹配：{row['来源任务ID']}@{row['来源任务单版本']}"
            )
        status = row["成果状态"]
        current = row["当前有效"]
        if (status == "可交接") != (current == "是"):
            raise TaskArtifactError(f"{row['成果ID']}@{row['成果版本']} 的状态与当前有效不一致")
        if row["成果类别"] == "Prompt" and status == "可交接" and not row["状态依据"].startswith("用户原文："):
            raise TaskArtifactError(
                f"Prompt成果激活必须在状态依据中保存以“用户原文：”开头的明确放行原文：{row['成果ID']}@{row['成果版本']}"
            )
        if Path(row["成果路径"]).is_absolute():
            raise TaskArtifactError(f"成果路径必须使用项目根目录内相对路径：{row['成果路径']}")
        artifact_path = _resolve_inside(project_root, row["成果路径"])
        if not artifact_path.is_file():
            raise TaskArtifactError(f"成果文件不存在：{artifact_path}")
        if row["内容指纹SHA256"] != _fingerprint(artifact_path):
            raise TaskArtifactError(f"成果内容指纹与文件不一致：{artifact_path}")
        references = _split_refs(row["上游精确引用集合"])
        self_reference = f"{row['成果ID']}@{row['成果版本']}"
        if self_reference in references:
            raise TaskArtifactError(f"任务成果不得引用自身：{self_reference}")
        for reference in references:
            if reference in local_references:
                continue
            # 正式资产、长期控制卡、分镜等使用各自索引，允许作为外部精确引用；
            # 本工具只验证格式，不把未知引用伪装成本索引内已解析记录。
        grouped.setdefault(row["成果ID"], []).append(row)
    for artifact_id, versions in grouped.items():
        numbers = sorted(_version_number(row["成果版本"]) for row in versions)
        if numbers != list(range(1, max(numbers) + 1)):
            raise TaskArtifactError(f"{artifact_id} 的成果版本不连续：{numbers}")
        if sum(row["当前有效"] == "是" for row in versions) > 1:
            raise TaskArtifactError(f"{artifact_id} 存在多个当前有效版本")
        by_number = {_version_number(row["成果版本"]): row for row in versions}
        for number, row in by_number.items():
            expected = "不适用" if number == 1 else f"v{number - 1:03d}"
            if row["上一成果版本"] != expected:
                raise TaskArtifactError(f"{artifact_id}@{row['成果版本']} 的上一版本应为 {expected}")
    local_graph = {
        f"{row['成果ID']}@{row['成果版本']}": [
            reference
            for reference in _split_refs(row["上游精确引用集合"])
            if reference in local_references
        ]
        for row in rows
    }
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(reference: str, chain: list[str]) -> None:
        if reference in visiting:
            cycle_start = chain.index(reference)
            raise TaskArtifactError(f"任务成果依赖形成循环：{' -> '.join(chain[cycle_start:] + [reference])}")
        if reference in visited:
            return
        visiting.add(reference)
        for upstream in local_graph[reference]:
            visit(upstream, [*chain, upstream])
        visiting.remove(reference)
        visited.add(reference)

    for artifact_reference in local_graph:
        visit(artifact_reference, [artifact_reference])


def _validate_index(
    index_path: Path,
    task_index: Path,
    project_id: str,
    project_root: Path,
) -> None:
    _schema_check(index_path, SCHEMA_PATH, project_id)
    _, rows = _read_csv(index_path)
    _validate_business(rows, project_id, project_root, _task_pairs(task_index, project_id))


def _load_payload(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TaskArtifactError(f"无法读取操作载荷：{exc}") from exc
    if not isinstance(payload, dict):
        raise TaskArtifactError("操作载荷顶层必须是对象")
    return payload


def _require_operation(payload: dict[str, Any]) -> None:
    required = ("项目ID", "事务ID", "操作日期", "操作依据")
    missing = [key for key in required if not isinstance(payload.get(key), str) or not payload[key]]
    if missing:
        raise TaskArtifactError(f"操作载荷缺少非空字段：{missing}")
    if TRANSACTION_RE.fullmatch(str(payload["事务ID"])) is None:
        raise TaskArtifactError("事务ID必须匹配 TAI-[A-Z0-9-]+")


def _draft(
    payload: dict[str, Any],
    rows: list[dict[str, str]],
    project_root: Path,
    headers: list[str],
) -> dict[str, Any]:
    _require_operation(payload)
    candidates = payload.get("记录")
    if not isinstance(candidates, list) or not candidates or not all(isinstance(item, dict) for item in candidates):
        raise TaskArtifactError("草案操作的“记录”必须是非空对象数组")
    added: list[str] = []
    existing = {(row["成果ID"], row["成果版本"]) for row in rows}
    for raw in candidates:
        row = {key: str(value) for key, value in raw.items()}
        if set(row) != set(headers):
            missing = [field for field in headers if field not in row]
            extra = [field for field in row if field not in headers]
            raise TaskArtifactError(f"草案记录字段与成果索引不一致；缺少={missing}；多出={extra}")
        if row.get("项目ID") != payload["项目ID"]:
            raise TaskArtifactError("草案记录项目ID与操作载荷不一致")
        artifact_id = row.get("成果ID", "")
        version = row.get("成果版本", "")
        if (artifact_id, version) in existing:
            raise TaskArtifactError(f"成果版本已经存在：{artifact_id}@{version}")
        same = [item for item in rows if item["成果ID"] == artifact_id]
        expected_number = 1 if not same else max(_version_number(item["成果版本"]) for item in same) + 1
        if _version_number(version) != expected_number:
            raise TaskArtifactError(f"{artifact_id} 的新版本必须为 v{expected_number:03d}")
        expected_previous = "不适用" if expected_number == 1 else f"v{expected_number - 1:03d}"
        if row.get("上一成果版本") != expected_previous:
            raise TaskArtifactError(f"{artifact_id}@{version} 的上一成果版本必须为 {expected_previous}")
        if row.get("成果状态") != "草案" or row.get("当前有效") != "否":
            raise TaskArtifactError("新成果版本必须为 草案 + 当前有效=否")
        if Path(row.get("成果路径", "")).is_absolute():
            raise TaskArtifactError(f"成果路径必须使用项目根目录内相对路径：{row.get('成果路径', '')}")
        artifact_path = _resolve_inside(project_root, row.get("成果路径", ""))
        if not artifact_path.is_file():
            raise TaskArtifactError(f"成果文件不存在：{artifact_path}")
        fingerprint = _fingerprint(artifact_path)
        if row.get("内容指纹SHA256") not in {"", fingerprint}:
            raise TaskArtifactError(f"载荷内容指纹与成果文件不一致：{artifact_path}")
        row["内容指纹SHA256"] = fingerprint
        if same:
            latest = max(same, key=lambda item: _version_number(item["成果版本"]))
            identity_fields = (
                "内容指纹SHA256",
                "成果类别",
                "成果类型",
                "成果名称",
                "责任Skill",
                "适用范围",
                "成果路径",
                "上游精确引用集合",
            )
            if all(row.get(field) == latest.get(field) for field in identity_fields):
                raise TaskArtifactError(f"{artifact_id} 的成果内容、范围和引用未变化，不得建立新版本")
        rows.append(row)
        existing.add((artifact_id, version))
        added.append(f"{artifact_id}@{version}")
    return {"新增草案版本": added}


def _targets(payload: dict[str, Any]) -> list[tuple[str, str]]:
    raw = payload.get("目标")
    if not isinstance(raw, list) or not raw or not all(isinstance(item, dict) for item in raw):
        raise TaskArtifactError("状态操作的“目标”必须是非空对象数组")
    result = [(str(item.get("成果ID", "")), str(item.get("成果版本", ""))) for item in raw]
    if any(not artifact_id or not version for artifact_id, version in result):
        raise TaskArtifactError("每个目标必须包含成果ID和成果版本")
    if len(result) != len(set(result)):
        raise TaskArtifactError("状态操作目标重复")
    if len({artifact_id for artifact_id, _ in result}) != len(result):
        raise TaskArtifactError("一次状态事务不能选择同一成果ID的多个版本")
    return result


def _activate_like(
    payload: dict[str, Any],
    rows: list[dict[str, str]],
    required_status: str,
) -> dict[str, Any]:
    _require_operation(payload)
    index = {(row["成果ID"], row["成果版本"]): row for row in rows}
    selected: list[dict[str, str]] = []
    for key in _targets(payload):
        row = index.get(key)
        if row is None or row["成果状态"] != required_status or row["当前有效"] != "否":
            raise TaskArtifactError(f"目标不存在或不是{required_status}版本：{key}")
        same_identity = [item for item in rows if item["成果ID"] == row["成果ID"]]
        if required_status == "草案":
            latest_number = max(_version_number(item["成果版本"]) for item in same_identity)
            if _version_number(row["成果版本"]) != latest_number:
                raise TaskArtifactError(
                    f"只能激活最新成果草案：{row['成果ID']} 当前最新为 v{latest_number:03d}"
                )
        elif any(item["当前有效"] == "是" for item in same_identity):
            raise TaskArtifactError(f"{row['成果ID']} 已有其他当前有效版本，不得恢复待复核版本")
        if row["成果类别"] == "Prompt" and not str(payload["操作依据"]).startswith("用户原文："):
            raise TaskArtifactError("Prompt成果激活或恢复必须在操作依据中保存以“用户原文：”开头的明确放行原文")
        selected.append(row)
    activated: list[str] = []
    replaced: list[str] = []
    for target in selected:
        for row in rows:
            if row["成果ID"] == target["成果ID"] and row["当前有效"] == "是":
                row["成果状态"] = "已替代"
                row["当前有效"] = "否"
                row["状态依据"] = f"被 {target['成果ID']}@{target['成果版本']} 替代；事务 {payload['事务ID']}"
                replaced.append(f"{row['成果ID']}@{row['成果版本']}")
        target["成果状态"] = "可交接"
        target["当前有效"] = "是"
        target["状态依据"] = str(payload["操作依据"])
        target["复核日期"] = str(payload["操作日期"])
        activated.append(f"{target['成果ID']}@{target['成果版本']}")
    return {"可交接版本": activated, "已替代版本": replaced}


def _mark_review(payload: dict[str, Any], rows: list[dict[str, str]]) -> dict[str, Any]:
    _require_operation(payload)
    index = {(row["成果ID"], row["成果版本"]): row for row in rows}
    affected: list[str] = []
    for key in _targets(payload):
        row = index.get(key)
        if row is None or row["成果状态"] != "可交接" or row["当前有效"] != "是":
            raise TaskArtifactError(f"目标不存在或不是当前可交接版本：{key}")
        row["成果状态"] = "待复核"
        row["当前有效"] = "否"
        row["状态依据"] = str(payload["操作依据"])
        row["复核日期"] = str(payload["操作日期"])
        affected.append(f"{row['成果ID']}@{row['成果版本']}")
    return {"待复核版本": affected, "自动恢复旧版": []}


def _invalidate(payload: dict[str, Any], rows: list[dict[str, str]]) -> dict[str, Any]:
    _require_operation(payload)
    index = {(row["成果ID"], row["成果版本"]): row for row in rows}
    invalidated: list[str] = []
    for key in _targets(payload):
        row = index.get(key)
        if row is None or row["成果状态"] in {"已替代", "已失效"}:
            raise TaskArtifactError(f"目标不存在或已不可失效：{key}")
        row["成果状态"] = "已失效"
        row["当前有效"] = "否"
        row["状态依据"] = str(payload["操作依据"])
        row["复核日期"] = str(payload["操作日期"])
        invalidated.append(f"{row['成果ID']}@{row['成果版本']}")
    return {"已失效版本": invalidated, "自动恢复旧版": []}


def _commit(
    project_root: Path,
    index_path: Path,
    task_index: Path,
    headers: list[str],
    rows: list[dict[str, str]],
    project_id: str,
    transaction_id: str,
) -> Path:
    token = uuid.uuid4().hex
    temp = index_path.with_name(f".{index_path.stem}.{token}.tmp{index_path.suffix}")
    backup_dir = project_root / "tasks/backups" / transaction_id
    if backup_dir.exists():
        raise TaskArtifactError(f"备份目录已存在，事务ID必须唯一：{backup_dir}")
    try:
        _write_csv(temp, headers, rows)
        _validate_index(temp, task_index, project_id, project_root)
        backup_dir.mkdir(parents=True)
        backup = backup_dir / index_path.name
        shutil.copyfile(index_path, backup)
        try:
            temp.replace(index_path)
            _validate_index(index_path, task_index, project_id, project_root)
        except Exception:
            shutil.copyfile(backup, index_path)
            raise
        return backup_dir
    finally:
        temp.unlink(missing_ok=True)


def _run(args: argparse.Namespace) -> dict[str, Any]:
    project_root = Path(args.project_root).resolve()
    if not project_root.is_dir():
        raise TaskArtifactError(f"项目数据根目录不存在：{project_root}")
    index_path = _resolve_inside(project_root, args.index or DEFAULT_INDEX)
    task_index = _resolve_inside(project_root, args.task_index or DEFAULT_TASK_INDEX)
    if args.command == "init":
        _task_pairs(task_index, args.project_id)
        if index_path.exists():
            _validate_index(index_path, task_index, args.project_id, project_root)
            return {"项目ID": args.project_id, "初始化结论": "已存在并通过检查", "索引路径": str(index_path)}
        index_path.parent.mkdir(parents=True, exist_ok=True)
        temp = index_path.with_name(f".{index_path.stem}.{uuid.uuid4().hex}.tmp{index_path.suffix}")
        try:
            shutil.copyfile(TEMPLATE_PATH, temp)
            _validate_index(temp, task_index, args.project_id, project_root)
            temp.replace(index_path)
        finally:
            temp.unlink(missing_ok=True)
        return {"项目ID": args.project_id, "初始化结论": "已初始化空索引", "索引路径": str(index_path)}
    if args.command in {"check", "impact"}:
        _validate_index(index_path, task_index, args.project_id, project_root)
    if args.command == "check":
        return {"项目ID": args.project_id, "检查结论": "通过"}
    if args.command == "impact":
        if REFERENCE_RE.fullmatch(args.upstream_ref) is None:
            raise TaskArtifactError("影响分析引用必须为 ID@版本")
        _, rows = _read_csv(index_path)
        live_rows = [row for row in rows if row["成果状态"] not in {"已替代", "已失效"}]
        reached = {args.upstream_ref}
        affected: list[dict[str, Any]] = []
        pending = [(args.upstream_ref, [args.upstream_ref])]
        while pending:
            changed_ref, chain = pending.pop(0)
            for row in live_rows:
                artifact_ref = f"{row['成果ID']}@{row['成果版本']}"
                if artifact_ref in reached or changed_ref not in _split_refs(row["上游精确引用集合"]):
                    continue
                reached.add(artifact_ref)
                artifact_chain = [*chain, artifact_ref]
                affected.append(
                    {
                        "成果": artifact_ref,
                        "成果状态": row["成果状态"],
                        "当前有效": row["当前有效"],
                        "责任Skill": row["责任Skill"],
                        "成果路径": row["成果路径"],
                        "影响链": artifact_chain,
                    }
                )
                pending.append((artifact_ref, artifact_chain))
        return {
            "项目ID": args.project_id,
            "被替代上游引用": args.upstream_ref,
            "潜在受影响成果": affected,
            "写入动作": "无；必须由责任Skill复核后另行决定",
        }
    payload = _load_payload(Path(args.payload).resolve())
    project_id = str(payload.get("项目ID", ""))
    _validate_index(index_path, task_index, project_id, project_root)
    headers, rows = _read_csv(index_path)
    if args.command == "draft":
        result = _draft(payload, rows, project_root, headers)
    elif args.command == "activate":
        result = _activate_like(payload, rows, "草案")
    elif args.command == "confirm-review":
        result = _activate_like(payload, rows, "待复核")
    elif args.command == "mark-review":
        result = _mark_review(payload, rows)
    else:
        result = _invalidate(payload, rows)
    backup_dir = _commit(
        project_root,
        index_path,
        task_index,
        headers,
        rows,
        project_id,
        str(payload["事务ID"]),
    )
    return {"项目ID": project_id, **result, "备份目录": str(backup_dir), "写入结论": "通过"}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="原子维护任务成果索引")
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("init", "check", "draft", "activate", "mark-review", "confirm-review", "invalidate", "impact"):
        sub = commands.add_parser(command)
        sub.add_argument("--project-root", required=True)
        sub.add_argument("--index")
        sub.add_argument("--task-index")
        if command in {"init", "check", "impact"}:
            sub.add_argument("--project-id", required=True)
        else:
            sub.add_argument("--payload", required=True)
        if command == "impact":
            sub.add_argument("--upstream-ref", required=True)
    return parser.parse_args()


def main() -> int:
    try:
        result = _run(_parse_args())
    except (TaskArtifactError, OSError, csv.Error, json.JSONDecodeError) as exc:
        print(f"任务成果索引事务失败：{exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
