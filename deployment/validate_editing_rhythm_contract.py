#!/usr/bin/env python3
"""Validate the C06 editing-rhythm data and handoff contract."""

from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]

CONTRACT_FILES = (
    "skills/editing-rhythm/SKILL.md",
    "skills/editing-rhythm/agents/openai.yaml",
    "skills/editing-rhythm/assets/剪辑节奏表模板.csv",
    "skills/editing-rhythm/assets/editing-rhythm.schema.json",
    "skills/editing-rhythm/assets/剪辑节奏卡模板.md",
    "skills/editing-rhythm/references/editing-rhythm-contract.md",
    "skills/editing-rhythm/references/c06-simulated-editing-task.md",
    "skills/shot-visual-design/SKILL.md",
    "skills/shot-visual-design/assets/分镜设计卡模板.md",
    "skills/shot-visual-design/assets/分镜表模板.csv",
    "skills/shot-visual-design/assets/storyboard-shot.schema.json",
    "skills/cinematography-direction/SKILL.md",
    "skills/cinematography-direction/assets/逐镜摄影审核卡模板.md",
    "skills/continuity-readiness-audit/SKILL.md",
    "skills/video-prompt-production/SKILL.md",
    "skills/production-router-handoff/SKILL.md",
    "skills/production-router-handoff/assets/创作任务单模板.md",
    "skills/production-router-handoff/assets/data-contract-map.json",
    "skills/production-router-handoff/references/handoff-contracts.md",
    "skills/production-router-handoff/references/task-artifact-index.md",
    "skills/production-router-handoff/references/shot-prompt-version-state.md",
    "docs/真人写实AI影视生产总流程_v0.1.md",
    "docs/Skill清单与交接矩阵_v0.1.md",
    "README.md",
)

DATASET_FIELDS = {
    "项目ID", "剪辑节奏数据集ID", "节奏数据集版本", "分镜组ID", "输入分镜组版本", "剪辑关系ID", "剪辑序号",
    "当前镜头ID与版本", "下一镜头ID与版本或场末", "当前时长秒", "建议时长秒", "时长依据", "镜头新增价值",
    "切点时机", "切点理由类型", "切点理由", "动作接点", "声音接点", "当前镜头第一帧状态", "当前镜头稳定结束状态",
    "下一镜头第一帧状态或场末", "相邻状态结论", "当前生成单元ID", "建议生成单元ID", "建议生成单元成员镜头ID集合",
    "生成单元决定", "被替代生成单元ID集合", "生成单元进入状态", "生成单元稳定结束状态", "修订动作", "返回责任Skill",
    "调度表演摄影来源引用", "字段依据与状态", "备注",
}

VAGUE_CUT_PATTERNS = ("动作后", "对白后", "情绪点", "合适时", "适时", "自然切", "看情况")
MECHANICAL_PATTERNS = ("平均时长", "统一时长", "每镜相同", "固定3秒", "平均3秒", "自动正反打", "每句对白正反打")
EDITING_OVERREACH = (
    "直接改写分镜", "直接修改分镜", "写入分镜CSV", "写分镜表", "建立正式镜头ID", "建立正式PromptID",
    "35mm", "50mm", "低机位", "俯拍机位", "改变台词", "重写台词", "建立声音身份", "登记声音资产",
)


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _required_text(record: dict[str, Any], field: str, errors: list[str]) -> str:
    value = str(record.get(field, "")).strip()
    if not value:
        errors.append(f"缺少必填字段：{field}")
    return value


def _positive_number(record: dict[str, Any], field: str, errors: list[str]) -> None:
    try:
        if float(record.get(field, 0)) <= 0:
            raise ValueError
    except (TypeError, ValueError):
        errors.append(f"{field}必须为正数")


def validate_generation_unit_change(record: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    decision = str(record.get("生成单元决定", "")).strip()
    current = str(record.get("当前生成单元ID", "")).strip()
    proposed = str(record.get("建议生成单元ID", "")).strip()
    replaced = str(record.get("被替代生成单元ID集合", "")).strip()
    members = str(record.get("建议生成单元成员镜头ID集合", "")).strip()

    if not members:
        errors.append("生成单元必须列出建议成员镜头ID集合")
    if decision == "保持":
        if proposed != current:
            errors.append("生成单元保持时必须保留原ID")
        if replaced not in {"无", "不适用"}:
            errors.append("生成单元保持时不得标记原ID被替代")
    elif decision in {"拆分", "合并", "成员变化", "新建"}:
        if not proposed:
            errors.append("生成单元变化时必须填写新ID或待镜头设计建立")
        if proposed == current:
            errors.append("生成单元拆分/合并/成员变化不得复用原ID")
        if decision != "新建" and current not in replaced:
            errors.append("生成单元变化时被替代集合必须包含原ID")
    else:
        errors.append("生成单元决定不在允许值内")
    return errors


def validate_editing_record(record: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for field in DATASET_FIELDS - {"备注"}:
        _required_text(record, field, errors)

    if not re.fullmatch(r"ERT-[A-Z0-9-]+", str(record.get("剪辑节奏数据集ID", ""))):
        errors.append("剪辑节奏数据集ID格式错误")
    if not re.fullmatch(r"v[0-9]{3,}", str(record.get("节奏数据集版本", ""))):
        errors.append("节奏数据集版本格式错误")
    if not re.fullmatch(r"CUT-[0-9]{3,}", str(record.get("剪辑关系ID", ""))):
        errors.append("剪辑关系ID格式错误")
    try:
        if int(record.get("剪辑序号", 0)) < 1:
            raise ValueError
    except (TypeError, ValueError):
        errors.append("剪辑序号必须为正整数")
    _positive_number(record, "当前时长秒", errors)
    _positive_number(record, "建议时长秒", errors)

    current = str(record.get("当前镜头ID与版本", ""))
    next_shot = str(record.get("下一镜头ID与版本或场末", ""))
    if not re.fullmatch(r"[^@；]+@v[0-9]{3,}", current):
        errors.append("当前镜头必须使用精确ID@版本")
    if next_shot != "场末" and not re.fullmatch(r"[^@；]+@v[0-9]{3,}", next_shot):
        errors.append("下一镜头必须使用精确ID@版本或场末")
    if current == next_shot:
        errors.append("剪辑关系两端不能是同一镜头")

    combined = "；".join(str(record.get(field, "")) for field in ("时长依据", "镜头新增价值", "切点时机", "切点理由", "修订动作"))
    for phrase in MECHANICAL_PATTERNS:
        if phrase in combined:
            errors.append(f"不得机械使用{phrase}")
    timing = str(record.get("切点时机", "")).strip()
    if timing in VAGUE_CUT_PATTERNS or len(timing) < 6:
        errors.append("切点时机必须定位到具体台词、动作、视线、声音或稳定状态")
    reason_type = str(record.get("切点理由类型", ""))
    if reason_type not in {"情绪", "信息", "动作", "声音", "组合", "场末"}:
        errors.append("切点理由类型不在允许值内")
    if len(str(record.get("切点理由", "")).strip()) < 8:
        errors.append("切点理由必须说明对观众理解、预期、冲击或余韵的作用")
    if next_shot == "场末":
        if reason_type != "场末":
            errors.append("场末关系必须使用场末理由类型")
        if "场末" not in str(record.get("下一镜头第一帧状态或场末", "")):
            errors.append("场末关系必须明确场末状态")
    elif reason_type == "场末":
        errors.append("非场末关系不得使用场末理由类型")

    if len(str(record.get("镜头新增价值", "")).strip()) < 6:
        errors.append("每镜必须说明非重复的新增价值")
    if len(str(record.get("时长依据", "")).strip()) < 8:
        errors.append("时长依据必须来自可观察过程")
    if "冲突" in str(record.get("相邻状态结论", "")) and str(record.get("返回责任Skill", "")) == "无需返工":
        errors.append("相邻状态冲突必须返回唯一责任Skill")
    if not any(token in str(record.get("调度表演摄影来源引用", "")) for token in ("DBD-", "DBC-")):
        errors.append("必须携带调度来源精确引用")
    if "表演" not in str(record.get("调度表演摄影来源引用", "")) or "摄影" not in str(record.get("调度表演摄影来源引用", "")):
        errors.append("必须携带表演卡和场戏摄影约束来源")

    for phrase in EDITING_OVERREACH:
        if phrase in combined or phrase in str(record.get("备注", "")):
            errors.append(f"剪辑越权：{phrase}")
    errors.extend(validate_generation_unit_change(record))
    return errors


def validate_editing_sequence(records: Iterable[dict[str, Any]]) -> list[str]:
    rows = list(records)
    errors: list[str] = []
    ids: set[str] = set()
    orders: set[int] = set()
    for row in rows:
        cut_id = str(row.get("剪辑关系ID", ""))
        try:
            order = int(row.get("剪辑序号", 0))
        except (TypeError, ValueError):
            order = 0
        if cut_id in ids:
            errors.append(f"重复剪辑关系ID：{cut_id}")
        ids.add(cut_id)
        if order in orders:
            errors.append(f"重复剪辑序号：{order}")
        orders.add(order)

    ordered = sorted(rows, key=lambda item: int(item.get("剪辑序号", 0))) if rows else []
    for index, row in enumerate(ordered):
        next_shot = str(row.get("下一镜头ID与版本或场末", ""))
        if index < len(ordered) - 1:
            actual_next = str(ordered[index + 1].get("当前镜头ID与版本", ""))
            if next_shot != actual_next:
                errors.append(f"{row.get('剪辑关系ID')}的下一镜头与后续行不一致")
            if next_shot == "场末":
                errors.append("只有最后一条剪辑关系可以指向场末")
        elif next_shot != "场末":
            errors.append("最后一条剪辑关系必须指向场末")
    return errors


def validate_dependency_direction(dataset_upstream: str, card_upstream: str) -> list[str]:
    errors: list[str] = []
    if re.search(r"ERC-[A-Z0-9-]+@v[0-9]{3,}", dataset_upstream):
        errors.append("ERT不得反向引用尚未形成的ERC")
    refs = re.findall(r"[A-Z][A-Z0-9-]+@v[0-9]{3,}", card_upstream)
    if len(refs) != 1 or not refs[0].startswith("ERT-"):
        errors.append("ERC必须只把一个精确ERT版本作为直接成果上游")
    return errors


def validate_profile_use(use: dict[str, str]) -> list[str]:
    errors: list[str] = []
    if use.get("使用Profile") == "是":
        if use.get("允许阶段") != "剪辑与节奏":
            errors.append("剪辑Profile只允许在剪辑与节奏阶段使用")
        if use.get("用户本次确认") != "是":
            errors.append("使用剪辑Profile必须有本阶段用户明确确认")
        if not use.get("ProfileID@版本", "").strip():
            errors.append("使用剪辑Profile必须记录精确ProfileID@版本")
    return errors


DATASET_VERSION_FIELDS = {
    "输入分镜组版本", "当前镜头ID与版本", "下一镜头ID与版本或场末", "当前时长秒", "建议时长秒", "时长依据",
    "镜头新增价值", "切点时机", "切点理由类型", "切点理由", "动作接点", "声音接点", "相邻状态结论",
    "当前生成单元ID", "建议生成单元ID", "建议生成单元成员镜头ID集合", "生成单元决定", "被替代生成单元ID集合",
    "生成单元进入状态", "生成单元稳定结束状态", "修订动作", "返回责任Skill", "调度表演摄影来源引用",
}
CARD_ONLY_VERSION_FIELDS = {"全组节奏判断", "Profile采用审计", "分镜写回切片", "输入阻断"}


def requires_new_dataset_version(changed_fields: set[str]) -> bool:
    return bool(DATASET_VERSION_FIELDS & changed_fields)


def requires_new_card_version(changed_fields: set[str]) -> bool:
    return requires_new_dataset_version(changed_fields) or bool(CARD_ONLY_VERSION_FIELDS & changed_fields)


def validate_card_record(card: dict[str, str]) -> list[str]:
    errors: list[str] = []
    if card.get("Profile关闭结论") not in {"未读取", "已关闭"}:
        errors.append("剪辑Profile没有在ERC交付前关闭")
    if card.get("输入阻断", "无") != "无":
        errors.append("存在输入阻断时ERC不得交接")
    if card.get("来源一致性") != "一致":
        errors.append("调度、表演、摄影与分镜来源不一致")
    if card.get("所有切点有理由") != "是":
        errors.append("每个切点必须有理由")
    if card.get("唯一写回Skill") != "shot-visual-design":
        errors.append("分镜唯一写回者必须是shot-visual-design")
    if card.get("写回后下一节点") != "cinematography-direction":
        errors.append("剪辑写回后必须进入逐镜摄影审核")
    return errors


def _csv_headers(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return next(csv.reader(handle))


def _schema_fields(path: Path) -> tuple[set[str], set[str]]:
    data = json.loads(_text(path))
    return set(data.get("properties", {})), set(data.get("required", []))


def validate(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    texts: dict[str, str] = {}
    for relative in CONTRACT_FILES:
        path = root / relative
        if not path.exists():
            errors.append(f"缺少C06合同文件：{relative}")
            continue
        try:
            texts[relative] = _text(path)
        except UnicodeDecodeError:
            errors.append(f"文件不是UTF-8：{relative}")

    csv_path = root / "skills/editing-rhythm/assets/剪辑节奏表模板.csv"
    schema_path = root / "skills/editing-rhythm/assets/editing-rhythm.schema.json"
    if csv_path.exists() and schema_path.exists():
        headers = set(_csv_headers(csv_path))
        properties, required = _schema_fields(schema_path)
        if headers != properties or DATASET_FIELDS != headers:
            errors.append("剪辑节奏表表头与Schema字段不一致")
        if required != headers - {"备注"}:
            errors.append("剪辑节奏Schema必填字段不完整")

    storyboard_csv = root / "skills/shot-visual-design/assets/分镜表模板.csv"
    storyboard_schema = root / "skills/shot-visual-design/assets/storyboard-shot.schema.json"
    if storyboard_csv.exists() and storyboard_schema.exists():
        headers = set(_csv_headers(storyboard_csv))
        properties, required = _schema_fields(storyboard_schema)
        if headers != properties:
            errors.append("分镜表表头与Schema字段不一致")
        writeback = {"生成单元成员镜头ID集合", "被替代生成单元ID集合", "下一镜头ID与版本或场末", "剪辑关系ID", "切点时机", "切点理由", "动作接点", "声音接点", "相邻状态结论", "剪辑节奏数据集与卡精确引用"}
        if not writeback <= required:
            errors.append("分镜Schema缺少剪辑写回必填字段")

    data_map_path = root / "skills/production-router-handoff/assets/data-contract-map.json"
    if data_map_path.exists():
        data_map = json.loads(_text(data_map_path))
        pair = {
            "template": "skills/editing-rhythm/assets/剪辑节奏表模板.csv",
            "schema": "skills/editing-rhythm/assets/editing-rhythm.schema.json",
            "card": "skills/editing-rhythm/assets/剪辑节奏卡模板.md",
        }
        if pair not in data_map.get("pairs", []):
            errors.append("数据契约清单未接入剪辑节奏CSV/Schema/卡")

    skill = texts.get("skills/editing-rhythm/SKILL.md", "")
    required_skill_phrases = (
        "A｜剪辑节奏审查或重设计", "B｜上游或分镜换版兼容复核", "不绕过上游直接读取节拍成果",
        "不自动把对白做成正反打", "不按平均时长", "shot-visual-design", "cinematography-direction",
        "ERT-<项目代号>-<分镜组代号>", "ERC-<项目代号>-<分镜组代号>", "CUT-###", "Profile已关闭",
    )
    for phrase in required_skill_phrases:
        if phrase not in skill:
            errors.append(f"editing-rhythm缺少关键合同：{phrase}")
    if len(skill.splitlines()) >= 500:
        errors.append("editing-rhythm/SKILL.md超过500行")

    yaml_text = texts.get("skills/editing-rhythm/agents/openai.yaml", "")
    if "$editing-rhythm" not in yaml_text or "allow_implicit_invocation: false" not in yaml_text:
        errors.append("editing-rhythm入口元数据未保持显式调用")

    integration_checks = {
        "skills/shot-visual-design/SKILL.md": ("ERT@版本 + ERC@版本", "逐项判断剪辑提案", "再次提交逐镜摄影审核"),
        "skills/cinematography-direction/SKILL.md": ("ERT@版本 + ERC@版本", "已写回剪辑修订", "不读取 ERC 的剪辑 Profile 审计区"),
        "skills/production-router-handoff/SKILL.md": ("剪辑节奏数据集ID@版本", "剪辑Profile状态", "shot-visual-design` 唯一写回"),
        "skills/production-router-handoff/references/handoff-contracts.md": ("### 剪辑与节奏任务", "剪辑不按平均时长", "随后 `cinematography-direction` 才执行逐镜摄影审核"),
        "skills/production-router-handoff/references/task-artifact-index.md": ("ERT-...", "ERC-...", "不允许 ERT 反向引用 ERC"),
        "skills/production-router-handoff/references/shot-prompt-version-state.md": ("成员集合与内部顺序", "不得让剪辑卡直接改分镜", "不因此递增单镜头版本"),
        "skills/continuity-readiness-audit/SKILL.md": ("ERT@版本 + ERC@版本", "待剪辑建立／待剪辑检查", "逐镜摄影审核"),
        "skills/video-prompt-production/SKILL.md": ("ERT@版本 + ERC@版本", "待剪辑建立／待剪辑检查", "逐镜摄影审核完成"),
    }
    for relative, phrases in integration_checks.items():
        value = texts.get(relative, "")
        for phrase in phrases:
            if phrase not in value:
                errors.append(f"{relative}缺少C06交接规则：{phrase}")

    simulation = texts.get("skills/editing-rhythm/references/c06-simulated-editing-task.md", "")
    if simulation.count("现在请你决定") != 1:
        errors.append("C06模拟回显必须只保留一个用户决定点")
    if "直接改分镜 CSV" not in simulation or "自动补一组正反打" not in simulation:
        errors.append("C06模拟任务缺少越权或机械剪辑负例")

    return errors


def main() -> int:
    errors = validate()
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("C06 editing-rhythm contract validated.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
