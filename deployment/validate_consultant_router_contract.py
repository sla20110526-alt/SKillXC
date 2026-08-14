#!/usr/bin/env python3
"""Validate the C03 specialist-consultant-router production contract."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from typing import Mapping


CONTRACT_FILES = (
    "skills/specialist-consultant-router/SKILL.md",
    "skills/specialist-consultant-router/agents/openai.yaml",
    "skills/specialist-consultant-router/assets/顾问问题包模板.md",
    "skills/specialist-consultant-router/assets/顾问结论卡模板.md",
    "skills/specialist-consultant-router/assets/顾问证据记录模板.csv",
    "skills/specialist-consultant-router/assets/consultant-evidence.schema.json",
    "skills/specialist-consultant-router/references/consultant-routing-contract.md",
    "skills/specialist-consultant-router/references/c03-simulated-consultant-task.md",
    "skills/production-router-handoff/SKILL.md",
    "skills/production-router-handoff/assets/创作任务单模板.md",
    "skills/production-router-handoff/assets/data-contract-map.json",
    "skills/production-router-handoff/references/handoff-contracts.md",
    "skills/production-router-handoff/references/task-artifact-index.md",
    "skills/art-lookdev-direction/SKILL.md",
    "skills/character-asset-production/SKILL.md",
    "skills/character-asset-production/assets/人物资产生产卡模板.md",
    "skills/location-spatial-production/SKILL.md",
    "skills/location-spatial-production/assets/场景空间生产卡模板.md",
    "skills/prop-vehicle-production/SKILL.md",
    "skills/prop-vehicle-production/assets/对象资产生产卡模板.md",
    "skills/creature-monster-production/SKILL.md",
    "skills/creature-monster-production/assets/生命体资产生产卡模板.md",
    "skills/vfx-asset-production/SKILL.md",
    "skills/vfx-asset-production/assets/VFX资产生产卡模板.md",
    "skills/directing-blocking/SKILL.md",
    "skills/shot-visual-design/SKILL.md",
    "skills/shot-visual-design/assets/分镜设计卡模板.md",
    "skills/image-prompt-production/SKILL.md",
    "skills/video-prompt-production/SKILL.md",
    "skills/continuity-readiness-audit/SKILL.md",
    "docs/Skill清单与交接矩阵_v0.1.md",
    "docs/真人写实AI影视生产总流程_v0.1.md",
    "README.md",
    "AGENTS.md",
)

QUESTION_VERSION_FIELDS = {
    "问题含义",
    "剧本出处",
    "准确性等级",
    "主专业领域",
    "次专业领域",
    "当前假设",
    "适用范围",
    "安全边界",
    "所需证据",
    "决策截止点",
}

CONCLUSION_VERSION_FIELDS = {
    "来源集合",
    "来源定位",
    "主张映射",
    "证据强度",
    "结论",
    "不确定性",
    "适用范围",
    "艺术化范围",
    "安全限制",
    "下游采用切片",
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


def _missing(record: Mapping[str, str], fields: tuple[str, ...]) -> list[str]:
    return [field for field in fields if not str(record.get(field, "")).strip()]


def validate_question_record(record: Mapping[str, str]) -> list[str]:
    """Validate a filled consultant question-package record."""
    errors: list[str] = []
    required = (
        "问题包ID",
        "问题包版本",
        "剧本内容版本",
        "原文定位",
        "待裁决字段",
        "当前假设",
        "准确性等级",
        "主专业领域",
        "次专业领域",
        "次领域不可拆分理由",
        "最晚决策点",
        "返回节点",
        "现实危险等级",
        "禁止回答的可执行细节",
        "允许回答的非操作性范围",
    )
    for field in _missing(record, required):
        errors.append(f"顾问问题包缺少：{field}")

    if not re.fullmatch(r"CQP-[A-Z0-9-]+", str(record.get("问题包ID", ""))):
        errors.append("顾问问题包ID不符合CQP稳定格式")
    if not re.fullmatch(r"v[0-9]{3,}", str(record.get("问题包版本", ""))):
        errors.append("顾问问题包版本不符合v###格式")
    if record.get("准确性等级") not in {"必须准确", "允许艺术化", "纯虚构规则"}:
        errors.append("顾问问题包准确性等级非法")
    secondary = str(record.get("次专业领域", "")).strip()
    reason = str(record.get("次领域不可拆分理由", "")).strip()
    if secondary not in {"", "无"} and reason in {"", "不适用", "更全面", "更专业"}:
        errors.append("次专业领域缺少不可拆分且会改变裁决的理由")
    if secondary not in {"", "无"} and secondary == str(record.get("主专业领域", "")).strip():
        errors.append("次专业领域不能与主专业领域相同")
    danger = str(record.get("现实危险等级", "")).strip()
    if danger in {"高风险受限", "需持证或现场专业复核"}:
        forbidden = str(record.get("禁止回答的可执行细节", "")).strip()
        allowed = str(record.get("允许回答的非操作性范围", "")).strip()
        if forbidden in {"", "不适用", "无"}:
            errors.append("高风险问题缺少禁止回答的可执行细节")
        if allowed in {"", "不适用", "无"}:
            errors.append("高风险问题缺少允许回答的非操作性范围")
    return errors


def validate_conclusion_record(record: Mapping[str, str]) -> list[str]:
    """Validate a filled consultant conclusion-card record."""
    errors: list[str] = []
    required = (
        "结论卡ID",
        "结论卡版本",
        "问题包精确引用",
        "证据集精确引用",
        "准确性等级",
        "结论状态",
        "证据强度",
        "来源可用性",
        "不确定性",
        "已核验事实",
        "合理推断",
        "允许艺术化建议",
        "项目纯虚构规则",
        "适用范围",
        "包含可执行伤害细节",
    )
    for field in _missing(record, required):
        errors.append(f"顾问结论卡缺少：{field}")

    if not re.fullmatch(r"CCR-[A-Z0-9-]+", str(record.get("结论卡ID", ""))):
        errors.append("顾问结论卡ID不符合CCR稳定格式")
    if not re.fullmatch(r"v[0-9]{3,}", str(record.get("结论卡版本", ""))):
        errors.append("顾问结论卡版本不符合v###格式")
    if not re.fullmatch(r"CQP-[A-Z0-9-]+@v[0-9]{3,}", str(record.get("问题包精确引用", ""))):
        errors.append("顾问结论卡没有精确引用CQP@版本")
    if not re.fullmatch(r"CED-[A-Z0-9-]+@v[0-9]{3,}", str(record.get("证据集精确引用", ""))):
        errors.append("顾问结论卡没有精确引用CED@版本")

    state = str(record.get("结论状态", ""))
    strength = str(record.get("证据强度", ""))
    availability = str(record.get("来源可用性", ""))
    if state not in {"可靠可采用", "有条件采用", "暂不可裁决"}:
        errors.append("顾问结论状态非法")
    if strength not in {"强", "中", "弱", "不可用"}:
        errors.append("顾问证据强度非法")
    if availability in {"不可靠或不适用", "冲突未解"} and state != "暂不可裁决":
        errors.append("无可靠资料或冲突未解时必须暂不可裁决")
    if record.get("准确性等级") == "必须准确" and state == "可靠可采用" and strength != "强":
        errors.append("必须准确的可靠结论需要强证据")
    if strength in {"弱", "不可用"} and state != "暂不可裁决":
        errors.append("弱或不可用证据不能形成可采用结论")
    if str(record.get("包含可执行伤害细节", "")).strip() != "否":
        errors.append("顾问结论不得包含可执行伤害细节")
    return errors


def validate_downstream_reference(reference: Mapping[str, str]) -> list[str]:
    errors: list[str] = []
    if not re.fullmatch(r"CCR-[A-Z0-9-]+@v[0-9]{3,}", str(reference.get("结论卡引用", ""))):
        errors.append("下游没有精确引用CCR@版本")
    if not re.fullmatch(r"CLM-[0-9]{3,}", str(reference.get("主张ID", ""))):
        errors.append("下游没有精确引用主张ID")
    if not str(reference.get("采用字段", "")).strip():
        errors.append("下游没有填写采用字段")
    if reference.get("结论状态") not in {"可靠可采用", "有条件采用"}:
        errors.append("暂不可裁决或非法结论不得被下游采用")
    if not str(reference.get("适用条件", "")).strip():
        errors.append("下游没有继承顾问结论适用条件")
    return errors


def validate_dependency_placement(input_control_refs: str, consultant_refs: str) -> list[str]:
    errors: list[str] = []
    if "CCR-" in input_control_refs or "CQP-" in input_control_refs or "CED-" in input_control_refs:
        errors.append("顾问成果不得进入长期控制卡直接依赖集合")
    if consultant_refs not in {"", "无"} and not all(
        re.fullmatch(r"CCR-[A-Z0-9-]+@v[0-9]{3,}", item.strip())
        for item in consultant_refs.split("；")
    ):
        errors.append("顾问任务成果引用集合必须只含精确CCR@版本")
    return errors


def requires_new_question_version(changed_fields: set[str]) -> bool:
    return bool(changed_fields & QUESTION_VERSION_FIELDS)


def requires_new_conclusion_version(changed_fields: set[str]) -> bool:
    return bool(changed_fields & CONCLUSION_VERSION_FIELDS)


def validate(root: Path) -> list[str]:
    errors: list[str] = []
    texts = {relative: _read(root, relative, errors) for relative in CONTRACT_FILES}
    skill = texts["skills/specialist-consultant-router/SKILL.md"]
    question = texts["skills/specialist-consultant-router/assets/顾问问题包模板.md"]
    conclusion = texts["skills/specialist-consultant-router/assets/顾问结论卡模板.md"]
    contract = texts["skills/specialist-consultant-router/references/consultant-routing-contract.md"]
    simulation = texts["skills/specialist-consultant-router/references/c03-simulated-consultant-task.md"]
    router = texts["skills/production-router-handoff/SKILL.md"]
    task = texts["skills/production-router-handoff/assets/创作任务单模板.md"]
    handoff = texts["skills/production-router-handoff/references/handoff-contracts.md"]

    for phrase in (
        "A｜专业点分级与最小路由",
        "B｜证据核验与结论形成",
        "C｜结论兼容与影响复核",
        "必须准确 / 允许艺术化 / 纯虚构规则",
        "每个问题包只设一个主专业领域",
        "可靠可采用 / 有条件采用 / 暂不可裁决",
        "不读取大师 Profile",
        "任务成果索引",
        "不得给出可执行步骤、配比剂量、关键参数",
    ):
        if phrase not in skill:
            errors.append(f"专业顾问Skill缺少成熟化合同：{phrase}")

    for phrase in (
        "剧本事实ID@版本",
        "原文定位",
        "当前假设",
        "准确性等级",
        "主专业领域",
        "次领域不可拆分理由",
        "最晚决策点",
        "返回节点",
        "现实危险等级",
    ):
        if phrase not in question:
            errors.append(f"顾问问题包缺少：{phrase}")

    for phrase in (
        "问题包精确引用",
        "证据集精确引用",
        "证据强度总评",
        "当前仍有的最大不确定性",
        "已核验事实",
        "合理推断",
        "允许艺术化建议",
        "项目纯虚构规则",
        "下游可采用切片",
        "本卡是否包含可执行伤害细节：否",
    ):
        if phrase not in conclusion:
            errors.append(f"顾问结论卡缺少：{phrase}")

    for phrase in (
        "每个问题包只能有一个主领域",
        "未核验线索",
        "来源数量不是评分公式",
        "暂不可裁决",
        "危险内容降维",
        "CCR-...@v### #CLM-###",
    ):
        if phrase not in contract:
            errors.append(f"顾问路由合同缺少：{phrase}")

    for phrase in (
        "顾问工作模式",
        "顾问准确性等级",
        "顾问问题包ID@版本",
        "顾问主专业领域",
        "顾问结论卡ID@版本与结论状态",
        "顾问决策截止点与返回节点",
    ):
        if phrase not in router or phrase not in task:
            errors.append(f"总路由/任务单没有交接C03字段：{phrase}")

    for phrase in (
        "顾问问题包",
        "顾问结论卡",
        "问题包或暂不可裁决结论不得进入正式创作事实",
        "不能写入“输入控制卡引用集合”",
    ):
        if phrase not in handoff:
            errors.append(f"顾问交接合同缺少：{phrase}")

    downstream_files = (
        "skills/art-lookdev-direction/SKILL.md",
        "skills/character-asset-production/SKILL.md",
        "skills/location-spatial-production/SKILL.md",
        "skills/prop-vehicle-production/SKILL.md",
        "skills/creature-monster-production/SKILL.md",
        "skills/vfx-asset-production/SKILL.md",
        "skills/directing-blocking/SKILL.md",
        "skills/shot-visual-design/SKILL.md",
        "skills/image-prompt-production/SKILL.md",
        "skills/video-prompt-production/SKILL.md",
    )
    for relative in downstream_files:
        if "CCR@版本 + 主张ID／采用字段 + 结论状态" not in texts[relative]:
            errors.append(f"下游没有精确引用顾问结论：{relative}")

    answer_match = re.search(r"## 合格轻量回显(?P<body>.*?)(?:## 不合格表现)", simulation, re.S)
    if not answer_match:
        errors.append("C03模拟任务缺少合格轻量回显")
    else:
        body = answer_match.group("body")
        if body.count("现在请你决定") != 1:
            errors.append("C03模拟回显必须只出现一个决定点")
        for phrase in ("必须准确", "允许艺术化", "纯虚构规则", "最小路由", "必要缺口", "不能形成“可靠可采用”"):
            if phrase not in body:
                errors.append(f"C03模拟回显缺少：{phrase}")

    csv_text = texts["skills/specialist-consultant-router/assets/顾问证据记录模板.csv"]
    schema_text = texts["skills/specialist-consultant-router/assets/consultant-evidence.schema.json"]
    try:
        schema = json.loads(schema_text)
        headers = next(csv.reader([csv_text.strip().splitlines()[0]]))
        if headers != list(schema["properties"]):
            errors.append("顾问证据CSV表头与Schema properties顺序不一致")
        if "结论卡ID与版本" in headers:
            errors.append("顾问证据集不得反向依赖尚未形成的结论卡")
    except (json.JSONDecodeError, KeyError, StopIteration) as exc:
        errors.append(f"无法核对顾问证据CSV/Schema：{exc}")

    try:
        manifest = json.loads(texts["skills/production-router-handoff/assets/data-contract-map.json"])
        pair = next(
            item for item in manifest["pairs"]
            if item["template"] == "skills/specialist-consultant-router/assets/顾问证据记录模板.csv"
        )
        if pair["schema"] != "skills/specialist-consultant-router/assets/consultant-evidence.schema.json":
            errors.append("数据契约清单中的顾问证据Schema映射错误")
        if pair["card"] != "skills/specialist-consultant-router/assets/顾问结论卡模板.md":
            errors.append("数据契约清单中的顾问证据说明卡映射错误")
    except (json.JSONDecodeError, KeyError, StopIteration) as exc:
        errors.append(f"数据契约清单没有登记顾问证据表：{exc}")

    openai_yaml = texts["skills/specialist-consultant-router/agents/openai.yaml"]
    if "$specialist-consultant-router" not in openai_yaml or "allow_implicit_invocation: false" not in openai_yaml:
        errors.append("专业顾问openai.yaml没有保持显式调用边界")
    return errors


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="检查C03专业顾问路由成熟化合同")
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    return parser.parse_args()


def main() -> int:
    _configure_utf8_stdio()
    errors = validate(Path(_parse_args().root).resolve())
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print("C03检查通过：专业点分级、最小领域、问题包、证据集、结论状态、安全边界与下游精确引用完整")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
