#!/usr/bin/env python3
"""Validate the C08 video QC, evidence, routing, and recording contract."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from typing import Any


CONTRACT_FILES = (
    "skills/video-qc-review/SKILL.md",
    "skills/video-qc-review/agents/openai.yaml",
    "skills/video-qc-review/assets/视频QC诊断与返工模板.md",
    "skills/video-qc-review/assets/视频QC记录模板.csv",
    "skills/video-qc-review/assets/video-qc.schema.json",
    "skills/video-qc-review/assets/视频QC记录卡模板.md",
    "skills/video-qc-review/assets/视频QC记录对话激活指令模板.md",
    "skills/video-qc-review/references/video-qc-diagnosis-contract.md",
    "skills/video-qc-review/references/c08-simulated-qc-task.md",
    "skills/production-router-handoff/SKILL.md",
    "skills/production-router-handoff/assets/创作任务单模板.md",
    "skills/production-router-handoff/assets/data-contract-map.json",
    "skills/production-router-handoff/references/handoff-contracts.md",
    "skills/production-router-handoff/references/interaction-modes.md",
    "skills/production-router-handoff/references/shot-prompt-version-state.md",
    "skills/video-prompt-production/SKILL.md",
    "skills/generation-version-log/SKILL.md",
    "AGENTS.md",
    "README.md",
    "docs/真人写实AI影视生产总流程_v0.1.md",
    "docs/Skill清单与交接矩阵_v0.1.md",
)

CATEGORIES = {
    "人物身份与状态", "表演与口型", "动作与物理接触", "构图与运镜",
    "空间与光线", "连续性", "VFX", "声音",
}
ROOT_LAYERS = {
    "上游设计错误", "Prompt漏译或冲突", "参考映射或负载问题",
    "模型随机偏差", "证据不足暂不可判定",
}
SEVERITIES = {"阻断", "重要", "可接受偏差"}
ROOT_STATES = {"已确认", "高概率", "待复核"}
EVIDENCE_TYPES = {"有声视频", "无声视频", "截图", "用户明确文字反馈", "组合证据"}
USER_RESULTS = {"未提供", "需返修", "部分可用", "可用", "放弃"}
FORMAL_HEADERS = (
    "项目ID", "QC记录集ID", "记录集版本", "QC工作模式", "问题ID", "分镜组ID与版本", "镜头ID与版本", "生成单元ID",
    "正式PromptID与版本", "参考映射ID与版本", "生成结果定位", "证据类型", "证据定位", "时间点或画面范围", "可观察问题",
    "期望依据ID与版本或用户要求", "严重度", "问题类别", "根因层", "根因判定状态", "根因证据", "唯一归属Skill或节点",
    "建议返回节点", "最小修订方向", "复核动作", "用户结果结论", "用户结论原文", "用户记录授权原文", "记录日期", "备注",
)


def _configure_utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="replace")


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def _required(record: dict[str, Any], fields: tuple[str, ...], errors: list[str]) -> None:
    for field in fields:
        value = record.get(field)
        if value is None or value == "" or value == []:
            errors.append(f"缺少诊断字段：{field}")


def validate_diagnosis(record: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required = (
        "对象与版本链", "生成结果定位", "证据类型", "证据定位", "可核验项", "不可核验项",
        "时间点或画面范围", "可观察问题", "期望依据", "严重度", "问题类别", "根因层",
        "根因判定状态", "根因证据", "唯一归属Skill或节点", "建议返回节点", "最小修订方向",
        "复核动作", "用户结果结论", "用户结论原文", "AI直接查看", "记录授权", "写入动作", "对照状态",
    )
    _required(record, required, errors)
    evidence = str(record.get("证据类型", ""))
    category = str(record.get("问题类别", ""))
    root = str(record.get("根因层", ""))
    root_state = str(record.get("根因判定状态", ""))
    owner = str(record.get("唯一归属Skill或节点", ""))
    checks = set(record.get("可核验项", [])) if isinstance(record.get("可核验项"), list) else set()
    comparison = record.get("对照状态", {}) if isinstance(record.get("对照状态"), dict) else {}

    if evidence not in EVIDENCE_TYPES:
        errors.append("证据类型不在允许集合")
    if category not in CATEGORIES:
        errors.append("问题必须归入八类之一")
    if root not in ROOT_LAYERS:
        errors.append("根因层不在允许集合")
    if record.get("严重度") not in SEVERITIES:
        errors.append("严重度不在允许集合")
    if root_state not in ROOT_STATES:
        errors.append("根因判定状态不在允许集合")
    if len(str(record.get("可观察问题", "")).strip()) < 8:
        errors.append("可观察问题必须具体")
    if len(str(record.get("根因证据", "")).strip()) < 8:
        errors.append("根因必须列出对照证据")
    if any(mark in owner for mark in ("；", "、", " + ", ",")):
        errors.append("每条问题只能有一个归属Skill或节点")

    if evidence == "截图":
        forbidden = checks & {"完整动作", "节奏", "声音", "运镜路径", "稳定结束"}
        if forbidden:
            errors.append(f"截图不能单独核验：{sorted(forbidden)}")
    if evidence == "无声视频" and "声音" in checks:
        errors.append("无声视频不能核验声音")
    if evidence == "用户明确文字反馈" and record.get("AI直接查看") == "是":
        errors.append("只有文字反馈时不得声称AI直接查看视频或截图")

    if root == "上游设计错误":
        if comparison.get("上游设计正确") is not False:
            errors.append("上游设计错误必须有当前上游不正确的对照")
        if owner in {"video-qc-review", "video-prompt-production", "外部人工生成节点"}:
            errors.append("上游设计错误必须返回实际字段唯一写入者")
    elif root == "Prompt漏译或冲突":
        if comparison.get("上游设计正确") is not True or comparison.get("VPR完整正确") is not False:
            errors.append("Prompt根因必须证明上游正确且VPR漏译或冲突")
        if owner != "video-prompt-production":
            errors.append("Prompt根因只能返回video-prompt-production")
    elif root == "参考映射或负载问题":
        if comparison.get("上游设计正确") is not True or comparison.get("VPR完整正确") is not True or comparison.get("VRM正确") is not False:
            errors.append("参考根因必须证明上游/VPR正确且VRM有问题")
        if owner != "video-prompt-production":
            errors.append("参考根因只能返回video-prompt-production")
        revision = str(record.get("最小修订方向", ""))
        if "VRM" not in revision or "VPR" not in revision:
            errors.append("参考映射变化必须先升级VRM再升级VPR")
    elif root == "模型随机偏差":
        needed = ("上游设计正确", "VPR完整正确", "VRM正确", "平台设置正确")
        if any(comparison.get(field) is not True for field in needed):
            errors.append("模型随机偏差必须先排除上游、VPR、VRM和设置问题")
        if owner != "外部人工生成节点":
            errors.append("模型随机偏差只能返回外部人工生成节点")
        if "原样重试" not in str(record.get("复核动作", "")) or "不升级" not in str(record.get("最小修订方向", "")):
            errors.append("随机偏差必须保持版本不变并原样重试")
        if root_state == "已确认" and int(record.get("相同输入结果数", 1)) < 2:
            errors.append("单次结果不能把模型随机偏差定为已确认")
    elif root == "证据不足暂不可判定":
        if root_state != "待复核":
            errors.append("证据不足时根因状态必须为待复核")
        if owner != "待补最小证据":
            errors.append("证据不足时不得预造上游返工任务")

    user_result = str(record.get("用户结果结论", ""))
    user_quote = str(record.get("用户结论原文", ""))
    if user_result not in USER_RESULTS:
        errors.append("用户结果结论不在允许集合")
    elif user_result == "未提供" and user_quote != "未提供":
        errors.append("用户未提供结果结论时不得写推断原文")
    elif user_result != "未提供" and user_quote in {"", "未提供"}:
        errors.append("用户结果结论必须保留用户原文")

    authorized = record.get("记录授权") is True
    if not authorized and record.get("写入动作") != "不落盘":
        errors.append("没有明确记录授权时必须不落盘")
    if authorized and not str(record.get("用户记录授权原文", "")).strip():
        errors.append("正式记录必须保留用户授权原文")
    return errors


def validate_formal_row(record: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for field in FORMAL_HEADERS[:-1]:
        if not str(record.get(field, "")).strip():
            errors.append(f"正式QC缺少必填字段：{field}")
    patterns = {
        "QC记录集ID": r"QCR-[A-Z0-9-]+",
        "记录集版本": r"v[0-9]{3,}",
        "问题ID": r"ISS-[0-9]{3,}",
        "正式PromptID与版本": r"VPR-[A-Z0-9-]+@v[0-9]{3,}",
        "参考映射ID与版本": r"VRM-[A-Z0-9-]+@v[0-9]{3,}",
        "记录日期": r"[0-9]{4}-[0-9]{2}-[0-9]{2}",
    }
    for field, pattern in patterns.items():
        if not re.fullmatch(pattern, str(record.get(field, ""))):
            errors.append(f"{field}格式错误")
    if record.get("QC工作模式") not in {"正式记录", "项目复盘记录"}:
        errors.append("QC正式表不得保存即时诊断模式")
    if record.get("问题类别") not in CATEGORIES:
        errors.append("正式QC问题类别非法")
    if record.get("根因层") not in ROOT_LAYERS:
        errors.append("正式QC根因层非法")
    if record.get("根因判定状态") not in ROOT_STATES:
        errors.append("正式QC根因判定状态非法")
    if record.get("用户结果结论") not in USER_RESULTS:
        errors.append("正式QC用户结果结论非法")
    if record.get("用户结果结论") == "未提供" and record.get("用户结论原文") != "未提供":
        errors.append("正式QC不得推断用户结果结论")
    if any(mark in str(record.get("唯一归属Skill或节点", "")) for mark in ("；", "、", " + ", ",")):
        errors.append("正式QC每行只能有一个归属Skill或节点")
    return errors


def validate_project_review(review: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if int(review.get("指定对象数", 0)) < 1:
        errors.append("项目复盘必须冻结至少一个对象")
    accessible = int(review.get("可访问对象数", 0))
    total = int(review.get("指定对象数", 0))
    missing = review.get("缺失对象", [])
    if accessible < total and not missing:
        errors.append("项目复盘必须列出不可访问对象")
    if review.get("自动修改中央Skill") is not False:
        errors.append("项目复盘不得自动修改中央Skill或建立模板Skill")
    if review.get("记录授权") is not True and review.get("写入动作") != "不落盘":
        errors.append("未授权的项目复盘只能分析不落盘")
    return errors


def validate_version_change(previous: dict[str, Any], current: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    tracked = set(FORMAL_HEADERS) - {"记录集版本", "备注"}
    changed = any(previous.get(field) != current.get(field) for field in tracked)
    old_match = re.fullmatch(r"v([0-9]{3,})", str(previous.get("记录集版本", "")))
    new_match = re.fullmatch(r"v([0-9]{3,})", str(current.get("记录集版本", "")))
    if not old_match or not new_match:
        return ["QCR版本格式错误"]
    old_number = int(old_match.group(1))
    new_number = int(new_match.group(1))
    if changed and new_number != old_number + 1:
        errors.append("正式QC内容变化必须建立完整下一QCR版本")
    if not changed and new_number != old_number:
        errors.append("正式QC内容未变不得空升QCR版本")
    return errors


def validate(root: Path) -> list[str]:
    errors: list[str] = []
    texts: dict[str, str] = {}
    for relative in CONTRACT_FILES:
        path = root / relative
        if not path.is_file():
            errors.append(f"缺少C08合同文件：{relative}")
            continue
        try:
            texts[relative] = _text(path)
        except (OSError, UnicodeDecodeError) as exc:
            errors.append(f"C08文件无法按UTF-8读取：{relative}：{exc}")

    csv_rel = "skills/video-qc-review/assets/视频QC记录模板.csv"
    schema_rel = "skills/video-qc-review/assets/video-qc.schema.json"
    if csv_rel in texts and schema_rel in texts:
        headers = next(csv.reader([texts[csv_rel].splitlines()[0]]))
        try:
            schema = json.loads(texts[schema_rel])
            properties = list(schema.get("properties", {}))
            required = set(schema.get("required", []))
            if headers != properties or tuple(headers) != FORMAL_HEADERS:
                errors.append("视频QC CSV表头与Schema字段顺序不一致")
            if required != set(headers) - {"备注"}:
                errors.append("视频QC Schema必填字段不完整")
        except json.JSONDecodeError as exc:
            errors.append(f"视频QC Schema无法解析：{exc}")

    manifest_text = texts.get("skills/production-router-handoff/assets/data-contract-map.json", "")
    if manifest_text:
        manifest = json.loads(manifest_text)
        matches = [
            item for item in manifest.get("pairs", [])
            if item.get("template") == csv_rel
        ]
        expected = {
            "template": csv_rel,
            "schema": schema_rel,
            "card": "skills/video-qc-review/assets/视频QC记录卡模板.md",
        }
        if matches != [expected]:
            errors.append("数据契约清单未正确接入视频QC CSV/Schema/卡")
        if manifest.get("manifest_revision") != "2026-08-14-c08-video-qc-v001":
            errors.append("数据契约清单修订号未更新到C08")

    skill = texts.get("skills/video-qc-review/SKILL.md", "")
    required_skill = (
        "A｜即时诊断", "B｜项目复盘", "C｜正式记录", "视频可检查", "截图只检查", "用户明确文字反馈",
        "人物身份与状态", "表演与口型", "动作与物理接触", "构图与运镜", "空间与光线", "连续性", "VFX", "声音",
        "上游设计错误", "Prompt漏译或冲突", "参考映射或负载问题", "模型随机偏差", "证据不足暂不可判定",
        "每个问题只给一个当前责任节点", "只有用户明确要求保存 QC/失败原因时才落盘", "不要求上传视频",
    )
    for phrase in required_skill:
        if phrase not in skill:
            errors.append(f"视频QC Skill缺少成熟化规则：{phrase}")

    yaml_text = texts.get("skills/video-qc-review/agents/openai.yaml", "")
    if "$video-qc-review" not in yaml_text or "allow_implicit_invocation: false" not in yaml_text:
        errors.append("视频QC入口元数据未保持显式调用")

    integration = {
        "skills/production-router-handoff/SKILL.md": ("视频 QC 任务", "VPR@版本 + VRM@版本", "正式记录必须有用户明确授权原文"),
        "skills/production-router-handoff/assets/创作任务单模板.md": ("视频QC工作模式", "视频QC证据类型与能力边界", "视频QC用户记录授权原文"),
        "skills/production-router-handoff/references/handoff-contracts.md": ("### 视频 QC 与结果回流任务", "每条问题只返回一个责任Skill", "Schema通过不等于根因正确"),
        "skills/production-router-handoff/references/interaction-modes.md": ("项目复盘分析本身仍不落盘", "保存/记录本次复盘"),
        "skills/production-router-handoff/references/shot-prompt-version-state.md": ("用户失败描述只在用户明确要求详细生成记录时保存", "正式QC根因与证据只在用户明确授权QCR时保存"),
        "skills/video-prompt-production/SKILL.md": ("接收 QC 返回时只按其唯一主根因执行", "先建下一VRM再建下一VPR", "外部原样重试"),
        "skills/generation-version-log/SKILL.md": ("不代替 `video-qc-review`", "必须分别取得对应明确授权"),
        "AGENTS.md": ("`video-qc-review` 只做即时诊断", "镜头可用结论不要求上传视频"),
        "README.md": ("视频QC分即时诊断、项目复盘和正式记录三种模式", "AI不替用户判镜头可用"),
    }
    for relative, phrases in integration.items():
        value = texts.get(relative, "")
        for phrase in phrases:
            if phrase not in value:
                errors.append(f"C08交接缺少规则：{relative}：{phrase}")

    card = texts.get("skills/video-qc-review/assets/视频QC记录卡模板.md", "")
    for phrase in ("QC记录集ID", "对应Schema", "数据契约版本", "本次不可核验", "用户结论原文", "Schema 通过不等于"):
        if phrase not in card:
            errors.append(f"视频QC记录卡缺少：{phrase}")

    simulation = texts.get("skills/video-qc-review/references/c08-simulated-qc-task.md", "")
    for phrase in ("截图即时诊断", "明确文字反馈但证据不足", "正式记录授权", "唯一返回节点：外部人工生成节点", "即时诊断，未记录"):
        if phrase not in simulation:
            errors.append(f"C08模拟任务缺少：{phrase}")
    if "下一步只需你决定是否原样重试" not in simulation:
        errors.append("C08模拟任务没有保持一个用户决定点")
    return errors


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="检查C08视频QC与结果回流成熟化合同")
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    return parser.parse_args()


def main() -> int:
    _configure_utf8_stdio()
    errors = validate(Path(_parse_args().root))
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print("C08 video QC contract validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
