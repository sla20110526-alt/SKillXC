#!/usr/bin/env python3
"""Validate the C04 dramaturgy scene-beat production contract."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from typing import Mapping, Sequence


CONTRACT_FILES = (
    "skills/dramaturgy-scene-beats/SKILL.md",
    "skills/dramaturgy-scene-beats/agents/openai.yaml",
    "skills/dramaturgy-scene-beats/assets/场戏节拍卡模板.md",
    "skills/dramaturgy-scene-beats/assets/场戏节拍表模板.csv",
    "skills/dramaturgy-scene-beats/assets/scene-beat.schema.json",
    "skills/dramaturgy-scene-beats/references/scene-beat-contract.md",
    "skills/dramaturgy-scene-beats/references/c04-simulated-scene-beat-task.md",
    "skills/script-truth-index/SKILL.md",
    "skills/production-router-handoff/SKILL.md",
    "skills/production-router-handoff/assets/创作任务单模板.md",
    "skills/production-router-handoff/assets/data-contract-map.json",
    "skills/production-router-handoff/references/handoff-contracts.md",
    "skills/production-router-handoff/references/task-artifact-index.md",
    "skills/directing-blocking/SKILL.md",
    "skills/acting-direction/SKILL.md",
    "skills/acting-direction/assets/场戏表演卡模板.md",
    "skills/cinematography-direction/SKILL.md",
    "skills/cinematography-direction/assets/场戏摄影约束卡模板.md",
    "skills/shot-visual-design/assets/分镜设计卡模板.md",
    "skills/editing-rhythm/SKILL.md",
    "skills/film-profile-library/references/phase-routing.md",
    "docs/Skill清单与交接矩阵_v0.1.md",
    "docs/真人写实AI影视生产总流程_v0.1.md",
    "README.md",
    "AGENTS.md",
)

DATASET_VERSION_FIELDS = {
    "节拍边界",
    "触发",
    "人物目标",
    "障碍",
    "策略",
    "可见行为",
    "潜台词",
    "信息变化",
    "权力变化",
    "进出状态",
    "原文定位",
    "原文锁定项",
    "事件顺序",
    "因果依据",
    "适用范围",
    "上游精确引用",
}

CARD_VERSION_FIELDS = {
    "节拍数据集精确引用",
    "场戏总体结构",
    "原文保护结论",
    "Profile采用方法",
    "导演调度切片",
    "场戏表演切片",
    "适用范围",
    "上游精确引用",
}

FORBIDDEN_VISUAL_FIELDS = {
    "景别",
    "构图",
    "机位",
    "摄影机距离",
    "焦段",
    "景深",
    "运镜",
    "摄影机运动",
    "支撑方式",
    "灯光",
    "剪辑切点",
    "正式Prompt",
}


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


def _missing(record: Mapping[str, object], fields: Sequence[str]) -> list[str]:
    return [field for field in fields if not str(record.get(field, "")).strip()]


def _is_no_change(value: object) -> bool:
    text = str(value).strip()
    return text in {"不变", "无变化", "不变：无", "不适用"} or text.startswith("不变：")


def validate_beat_record(record: Mapping[str, object]) -> list[str]:
    """Validate one filled beat row beyond JSON Schema surface checks."""
    errors: list[str] = []
    required = (
        "项目ID",
        "场戏节拍集ID",
        "节拍集版本",
        "场次ID",
        "节拍ID",
        "节拍序号",
        "剧本内容版本",
        "原文定位",
        "剧本事实ID集合",
        "原文锁定项",
        "触发",
        "行动人物ID",
        "人物目标",
        "障碍",
        "策略",
        "可见行为",
        "潜台词",
        "信息进入状态",
        "信息变化",
        "信息离开状态",
        "权力进入状态",
        "权力变化",
        "权力离开状态",
        "节拍进入状态",
        "节拍离开状态",
        "事件顺序锚点",
        "因果依据",
        "字段依据与标签",
        "锁定项保护结论",
    )
    for field in _missing(record, required):
        errors.append(f"场戏节拍缺少：{field}")

    if not re.fullmatch(r"BDT-[A-Z0-9-]+", str(record.get("场戏节拍集ID", ""))):
        errors.append("场戏节拍集ID不符合BDT稳定格式")
    if not re.fullmatch(r"v[0-9]{3,}", str(record.get("节拍集版本", ""))):
        errors.append("节拍集版本不符合v###格式")
    if not re.fullmatch(r"SCN-[A-Z0-9-]+", str(record.get("场次ID", ""))):
        errors.append("场次ID不符合SCN稳定格式")
    if not re.fullmatch(r"BT-[0-9]{3,}", str(record.get("节拍ID", ""))):
        errors.append("节拍ID不符合BT稳定格式")
    try:
        if int(record.get("节拍序号", 0)) < 1:
            errors.append("节拍序号必须从1开始")
    except (TypeError, ValueError):
        errors.append("节拍序号必须是整数")
    mapping = str(record.get("字段依据与标签", ""))
    allowed_tags = (
        "SCRIPT_EXPLICIT",
        "SCRIPT_INFERRED",
        "USER_LOCKED",
        "CREATIVE_PROPOSAL",
        "UNKNOWN",
    )
    for field in ("触发", "目标", "策略", "可见行为", "潜台词", "信息变化", "权力变化"):
        match = re.search(rf"(?:^|；){field}=([^；]+)", mapping)
        if not match or not any(tag in match.group(1) for tag in allowed_tags):
            errors.append(f"字段依据与标签缺少有效映射：{field}")
    if record.get("锁定项保护结论") not in {"保持原文", "不适用"}:
        errors.append("锁定项保护结论非法")

    no_information = _is_no_change(record.get("信息变化", ""))
    no_power = _is_no_change(record.get("权力变化", ""))
    same_state = str(record.get("节拍进入状态", "")).strip() == str(record.get("节拍离开状态", "")).strip()
    if no_information and no_power and same_state:
        errors.append("独立节拍没有信息、权力或状态的真实变化")
    return errors


def validate_beat_sequence(records: Sequence[Mapping[str, object]]) -> list[str]:
    errors: list[str] = []
    if not records:
        return ["场戏节拍表不能为空"]
    ids = [str(item.get("节拍ID", "")) for item in records]
    orders: list[int] = []
    for item in records:
        try:
            orders.append(int(item.get("节拍序号", 0)))
        except (TypeError, ValueError):
            orders.append(0)
    if len(ids) != len(set(ids)):
        errors.append("同一节拍表存在重复节拍ID")
    if len(orders) != len(set(orders)):
        errors.append("同一节拍表存在重复节拍序号")
    if sorted(orders) != list(range(1, len(records) + 1)):
        errors.append("节拍序号必须形成从1开始的连续当前顺序")
    for field in ("项目ID", "场戏节拍集ID", "节拍集版本", "场次ID", "剧本内容版本"):
        values = {str(item.get(field, "")).strip() for item in records}
        if len(values) != 1:
            errors.append(f"同一节拍表的{field}必须一致")
    return errors


def validate_scene_card_record(record: Mapping[str, object]) -> list[str]:
    errors: list[str] = []
    required = (
        "场戏节拍卡ID",
        "场戏节拍卡版本",
        "场戏节拍数据集精确引用",
        "场次ID",
        "剧本内容版本",
        "本场原文定位",
        "锁定台词逐字保持",
        "事件顺序保持",
        "因果保持",
        "出入场保持",
        "未授权改写",
        "Profile关闭结论",
    )
    for field in _missing(record, required):
        errors.append(f"场戏节拍卡缺少：{field}")
    if not re.fullmatch(r"DSB-[A-Z0-9-]+", str(record.get("场戏节拍卡ID", ""))):
        errors.append("场戏节拍卡ID不符合DSB稳定格式")
    if not re.fullmatch(r"v[0-9]{3,}", str(record.get("场戏节拍卡版本", ""))):
        errors.append("场戏节拍卡版本不符合v###格式")
    if not re.fullmatch(r"BDT-[A-Z0-9-]+@v[0-9]{3,}", str(record.get("场戏节拍数据集精确引用", ""))):
        errors.append("场戏节拍卡没有精确引用BDT@版本")
    for field in ("锁定台词逐字保持", "事件顺序保持", "因果保持", "出入场保持"):
        if str(record.get(field, "")).strip() not in {"通过", "不适用"}:
            errors.append(f"原文保护门未通过：{field}")
    if str(record.get("未授权改写", "")).strip() != "无":
        errors.append("存在未授权剧本改写")
    if str(record.get("Profile关闭结论", "")).strip() not in {"未读取", "已关闭"}:
        errors.append("场戏节拍卡交付前没有关闭完整剧作Profile")
    return errors


def validate_script_change(change: Mapping[str, object]) -> list[str]:
    errors: list[str] = []
    changed = [str(item) for item in change.get("锁定内容变化", []) if str(item).strip()]
    authorized = str(change.get("用户改写授权", "否")).strip() == "是"
    old_version = str(change.get("旧剧本内容版本", "")).strip()
    new_version = str(change.get("新剧本内容版本", "")).strip()
    if changed and not authorized:
        errors.append("未授权时不得改写锁定台词、事件顺序或因果")
    if changed and authorized and (not new_version or new_version == old_version):
        errors.append("获授权的改写也必须先建立新的剧本内容版本")
    return errors


def validate_dependency_direction(dataset_refs: str, card_dataset_ref: str) -> list[str]:
    errors: list[str] = []
    if "DSB-" in dataset_refs:
        errors.append("BDT逐节拍数据不得反向引用DSB场戏节拍卡")
    if not re.fullmatch(r"BDT-[A-Z0-9-]+@v[0-9]{3,}", card_dataset_ref.strip()):
        errors.append("DSB场戏节拍卡必须精确引用一个BDT@版本")
    return errors


def validate_downstream_slice(slice_record: Mapping[str, object]) -> list[str]:
    errors: list[str] = []
    recipient = str(slice_record.get("下游Skill", "")).strip()
    if recipient not in {"directing-blocking", "acting-direction"}:
        errors.append("场戏节拍成果只能直接交导演调度或场戏表演适配")
    for key, value in slice_record.items():
        combined = f"{key} {value}"
        for term in FORBIDDEN_VISUAL_FIELDS:
            if term in combined:
                errors.append(f"剧作下游切片越权包含：{term}")
                break
    if not re.search(r"DSB-[A-Z0-9-]+@v[0-9]{3,}", str(slice_record.get("精确成果引用", ""))):
        errors.append("剧作下游切片缺少DSB精确版本")
    if not re.search(r"BDT-[A-Z0-9-]+@v[0-9]{3,}", str(slice_record.get("精确成果引用", ""))):
        errors.append("剧作下游切片缺少BDT精确版本")
    return errors


def validate_profile_use(record: Mapping[str, object]) -> list[str]:
    errors: list[str] = []
    if str(record.get("使用Profile", "否")) == "是":
        if str(record.get("允许阶段", "")) != "剧作与场戏节拍":
            errors.append("编剧／剧作Profile只能在剧作与场戏节拍阶段使用")
        if str(record.get("用户本次确认", "否")) != "是":
            errors.append("读取编剧／剧作Profile前缺少用户本次明确确认")
        if not str(record.get("ProfileID@版本", "")).strip():
            errors.append("剧作Profile缺少精确ID@版本")
    return errors


def requires_new_dataset_version(changed_fields: set[str]) -> bool:
    return bool(changed_fields & DATASET_VERSION_FIELDS)


def requires_new_card_version(changed_fields: set[str]) -> bool:
    return bool(changed_fields & CARD_VERSION_FIELDS)


def validate(root: Path) -> list[str]:
    errors: list[str] = []
    texts = {relative: _read(root, relative, errors) for relative in CONTRACT_FILES}
    skill = texts["skills/dramaturgy-scene-beats/SKILL.md"]
    card = texts["skills/dramaturgy-scene-beats/assets/场戏节拍卡模板.md"]
    contract = texts["skills/dramaturgy-scene-beats/references/scene-beat-contract.md"]
    simulation = texts["skills/dramaturgy-scene-beats/references/c04-simulated-scene-beat-task.md"]
    router = texts["skills/production-router-handoff/SKILL.md"]
    task = texts["skills/production-router-handoff/assets/创作任务单模板.md"]
    handoff = texts["skills/production-router-handoff/references/handoff-contracts.md"]

    for phrase in (
        "A｜场戏节拍建立",
        "B｜剧本／上游换版兼容复核",
        "BDT-<项目代号>-<场次代号>@v###",
        "DSB-<项目代号>-<场次代号>@v###",
        "只交给以下两个责任 Skill",
        "未获授权时",
        "不决定景别、构图、机位",
        "继续兼容",
        "需要下一版本",
        "输入不足",
    ):
        if phrase not in skill:
            errors.append(f"剧作Skill缺少成熟化合同：{phrase}")

    for phrase in (
        "场戏节拍卡ID",
        "场戏节拍数据集精确引用",
        "剧本内容版本",
        "本场原文定位",
        "锁定台词引用与原文",
        "原文保护门",
        "给导演调度的最小切片",
        "给场戏表演适配的最小切片",
        "未授权改写：无 / 有【有则不得交接】",
    ):
        if phrase not in card:
            errors.append(f"场戏节拍卡缺少：{phrase}")

    for phrase in (
        "一个节拍可以包含多句台词和多个动作",
        "不构成新节拍",
        "锁定保护不是“意思差不多”",
        "SCRIPT_INFERRED",
        "DSB 交付即关闭 Profile",
        "BDT 不引用 DSB",
        "不得出现在两个交接切片的决定中",
    ):
        if phrase not in contract:
            errors.append(f"场戏节拍合同缺少：{phrase}")

    for phrase in (
        "剧作工作模式",
        "剧本内容版本与原文定位",
        "剧作锁定保护状态",
        "场戏节拍数据集ID@版本",
        "场戏节拍卡ID@版本",
        "剧作Profile状态",
    ):
        if phrase not in router or phrase not in task:
            errors.append(f"总路由/任务单没有交接C04字段：{phrase}")

    for phrase in (
        "### 场戏剧作任务",
        "BDT-...@v###",
        "DSB-...@v###",
        "下游只有两个",
        "不得预设景别、构图、机位",
    ):
        if phrase not in handoff:
            errors.append(f"剧作交接合同缺少：{phrase}")

    for relative in (
        "skills/directing-blocking/SKILL.md",
        "skills/acting-direction/SKILL.md",
    ):
        downstream = texts[relative]
        for phrase in ("DSB-...@v###", "BDT-...@v###", "不得读取完整编剧／剧作 Profile"):
            if phrase not in downstream:
                errors.append(f"下游没有正确接收C04切片：{relative}：{phrase}")

    acting_card = texts["skills/acting-direction/assets/场戏表演卡模板.md"]
    if "DSB-...@v###；BDT-...@v###" not in acting_card or "剧作Profile关闭状态" not in acting_card:
        errors.append("场戏表演卡没有保存精确节拍成果与Profile关闭状态")

    cinematography = texts["skills/cinematography-direction/SKILL.md"]
    if "摄影不直接读取场戏节拍卡" not in cinematography or "DSB@版本 + BDT@版本" not in cinematography:
        errors.append("摄影没有经导演/表演成果核对剧作来源")
    cinematography_card = texts["skills/cinematography-direction/assets/场戏摄影约束卡模板.md"]
    if "剧作来源一致性" not in cinematography_card or "场戏节拍引用：" in cinematography_card:
        errors.append("场戏摄影约束卡仍在直接引用场戏节拍成果")
    shot_card = texts["skills/shot-visual-design/assets/分镜设计卡模板.md"]
    if "DSB/BDT来源" not in shot_card or "场戏节拍版本：" in shot_card:
        errors.append("分镜设计卡没有经调度/表演继承剧作来源")
    editing = texts["skills/editing-rhythm/SKILL.md"]
    if "不绕过上游直接读取节拍成果" not in editing:
        errors.append("剪辑仍可能绕过导演/表演直接读取剧作成果")

    phase = texts["skills/film-profile-library/references/phase-routing.md"]
    for phrase in ("DSB@版本 + BDT@版本", "DSB交付后关闭", "script-truth-index"):
        if phrase not in phase:
            errors.append(f"剧作Profile阶段合同缺少：{phrase}")

    answer_match = re.search(r"## 合格轻量回显(?P<body>.*?)(?:## 不合格表现)", simulation, re.S)
    if not answer_match:
        errors.append("C04模拟任务缺少合格轻量回显")
    else:
        body = answer_match.group("body")
        if body.count("现在请你决定") != 1:
            errors.append("C04模拟回显必须只出现一个决定点")
        for phrase in ("三拍", "锁定台词", "必要缺口", "不预设任何机位、焦段或运镜", "BDT-DEMO-SCN012@v001"):
            if phrase not in body:
                errors.append(f"C04模拟回显缺少：{phrase}")

    csv_text = texts["skills/dramaturgy-scene-beats/assets/场戏节拍表模板.csv"]
    schema_text = texts["skills/dramaturgy-scene-beats/assets/scene-beat.schema.json"]
    try:
        schema = json.loads(schema_text)
        headers = next(csv.reader([csv_text.strip().splitlines()[0]]))
        if headers != list(schema["properties"]):
            errors.append("场戏节拍CSV表头与Schema properties顺序不一致")
        forbidden = FORBIDDEN_VISUAL_FIELDS & set(schema["properties"])
        if forbidden:
            errors.append(f"场戏节拍Schema越权包含视觉决定字段：{'、'.join(sorted(forbidden))}")
    except (json.JSONDecodeError, KeyError, StopIteration) as exc:
        errors.append(f"无法核对场戏节拍CSV/Schema：{exc}")

    try:
        manifest = json.loads(texts["skills/production-router-handoff/assets/data-contract-map.json"])
        pair = next(
            item for item in manifest["pairs"]
            if item["template"] == "skills/dramaturgy-scene-beats/assets/场戏节拍表模板.csv"
        )
        if pair["schema"] != "skills/dramaturgy-scene-beats/assets/scene-beat.schema.json":
            errors.append("数据契约清单中的场戏节拍Schema映射错误")
        if pair["card"] != "skills/dramaturgy-scene-beats/assets/场戏节拍卡模板.md":
            errors.append("数据契约清单中的场戏节拍卡映射错误")
    except (json.JSONDecodeError, KeyError, StopIteration) as exc:
        errors.append(f"数据契约清单没有登记场戏节拍表：{exc}")

    openai_yaml = texts["skills/dramaturgy-scene-beats/agents/openai.yaml"]
    if "$dramaturgy-scene-beats" not in openai_yaml or "allow_implicit_invocation: false" not in openai_yaml:
        errors.append("剧作openai.yaml没有保持显式调用边界")
    return errors


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="检查C04剧作与场戏节拍成熟化合同")
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    return parser.parse_args()


def main() -> int:
    _configure_utf8_stdio()
    errors = validate(Path(_parse_args().root).resolve())
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print("C04检查通过：场戏节拍、原文保护、稳定版本、Profile关闭与导演/表演最小交接完整")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
