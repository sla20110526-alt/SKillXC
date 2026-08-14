#!/usr/bin/env python3
"""Validate the C05 directing and blocking production contract."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from typing import Mapping, Sequence


CONTRACT_FILES = (
    "skills/directing-blocking/SKILL.md",
    "skills/directing-blocking/agents/openai.yaml",
    "skills/directing-blocking/assets/场戏调度卡模板.md",
    "skills/directing-blocking/assets/场戏调度表模板.csv",
    "skills/directing-blocking/assets/directing-blocking.schema.json",
    "skills/directing-blocking/references/directing-blocking-contract.md",
    "skills/directing-blocking/references/c05-simulated-blocking-task.md",
    "skills/dramaturgy-scene-beats/SKILL.md",
    "skills/acting-direction/SKILL.md",
    "skills/acting-direction/assets/场戏表演卡模板.md",
    "skills/location-spatial-production/references/spatial-bible.md",
    "skills/cinematography-direction/SKILL.md",
    "skills/cinematography-direction/assets/场戏摄影约束卡模板.md",
    "skills/shot-visual-design/SKILL.md",
    "skills/shot-visual-design/assets/分镜设计卡模板.md",
    "skills/production-router-handoff/SKILL.md",
    "skills/production-router-handoff/assets/创作任务单模板.md",
    "skills/production-router-handoff/assets/data-contract-map.json",
    "skills/production-router-handoff/references/handoff-contracts.md",
    "skills/production-router-handoff/references/task-artifact-index.md",
    "skills/film-profile-library/references/phase-routing.md",
    "docs/Skill清单与交接矩阵_v0.1.md",
    "docs/真人写实AI影视生产总流程_v0.1.md",
    "README.md",
    "AGENTS.md",
)

DATASET_VERSION_FIELDS = {
    "人物起始坐标或分区",
    "人物结束坐标或分区",
    "与对象起始距离",
    "与对象结束距离",
    "起始朝向",
    "结束朝向",
    "起始视线目标",
    "结束视线目标",
    "遮挡与揭示",
    "进入或离开",
    "移动触发",
    "空间行动与路径",
    "行动目的",
    "接触对象与结果",
    "权力空间变化",
    "轴线ID",
    "银幕方向",
    "越轴与重建空间",
    "连续性结束状态",
    "生命体运动约束引用",
    "VFX时序与接触引用",
    "顾问结论精确引用",
    "专项场景视图缺口",
    "适用范围",
    "上游精确引用",
}

CARD_VERSION_FIELDS = {
    "场戏调度数据集精确引用",
    "观众视点与知情关系",
    "轴线与银幕方向",
    "Profile采用审计",
    "专项场景视图缺口",
    "原文保护门",
    "下游执行切片",
    "适用范围",
}

FORBIDDEN_SCHEMA_FIELDS = {
    "景别",
    "构图",
    "具体机位",
    "摄影机距离",
    "焦段",
    "景深",
    "支撑方式",
    "运镜",
    "摄影机运动",
    "剪辑切点",
    "正式Prompt",
}

FORBIDDEN_BLOCKING_TERMS = (
    "低机位",
    "高机位",
    "俯拍",
    "仰拍",
    "长焦",
    "广角镜头",
    "手持跟拍",
    "摄影机推进",
    "运镜",
    "景别",
    "构图",
)


def _configure_utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="replace")


def _read(root: Path, relative: str, errors: list[str]) -> str:
    try:
        return (root / relative).read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError) as exc:
        errors.append(f"无法按UTF-8读取：{relative}：{exc}")
        return ""


def _missing(record: Mapping[str, object], fields: Sequence[str]) -> list[str]:
    return [field for field in fields if not str(record.get(field, "")).strip()]


def validate_blocking_record(record: Mapping[str, object]) -> list[str]:
    """Validate one filled blocking row beyond JSON Schema surface checks."""
    errors: list[str] = []
    required = (
        "项目ID",
        "场戏调度数据集ID",
        "调度数据集版本",
        "场次ID",
        "调度单元ID",
        "调度序号",
        "节拍ID",
        "行动人物ID",
        "DSB与BDT精确引用",
        "空间圣经ID与版本",
        "空间锚点ID集合",
        "表演母档ID与版本",
        "观众跟随对象",
        "观众知情关系",
        "必须看见信息",
        "暂不可见信息",
        "人物起始坐标或分区",
        "人物结束坐标或分区",
        "与对象起始距离",
        "与对象结束距离",
        "起始朝向",
        "结束朝向",
        "起始视线目标",
        "结束视线目标",
        "遮挡与揭示",
        "进入或离开",
        "移动触发",
        "空间行动与路径",
        "行动目的",
        "接触对象与结果",
        "权力进入状态",
        "权力空间变化",
        "权力离开状态",
        "轴线ID",
        "银幕方向",
        "越轴与重建空间",
        "画外行动与声音线索",
        "连续性结束状态",
        "生命体运动约束引用",
        "VFX时序与接触引用",
        "顾问结论精确引用",
        "专项场景视图缺口",
        "字段依据与状态",
    )
    for field in _missing(record, required):
        errors.append(f"场戏调度缺少：{field}")

    patterns = {
        "场戏调度数据集ID": r"DBD-[A-Z0-9-]+",
        "调度数据集版本": r"v[0-9]{3,}",
        "场次ID": r"SCN-[A-Z0-9-]+",
        "调度单元ID": r"BLK-[0-9]{3,}",
        "节拍ID": r"BT-[0-9]{3,}",
        "轴线ID": r"AX-[A-Z0-9-]+",
    }
    for field, pattern in patterns.items():
        if not re.fullmatch(pattern, str(record.get(field, ""))):
            errors.append(f"{field}不符合稳定格式")
    try:
        if int(record.get("调度序号", 0)) < 1:
            errors.append("调度序号必须从1开始")
    except (TypeError, ValueError):
        errors.append("调度序号必须是整数")

    exact_sources = str(record.get("DSB与BDT精确引用", ""))
    if not re.fullmatch(
        r"DSB-[A-Z0-9-]+@v[0-9]{3,}；BDT-[A-Z0-9-]+@v[0-9]{3,}",
        exact_sources,
    ):
        errors.append("调度单元缺少匹配的DSB与BDT精确版本")

    movement = str(record.get("空间行动与路径", "")).strip()
    trigger = str(record.get("移动触发", "")).strip()
    start = str(record.get("人物起始坐标或分区", "")).strip()
    end = str(record.get("人物结束坐标或分区", "")).strip()
    if movement == "保持位置":
        if start != end:
            errors.append("保持位置时起始与结束位置必须一致")
        if not trigger.startswith("不适用：保持位置"):
            errors.append("保持位置必须明确移动触发不适用")
    elif trigger in {"", "无", "不适用", "不适用：无"} or trigger.startswith("不适用"):
        errors.append("人物移动缺少戏剧触发")

    crossing = str(record.get("越轴与重建空间", "")).strip()
    if crossing != "不越轴" and not ("叙事理由=" in crossing and "重新建立=" in crossing):
        errors.append("故意越轴必须写叙事理由与重新建立空间的方法")

    evidence = str(record.get("字段依据与状态", ""))
    allowed_states = (
        "SCRIPT_EXPLICIT",
        "SCRIPT_INFERRED",
        "USER_LOCKED",
        "CREATIVE_PROPOSAL",
        "可见锁定",
        "关系锁定",
    )
    for field in ("位置", "移动触发", "行动目的", "权力变化"):
        match = re.search(rf"(?:^|；){field}=([^；]+)", evidence)
        if not match or not any(state in match.group(1) for state in allowed_states):
            errors.append(f"字段依据与状态缺少有效映射：{field}")

    combined = " ".join(str(value) for value in record.values())
    if re.search(r"(?<![A-Za-z0-9])\d+(?:\.\d+)?\s*mm(?![A-Za-z])", combined, re.I):
        errors.append("导演调度越权包含具体焦段")
    for term in FORBIDDEN_BLOCKING_TERMS:
        if term in combined:
            errors.append(f"导演调度越权包含逐镜实现：{term}")
            break
    return errors


def validate_blocking_sequence(records: Sequence[Mapping[str, object]]) -> list[str]:
    errors: list[str] = []
    if not records:
        return ["场戏调度表不能为空"]
    ids = [str(row.get("调度单元ID", "")) for row in records]
    orders: list[int] = []
    for row in records:
        try:
            orders.append(int(row.get("调度序号", 0)))
        except (TypeError, ValueError):
            orders.append(0)
    if len(ids) != len(set(ids)):
        errors.append("同一调度表存在重复调度单元ID")
    if len(orders) != len(set(orders)):
        errors.append("同一调度表存在重复调度序号")
    if sorted(orders) != list(range(1, len(records) + 1)):
        errors.append("调度序号必须形成从1开始的连续当前顺序")
    for field in (
        "项目ID",
        "场戏调度数据集ID",
        "调度数据集版本",
        "场次ID",
        "DSB与BDT精确引用",
        "空间圣经ID与版本",
    ):
        if len({str(row.get(field, "")).strip() for row in records}) != 1:
            errors.append(f"同一调度表的{field}必须一致")
    return errors


def validate_scene_card_record(record: Mapping[str, object]) -> list[str]:
    errors: list[str] = []
    required = (
        "场戏调度卡ID",
        "场戏调度卡版本",
        "场戏调度数据集精确引用",
        "场次ID",
        "场戏节拍成果精确来源",
        "剧作原文保护门",
        "Profile关闭结论",
        "阻断缺口",
        "所有移动均有触发目的路径和结束",
        "轴线与银幕方向检查",
    )
    for field in _missing(record, required):
        errors.append(f"场戏调度卡缺少：{field}")
    if not re.fullmatch(r"DBC-[A-Z0-9-]+", str(record.get("场戏调度卡ID", ""))):
        errors.append("场戏调度卡ID不符合DBC稳定格式")
    if not re.fullmatch(r"v[0-9]{3,}", str(record.get("场戏调度卡版本", ""))):
        errors.append("场戏调度卡版本不符合v###格式")
    if not re.fullmatch(
        r"DBD-[A-Z0-9-]+@v[0-9]{3,}",
        str(record.get("场戏调度数据集精确引用", "")),
    ):
        errors.append("场戏调度卡没有精确引用DBD@版本")
    if str(record.get("剧作原文保护门", "")) != "通过":
        errors.append("剧作原文保护门未通过")
    if str(record.get("Profile关闭结论", "")) not in {"未读取", "已关闭"}:
        errors.append("场戏调度卡交付前没有关闭完整导演Profile")
    blocking_gap = str(record.get("阻断缺口", ""))
    if blocking_gap != "无" and not blocking_gap.startswith("仅专项视图生产缺口："):
        errors.append("场戏调度卡仍有阻断缺口")
    if str(record.get("所有移动均有触发目的路径和结束", "")) != "是":
        errors.append("场戏调度卡存在无依据移动")
    if str(record.get("轴线与银幕方向检查", "")) != "通过":
        errors.append("轴线与银幕方向尚未通过")
    return errors


def validate_special_view_gap(record: Mapping[str, object]) -> list[str]:
    if str(record.get("状态", "")).strip() == "无":
        return []
    errors: list[str] = []
    required = (
        "缺口ID",
        "调度单元ID",
        "调度用途",
        "相对空间锚点观察关系",
        "必须可见锚点",
        "必须遮挡锚点",
        "必须离画锚点",
        "返回链",
    )
    for field in _missing(record, required):
        errors.append(f"专项场景视图缺口缺少：{field}")
    if not re.fullmatch(r"SV3-[A-Z0-9-]+", str(record.get("缺口ID", ""))):
        errors.append("专项场景视图缺口ID不符合SV3稳定格式")
    if not re.fullmatch(r"BLK-[0-9]{3,}", str(record.get("调度单元ID", ""))):
        errors.append("专项场景视图缺口没有绑定BLK调度单元")
    if str(record.get("返回链", "")) != "asset-demand-plan → location-spatial-production":
        errors.append("专项场景视图缺口返回链错误")
    return errors


def validate_dependency_direction(dataset_refs: str, card_dataset_ref: str) -> list[str]:
    errors: list[str] = []
    if "DBC-" in dataset_refs:
        errors.append("DBD调度数据不得反向引用DBC调度卡")
    if not re.fullmatch(r"DBD-[A-Z0-9-]+@v[0-9]{3,}", card_dataset_ref.strip()):
        errors.append("DBC调度卡必须精确引用一个DBD@版本")
    return errors


def validate_downstream_slice(record: Mapping[str, object]) -> list[str]:
    errors: list[str] = []
    if str(record.get("下游Skill", "")) not in {
        "acting-direction",
        "cinematography-direction",
        "shot-visual-design",
    }:
        errors.append("导演调度只能交场戏表演、摄影约束或逐镜设计")
    refs = str(record.get("精确成果引用", ""))
    for prefix in ("DBD-", "DBC-", "DSB-", "BDT-"):
        if not re.search(rf"{prefix}[A-Z0-9-]+@v[0-9]{{3,}}", refs):
            errors.append(f"导演下游切片缺少{prefix.rstrip('-')}精确版本")
    forbidden_keys = {"ProfileID@版本", "主体姓名", "片名", "未采用方法"}
    if forbidden_keys & set(record):
        errors.append("导演下游切片泄露Profile采用审计")
    combined = " ".join(str(value) for value in record.values())
    if re.search(r"\d+(?:\.\d+)?\s*mm", combined, re.I):
        errors.append("导演下游切片越权决定具体焦段")
    return errors


def validate_profile_use(record: Mapping[str, object]) -> list[str]:
    errors: list[str] = []
    if str(record.get("使用Profile", "否")) == "是":
        if str(record.get("允许阶段", "")) != "导演与人物调度":
            errors.append("导演Profile本次只能在导演与人物调度阶段使用")
        if str(record.get("用户本次确认", "否")) != "是":
            errors.append("读取导演Profile前缺少本阶段用户明确确认")
        if not str(record.get("ProfileID@版本", "")).strip():
            errors.append("导演Profile缺少精确ID@版本")
    return errors


def requires_new_dataset_version(changed_fields: set[str]) -> bool:
    return bool(changed_fields & DATASET_VERSION_FIELDS)


def requires_new_card_version(changed_fields: set[str]) -> bool:
    return bool(changed_fields & CARD_VERSION_FIELDS)


def validate(root: Path) -> list[str]:
    errors: list[str] = []
    texts = {relative: _read(root, relative, errors) for relative in CONTRACT_FILES}
    skill = texts["skills/directing-blocking/SKILL.md"]
    card = texts["skills/directing-blocking/assets/场戏调度卡模板.md"]
    contract = texts["skills/directing-blocking/references/directing-blocking-contract.md"]
    router = texts["skills/production-router-handoff/SKILL.md"]
    task = texts["skills/production-router-handoff/assets/创作任务单模板.md"]
    handoff = texts["skills/production-router-handoff/references/handoff-contracts.md"]
    artifacts = texts["skills/production-router-handoff/references/task-artifact-index.md"]

    for phrase in (
        "A｜场戏调度建立或重设计",
        "B｜上游或空间换版兼容复核",
        "DBD-<项目代号>-<场次代号>@v###",
        "DBC-<项目代号>-<场次代号>@v###",
        "观众相对各角色知道得更多/相同/更少",
        "人物起始/结束坐标",
        "故意越轴必须同时写叙事理由与重新建立空间的方法",
        "SV3",
        "不设计具体焦段",
        "不写分镜表",
        "继续兼容 / 需要下一版本 / 输入不足",
    ):
        if phrase not in skill:
            errors.append(f"导演调度Skill缺少成熟化合同：{phrase}")

    for phrase in (
        "场戏调度卡ID",
        "场戏调度数据集精确引用",
        "场戏节拍成果精确来源",
        "导演 Profile 采用审计【本区不下传】",
        "场戏级观众关系",
        "轴线与银幕方向",
        "SV3 专项场景视图缺口",
        "下游执行切片【可下传】",
        "Profile关闭结论",
    ):
        if phrase not in card:
            errors.append(f"场戏调度卡缺少：{phrase}")

    for phrase in (
        "`DBD` 不引用 `DBC`",
        "一个调度单元对应",
        "观众视点与逐镜实现边界",
        "触发 → 行动目的 → 可行路径 → 结束状态",
        "更有冲击力",
        "`SV3` 是需求缺口，不是图片资产",
        "只拿转译后的观众关系",
    ):
        if phrase not in contract:
            errors.append(f"导演调度合同缺少：{phrase}")

    for phrase in (
        "导演调度工作模式",
        "场戏调度数据集ID@版本",
        "场戏调度卡ID@版本",
        "导演Profile状态",
        "观众视点与知情关系",
        "轴线与银幕方向状态",
        "SV3专项场景视图缺口",
    ):
        if phrase not in router or phrase not in task:
            errors.append(f"总路由/任务单没有交接C05字段：{phrase}")

    for phrase in (
        "### 场戏导演调度任务",
        "DBD-...@v###",
        "DBC-...@v###",
        "故意越轴",
        "不决定具体焦段",
    ):
        if phrase not in handoff:
            errors.append(f"导演调度交接合同缺少：{phrase}")
    for phrase in ("DBD-...", "DBC-...", "不允许 DBD 反向引用 DBC"):
        if phrase not in artifacts:
            errors.append(f"任务成果索引没有接入C05：{phrase}")

    acting = texts["skills/acting-direction/SKILL.md"]
    acting_card = texts["skills/acting-direction/assets/场戏表演卡模板.md"]
    for phrase in ("DBD-...@v###", "DBC-...@v###", "不读取 DSB 或 DBC 的 Profile 采用审计区"):
        if phrase not in acting:
            errors.append(f"场戏表演没有正确接收C05：{phrase}")
    if "DBD-...@v###；DBC-...@v###" not in acting_card or "导演Profile关闭状态" not in acting_card:
        errors.append("场戏表演卡没有保存导演成果精确版本与Profile关闭状态")

    cinema = texts["skills/cinematography-direction/SKILL.md"]
    cinema_card = texts["skills/cinematography-direction/assets/场戏摄影约束卡模板.md"]
    if "DBD/DBC/DSB/BDT" not in cinema or "不读取 DBC 的导演 Profile 审计区" not in cinema:
        errors.append("场戏摄影约束没有核对C05来源或隔离Profile审计")
    if "DBD-...@v###；DBC-...@v###" not in cinema_card or "四项来源一致性" not in cinema_card:
        errors.append("场戏摄影约束卡没有保存C05来源一致性")

    shot = texts["skills/shot-visual-design/SKILL.md"]
    shot_card = texts["skills/shot-visual-design/assets/分镜设计卡模板.md"]
    if (
        "DBD@版本 + DBC@版本" not in shot
        or "不读取 DBC 的导演 Profile 采用审计区" not in shot
        or "仍标记“仅专项视图生产缺口”" not in shot
    ):
        errors.append("逐镜设计没有读取C05执行切片或隔离Profile审计")
    if "DBD-...@v###；DBC-...@v###" not in shot_card or "调度/表演/摄影来源一致性" not in shot_card:
        errors.append("分镜设计卡没有保存C05精确来源")

    phase = texts["skills/film-profile-library/references/phase-routing.md"]
    for phrase in ("导演与人物调度", "当前导演调度卡交付后", "观众视点、信息顺序、空间行动、轴线"):
        if phrase not in phase:
            errors.append(f"导演Profile阶段合同缺少：{phrase}")

    simulation = texts["skills/directing-blocking/references/c05-simulated-blocking-task.md"]
    answer_match = re.search(r"## 合格轻量回显(?P<body>.*?)(?:## 不合格表现)", simulation, re.S)
    if not answer_match:
        errors.append("C05模拟任务缺少合格轻量回显")
    else:
        body = answer_match.group("body")
        if body.count("现在请你决定") != 1:
            errors.append("C05模拟回显必须只出现一个决定点")
        for phrase in ("两条调度单元", "保持位置", "必要缺口", "DBD-DEMO-SCN012@v001", "不会在本阶段预设机位、焦段或运镜"):
            if phrase not in body:
                errors.append(f"C05模拟回显缺少：{phrase}")

    csv_text = texts["skills/directing-blocking/assets/场戏调度表模板.csv"]
    schema_text = texts["skills/directing-blocking/assets/directing-blocking.schema.json"]
    try:
        schema = json.loads(schema_text)
        headers = next(csv.reader([csv_text.strip().splitlines()[0]]))
        if headers != list(schema["properties"]):
            errors.append("场戏调度CSV表头与Schema properties顺序不一致")
        forbidden = FORBIDDEN_SCHEMA_FIELDS & set(schema["properties"])
        if forbidden:
            errors.append(f"场戏调度Schema越权包含逐镜字段：{'、'.join(sorted(forbidden))}")
    except (json.JSONDecodeError, KeyError, StopIteration) as exc:
        errors.append(f"无法核对场戏调度CSV/Schema：{exc}")

    try:
        manifest = json.loads(texts["skills/production-router-handoff/assets/data-contract-map.json"])
        pair = next(
            item for item in manifest["pairs"]
            if item["template"] == "skills/directing-blocking/assets/场戏调度表模板.csv"
        )
        if pair["schema"] != "skills/directing-blocking/assets/directing-blocking.schema.json":
            errors.append("数据契约清单中的场戏调度Schema映射错误")
        if pair["card"] != "skills/directing-blocking/assets/场戏调度卡模板.md":
            errors.append("数据契约清单中的场戏调度卡映射错误")
    except (json.JSONDecodeError, KeyError, StopIteration) as exc:
        errors.append(f"数据契约清单没有登记场戏调度表：{exc}")

    yaml_text = texts["skills/directing-blocking/agents/openai.yaml"]
    if "$directing-blocking" not in yaml_text or "allow_implicit_invocation: false" not in yaml_text:
        errors.append("导演调度openai.yaml没有保持显式调用边界")

    docs = "\n".join(
        texts[path]
        for path in (
            "docs/Skill清单与交接矩阵_v0.1.md",
            "docs/真人写实AI影视生产总流程_v0.1.md",
            "README.md",
            "AGENTS.md",
        )
    )
    for phrase in ("DBD@版本", "DBC@版本", "SV3", "不写分镜表"):
        if phrase not in docs:
            errors.append(f"系统文档没有同步C05：{phrase}")
    return errors


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="检查C05导演与人物调度成熟化合同")
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    return parser.parse_args()


def main() -> int:
    _configure_utf8_stdio()
    errors = validate(Path(_parse_args().root).resolve())
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print("C05检查通过：调度数据、观众关系、移动触发、轴线、专项视图、稳定版本与下游边界完整")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
