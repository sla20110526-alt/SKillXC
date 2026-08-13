#!/usr/bin/env python3
"""Validate that obsolete discussion archives cannot enter the active rule surface."""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
import sys
from pathlib import Path


MANIFEST_NAME = "active-rule-sources.json"
AGENTS_SENTINEL = "ARCHIVE_EXPLICIT_ONLY"
FORBIDDEN_PATH_PATTERNS = (
    re.compile(r"对话接续记录"),
    re.compile(r"历史讨论全文"),
    re.compile(r"聊天对话全文"),
    re.compile(r"discussion[-_ ]?(?:transcript|archive)", re.I),
    re.compile(r"conversation[-_ ]?(?:transcript|history)", re.I),
)
FORBIDDEN_REFERENCE_PATTERNS = (
    re.compile(r"AI影视生产系统_对话接续记录"),
    re.compile(r"docs[\\/][^\s)\]]*对话接续记录"),
    re.compile(r'docs[\\/][^"\s)\]]*历史讨论全文'),
    re.compile(r"历史归档[\\/]"),
    re.compile(r"historical[-_ ]archive[\\/]", re.I),
)
IGNORED_PARTS = {".git", "__pycache__"}
REFERENCE_SCAN_EXEMPT = {
    "deployment/validate_active_rule_boundary.py",
    "deployment/test_validate_active_rule_boundary.py",
}
REQUIRED_LOAD_POLICIES = {
    "AGENTS.md": "automatic-instruction",
    MANIFEST_NAME: "manifest-only",
    "skills": "skill-metadata-then-explicit-activation",
    ".codex-plugin/plugin.json": "discovery-metadata-only",
}


def _inside(root: Path, value: str) -> Path:
    path = (root / value).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"现行规则路径越出仓库：{value}") from exc
    return path


def _candidate_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*"):
        if any(part in IGNORED_PARTS for part in path.relative_to(root).parts):
            continue
        if path.is_file():
            files.append(path)
    return files


def _is_link_or_reparse(path: Path) -> bool:
    try:
        if path.is_symlink():
            return True
        attributes = getattr(os.lstat(path), "st_file_attributes", 0)
        return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
    except OSError:
        return False


def validate(root: Path) -> list[str]:
    root = root.resolve()
    errors: list[str] = []
    manifest_path = root / MANIFEST_NAME
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"无法读取 {MANIFEST_NAME}：{exc}"]
    if not isinstance(manifest, dict) or not isinstance(manifest.get("authority_order"), list):
        return [f"{MANIFEST_NAME}: authority_order 必须是数组"]
    authority_paths: list[str] = []
    for index, item in enumerate(manifest["authority_order"], start=1):
        if not isinstance(item, dict) or not isinstance(item.get("path"), str) or not item["path"]:
            errors.append(f"{MANIFEST_NAME}: authority_order[{index}] 缺少非空 path")
            continue
        value = item["path"]
        authority_paths.append(value)
        load_policy = item.get("load_policy")
        if not isinstance(load_policy, str) or not load_policy:
            errors.append(f"{MANIFEST_NAME}: authority_order[{index}] 缺少非空 load_policy")
        expected_policy = REQUIRED_LOAD_POLICIES.get(value)
        if expected_policy and load_policy != expected_policy:
            errors.append(f"{MANIFEST_NAME}: {value} 的 load_policy 必须是 {expected_policy}")
        try:
            active_path = _inside(root, value)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        if not active_path.exists():
            errors.append(f"现行规则源不存在：{value}")
        if any(pattern.search(value) for pattern in FORBIDDEN_PATH_PATTERNS):
            errors.append(f"历史材料不得登记为现行规则源：{value}")
    if len(authority_paths) != len(set(authority_paths)):
        errors.append(f"{MANIFEST_NAME}: authority_order 路径重复")
    support_records = manifest.get("support_documents")
    if not isinstance(support_records, list):
        errors.append(f"{MANIFEST_NAME}: support_documents 必须是数组")
        support_records = []
    support_paths: list[str] = []
    for index, item in enumerate(support_records, start=1):
        if not isinstance(item, dict) or not isinstance(item.get("path"), str) or not item["path"]:
            errors.append(f"{MANIFEST_NAME}: support_documents[{index}] 缺少非空 path")
            continue
        value = item["path"]
        support_paths.append(value)
        if item.get("load_policy") != "explicit-support-only":
            errors.append(
                f"{MANIFEST_NAME}: support_documents[{index}] 的 load_policy 必须是 explicit-support-only"
            )
        try:
            support_path = _inside(root, value)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        if not support_path.is_file():
            errors.append(f"支持文档不存在：{value}")
    if len(support_paths) != len(set(support_paths)):
        errors.append(f"{MANIFEST_NAME}: support_documents 路径重复")
    classified_docs = {
        value for value in (*authority_paths, *support_paths) if value.startswith("docs/")
    }
    actual_docs = {
        path.relative_to(root).as_posix()
        for path in (root / "docs").rglob("*")
        if path.is_file()
    }
    if actual_docs != classified_docs:
        errors.append(
            f"docs目录存在未分类或缺失文档：实际={sorted(actual_docs)}，已分类={sorted(classified_docs)}"
        )
    policy = manifest.get("historical_access_policy")
    if not isinstance(policy, str) or "用户" not in policy or "明确" not in policy:
        errors.append(f"{MANIFEST_NAME}: historical_access_policy 必须要求用户当前明确授权")

    agents_path = root / "AGENTS.md"
    try:
        agents_text = agents_path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        errors.append(f"无法读取 AGENTS.md：{exc}")
        agents_text = ""
    if AGENTS_SENTINEL not in agents_text:
        errors.append(f"AGENTS.md 缺少历史隔离哨兵 {AGENTS_SENTINEL}")

    for path in root.rglob("*"):
        if any(part in IGNORED_PARTS for part in path.relative_to(root).parts):
            continue
        if _is_link_or_reparse(path):
            errors.append(
                f"现行仓库不得包含通向外部内容的链接或重解析点：{path.relative_to(root).as_posix()}"
            )

    for path in _candidate_files(root):
        relative = path.relative_to(root).as_posix()
        if any(pattern.search(relative) for pattern in FORBIDDEN_PATH_PATTERNS):
            errors.append(f"现行仓库包含历史讨论文件：{relative}")
            continue
        if relative in REFERENCE_SCAN_EXEMPT:
            continue
        if path.suffix.lower() not in {".md", ".json", ".yaml", ".yml", ".txt", ".csv", ".py"}:
            continue
        try:
            text = path.read_text(encoding="utf-8-sig")
        except OSError:
            continue
        except UnicodeDecodeError:
            errors.append(f"现行文本无法按UTF-8读取：{relative}")
            continue
        for pattern in FORBIDDEN_REFERENCE_PATTERNS:
            if pattern.search(text):
                errors.append(f"现行文件引用了历史讨论材料：{relative}")
                break
    return errors


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="检查现行规则与历史讨论归档的隔离边界")
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    return parser.parse_args()


def main() -> int:
    errors = validate(Path(_parse_args().root))
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print("现行规则与历史讨论归档边界检查通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
