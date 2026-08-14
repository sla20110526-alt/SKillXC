#!/usr/bin/env python3
"""Validate the C02 lighting-direction production contract."""

from __future__ import annotations

import argparse
import csv
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
    skill = _read(root, "skills/lighting-direction/SKILL.md", errors)
    baseline = _read(root, "skills/lighting-direction/assets/项目灯光基线卡模板.md", errors)
    map_card = _read(root, "skills/lighting-direction/assets/场景光源地图说明卡模板.md", errors)
    map_csv = _read(root, "skills/lighting-direction/assets/场景光源地图模板.csv", errors)
    person = _read(root, "skills/lighting-direction/assets/人物受光卡模板.md", errors)
    multiview = _read(root, "skills/lighting-direction/assets/多视图灯光继承卡模板.md", errors)
    shot = _read(root, "skills/lighting-direction/assets/镜头灯光短执行卡模板.md", errors)
    decision = _read(root, "skills/lighting-direction/references/lighting-decision-contract.md", errors)
    simulation = _read(root, "skills/lighting-direction/references/c02-simulated-lighting-task.md", errors)
    map_schema = _read(root, "skills/lighting-direction/assets/lighting-source-map.schema.json", errors)
    router = _read(root, "skills/production-router-handoff/SKILL.md", errors)
    task = _read(root, "skills/production-router-handoff/assets/创作任务单模板.md", errors)
    location = _read(root, "skills/location-spatial-production/SKILL.md", errors)
    spatial_bible = _read(root, "skills/location-spatial-production/references/spatial-bible.md", errors)
    image_prompt = _read(root, "skills/image-prompt-production/SKILL.md", errors)
    video_prompt = _read(root, "skills/video-prompt-production/SKILL.md", errors)

    for phrase in (
        "A｜项目灯光长期基线",
        "B｜场景光源地图",
        "C｜人物受光设计",
        "D｜多视图灯光继承",
        "E｜镜头灯光短执行",
        "灯光阶段不读取大师 Profile",
        "不写完整 Prompt、不生成候选、不登记资产",
        "稳定 `LMP-<项目ID>-<场景ID>-<光影状态ID>`",
        "任务成果索引",
    ):
        if phrase not in skill:
            errors.append(f"灯光Skill缺少成熟化合同：{phrase}")

    for phrase in (
        "CCS-LIGHTING@v003",
        "摄影约束承接",
        "人工实景光",
        "环境填充与反射／回弹关系",
        "负补光与控光原则",
        "VFX自发光接入原则",
        "允许剪影的对象、范围与叙事条件",
        "换摄影机后必须重新计算",
    ):
        if phrase not in baseline:
            errors.append(f"项目灯光基线模板缺少：{phrase}")

    for phrase in (
        "主方向光",
        "实景光",
        "环境填充",
        "反射或回弹",
        "负补光",
        "VFX自发光",
    ):
        if phrase not in map_card or phrase not in map_schema:
            errors.append(f"光源地图没有覆盖光角色：{phrase}")

    for phrase in ("眼神光来源", "起点受光", "转折点／遮挡点受光", "禁止无来源补亮"):
        if phrase not in person:
            errors.append(f"人物受光模板缺少：{phrase}")

    for phrase in ("世界光场硬继承", "屏幕阴影方向", "不得替代世界方向", "是否需要新光影状态"):
        if phrase not in multiview:
            errors.append(f"多视图继承模板缺少：{phrase}")

    for phrase in ("灯光执行时间线", "开始—变化—结束", "不是完整Prompt", "不重新导演"):
        if phrase not in shot:
            errors.append(f"镜头灯光短执行模板缺少：{phrase}")

    for phrase in (
        "一个光源、一个阴影方向",
        "摄影规则定义相机侧",
        "不伪造 lux、EV、瓦数或精确光比",
        "摄影机移动不改变光的世界位置",
        "时间、天气、灯具开关、主光条件或VFX阶段改变",
    ):
        if phrase not in decision:
            errors.append(f"灯光决策合同缺少：{phrase}")

    for phrase in (
        "灯光工作模式",
        "当前项目灯光基线ID@版本",
        "场景光源地图ID@版本与光影状态ID",
        "镜头灯光短执行卡ID@版本",
    ):
        if phrase not in router or phrase not in task:
            errors.append(f"总路由/任务单没有交接C02字段：{phrase}")

    if "光源地图由 `lighting-direction` 唯一写入" not in location:
        errors.append("场景空间Skill仍未让出光源地图唯一写入权")
    if "不得反向引用以它为上游的光源地图" not in spatial_bible:
        errors.append("空间圣经与光源地图仍可能形成双向版本依赖")
    if "多视图灯光继承卡" not in image_prompt:
        errors.append("图片Prompt没有读取多视图灯光继承卡")
    if "镜头灯光短执行卡" not in video_prompt:
        errors.append("视频Prompt没有读取镜头灯光短执行卡")

    answer_match = re.search(r"## 合格轻量回显(?P<body>.*?)(?:## 不合格表现)", simulation, re.S)
    if not answer_match:
        errors.append("C02模拟任务缺少合格轻量回显")
    else:
        body = answer_match.group("body")
        if body.count("现在请你决定") != 1:
            errors.append("C02模拟回显必须只出现一个决定点")
        for phrase in ("不是“只有一个光源”", "眼神光来自台灯", "必要缺口", "反向视图"):
            if phrase not in body:
                errors.append(f"C02模拟回显缺少可观察灯光推导：{phrase}")

    schema_path = root / "skills/lighting-direction/assets/lighting-source-map.schema.json"
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8-sig"))
        headers = next(csv.reader([map_csv.strip().splitlines()[0]]))
        if headers != list(schema["properties"]):
            errors.append("光源地图CSV表头与Schema properties顺序不一致")
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError, StopIteration) as exc:
        errors.append(f"无法核对光源地图CSV/Schema：{exc}")

    manifest_path = root / "skills/production-router-handoff/assets/data-contract-map.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        pair = next(
            item for item in manifest["pairs"]
            if item["template"] == "skills/lighting-direction/assets/场景光源地图模板.csv"
        )
        if pair["schema"] != "skills/lighting-direction/assets/lighting-source-map.schema.json":
            errors.append("数据契约清单中的光源地图Schema映射错误")
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError, StopIteration) as exc:
        errors.append(f"数据契约清单没有登记光源地图：{exc}")

    catalog_path = root / "skills/creative-control-versioning/references/control-source-catalog.json"
    try:
        catalog = json.loads(catalog_path.read_text(encoding="utf-8-sig"))
        lighting = next(item for item in catalog["sources"] if item["source_id"] == "CCS-LIGHTING")
        if lighting["current_version"] != "v003" or lighting["available_versions"] != ["v001", "v002", "v003"]:
            errors.append("灯光中央源目录未发布连续v003")
        history = "skills/lighting-direction/references/CCS-LIGHTING@v002.md"
        if history not in lighting["definition_paths"]:
            errors.append("灯光中央源目录缺少v002只读历史")
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError, StopIteration) as exc:
        errors.append(f"无法核对灯光中央源目录：{exc}")
    return errors


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="检查C02灯光指导成熟化合同")
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    return parser.parse_args()


def main() -> int:
    _configure_utf8_stdio()
    errors = validate(Path(_parse_args().root).resolve())
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print("C02检查通过：灯光基线、光源地图、人物受光、多视图继承、镜头短执行与专业边界完整")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
