#!/usr/bin/env python3
"""Validate the C07 Seedance video Prompt contract."""

from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]

CONTRACT_FILES = (
    "skills/video-prompt-production/SKILL.md",
    "skills/video-prompt-production/agents/openai.yaml",
    "skills/video-prompt-production/assets/视频Prompt参考映射表模板.csv",
    "skills/video-prompt-production/assets/video-prompt-reference.schema.json",
    "skills/video-prompt-production/assets/正式Prompt交付卡模板.md",
    "skills/video-prompt-production/assets/单镜头Prompt正文模板.md",
    "skills/video-prompt-production/assets/镜头组Prompt正文模板.md",
    "skills/video-prompt-production/references/seedance-prompt-structure.md",
    "skills/video-prompt-production/references/seedance-prompt-contract.md",
    "skills/video-prompt-production/references/c07-simulated-prompt-task.md",
    "skills/production-router-handoff/SKILL.md",
    "skills/production-router-handoff/assets/创作任务单模板.md",
    "skills/production-router-handoff/assets/data-contract-map.json",
    "skills/production-router-handoff/references/handoff-contracts.md",
    "skills/production-router-handoff/references/task-artifact-index.md",
    "skills/production-router-handoff/references/shot-prompt-version-state.md",
    "skills/production-router-handoff/scripts/test_validate_project_data.py",
    "skills/continuity-readiness-audit/SKILL.md",
    "docs/真人写实AI影视生产总流程_v0.1.md",
    "docs/Skill清单与交接矩阵_v0.1.md",
    "README.md",
    "AGENTS.md",
)

REFERENCE_FIELDS = {
    "项目ID", "参考映射数据集ID", "映射版本", "生成单元ID", "分镜组ID与版本", "参考序号", "平台引用名", "参考类型",
    "主体或对象ID", "正式来源ID与版本或用户参考定位", "当前服装状态或阶段", "适用镜头ID与版本集合", "唯一用途",
    "允许继承", "禁止继承", "平台处理方式", "平台能力核对状态", "来源状态", "备注",
}

PROMPT_ORDER = ("空间与摄影", "第一帧", "动作与表演", "物理接触", "台词与声音", "光影", "稳定结束")
VAGUE_PURPOSES = ("全部参考", "整体参考", "综合风格", "保持一致", "都参考", "全都继承")
MANAGEMENT_MARKERS = ("tasks/", "任务ID", "成果状态", "当前有效", "读取某卡", "读取文件", "登记这张", "ProfileID", "@v001", "@v002")
QUALITY_SLOGANS = ("8K", "IMAX", "电影级", "超真实", "非3D", "杰作品质", "获奖级")
FORBIDDEN_EXTERNAL_ACTIONS = ("提交生成任务", "查询生成进度", "下载视频", "已上传参考", "已提交Seedance", "轮询任务")


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _required(record: dict[str, Any], field: str, errors: list[str]) -> str:
    value = str(record.get(field, "")).strip()
    if not value:
        errors.append(f"缺少必填字段：{field}")
    return value


def validate_reference_record(record: dict[str, Any], for_delivery: bool = True) -> list[str]:
    errors: list[str] = []
    for field in REFERENCE_FIELDS - {"备注"}:
        _required(record, field, errors)

    if not re.fullmatch(r"VRM-[A-Z0-9-]+", str(record.get("参考映射数据集ID", ""))):
        errors.append("参考映射数据集ID格式错误")
    if not re.fullmatch(r"v[0-9]{3,}", str(record.get("映射版本", ""))):
        errors.append("映射版本格式错误")
    if not re.fullmatch(r"[^@；]+@v[0-9]{3,}", str(record.get("分镜组ID与版本", ""))):
        errors.append("分镜组必须使用精确ID@版本")
    try:
        if int(record.get("参考序号", 0)) < 1:
            raise ValueError
    except (TypeError, ValueError):
        errors.append("参考序号必须为正整数")

    purpose = str(record.get("唯一用途", ""))
    if len(purpose.strip()) < 5:
        errors.append("唯一用途必须具体说明可见职责")
    for phrase in VAGUE_PURPOSES:
        if phrase in purpose:
            errors.append(f"参考用途含糊：{phrase}")
    if "人物和场景" in purpose or "身份、动作和光线" in purpose:
        errors.append("一项参考只能承担一个主要用途")

    source_status = str(record.get("来源状态", ""))
    source = str(record.get("正式来源ID与版本或用户参考定位", ""))
    if source_status == "正式可调用资产" and not re.search(r"[^@；\s]+@v[0-9]{3,}", source):
        errors.append("正式媒体来源必须使用精确资产ID@版本")
    if source_status == "用户确认的一次性参考" and len(source.strip()) < 6:
        errors.append("一次性参考必须有可定位来源")

    if str(record.get("参考类型")) == "人物五视图总览卡":
        if source_status != "正式可调用资产":
            errors.append("人物五视图必须来自正式可调用资产")
        if str(record.get("当前服装状态或阶段", "")) in {"", "不适用", "未知", "待确认"}:
            errors.append("人物五视图必须明确匹配当前服装与状态")

    if str(record.get("参考类型")) == "动作或运镜视频参考":
        forbidden = str(record.get("禁止继承", ""))
        for item in ("人物身份", "服装", "场景", "光线"):
            if item not in forbidden:
                errors.append(f"动作/运镜参考必须禁止继承{item}")

    if for_delivery:
        if str(record.get("平台能力核对状态")) != "已核对":
            errors.append("正式交付前平台能力必须已核对")
        if str(record.get("平台处理方式")) == "使用时待核对":
            errors.append("使用时待核对的参考不能进入正式交付")
    return errors


def validate_reference_sequence(
    records: Iterable[dict[str, Any]], expected_character_states: dict[str, str] | None = None
) -> list[str]:
    rows = list(records)
    errors: list[str] = []
    orders: set[int] = set()
    aliases: set[str] = set()
    people: set[str] = set()
    purposes: set[tuple[str, str]] = set()
    for row in rows:
        try:
            order = int(row.get("参考序号", 0))
        except (TypeError, ValueError):
            order = 0
        alias = str(row.get("平台引用名", ""))
        subject = str(row.get("主体或对象ID", ""))
        purpose_key = (subject, str(row.get("唯一用途", "")))
        if order in orders:
            errors.append(f"重复参考序号：{order}")
        orders.add(order)
        if alias in aliases:
            errors.append(f"重复平台引用名：{alias}")
        aliases.add(alias)
        if purpose_key in purposes:
            errors.append(f"同一对象存在重复主要用途：{subject}")
        purposes.add(purpose_key)
        if str(row.get("参考类型")) == "人物五视图总览卡":
            if subject in people:
                errors.append(f"同一人物只能调用一张五视图总览卡：{subject}")
            people.add(subject)
            if expected_character_states and subject in expected_character_states:
                if str(row.get("当前服装状态或阶段")) != expected_character_states[subject]:
                    errors.append(f"人物五视图与当前服装/状态不匹配：{subject}")
    if rows and sorted(orders) != list(range(1, len(rows) + 1)):
        errors.append("参考序号必须从1开始连续排列")
    return errors


def validate_dependency_direction(vrm_upstream: str, prompt_upstream: str) -> list[str]:
    errors: list[str] = []
    if re.search(r"VPR-[A-Z0-9-]+@v[0-9]{3,}", vrm_upstream):
        errors.append("VRM不得反向引用尚未形成的VPR")
    if not re.search(r"VRM-[A-Z0-9-]+@v[0-9]{3,}", prompt_upstream):
        errors.append("正式Prompt必须精确引用当前VRM版本")
    return errors


def validate_prompt_body(body: str, direct_reference_aliases: Iterable[str] = ()) -> list[str]:
    errors: list[str] = []
    positions = [body.find(section) for section in PROMPT_ORDER]
    if any(position < 0 for position in positions):
        missing = [section for section, position in zip(PROMPT_ORDER, positions) if position < 0]
        errors.append(f"Prompt正文缺少装配段落：{'；'.join(missing)}")
    elif positions != sorted(positions):
        errors.append("Prompt正文装配优先级顺序错误")
    for marker in MANAGEMENT_MARKERS:
        if marker in body:
            errors.append(f"Prompt正文泄露管理语言：{marker}")
    slogan_count = sum(1 for slogan in QUALITY_SLOGANS if slogan in body)
    if slogan_count >= 2:
        errors.append("Prompt正文堆叠互相重复的质量口号")
    for alias in direct_reference_aliases:
        if alias not in body:
            errors.append(f"直接平台参考没有在正文绑定唯一用途：{alias}")
    return errors


def validate_prompt_package(package: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    mode = str(package.get("工作模式", ""))
    if mode not in {"单镜头正式Prompt装配", "镜头组正式Prompt装配", "Prompt层返修或上游换版重装配"}:
        errors.append("视频Prompt工作模式无效")
    for field in ("生成单元ID", "分镜组ID与版本", "镜头ID与版本集合", "VRM精确引用", "ERT与ERC精确引用", "逐镜摄影审核", "生成就绪结论", "Prompt正文"):
        _required(package, field, errors)
    if not re.fullmatch(r"[^@；]+@v[0-9]{3,}", str(package.get("分镜组ID与版本", ""))):
        errors.append("Prompt必须精确引用分镜组ID@版本")
    if not re.fullmatch(r"VRM-[A-Z0-9-]+@v[0-9]{3,}", str(package.get("VRM精确引用", ""))):
        errors.append("Prompt必须精确引用VRM@版本")
    source = str(package.get("ERT与ERC精确引用", ""))
    if not re.fullmatch(r"ERT-[A-Z0-9-]+@v[0-9]{3,}；ERC-[A-Z0-9-]+@v[0-9]{3,}", source):
        errors.append("Prompt必须精确引用ERT与ERC")
    if str(package.get("生成就绪结论")) not in {"可继续", "有条件继续"}:
        errors.append("生成就绪暂停时不得交付正式Prompt")
    if str(package.get("仍待核对能力", "无")) != "无":
        errors.append("仍有平台能力待核对时不得交付正式Prompt")
    if str(package.get("分镜写回状态", "全部完成")) != "全部完成":
        errors.append("剪辑或摄影写回未完成时不得交付正式Prompt")

    shots = list(package.get("逐镜", []))
    try:
        total = float(package.get("生成单元总时长", 0))
    except (TypeError, ValueError):
        total = 0
    if total <= 0:
        errors.append("生成单元总时长必须为正数")
    if mode == "单镜头正式Prompt装配":
        if len(shots) != 1:
            errors.append("单镜头模式必须且只能包含一个镜头")
        if "连续单镜头" not in str(package.get("Prompt正文", "")):
            errors.append("单镜头正文必须明确连续单镜头")
    if mode == "镜头组正式Prompt装配":
        if len(shots) < 2:
            errors.append("镜头组模式至少包含两个镜头")
        for shot in shots:
            if not str(shot.get("CUT", "")).strip():
                errors.append("镜头组每镜必须携带CUT或单元边界")
            if not str(shot.get("第一帧", "")).strip() or not str(shot.get("稳定结束", "")).strip():
                errors.append("镜头组每镜必须有第一帧和稳定结束状态")
        if "一镜到底" in str(package.get("Prompt正文", "")) and "不合并成一镜到底" not in str(package.get("Prompt正文", "")):
            errors.append("镜头组不得被改写成一镜到底")
    duration_sum = 0.0
    for shot in shots:
        try:
            duration_sum += float(shot.get("时长", 0))
        except (TypeError, ValueError):
            errors.append("逐镜时长必须是数字")
    if shots and abs(duration_sum - total) > 1e-6:
        errors.append("逐镜时长之和必须等于生成单元总时长")
    errors.extend(validate_prompt_body(str(package.get("Prompt正文", "")), package.get("直接参考别名", [])))
    return errors


VRM_VERSION_FIELDS = {"媒体来源", "参考顺序", "平台引用名", "唯一用途", "允许继承", "禁止继承", "平台处理方式", "适用镜头", "当前服装状态"}
PROMPT_VERSION_FIELDS = {"Prompt正文", "VRM精确引用", "平台设置", "上游精确引用"}


def requires_new_vrm_version(changed_fields: set[str]) -> bool:
    return bool(VRM_VERSION_FIELDS & changed_fields)


def requires_new_prompt_version(changed_fields: set[str]) -> bool:
    return requires_new_vrm_version(changed_fields) or bool(PROMPT_VERSION_FIELDS & changed_fields)


def identity_decision(generation_unit_changed: bool) -> str:
    return "新生成单元+新VRM+新VPR身份" if generation_unit_changed else "保留身份，按内容决定版本"


def validate_external_actions(actions: Iterable[str]) -> list[str]:
    errors: list[str] = []
    text = "；".join(actions)
    for phrase in FORBIDDEN_EXTERNAL_ACTIONS:
        if phrase in text:
            errors.append(f"当前外部人工节点禁止：{phrase}")
    return errors


def _csv_headers(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return next(csv.reader(handle))


def _schema_fields(path: Path) -> tuple[set[str], set[str]]:
    schema = json.loads(_text(path))
    return set(schema.get("properties", {})), set(schema.get("required", []))


def validate(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    texts: dict[str, str] = {}
    for relative in CONTRACT_FILES:
        path = root / relative
        if not path.exists():
            errors.append(f"缺少C07合同文件：{relative}")
            continue
        try:
            texts[relative] = _text(path)
        except UnicodeDecodeError:
            errors.append(f"文件不是UTF-8：{relative}")

    csv_path = root / "skills/video-prompt-production/assets/视频Prompt参考映射表模板.csv"
    schema_path = root / "skills/video-prompt-production/assets/video-prompt-reference.schema.json"
    if csv_path.exists() and schema_path.exists():
        headers = set(_csv_headers(csv_path))
        properties, required = _schema_fields(schema_path)
        if headers != properties or headers != REFERENCE_FIELDS:
            errors.append("视频Prompt参考映射表表头与Schema字段不一致")
        if required != headers - {"备注"}:
            errors.append("视频Prompt参考映射Schema必填字段不完整")

    map_path = root / "skills/production-router-handoff/assets/data-contract-map.json"
    if map_path.exists():
        data = json.loads(_text(map_path))
        pair = {
            "template": "skills/video-prompt-production/assets/视频Prompt参考映射表模板.csv",
            "schema": "skills/video-prompt-production/assets/video-prompt-reference.schema.json",
            "card": "skills/video-prompt-production/assets/正式Prompt交付卡模板.md",
        }
        if pair not in data.get("pairs", []):
            errors.append("数据契约清单未接入视频Prompt参考映射")

    skill = texts.get("skills/video-prompt-production/SKILL.md", "")
    required_skill = (
        "A｜单镜头正式Prompt装配", "B｜镜头组正式Prompt装配", "C｜Prompt层返修或上游换版重装配",
        "VRM-<项目代号>-<生成单元代号>", "VPR-<项目代号>-<生成单元代号>", "每个出场人物只调用一张",
        "空间与摄影", "第一帧", "动作与表演", "物理接触", "台词与声音", "光影", "稳定结束状态",
        "用户手工复制到 Seedance", "不得提交生成任务", "真实 Seedance 生成质量", "不询问或加载任何大师 Profile",
    )
    for phrase in required_skill:
        if phrase not in skill:
            errors.append(f"video-prompt-production缺少关键合同：{phrase}")
    if len(skill.splitlines()) >= 500:
        errors.append("video-prompt-production/SKILL.md超过500行")

    yaml_text = texts.get("skills/video-prompt-production/agents/openai.yaml", "")
    if "$video-prompt-production" not in yaml_text or "allow_implicit_invocation: false" not in yaml_text:
        errors.append("video-prompt-production入口元数据未保持显式调用")

    single = texts.get("skills/video-prompt-production/assets/单镜头Prompt正文模板.md", "")
    group = texts.get("skills/video-prompt-production/assets/镜头组Prompt正文模板.md", "")
    for section in PROMPT_ORDER:
        if section not in single:
            errors.append(f"单镜头模板缺少：{section}")
        if section not in group:
            errors.append(f"镜头组模板缺少：{section}")
    if "连续单镜头" not in single:
        errors.append("单镜头模板没有锁定连续单镜头")
    for phrase in ("总时长", "镜头数", "逐镜时长之和", "CUT", "不得用“同上”"):
        if phrase not in group:
            errors.append(f"镜头组模板缺少：{phrase}")

    card = texts.get("skills/video-prompt-production/assets/正式Prompt交付卡模板.md", "")
    for phrase in ("参考映射Schema", "Prompt成果Schema", "本次 Seedance 工作配置", "人物五视图总览卡检查", "只使用平台引用名"):
        if phrase not in card:
            errors.append(f"正式Prompt交付卡缺少：{phrase}")

    integration = {
        "skills/production-router-handoff/SKILL.md": ("VRM-...@v###", "VPR-...@v###", "不提交、查询或下载 Seedance 任务"),
        "skills/production-router-handoff/references/handoff-contracts.md": ("### Seedance 2.0 视频 Prompt 任务", "逐镜时长之和必须等于总时长", "VRM不得反向引用VPR"),
        "skills/production-router-handoff/references/task-artifact-index.md": ("VRM-...", "VPR-...", "不反向引用 VPR"),
        "skills/production-router-handoff/references/shot-prompt-version-state.md": ("五类稳定身份", "视频参考映射版本", "新 VRM 身份"),
        "docs/真人写实AI影视生产总流程_v0.1.md": ("VRM@版本", "每名人物只调用一张", "系统不提交、查询或下载"),
        "README.md": ("VRM@版本", "单镜和镜头组分别装配", "只供用户手工复制"),
        "AGENTS.md": ("VRM@版本", "VPR@版本", "不提交、查询或下载任务"),
    }
    for relative, phrases in integration.items():
        value = texts.get(relative, "")
        for phrase in phrases:
            if phrase not in value:
                errors.append(f"{relative}缺少C07交接规则：{phrase}")

    contract = texts.get("skills/video-prompt-production/references/seedance-prompt-contract.md", "")
    if len(contract.splitlines()) > 100 and "## 目录" not in contract:
        errors.append("长参考文件缺少目录")
    simulation = texts.get("skills/video-prompt-production/references/c07-simulated-prompt-task.md", "")
    if simulation.count("现在请你决定") != 1:
        errors.append("C07模拟回显必须只保留一个用户决定点")
    if "不会提交、查询或下载" not in simulation or "只有一张匹配状态的五视图总览卡" not in simulation:
        errors.append("C07模拟任务缺少外部节点或人物单卡边界")

    return errors


def main() -> int:
    errors = validate()
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("C07 video Prompt contract validated.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
