#!/usr/bin/env python3
"""Validate the lightweight-production and strict-record interaction contract."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


STRICT_ACTIVATION_FILES = (
    "skills/approval-asset-registry/assets/项目绑定对话激活指令模板.md",
    "skills/approval-asset-registry/assets/登记对话激活指令模板.md",
    "skills/creative-control-versioning/assets/创作控制对话激活指令模板.md",
    "skills/generation-version-log/assets/镜头进度记录对话激活指令模板.md",
    "skills/generation-version-log/assets/生成详细记录对话激活指令模板.md",
    "skills/continuity-readiness-audit/assets/正式审计对话激活指令模板.md",
    "skills/video-qc-review/assets/视频QC记录对话激活指令模板.md",
)


def _configure_utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="replace")


def _read(root: Path, relative: str, errors: list[str]) -> str:
    path = root / relative
    try:
        return path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError) as exc:
        errors.append(f"无法按UTF-8读取：{relative}：{exc}")
        return ""


def validate(root: Path) -> list[str]:
    errors: list[str] = []
    interaction = _read(
        root, "skills/production-router-handoff/references/interaction-modes.md", errors
    )
    router = _read(root, "skills/production-router-handoff/SKILL.md", errors)
    short_package = _read(
        root, "skills/production-router-handoff/assets/短交接包模板.md", errors
    )
    lightweight = _read(
        root, "skills/production-router-handoff/assets/轻量生产回显模板.md", errors
    )
    simulation = _read(
        root,
        "skills/production-router-handoff/references/s05-simulated-production-round.md",
        errors,
    )

    required_contract_phrases = (
        "轻量生产模式（默认）",
        "严格记录模式（按明确请求进入）",
        "共享硬规则",
        "完整后台包与短交接包",
        "一个决定点",
        "连续性/就绪门",
    )
    for phrase in required_contract_phrases:
        if phrase not in interaction:
            errors.append(f"交互模式合同缺少：{phrase}")

    for phrase in ("不要把完整任务单当成对话回复", "短交接包模板", "严格记录对话"):
        if phrase not in router:
            errors.append(f"总路由没有落实交互边界：{phrase}")

    for phrase in (
        "项目ID",
        "任务ID@任务单版本",
        "唯一责任Skill",
        "完整任务单路径",
        "最小数据切片",
        "当前唯一目标",
        "用户尚需决定",
        "禁止事项",
        "返回条件",
        "不要加载其他 SKillXC Skill",
    ):
        if phrase not in short_package:
            errors.append(f"短交接包缺少：{phrase}")

    if short_package.count("## 短激活指令") != 1:
        errors.append("短交接包必须且只能有一段短激活指令")
    if "完整任务单路径" not in short_package or "任务ID@任务单版本" not in short_package:
        errors.append("短交接包无法恢复完整版本依据")

    for phrase in ("本轮目标", "必要缺口", "本轮结果", "现在请你决定", "下一步"):
        if phrase not in lightweight:
            errors.append(f"轻量回显模板缺少：{phrase}")
    forbidden_lightweight = ("内容指纹SHA256", "Schema properties", "任务成果索引路径")
    for phrase in forbidden_lightweight:
        if phrase in lightweight:
            errors.append(f"轻量回显模板泄露后台字段：{phrase}")

    for relative in STRICT_ACTIVATION_FILES:
        text = _read(root, relative, errors)
        if "严格记录" not in text and relative.endswith(
            ("登记对话激活指令模板.md", "创作控制对话激活指令模板.md", "镜头进度记录对话激活指令模板.md")
        ):
            errors.append(f"既有专用数据激活指令未声明严格记录：{relative}")
        if "项目" not in text or not any(marker in text for marker in ("禁止", "不生产", "不进行", "不修改", "不创作")):
            errors.append(f"严格记录激活指令缺少项目或禁止边界：{relative}")

    if "第二张保留为当前候选" not in simulation or "没有触发正式登记" not in simulation:
        errors.append("模拟回合没有保持候选/登记边界")
    decision_section = re.search(
        r"## 轻量生产模式应答(?P<body>.*?)(?:## 不应出现在这个回合)",
        simulation,
        re.S,
    )
    if not decision_section:
        errors.append("模拟回合缺少独立轻量应答")
    else:
        body = decision_section.group("body")
        if body.count("现在请你决定") != 1:
            errors.append("模拟回合必须只出现一个决定点")
        for forbidden in ("内容指纹SHA256", "handoff-task.schema.json", "任务索引.csv"):
            if forbidden in body:
                errors.append(f"模拟轻量应答泄露后台字段：{forbidden}")

    continuity = _read(root, "skills/continuity-readiness-audit/SKILL.md", errors)
    if "轻量就绪门（默认）" not in continuity or "不得为了轻量而省略任何检查" not in continuity:
        errors.append("连续性审计没有区分轻量回显与完整业务检查")
    continuity_agent = _read(
        root, "skills/continuity-readiness-audit/agents/openai.yaml", errors
    )
    for phrase in ("默认轻量检查", "明确要求保存正式审计"):
        if phrase not in continuity_agent:
            errors.append(f"连续性审计入口元数据没有保持模式边界：{phrase}")
    return errors


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="检查轻量生产与严格记录交互合同")
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    return parser.parse_args()


def main() -> int:
    _configure_utf8_stdio()
    errors = validate(Path(_parse_args().root).resolve())
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print("交互模式检查通过：默认轻量生产，7类严格记录入口，短交接可恢复完整版本依据")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
