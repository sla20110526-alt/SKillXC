#!/usr/bin/env python3
"""Tests for the C08 video QC contract validator."""

from __future__ import annotations

import csv
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "deployment/validate_video_qc_contract.py"
SPEC = importlib.util.spec_from_file_location("validate_video_qc_contract", MODULE_PATH)
assert SPEC and SPEC.loader
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


def valid_diagnosis() -> dict[str, object]:
    return {
        "对象与版本链": "SBG-DEMO@v002；SHOT-DEMO-003@v002；GU-DEMO-002；VPR-DEMO-GU002@v001；VRM-DEMO-GU002@v001",
        "生成结果定位": "截图02",
        "证据类型": "截图",
        "证据定位": "末帧截图02",
        "可核验项": ["静态连续性"],
        "不可核验项": ["完整动作", "声音", "运镜路径"],
        "时间点或画面范围": "末帧/截图02",
        "可观察问题": "信封在末帧由锁定的右手变为左手",
        "期望依据": "SHOT-DEMO-003@v002与VPR-DEMO-GU002@v001稳定结束段",
        "严重度": "阻断",
        "问题类别": "连续性",
        "根因层": "模型随机偏差",
        "根因判定状态": "高概率",
        "根因证据": "上游与VPR均写右手，VRM只锁信封外观和尺度",
        "唯一归属Skill或节点": "外部人工生成节点",
        "建议返回节点": "外部人工生成节点｜同一输入重试",
        "最小修订方向": "VPR、VRM与设置均不升级",
        "复核动作": "使用完全相同输入原样重试",
        "用户结果结论": "未提供",
        "用户结论原文": "未提供",
        "AI直接查看": "是",
        "记录授权": False,
        "写入动作": "不落盘",
        "对照状态": {"上游设计正确": True, "VPR完整正确": True, "VRM正确": True, "平台设置正确": True},
        "相同输入结果数": 1,
    }


def valid_formal_row() -> dict[str, str]:
    return {
        "项目ID": "DEMO", "QC记录集ID": "QCR-DEMO-GU002", "记录集版本": "v001", "QC工作模式": "正式记录",
        "问题ID": "ISS-001", "分镜组ID与版本": "SBG-DEMO@v002", "镜头ID与版本": "SHOT-DEMO-003@v002", "生成单元ID": "GU-DEMO-002",
        "正式PromptID与版本": "VPR-DEMO-GU002@v001", "参考映射ID与版本": "VRM-DEMO-GU002@v001", "生成结果定位": "截图02",
        "证据类型": "截图", "证据定位": "末帧截图02", "时间点或画面范围": "末帧", "可观察问题": "信封在末帧从右手变为左手",
        "期望依据ID与版本或用户要求": "SHOT-DEMO-003@v002；VPR-DEMO-GU002@v001", "严重度": "阻断", "问题类别": "连续性",
        "根因层": "模型随机偏差", "根因判定状态": "高概率", "根因证据": "上游和VPR都锁定右手，VRM不负责左右手",
        "唯一归属Skill或节点": "外部人工生成节点", "建议返回节点": "相同输入原样重试", "最小修订方向": "不升级任何版本，先原样重试",
        "复核动作": "检查下一次相同输入的末帧持物手", "用户结果结论": "需返修", "用户结论原文": "镜头目前需返修",
        "用户记录授权原文": "把刚才信封左右手问题记录成正式QC", "记录日期": "2026-08-14", "备注": "",
    }


class VideoQcContractTests(unittest.TestCase):
    def test_positive_screenshot_diagnosis_passes(self) -> None:
        self.assertEqual(validator.validate_diagnosis(valid_diagnosis()), [])

    def test_screenshot_cannot_claim_motion_sound_or_rhythm(self) -> None:
        record = valid_diagnosis()
        record["可核验项"] = ["完整动作", "声音", "节奏"]
        errors = validator.validate_diagnosis(record)
        self.assertTrue(any("截图不能单独核验" in item for item in errors))

    def test_silent_video_cannot_verify_sound(self) -> None:
        record = valid_diagnosis()
        record["证据类型"] = "无声视频"
        record["可核验项"] = ["完整动作", "声音"]
        self.assertTrue(any("无声视频不能核验声音" in item for item in validator.validate_diagnosis(record)))

    def test_text_feedback_cannot_claim_direct_view(self) -> None:
        record = valid_diagnosis()
        record["证据类型"] = "用户明确文字反馈"
        self.assertTrue(any("不得声称AI直接查看" in item for item in validator.validate_diagnosis(record)))

    def test_random_root_requires_all_four_comparisons(self) -> None:
        record = valid_diagnosis()
        record["对照状态"] = {"上游设计正确": True, "VPR完整正确": True, "VRM正确": False, "平台设置正确": True}
        self.assertTrue(any("必须先排除" in item for item in validator.validate_diagnosis(record)))

    def test_single_result_cannot_confirm_random_root(self) -> None:
        record = valid_diagnosis()
        record["根因判定状态"] = "已确认"
        self.assertTrue(any("单次结果" in item for item in validator.validate_diagnosis(record)))

    def test_random_root_keeps_versions_and_reruns_identically(self) -> None:
        record = valid_diagnosis()
        record["最小修订方向"] = "升级VPR"
        record["复核动作"] = "改写后生成"
        errors = validator.validate_diagnosis(record)
        self.assertTrue(any("保持版本不变" in item for item in errors))

    def test_prompt_root_requires_upstream_right_and_vpr_wrong(self) -> None:
        record = valid_diagnosis()
        record.update({"根因层": "Prompt漏译或冲突", "唯一归属Skill或节点": "video-prompt-production"})
        self.assertTrue(any("必须证明上游正确" in item for item in validator.validate_diagnosis(record)))
        record["对照状态"] = {"上游设计正确": True, "VPR完整正确": False}
        self.assertEqual(validator.validate_diagnosis(record), [])

    def test_reference_root_requires_vrm_then_vpr(self) -> None:
        record = valid_diagnosis()
        record.update({
            "根因层": "参考映射或负载问题", "唯一归属Skill或节点": "video-prompt-production",
            "对照状态": {"上游设计正确": True, "VPR完整正确": True, "VRM正确": False},
            "最小修订方向": "只升级VPR",
        })
        self.assertTrue(any("先升级VRM" in item for item in validator.validate_diagnosis(record)))

    def test_upstream_root_returns_actual_writer(self) -> None:
        record = valid_diagnosis()
        record.update({"根因层": "上游设计错误", "唯一归属Skill或节点": "shot-visual-design", "对照状态": {"上游设计正确": False}})
        self.assertEqual(validator.validate_diagnosis(record), [])

    def test_insufficient_evidence_cannot_precreate_rework(self) -> None:
        record = valid_diagnosis()
        record.update({"根因层": "证据不足暂不可判定", "根因判定状态": "高概率", "唯一归属Skill或节点": "shot-visual-design"})
        errors = validator.validate_diagnosis(record)
        self.assertTrue(any("必须为待复核" in item for item in errors))
        self.assertTrue(any("不得预造" in item for item in errors))

    def test_one_issue_cannot_have_multiple_owners(self) -> None:
        record = valid_diagnosis()
        record["唯一归属Skill或节点"] = "shot-visual-design；video-prompt-production"
        self.assertTrue(any("只能有一个" in item for item in validator.validate_diagnosis(record)))

    def test_user_result_cannot_be_inferred(self) -> None:
        record = valid_diagnosis()
        record["用户结果结论"] = "可用"
        self.assertTrue(any("必须保留用户原文" in item for item in validator.validate_diagnosis(record)))

    def test_no_recording_without_explicit_authorization(self) -> None:
        record = valid_diagnosis()
        record["写入动作"] = "写QCR"
        self.assertTrue(any("必须不落盘" in item for item in validator.validate_diagnosis(record)))

    def test_positive_formal_row_passes(self) -> None:
        self.assertEqual(validator.validate_formal_row(valid_formal_row()), [])

    def test_formal_table_cannot_store_instant_mode(self) -> None:
        record = valid_formal_row()
        record["QC工作模式"] = "即时诊断"
        self.assertTrue(any("不得保存即时诊断" in item for item in validator.validate_formal_row(record)))

    def test_formal_row_cannot_infer_user_conclusion(self) -> None:
        record = valid_formal_row()
        record["用户结果结论"] = "未提供"
        self.assertTrue(any("不得推断" in item for item in validator.validate_formal_row(record)))

    def test_qcr_content_change_requires_next_version(self) -> None:
        previous = valid_formal_row()
        current = dict(previous)
        current["根因层"] = "Prompt漏译或冲突"
        self.assertTrue(any("完整下一QCR版本" in item for item in validator.validate_version_change(previous, current)))
        current["记录集版本"] = "v002"
        self.assertEqual(validator.validate_version_change(previous, current), [])

    def test_project_review_lists_missing_objects_and_does_not_mutate_skills(self) -> None:
        review = {"指定对象数": 5, "可访问对象数": 3, "缺失对象": [], "自动修改中央Skill": True, "记录授权": False, "写入动作": "写文件"}
        errors = validator.validate_project_review(review)
        self.assertTrue(any("不可访问对象" in item for item in errors))
        self.assertTrue(any("不得自动修改" in item for item in errors))
        self.assertTrue(any("只能分析不落盘" in item for item in errors))

    def test_repository_contract_is_complete(self) -> None:
        self.assertEqual(validator.validate(ROOT), [])

    def test_schema_cannot_lose_root_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self._copy_surface(Path(temp))
            path = root / "skills/video-qc-review/assets/video-qc.schema.json"
            schema = json.loads(path.read_text(encoding="utf-8"))
            schema["required"].remove("根因证据")
            path.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            self.assertTrue(any("必填字段不完整" in item for item in validator.validate(root)))

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
