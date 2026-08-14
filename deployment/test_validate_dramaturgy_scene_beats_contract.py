#!/usr/bin/env python3
"""Tests for the C04 dramaturgy scene-beat contract."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import validate_dramaturgy_scene_beats_contract as validator


ROOT = Path(__file__).resolve().parents[1]


def valid_beat() -> dict[str, object]:
    return {
        "项目ID": "DEMO",
        "场戏节拍集ID": "BDT-DEMO-SCN012",
        "节拍集版本": "v001",
        "场次ID": "SCN-012",
        "节拍ID": "BT-001",
        "节拍序号": 1,
        "剧本内容版本": "SCRIPT-DEMO@v001",
        "原文定位": "测试页4第2—3段",
        "剧本事实ID集合": "FACT-012-001；FACT-012-002",
        "原文锁定项": "主任：坐。；林舟没有坐并放下信封",
        "触发": "主任命令林舟坐下",
        "行动人物ID": "CHR-LINZHOU",
        "人物目标": "迫使主任正视信封并接受由林舟设定的议程",
        "障碍": "主任以职位和场所权威控制会面",
        "策略": "拒绝服从并展示未拆信封",
        "可见行为": "林舟没有坐，把未拆信封放在桌上",
        "潜台词": "今天的议程由我决定",
        "信息进入状态": "主任不知道林舟带来什么",
        "信息变化": "主任确认林舟持有未拆信封",
        "信息离开状态": "主任知道信封存在但不知道内容",
        "权力进入状态": "主任单方面控制会面",
        "权力变化": "信封成为林舟可控制的筹码",
        "权力离开状态": "控制权进入争夺",
        "节拍进入状态": "主任拥有场所权威，林舟尚未出牌",
        "节拍离开状态": "信封在桌面，双方围绕筹码对峙",
        "事件顺序锚点": "E01关门之后；E04主任伸手之前",
        "因果依据": "主任以命令压制，林舟因此拒绝服从并展示筹码",
        "字段依据与标签": "触发=FACT-012-001/SCRIPT_EXPLICIT；目标=FACT-012-001与ACT-LINZHOU@v001/SCRIPT_INFERRED；策略=拒绝坐下与展示信封/SCRIPT_INFERRED；可见行为=FACT-012-001/SCRIPT_EXPLICIT；潜台词=台词与拒绝服从的矛盾/SCRIPT_INFERRED；信息变化=FACT-012-002/SCRIPT_INFERRED；权力变化=信封控制权变化/SCRIPT_INFERRED",
        "锁定项保护结论": "保持原文",
        "歧义或缺口": "信封内容未知",
    }


def valid_card() -> dict[str, object]:
    return {
        "场戏节拍卡ID": "DSB-DEMO-SCN012",
        "场戏节拍卡版本": "v001",
        "场戏节拍数据集精确引用": "BDT-DEMO-SCN012@v001",
        "场次ID": "SCN-012",
        "剧本内容版本": "SCRIPT-DEMO@v001",
        "本场原文定位": "测试页4第2—7段",
        "锁定台词逐字保持": "通过",
        "事件顺序保持": "通过",
        "因果保持": "通过",
        "出入场保持": "通过",
        "未授权改写": "无",
        "Profile关闭结论": "未读取",
    }


class DramaturgySceneBeatsContractTests(unittest.TestCase):
    def test_repository_contract_passes(self) -> None:
        self.assertEqual(validator.validate(ROOT), [])

    def test_positive_beat_and_card_pass(self) -> None:
        self.assertEqual(validator.validate_beat_record(valid_beat()), [])
        self.assertEqual(validator.validate_scene_card_record(valid_card()), [])

    def test_beat_requires_original_location(self) -> None:
        record = valid_beat()
        record["原文定位"] = ""
        self.assertTrue(any("原文定位" in item for item in validator.validate_beat_record(record)))

    def test_beat_requires_every_dramatic_field(self) -> None:
        record = valid_beat()
        record["障碍"] = ""
        self.assertTrue(any("障碍" in item for item in validator.validate_beat_record(record)))

    def test_beat_requires_per_field_evidence_labels(self) -> None:
        record = valid_beat()
        record["字段依据与标签"] = "整拍=SCRIPT_INFERRED"
        self.assertTrue(any("潜台词" in item for item in validator.validate_beat_record(record)))

    def test_beat_must_contain_real_change(self) -> None:
        record = valid_beat()
        record["信息变化"] = "不变"
        record["权力变化"] = "不变"
        record["节拍离开状态"] = record["节拍进入状态"]
        self.assertTrue(any("真实变化" in item for item in validator.validate_beat_record(record)))

    def test_sequence_rejects_duplicate_id_and_order(self) -> None:
        first = valid_beat()
        second = valid_beat()
        errors = validator.validate_beat_sequence([first, second])
        self.assertTrue(any("重复节拍ID" in item for item in errors))
        self.assertTrue(any("重复节拍序号" in item for item in errors))

    def test_unauthorized_locked_script_change_is_rejected(self) -> None:
        change = {
            "锁定内容变化": ["把主任台词从‘坐’改为‘请坐’"],
            "用户改写授权": "否",
            "旧剧本内容版本": "SCRIPT-DEMO@v001",
            "新剧本内容版本": "SCRIPT-DEMO@v001",
        }
        self.assertTrue(any("未授权" in item for item in validator.validate_script_change(change)))

    def test_authorized_change_still_requires_new_script_version(self) -> None:
        change = {
            "锁定内容变化": ["新增一句台词"],
            "用户改写授权": "是",
            "旧剧本内容版本": "SCRIPT-DEMO@v001",
            "新剧本内容版本": "SCRIPT-DEMO@v001",
        }
        self.assertTrue(any("新的剧本内容版本" in item for item in validator.validate_script_change(change)))

    def test_dataset_cannot_depend_on_scene_card(self) -> None:
        errors = validator.validate_dependency_direction(
            "SCRIPT-DEMO@v001；DSB-DEMO-SCN012@v001",
            "BDT-DEMO-SCN012@v001",
        )
        self.assertTrue(any("反向引用" in item for item in errors))

    def test_downstream_slice_rejects_camera_decisions(self) -> None:
        slice_record = {
            "下游Skill": "directing-blocking",
            "精确成果引用": "DSB-DEMO-SCN012@v001；BDT-DEMO-SCN012@v001",
            "戏剧依据": "BT-003用低机位和长焦强化控制权",
        }
        self.assertTrue(any("越权" in item for item in validator.validate_downstream_slice(slice_record)))

    def test_downstream_slice_only_allows_director_or_acting(self) -> None:
        slice_record = {
            "下游Skill": "shot-visual-design",
            "精确成果引用": "DSB-DEMO-SCN012@v001；BDT-DEMO-SCN012@v001",
            "戏剧依据": "BT-003林舟获得谈判主动",
        }
        self.assertTrue(any("只能直接交" in item for item in validator.validate_downstream_slice(slice_record)))

    def test_profile_requires_allowed_stage_and_confirmation(self) -> None:
        use = {
            "使用Profile": "是",
            "允许阶段": "导演与人物调度",
            "用户本次确认": "否",
            "ProfileID@版本": "FP-WRI-DEMO@v1.1",
        }
        errors = validator.validate_profile_use(use)
        self.assertTrue(any("只能在剧作与场戏节拍" in item for item in errors))
        self.assertTrue(any("用户本次明确确认" in item for item in errors))

    def test_version_triggers_separate_content_from_status(self) -> None:
        self.assertTrue(validator.requires_new_dataset_version({"潜台词"}))
        self.assertFalse(validator.requires_new_dataset_version({"复核日期"}))
        self.assertTrue(validator.requires_new_card_version({"导演调度切片"}))
        self.assertFalse(validator.requires_new_card_version({"成果状态"}))

    def test_simulation_must_keep_one_decision(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self._copy_surface(Path(temp))
            path = root / "skills/dramaturgy-scene-beats/references/c04-simulated-scene-beat-task.md"
            text = path.read_text(encoding="utf-8").replace(
                "下一步：按你的决定完成",
                "现在请你决定：是否加载某位编剧Profile？\n\n下一步：按你的决定完成",
            )
            path.write_text(text, encoding="utf-8")
            self.assertTrue(any("一个决定点" in item for item in validator.validate(root)))

    def test_schema_cannot_gain_camera_field(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self._copy_surface(Path(temp))
            path = root / "skills/dramaturgy-scene-beats/assets/scene-beat.schema.json"
            text = path.read_text(encoding="utf-8").replace(
                '    "项目ID": {"type": "string", "minLength": 1},',
                '    "景别": {"type": "string"},\n    "项目ID": {"type": "string", "minLength": 1},',
                1,
            )
            path.write_text(text, encoding="utf-8")
            self.assertTrue(any("表头与Schema" in item or "越权" in item for item in validator.validate(root)))

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
