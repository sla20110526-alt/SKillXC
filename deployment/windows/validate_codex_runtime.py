#!/usr/bin/env python3
"""Probe Codex to validate the active SKillXC runtime catalog on Windows."""

from __future__ import annotations

import argparse
import json
import os
import queue
import re
import subprocess
import sys
import threading
import time
from pathlib import Path


PLUGIN_STATUS_PATTERN = re.compile(r"(?m)^skillxc@personal\s+not installed(?:\s|$)")
VISIBLE_SKILL_PATTERN = re.compile(r"(?m)^- skillxc:([a-z0-9-]+):")


def _configure_utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="replace")


def _run(executable: Path, *arguments: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(executable), *arguments],
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def _string_values(value: object):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _string_values(item)
    elif isinstance(value, list):
        for item in value:
            yield from _string_values(item)


def _read_response(
    messages: queue.Queue[bytes | None], request_id: int, deadline: float
) -> dict:
    while time.monotonic() < deadline:
        remaining = max(0.1, deadline - time.monotonic())
        try:
            raw = messages.get(timeout=remaining)
        except queue.Empty as exc:
            raise TimeoutError(
                f"Codex app-server did not answer request {request_id} within 30 seconds"
            ) from exc
        if raw is None:
            break
        try:
            message = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        if message.get("id") == request_id:
            if "error" in message:
                raise RuntimeError(f"Codex JSON-RPC error: {message['error']}")
            return message.get("result", {})
    raise TimeoutError(f"Codex app-server did not answer request {request_id} within 30 seconds")


def _runtime_catalog(executable: Path, root: Path) -> dict:
    process = subprocess.Popen(
        [str(executable), "app-server", "--stdio"],
        cwd=root,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    deadline = time.monotonic() + 30
    try:
        assert process.stdin is not None
        assert process.stdout is not None
        messages: queue.Queue[bytes | None] = queue.Queue()

        def read_stdout() -> None:
            for line in process.stdout:
                messages.put(line)
            messages.put(None)

        reader = threading.Thread(target=read_stdout, daemon=True)
        reader.start()
        initialize = {
            "id": 1,
            "method": "initialize",
            "params": {"clientInfo": {"name": "skillxc-s04-runtime-audit", "version": "1.0.0"}},
        }
        process.stdin.write((json.dumps(initialize) + "\n").encode("utf-8"))
        process.stdin.flush()
        _read_response(messages, 1, deadline)
        request = {
            "id": 2,
            "method": "skills/list",
            "params": {"cwds": [str(root)], "forceReload": True},
        }
        process.stdin.write((json.dumps(request, ensure_ascii=False) + "\n").encode("utf-8"))
        process.stdin.flush()
        return _read_response(messages, 2, deadline)
    finally:
        if process.poll() is None:
            process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def validate(root: Path, user_home: Path, executable: Path) -> list[str]:
    errors: list[str] = []
    manifest_path = root / "deployment/windows/install-manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        activation = manifest["skillxc_activation"]
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError) as exc:
        return [f"无法读取运行时安装清单：{exc}"]
    expected_short = sorted(activation["central_skill_names"])
    expected_runtime = [f"skillxc:{name}" for name in expected_short]
    expected_root = os.path.normcase(os.path.normpath(str(root / "skills"))) + os.sep

    version = _run(executable, "--version", cwd=root)
    if version.returncode or not re.search(r"(?m)^codex-cli\s+", version.stdout):
        errors.append("Codex --version命令不可运行")

    plugins = _run(executable, "plugin", "list", cwd=root)
    if plugins.returncode:
        errors.append("Codex plugin list命令不可运行")
    elif not PLUGIN_STATUS_PATTERN.search(plugins.stdout):
        errors.append("重复发现风险：直接Skill链接生效时skillxc@personal必须保持未安装")
    plugin_cache = user_home / ".codex/plugins/cache/personal/skillxc"
    if plugin_cache.exists():
        errors.append(f"重复发现风险：存在skillxc插件安装缓存：{plugin_cache}")

    try:
        result = _runtime_catalog(executable, root)
        groups = result.get("data", [])
        if len(groups) != 1:
            errors.append(f"skills/list应返回1个工作目录分组，实际为{len(groups)}个")
        skills = []
        for group in groups:
            if group.get("errors"):
                errors.append(f"Codex报告Skill加载错误：{group['errors']}")
            for skill in group.get("skills", []):
                path = skill.get("path", "")
                normalized = os.path.normcase(os.path.normpath(path))
                if normalized.startswith(expected_root):
                    skills.append(skill)
        actual_names = sorted(skill.get("name", "") for skill in skills)
        if len(actual_names) != len(set(actual_names)):
            errors.append("Codex实际发现结果存在重复的SKillXC名称")
        if actual_names != expected_runtime:
            missing = sorted(set(expected_runtime) - set(actual_names))
            extra = sorted(set(actual_names) - set(expected_runtime))
            errors.append(f"Codex实际发现结果与清单不一致；缺失={missing}；多余={extra}")
        for skill in skills:
            short_name = skill["name"].removeprefix("skillxc:")
            expected_path = os.path.normcase(os.path.normpath(str(root / "skills" / short_name / "SKILL.md")))
            actual_path = os.path.normcase(os.path.normpath(skill["path"]))
            if actual_path != expected_path:
                errors.append(f"Skill未指向中央源：{skill['name']}")
            if not skill.get("enabled"):
                errors.append(f"Skill在运行时被禁用：{skill['name']}")
    except (OSError, RuntimeError, TimeoutError, KeyError, TypeError, ValueError) as exc:
        errors.append(f"Codex运行时目录检查失败：{exc}")

    prompt = _run(executable, "debug", "prompt-input", "请确认生产路由入口。", cwd=root)
    if prompt.returncode:
        errors.append("Codex debug prompt-input命令不可运行")
    else:
        try:
            prompt_object = json.loads(prompt.stdout)
            prompt_text = "\n".join(_string_values(prompt_object))
            visible = sorted(set(VISIBLE_SKILL_PATTERN.findall(prompt_text)))
            expected_visible = sorted(activation["implicit_skill_names"])
            if visible != expected_visible:
                errors.append(f"新对话初始提示只能显示总路由；实际={visible}")
        except json.JSONDecodeError as exc:
            errors.append(f"Codex初始提示输出不是有效JSON：{exc}")
    return errors


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="检查Codex实际发现的SKillXC运行时目录")
    parser.add_argument("--root", required=True)
    parser.add_argument("--user-home", required=True)
    parser.add_argument("--codex", required=True)
    return parser.parse_args()


def main() -> int:
    _configure_utf8_stdio()
    args = _parse_args()
    root = Path(args.root).resolve()
    user_home = Path(args.user_home).resolve()
    executable = Path(args.codex).resolve()
    errors = validate(root, user_home, executable)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    manifest = json.loads((root / "deployment/windows/install-manifest.json").read_text(encoding="utf-8"))
    count = len(manifest["skillxc_activation"]["central_skill_names"])
    version = _run(executable, "--version", cwd=root).stdout.strip()
    print(f"Codex executable: {executable}")
    print(f"Codex version: {version}")
    print(f"Runtime SKillXC catalog: {count}/{count}, no missing or duplicate entries")
    print("Initial prompt: production-router-handoff only")
    print("skillxc@personal plugin: not installed")
    print("Codex Skill runtime validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
