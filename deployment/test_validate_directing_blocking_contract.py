#!/usr/bin/env python3
"""Tests for the C05 directing and blocking contract."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import validate_directing_blocking_contract as validator


ROOT = Path(__file__).resolve().parents[1]


def valid_blocking() -> dict[str, object]:
    return {
        "项目ID": "DEMO",
        "场戏调度数据集ID": "DBD-DEMO-SCN012",
        "调度数据集版本": "v001",
        "场次ID": "SCN-012",
        "调度单元ID": "BLK-001",
        "调度序号": 1,
        "节拍ID": "BT-001",
        "行动人物ID": "CHR-LINZHOU",
        "DSB与BDT精确引用": "DSB-DEMO-SCN012@v001；BDT-DEMO-SCN012@v001",
        "空间圣经ID与版本": "SPB-DEMO-OFFICE@v001",
        "空间锚点ID集合": "ANC-DOOR-A；ANC-CHAIR-A；ANC-DESK-A",
        "表演母档ID与版本": "ACT-LINZHOU@v001",
        "观众跟随对象": "林舟",
        "观众知情关系": "观众与林舟同时知道信封存在，比主任多知道一项",
        "必须看见信息": "林舟明确拒绝坐下并控制信封",
        "暂不可见信息": "信封内容",
        "人物起始坐标或分区": "访客椅后方活动区",
        "人物结束坐标或分区": "办公桌南侧一臂外",
        "与对象起始距离": "与主任隔桌约两步",
        "与对象结束距离": "与主任隔桌约一臂半",
        "起始朝向": "肩胯朝向主任与办公桌",
        "结束朝向": "身体偏向门，肩线仍对主任",
        "起始视线目标": "主任双眼",
        "结束视线目标": "信封后回到主任双眼",
        "遮挡与揭示": "访客椅先遮住手部；绕过椅背后信封被揭示",
        "进入或离开": "无",
        "移动触发": "主任再次命令坐下并伸手指向访客椅",
        "空间行动与路径": "林舟沿访客椅外侧到办公桌南侧，避开桌角",
        "行动目的": "拒绝服从并把信封放入双方争夺区",
        "接触对象与结果": "信封；放到桌面中央后手离开",
        "权力进入状态": "主任控制办公桌和座位安排",
        "权力空间变化": "林舟绕开被指定座位并把筹码放入中心，削弱主任单边控制",
        "权力离开状态": "双方围绕桌面筹码争夺控制",
        "轴线ID": "AX-DEMO-LIN-DIR",
        "银幕方向": "林舟由门侧向桌侧；主任保持桌后关系方向",
        "越轴与重建空间": "不越轴",
        "画外行动与声音线索": "不适用：两人均在当前场内",
        "连续性结束状态": "林舟站在桌南侧，信封在桌面中央，右手已离开信封",
        "生命体运动约束引用": "不适用",
        "VFX时序与接触引用": "不适用",
        "顾问结论精确引用": "不适用",
        "专项场景视图缺口": "无",
        "字段依据与状态": "位置=空间圣经/关系锁定；移动触发=BT-001/SCRIPT_EXPLICIT；行动目的=DSB导演切片/SCRIPT_INFERRED；权力变化=BDT-001/SCRIPT_INFERRED；距离边界=ACT-LINZHOU@v001/USER_LOCKED",
        "备注": "",
    }


def valid_card() -> dict[str, object]:
    return {
        "场戏调度卡ID": "DBC-DEMO-SCN012",
        "场戏调度卡版本": "v001",
        "场戏调度数据集精确引用": "DBD-DEMO-SCN012@v001",
        "场次ID": "SCN-012",
        "场戏节拍成果精确来源": "DSB-DEMO-SCN012@v001；BDT-DEMO-SCN012@v001",
        "剧作原文保护门": "通过",
        "Profile关闭结论": "未读取",
        "阻断缺口": "无",
        "所有移动均有触发目的路径和结束": "是",
        "轴线与银幕方向检查": "通过",
    }


class DirectingBlockingContractTests(unittest.TestCase):
    def test_repository_contract_passes(self) -> None:
        self.assertEqual(validator.validate(ROOT), [])

    def test_positive_blocking_and_card_pass(self) -> None:
        self.assertEqual(validator.validate_blocking_record(valid_blocking()), [])
        self.assertEqual(validator.validate_scene_card_record(valid_card()), [])

    def test_blocking_requires_audience_information_relation(self) -> None:
        record = valid_blocking()
        record["观众知情关系"] = ""
        self.assertTrue(any("观众知情关系" in item for item in validator.validate_blocking_record(record)))

    def test_movement_requires_dramatic_trigger(self) -> None:
        record = valid_blocking()
        record["移动触发"] = "无"
        self.assertTrue(any("移动缺少戏剧触发" in item for item in validator.validate_blocking_record(record)))

    def test_blocking_requires_per_field_evidence_states(self) -> None:
        record = valid_blocking()
        record["字段依据与状态"] = "整行=SCRIPT_INFERRED"
        errors = validator.validate_blocking_record(record)
        self.assertTrue(any("位置" in item for item in errors))
        self.assertTrue(any("权力变化" in item for item in errors))

    def test_hold_position_requires_same_start_and_end(self) -> None:
        record = valid_blocking()
        record["空间行动与路径"] = "保持位置"
        record["移动触发"] = "不适用：保持位置"
        self.assertTrue(any("起始与结束位置" in item for item in validator.validate_blocking_record(record)))

    def test_intentional_axis_cross_requires_reason_and_reestablish(self) -> None:
        record = valid_blocking()
        record["越轴与重建空间"] = "故意越轴：让关系更紧张"
        self.assertTrue(any("叙事理由" in item for item in validator.validate_blocking_record(record)))

    def test_director_cannot_write_focal_length_or_shot_implementation(self) -> None:
        record = valid_blocking()
        record["观众知情关系"] = "使用35mm低机位让观众仰视主任"
        errors = validator.validate_blocking_record(record)
        self.assertTrue(any("具体焦段" in item for item in errors))
        self.assertTrue(any("逐镜实现" in item for item in errors))

    def test_sequence_rejects_duplicate_id_and_order(self) -> None:
        first = valid_blocking()
        second = valid_blocking()
        errors = validator.validate_blocking_sequence([first, second])
        self.assertTrue(any("重复调度单元ID" in item for item in errors))
        self.assertTrue(any("重复调度序号" in item for item in errors))

    def test_special_view_gap_requires_complete_anchor_relation(self) -> None:
        gap = {
            "状态": "有",
            "缺口ID": "SV3-DEMO-SCN012-001",
            "调度单元ID": "BLK-001",
            "调度用途": "核实绕桌路径",
            "相对空间锚点观察关系": "从门侧观察桌南通道",
            "必须可见锚点": "门；办公桌南边",
            "必须遮挡锚点": "窗",
            "必须离画锚点": "走廊尽头",
            "返回链": "asset-demand-plan → location-spatial-production",
        }
        self.assertEqual(validator.validate_special_view_gap(gap), [])
        gap["相对空间锚点观察关系"] = ""
        self.assertTrue(any("观察关系" in item for item in validator.validate_special_view_gap(gap)))

    def test_dataset_cannot_depend_on_card(self) -> None:
        errors = validator.validate_dependency_direction(
            "DSB-DEMO-SCN012@v001；DBC-DEMO-SCN012@v001",
            "DBD-DEMO-SCN012@v001",
        )
        self.assertTrue(any("反向引用" in item for item in errors))

    def test_downstream_slice_requires_all_four_source_versions(self) -> None:
        record = {
            "下游Skill": "acting-direction",
            "精确成果引用": "DBD-DEMO-SCN012@v001；DBC-DEMO-SCN012@v001",
        }
        errors = validator.validate_downstream_slice(record)
        self.assertTrue(any("DSB精确版本" in item for item in errors))
        self.assertTrue(any("BDT精确版本" in item for item in errors))

    def test_downstream_slice_cannot_leak_profile_audit(self) -> None:
        record = {
            "下游Skill": "shot-visual-design",
            "精确成果引用": "DBD-DEMO-SCN012@v001；DBC-DEMO-SCN012@v001；DSB-DEMO-SCN012@v001；BDT-DEMO-SCN012@v001",
            "ProfileID@版本": "FP-DIR-DEMO@v1.1",
        }
        self.assertTrue(any("泄露Profile" in item for item in validator.validate_downstream_slice(record)))

    def test_profile_requires_current_stage_confirmation(self) -> None:
        use = {
            "使用Profile": "是",
            "允许阶段": "项目风格意图基线",
            "用户本次确认": "否",
            "ProfileID@版本": "FP-DIR-DEMO@v1.1",
        }
        errors = validator.validate_profile_use(use)
        self.assertTrue(any("导演与人物调度阶段" in item for item in errors))
        self.assertTrue(any("本阶段用户明确确认" in item for item in errors))

    def test_version_triggers_separate_dataset_card_and_status(self) -> None:
        self.assertTrue(validator.requires_new_dataset_version({"移动触发"}))
        self.assertTrue(validator.requires_new_dataset_version({"专项场景视图缺口"}))
        self.assertFalse(validator.requires_new_dataset_version({"复核日期"}))
        self.assertTrue(validator.requires_new_card_version({"专项场景视图缺口"}))
        self.assertFalse(validator.requires_new_card_version({"成果状态"}))

    def test_card_rejects_open_profile_or_blocking_gap(self) -> None:
        card = valid_card()
        card["Profile关闭结论"] = "仍在使用"
        card["阻断缺口"] = "通道宽度未知"
        errors = validator.validate_scene_card_record(card)
        self.assertTrue(any("没有关闭" in item for item in errors))
        self.assertTrue(any("阻断缺口" in item for item in errors))

    def test_card_allows_view_only_gap_before_acting_handoff(self) -> None:
        card = valid_card()
        card["阻断缺口"] = "仅专项视图生产缺口：SV3-DEMO-SCN012-001；逐镜设计前解决"
        self.assertEqual(validator.validate_scene_card_record(card), [])

    def test_simulation_must_keep_one_decision(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self._copy_surface(Path(temp))
            path = root / "skills/directing-blocking/references/c05-simulated-blocking-task.md"
            text = path.read_text(encoding="utf-8").replace(
                "下一步：按你的决定完成",
                "现在请你决定：是否加载导演Profile？\n\n下一步：按你的决定完成",
            )
            path.write_text(text, encoding="utf-8")
            self.assertTrue(any("一个决定点" in item for item in validator.validate(root)))

    def test_schema_cannot_gain_storyboard_field(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self._copy_surface(Path(temp))
            path = root / "skills/directing-blocking/assets/directing-blocking.schema.json"
            text = path.read_text(encoding="utf-8").replace(
                '    "项目ID": {"type": "string", "minLength": 1},',
                '    "焦段": {"type": "string"},\n    "项目ID": {"type": "string", "minLength": 1},',
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
