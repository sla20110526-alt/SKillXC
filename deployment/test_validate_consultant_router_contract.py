#!/usr/bin/env python3
"""Tests for the C03 specialist-consultant-router contract."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import validate_consultant_router_contract as validator


ROOT = Path(__file__).resolve().parents[1]


def valid_question() -> dict[str, str]:
    return {
        "问题包ID": "CQP-DEMO-SCN01-001",
        "问题包版本": "v001",
        "剧本内容版本": "SCRIPT-DEMO@v001",
        "原文定位": "SCN-001段落03",
        "待裁决字段": "人物是否可以进入未知云雾区",
        "当前假设": "未知物质，暂不命名",
        "准确性等级": "必须准确",
        "主专业领域": "特技VFX现象与现场安全",
        "次专业领域": "无",
        "次领域不可拆分理由": "不适用",
        "最晚决策点": "导演调度确认前",
        "返回节点": "vfx-asset-production；directing-blocking",
        "现实危险等级": "高风险受限",
        "禁止回答的可执行细节": "配比剂量、获取和释放步骤",
        "允许回答的非操作性范围": "可见后果、人物安全反应和现场复核需求",
    }


def valid_conclusion() -> dict[str, str]:
    return {
        "结论卡ID": "CCR-DEMO-SCN01-001",
        "结论卡版本": "v001",
        "问题包精确引用": "CQP-DEMO-SCN01-001@v001",
        "证据集精确引用": "CED-DEMO-SCN01-001@v001",
        "准确性等级": "必须准确",
        "结论状态": "可靠可采用",
        "证据强度": "强",
        "来源可用性": "可靠且适用",
        "不确定性": "真实物质身份未定义，本卡只裁决安全反应",
        "已核验事实": "未知危险云雾区不得由未防护角色直接进入",
        "合理推断": "不适用",
        "允许艺术化建议": "只可调整白雾可见密度",
        "项目纯虚构规则": "不适用",
        "适用范围": "SCN-001主角门外观察段落",
        "包含可执行伤害细节": "否",
    }


class ConsultantRouterContractTests(unittest.TestCase):
    def test_repository_contract_passes(self) -> None:
        self.assertEqual(validator.validate(ROOT), [])

    def test_question_requires_script_provenance(self) -> None:
        record = valid_question()
        record["原文定位"] = ""
        self.assertTrue(any("原文定位" in item for item in validator.validate_question_record(record)))

    def test_secondary_domain_requires_non_split_reason(self) -> None:
        record = valid_question()
        record["次专业领域"] = "医学法医与生理"
        record["次领域不可拆分理由"] = "更全面"
        self.assertTrue(any("次专业领域" in item for item in validator.validate_question_record(record)))

    def test_high_risk_question_requires_non_operational_boundary(self) -> None:
        record = valid_question()
        record["允许回答的非操作性范围"] = "无"
        self.assertTrue(any("非操作性范围" in item for item in validator.validate_question_record(record)))

    def test_unreliable_source_cannot_be_adopted_as_fact(self) -> None:
        record = valid_conclusion()
        record["来源可用性"] = "冲突未解"
        self.assertTrue(any("暂不可裁决" in item for item in validator.validate_conclusion_record(record)))

    def test_must_be_accurate_requires_strong_evidence(self) -> None:
        record = valid_conclusion()
        record["证据强度"] = "中"
        self.assertTrue(any("强证据" in item for item in validator.validate_conclusion_record(record)))

    def test_dangerous_conclusion_cannot_contain_executable_harm(self) -> None:
        record = valid_conclusion()
        record["包含可执行伤害细节"] = "是"
        self.assertTrue(any("可执行伤害细节" in item for item in validator.validate_conclusion_record(record)))

    def test_downstream_cannot_adopt_undecided_conclusion(self) -> None:
        reference = {
            "结论卡引用": "CCR-DEMO-SCN01-001@v001",
            "主张ID": "CLM-001",
            "采用字段": "人物安全反应",
            "结论状态": "暂不可裁决",
            "适用条件": "仅SCN-001",
        }
        self.assertTrue(any("不得被下游采用" in item for item in validator.validate_downstream_reference(reference)))

    def test_consultant_result_cannot_enter_long_term_direct_dependency(self) -> None:
        errors = validator.validate_dependency_placement(
            "CC-STYLE-001@v001；CCR-DEMO-SCN01-001@v001",
            "CCR-DEMO-SCN01-001@v001",
        )
        self.assertTrue(any("直接依赖集合" in item for item in errors))

    def test_version_triggers_are_separate(self) -> None:
        self.assertTrue(validator.requires_new_question_version({"剧本出处"}))
        self.assertFalse(validator.requires_new_question_version({"索引状态"}))
        self.assertTrue(validator.requires_new_conclusion_version({"证据强度"}))
        self.assertFalse(validator.requires_new_conclusion_version({"复核日期"}))

    def test_simulation_must_keep_one_decision(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self._copy_surface(Path(temp))
            path = root / "skills/specialist-consultant-router/references/c03-simulated-consultant-task.md"
            text = path.read_text(encoding="utf-8").replace(
                "下一步：确认后建立",
                "现在请你决定：是否命名物质？\n\n下一步：确认后建立",
            )
            path.write_text(text, encoding="utf-8")
            self.assertTrue(any("一个决定点" in item for item in validator.validate(root)))

    def test_schema_cannot_lose_evidence_strength(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self._copy_surface(Path(temp))
            path = root / "skills/specialist-consultant-router/assets/consultant-evidence.schema.json"
            path.write_text(
                path.read_text(encoding="utf-8").replace(
                    '    "证据强度": {"type": "string"',
                    '    "证据等级": {"type": "string"',
                    1,
                ),
                encoding="utf-8",
            )
            self.assertTrue(any("表头与Schema" in item for item in validator.validate(root)))

    @staticmethod
    def _copy_surface(target: Path) -> Path:
        for relative in validator.CONTRACT_FILES:
            source = ROOT / relative
            destination = target / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(source.read_bytes())
        return target


if __name__ == "__main__":
    unittest.main()
