#!/usr/bin/env python3
"""Validate the C01 art and LookDev production contract."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


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
    skill = _read(root, "skills/art-lookdev-direction/SKILL.md", errors)
    baseline = _read(root, "skills/art-lookdev-direction/assets/美术LookDev基线卡模板.md", errors)
    handoff = _read(root, "skills/art-lookdev-direction/assets/美术执行交接包模板.md", errors)
    decision = _read(root, "skills/art-lookdev-direction/references/art-lookdev-decision-contract.md", errors)
    simulation = _read(root, "skills/art-lookdev-direction/references/c01-simulated-lookdev-task.md", errors)
    router = _read(root, "skills/production-router-handoff/SKILL.md", errors)
    task = _read(root, "skills/production-router-handoff/assets/创作任务单模板.md", errors)
    style = _read(root, "skills/style-lock-director/SKILL.md", errors)

    for phrase in (
        "A｜项目 LookDev 长期基线",
        "B｜资产类别执行交接",
        "C｜场次美术状态适配",
        "D｜美术规则兼容复核",
        "事实到设计的决策顺序",
        "稳定 `ALD-<项目ID>-<范围>`",
        "任务成果索引",
        "不得决定摄影机位置",
        "不得直接生产资产图片、Prompt 或登记申请",
        "只在本模式列出美术",
        "未明确选择时只使用通用方法",
    ):
        if phrase not in skill:
            errors.append(f"美术Skill缺少成熟化合同：{phrase}")

    for phrase in (
        "建筑、室内、功能分区与尺度秩序",
        "服装、妆造、身份、阶层、职业与季节关系",
        "道具／载具／图案文字",
        "材料生态",
        "维护、老化、磨损与污迹",
        "固有色层级",
        "视觉母题",
        "资产类别规则",
        "镜头临时效果判定与责任Skill",
        "GPT Image 2美术短执行切片生成规则",
        "项目灯光不得直接反向引用本卡",
        "CCS-ART-LOOKDEV@v003",
    ):
        if phrase not in baseline:
            errors.append(f"美术长期基线模板缺少：{phrase}")

    for phrase in (
        "永久世界规则（只读继承）",
        "本包资产类别规则",
        "本包场次美术状态",
        "镜头临时效果",
        "GPT Image 2 美术短执行切片",
        "必须准确 / 允许艺术化 / 纯虚构规则",
        "task-artifact.schema.json",
        "不是长期基线、正式资产、风格评审或批量放行",
    ):
        if phrase not in handoff:
            errors.append(f"美术执行交接包缺少：{phrase}")

    for phrase in (
        "事实出处 → 社会／功能含义 → 物质规则 → 可观察结果",
        "建材、服装、对象来源、污染与维护",
        "美术只定义材料／物体固有色",
        "磨损不能均匀撒满全表面",
        "必须准确",
        "纯虚构规则",
    ):
        if phrase not in decision:
            errors.append(f"美术决策合同缺少：{phrase}")

    for phrase in (
        "美术工作模式",
        "当前美术LookDev基线ID@版本",
        "美术四层边界",
    ):
        if phrase not in task or phrase not in router:
            errors.append(f"总路由/任务单没有交接C01字段：{phrase}")

    for phrase in ("资产类别执行交接", "不能把美术部门短包单独当成测试授权", "不在评审卡里临时发明美术答案"):
        if phrase not in style:
            errors.append(f"风格总控没有保持美术交接边界：{phrase}")

    answer_match = re.search(
        r"## 合格轻量回显(?P<body>.*?)(?:## 不合格表现)", simulation, re.S
    )
    if not answer_match:
        errors.append("C01模拟任务缺少合格轻量回显")
    else:
        body = answer_match.group("body")
        if body.count("现在请你决定") != 1:
            errors.append("C01模拟回显必须只出现一个决定点")
        for phrase in ("不是“贫穷破旧”", "固有色", "四层边界", "必要缺口", "安全回退"):
            if phrase not in body:
                errors.append(f"C01模拟回显缺少可观察推导：{phrase}")
        for forbidden in ("焦段：", "主光位置：", "完整 GPT Image 2 Prompt"):
            if forbidden in body:
                errors.append(f"C01模拟回显越权：{forbidden}")

    catalog_path = root / "skills/creative-control-versioning/references/control-source-catalog.json"
    try:
        catalog = json.loads(catalog_path.read_text(encoding="utf-8-sig"))
        art = next(item for item in catalog["sources"] if item["source_id"] == "CCS-ART-LOOKDEV")
        if art["current_version"] != "v003" or art["available_versions"] != ["v001", "v002", "v003"]:
            errors.append("美术中央源目录未发布连续v003")
        for relative in (
            "skills/art-lookdev-direction/references/CCS-ART-LOOKDEV@v001.md",
            "skills/art-lookdev-direction/references/CCS-ART-LOOKDEV@v002.md",
            "skills/art-lookdev-direction/assets/美术LookDev基线卡模板.md",
        ):
            if relative not in art["definition_paths"]:
                errors.append(f"美术中央源目录缺少定义：{relative}")
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError, StopIteration) as exc:
        errors.append(f"无法核对美术中央源目录：{exc}")
    return errors


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="检查C01美术与LookDev成熟化合同")
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    return parser.parse_args()


def main() -> int:
    _configure_utf8_stdio()
    errors = validate(Path(_parse_args().root).resolve())
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print("C01检查通过：事实驱动世界设计、四层边界、专业交接、短执行切片与返工路由完整")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
