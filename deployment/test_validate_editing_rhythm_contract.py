#!/usr/bin/env python3
"""Tests for the C06 editing-rhythm contract validator."""

from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "deployment/validate_editing_rhythm_contract.py"
SPEC = importlib.util.spec_from_file_location("validate_editing_rhythm_contract", MODULE_PATH)
assert SPEC and SPEC.loader
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


def valid_record() -> dict[str, object]:
    return {
        "项目ID": "DEMO",
        "剪辑节奏数据集ID": "ERT-DEMO-SBG012",
        "节奏数据集版本": "v001",
        "分镜组ID": "SBG-DEMO-012",
        "输入分镜组版本": "v001",
        "剪辑关系ID": "CUT-001",
        "剪辑序号": 1,
        "当前镜头ID与版本": "SH-DEMO-001@v001",
        "下一镜头ID与版本或场末": "SH-DEMO-002@v001",
        "当前时长秒": 2.5,
        "建议时长秒": 3.2,
        "时长依据": "让命令结束、拒绝停顿成立后再开始移动",
        "镜头新增价值": "建立主任命令压力与林舟拒绝服从",
        "切点时机": "林舟停顿结束且右脚第一次迈出时",
        "切点理由类型": "动作",
        "切点理由": "在行动启动点切入，让观众从语言压力转向可见反抗",
        "动作接点": "A镜右脚启动，B镜同方向承接第一步",
        "声音接点": "命令同期结束，房间底噪跨切保持",
        "当前镜头第一帧状态": "主任指向椅子，林舟站定",
        "当前镜头稳定结束状态": "林舟重心前移、右脚启动",
        "下一镜头第一帧状态或场末": "林舟右脚继续同方向迈出",
        "相邻状态结论": "匹配：动作、视线与银幕方向连续",
        "当前生成单元ID": "GU-001",
        "建议生成单元ID": "GU-001",
        "建议生成单元成员镜头ID集合": "SH-DEMO-001；SH-DEMO-002",
        "生成单元决定": "保持",
        "被替代生成单元ID集合": "不适用",
        "生成单元进入状态": "主任抬手指向椅子",
        "生成单元稳定结束状态": "林舟到达桌边并停稳",
        "修订动作": "调整当前镜头时长；细化切点",
        "返回责任Skill": "无需返工",
        "调度表演摄影来源引用": "DBD-DEMO-SCN012@v001；DBC-DEMO-SCN012@v001；场戏表演卡ACT-SCN012@v001；场戏摄影约束CIN-SCN012@v001",
        "字段依据与状态": "时长=上游明确；切点=剪辑推断已说明",
        "备注": "",
    }


def valid_card() -> dict[str, str]:
    return {
        "Profile关闭结论": "已关闭",
        "输入阻断": "无",
        "来源一致性": "一致",
        "所有切点有理由": "是",
        "唯一写回Skill": "shot-visual-design",
        "写回后下一节点": "cinematography-direction",
    }


class EditingRhythmContractTests(unittest.TestCase):
    def test_repository_contract_is_complete(self) -> None:
        self.assertEqual(validator.validate(ROOT), [])

    def test_positive_record_passes(self) -> None:
        self.assertEqual(validator.validate_editing_record(valid_record()), [])

    def test_missing_input_and_nonpositive_duration_fail(self) -> None:
        record = valid_record()
        record["时长依据"] = ""
        record["建议时长秒"] = 0
        errors = validator.validate_editing_record(record)
        self.assertTrue(any("时长依据" in item for item in errors))
        self.assertTrue(any("正数" in item for item in errors))

    def test_vague_cut_and_weak_reason_fail(self) -> None:
        record = valid_record()
        record["切点时机"] = "动作后"
        record["切点理由"] = "更好"
        errors = validator.validate_editing_record(record)
        self.assertTrue(any("切点时机" in item for item in errors))
        self.assertTrue(any("切点理由" in item for item in errors))

    def test_mechanical_average_and_auto_reverse_shot_fail(self) -> None:
        record = valid_record()
        record["时长依据"] = "按平均时长统一处理"
        record["镜头新增价值"] = "每句对白正反打"
        errors = validator.validate_editing_record(record)
        self.assertTrue(any("平均时长" in item for item in errors))
        self.assertTrue(any("正反打" in item for item in errors))

    def test_editing_overreach_focal_length_and_storyboard_write_fail(self) -> None:
        record = valid_record()
        record["修订动作"] = "直接改写分镜并改成35mm低机位"
        errors = validator.validate_editing_record(record)
        self.assertTrue(any("越权" in item for item in errors))

    def test_split_generation_unit_requires_new_identity_and_replacement(self) -> None:
        record = valid_record()
        record["生成单元决定"] = "拆分"
        record["建议生成单元ID"] = "GU-001"
        record["被替代生成单元ID集合"] = "无"
        errors = validator.validate_editing_record(record)
        self.assertTrue(any("不得复用原ID" in item for item in errors))
        self.assertTrue(any("被替代集合" in item for item in errors))

    def test_valid_generation_split_can_defer_new_id_to_shot_design(self) -> None:
        record = valid_record()
        record["生成单元决定"] = "拆分"
        record["建议生成单元ID"] = "待shot-visual-design建立"
        record["建议生成单元成员镜头ID集合"] = "SH-DEMO-001"
        record["被替代生成单元ID集合"] = "GU-001"
        self.assertEqual(validator.validate_editing_record(record), [])

    def test_scene_end_requires_scene_end_reason_and_state(self) -> None:
        record = valid_record()
        record["下一镜头ID与版本或场末"] = "场末"
        errors = validator.validate_editing_record(record)
        self.assertTrue(any("场末理由" in item for item in errors))
        self.assertTrue(any("场末状态" in item for item in errors))

    def test_sequence_rejects_duplicate_cut_order_and_broken_adjacency(self) -> None:
        first = valid_record()
        second = valid_record()
        second["当前镜头ID与版本"] = "SH-DEMO-003@v001"
        second["下一镜头ID与版本或场末"] = "场末"
        errors = validator.validate_editing_sequence([first, second])
        self.assertTrue(any("重复剪辑关系ID" in item for item in errors))
        self.assertTrue(any("重复剪辑序号" in item for item in errors))
        self.assertTrue(any("后续行不一致" in item for item in errors))

    def test_dependency_direction_is_one_way(self) -> None:
        errors = validator.validate_dependency_direction(
            "SBG-DEMO-012@v001；ERC-DEMO-SBG012@v001",
            "ERT-DEMO-SBG012@v001；DBD-DEMO-SCN012@v001",
        )
        self.assertTrue(any("反向引用" in item for item in errors))
        self.assertTrue(any("只把一个" in item for item in errors))

    def test_profile_requires_editing_stage_confirmation(self) -> None:
        use = {
            "使用Profile": "是",
            "允许阶段": "项目风格意图基线",
            "用户本次确认": "否",
            "ProfileID@版本": "FP-EDI-DEMO@v1.1",
        }
        errors = validator.validate_profile_use(use)
        self.assertTrue(any("剪辑与节奏阶段" in item for item in errors))
        self.assertTrue(any("本阶段用户明确确认" in item for item in errors))

    def test_version_triggers_separate_dataset_card_and_status(self) -> None:
        self.assertTrue(validator.requires_new_dataset_version({"切点时机"}))
        self.assertTrue(validator.requires_new_dataset_version({"建议生成单元ID"}))
        self.assertFalse(validator.requires_new_dataset_version({"复核日期"}))
        self.assertTrue(validator.requires_new_card_version({"Profile采用审计"}))
        self.assertFalse(validator.requires_new_card_version({"成果状态"}))

    def test_card_rejects_open_profile_or_input_block(self) -> None:
        card = valid_card()
        card["Profile关闭结论"] = "仍在使用"
        card["输入阻断"] = "表演卡版本不一致"
        errors = validator.validate_card_record(card)
        self.assertTrue(any("没有在ERC交付前关闭" in item for item in errors))
        self.assertTrue(any("输入阻断" in item for item in errors))

    def test_card_enforces_unique_writeback_and_camera_review_order(self) -> None:
        card = valid_card()
        card["唯一写回Skill"] = "editing-rhythm"
        card["写回后下一节点"] = "video-prompt-production"
        errors = validator.validate_card_record(card)
        self.assertTrue(any("唯一写回者" in item for item in errors))
        self.assertTrue(any("逐镜摄影审核" in item for item in errors))

    def test_simulation_must_keep_one_decision(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self._copy_surface(Path(temp))
            path = root / "skills/editing-rhythm/references/c06-simulated-editing-task.md"
            text = path.read_text(encoding="utf-8").replace(
                "下一步：按你的决定完成",
                "现在请你决定：是否加载剪辑Profile？\n\n下一步：按你的决定完成",
            )
            path.write_text(text, encoding="utf-8")
            self.assertTrue(any("一个用户决定点" in item for item in validator.validate(root)))

    def test_schema_cannot_lose_writeback_field(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self._copy_surface(Path(temp))
            path = root / "skills/shot-visual-design/assets/storyboard-shot.schema.json"
            text = path.read_text(encoding="utf-8").replace('    "声音接点",\n', "", 1)
            path.write_text(text, encoding="utf-8")
            errors = validator.validate(root)
            self.assertTrue(any("写回必填字段" in item for item in errors))

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
