#!/usr/bin/env python3
"""Regression tests for asset registration and transitive state propagation."""

from __future__ import annotations

import csv
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("update_asset_registry.py")
SPEC = importlib.util.spec_from_file_location("update_asset_registry", MODULE_PATH)
assert SPEC and SPEC.loader
REGISTRY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REGISTRY)
SKILL_ROOT = Path(__file__).resolve().parents[1]


class RegistryTransactionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.registry = self.root / "registry"
        self.registry.mkdir()
        templates = {
            "正式资产登记表.csv": "正式资产登记表模板.csv",
            "可调用资产表.csv": "可调用资产表模板.csv",
            "资产状态传播表.csv": "资产状态传播表模板.csv",
        }
        for output_name, template_name in templates.items():
            source = SKILL_ROOT / "assets" / template_name
            (self.registry / output_name).write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        self.next_event = 1

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def table(self, name: str) -> list[dict[str, str]]:
        with (self.registry / name).open("r", encoding="utf-8-sig", newline="") as handle:
            return list(csv.DictReader(handle))

    def event_id(self) -> str:
        value = f"ASP-TEST-{self.next_event:03d}"
        self.next_event += 1
        return value

    def formal_row(
        self,
        asset_id: str,
        version: str,
        role: str,
        parent: str = "不适用",
        extras: str = "不适用",
        slot: str | None = None,
    ) -> dict[str, str]:
        compatible_values = [value for value in (parent, extras) if value != "不适用"]
        compatible = "；".join(compatible_values) if compatible_values else "不适用"
        return {
            "项目ID": "PRJ-001",
            "绑定卡版本": "v001",
            "正式资产ID": asset_id,
            "需求槽位ID": slot or f"REQ-{asset_id}",
            "版本": version,
            "资产类型": "人物" if asset_id.startswith("CHR") else "服装妆造",
            "资产名称": asset_id,
            "资产角色": role,
            "生产图片PromptID与版本": f"IPR-{asset_id}@v001",
            "生产依据父资产ID与版本": parent,
            "生产依据附加资产ID与版本": extras,
            "当前兼容依赖资产ID与版本": compatible,
            "文件路径": f"assets/{asset_id}-{version}.png",
            "剧本出处": "SC-001",
            "关联场次": "SC-001",
            "必须继承": "脸与结构",
            "允许变化": "当前槽位状态",
            "声音类别": "",
            "关联说话者ID": "",
            "关联声音身份卡ID与版本": "",
            "声音来源与授权状态": "",
            "音频污染与限制": "",
            "正式用途": "真人写实角色资产",
            "模型": "GPT Image 2",
            "登记指令原文": f"登记这张为{asset_id}",
            "登记日期": "2026-08-13",
            "状态": "可调用",
            "状态依据": "用户明确登记",
            "状态更新时间": "2026-08-13",
        }

    def spatial_row(
        self,
        asset_id: str,
        version: str,
        asset_type: str,
        role: str,
        parent: str = "不适用",
        extras: str = "不适用",
    ) -> dict[str, str]:
        row = self.formal_row(asset_id, version, role, parent, extras)
        row["资产类型"] = asset_type
        row["正式用途"] = "真人写实场景空间资产"
        row["必须继承"] = "空间结构、锚点、尺度、材质和光源逻辑"
        row["允许变化"] = "当前槽位指定视图或状态"
        return row

    def object_row(
        self,
        asset_id: str,
        version: str,
        asset_type: str,
        role: str,
        parent: str = "不适用",
        extras: str = "不适用",
    ) -> dict[str, str]:
        row = self.formal_row(asset_id, version, role, parent, extras)
        row["资产类型"] = asset_type
        row["正式用途"] = "真人写实道具、载具或图案文字资产"
        row["必须继承"] = "对象身份、结构、尺度、锚点、材质和功能"
        row["允许变化"] = "当前槽位唯一变化"
        return row

    def creature_row(
        self,
        asset_id: str,
        version: str,
        role: str,
        parent: str = "不适用",
        extras: str = "不适用",
    ) -> dict[str, str]:
        row = self.formal_row(asset_id, version, role, parent, extras)
        row["资产类型"] = "生物怪物"
        row["正式用途"] = "真人写实特殊生物或怪物资产"
        row["必须继承"] = "形态身份、解剖锚点、尺度、表皮和运动约束"
        row["允许变化"] = "当前槽位唯一结构、状态或交互变化"
        return row

    def vfx_row(
        self,
        asset_id: str,
        version: str,
        role: str,
        parent: str = "不适用",
        extras: str = "不适用",
    ) -> dict[str, str]:
        row = self.formal_row(asset_id, version, role, parent, extras)
        row["资产类型"] = "VFX"
        row["正式用途"] = "真人写实可复用VFX视觉参考"
        row["必须继承"] = "VFX定义、来源、材料层级、发光边界和物理规则"
        row["允许变化"] = "当前槽位唯一状态或接触变化"
        return row

    @staticmethod
    def callable_row(formal: dict[str, str]) -> dict[str, str]:
        return {
            "项目ID": formal["项目ID"],
            "绑定卡版本": formal["绑定卡版本"],
            "正式资产ID": formal["正式资产ID"],
            "版本": formal["版本"],
            "资产类型": formal["资产类型"],
            "资产名称": formal["资产名称"],
            "资产角色": formal["资产角色"],
            "文件路径": formal["文件路径"],
            "平台引用名": formal["正式资产ID"],
            "可调用范围": "当前项目",
            "声音类别": formal["声音类别"],
            "关联说话者ID": formal["关联说话者ID"],
            "关联声音身份卡ID与版本": formal["关联声音身份卡ID与版本"],
            "调用方式": "",
            "音频污染与限制": formal["音频污染与限制"],
            "生产依据父资产ID与版本": formal["生产依据父资产ID与版本"],
            "生产依据附加资产ID与版本": formal["生产依据附加资产ID与版本"],
            "当前兼容依赖资产ID与版本": formal["当前兼容依赖资产ID与版本"],
            "连续性备注": "",
            "状态": formal["状态"],
            "状态依据": formal["状态依据"],
            "状态更新时间": formal["状态更新时间"],
        }

    def register(self, formal: dict[str, str]) -> dict[str, object]:
        payload = {
            "项目ID": "PRJ-001",
            "传播事件ID": self.event_id(),
            "记录日期": "2026-08-13",
            "正式登记行": formal,
            "可调用行": self.callable_row(formal),
        }
        payload_path = self.root / "payload.json"
        payload_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        args = type(
            "Args",
            (),
            {
                "command": "register",
                "project_root": str(self.root),
                "formal_table": "registry/正式资产登记表.csv",
                "callable_table": "registry/可调用资产表.csv",
                "propagation_table": "registry/资产状态传播表.csv",
                "payload": str(payload_path),
            },
        )()
        return REGISTRY._run(args)

    def confirm(self, asset_id: str, version: str, trigger_asset: str, old: str, new: str) -> dict[str, object]:
        payload = {
            "项目ID": "PRJ-001",
            "传播事件ID": self.event_id(),
            "记录日期": "2026-08-14",
            "触发正式资产ID": trigger_asset,
            "被替代版本": old,
            "当前新版本": new,
            "受影响正式资产ID": asset_id,
            "受影响版本": version,
            "用户处理原文": "确认这个版本继续可用",
            "处理日期": "2026-08-14",
            "复核结论": "可继续",
            "复核依据": "脸、服装和接触均与新父版本一致",
        }
        payload_path = self.root / "confirm.json"
        payload_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        args = type(
            "Args",
            (),
            {
                "command": "confirm-compatible",
                "project_root": str(self.root),
                "formal_table": "registry/正式资产登记表.csv",
                "callable_table": "registry/可调用资产表.csv",
                "propagation_table": "registry/资产状态传播表.csv",
                "payload": str(payload_path),
            },
        )()
        return REGISTRY._run(args)

    def build_chain(self) -> None:
        self.register(self.formal_row("CHR-001", "v001", "基础"))
        self.register(self.formal_row("CST-001", "v001", "服装妆造", "CHR-001@v001"))
        self.register(self.formal_row("STA-001", "v001", "状态变体", "CST-001@v001"))
        self.register(self.formal_row("PRP-001", "v001", "独立对象"))
        self.register(
            self.formal_row(
                "INT-001",
                "v001",
                "交互组合",
                "STA-001@v001",
                "PRP-001@v001",
            )
        )

    def test_first_registration_writes_all_three_tables(self) -> None:
        result = self.register(self.formal_row("CHR-001", "v001", "基础"))
        self.assertEqual(result["写入结论"], "通过")
        formal_rows = self.table("正式资产登记表.csv")
        self.assertEqual(len(formal_rows), 1)
        self.assertEqual(formal_rows[0]["生产图片PromptID与版本"], "IPR-CHR-001@v001")
        self.assertEqual(len(self.table("可调用资产表.csv")), 1)
        events = self.table("资产状态传播表.csv")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["传播对象"], "新登记版本")

    def test_sound_asset_rejects_image_prompt_provenance(self) -> None:
        invalid = self.formal_row("VOC-001", "v001", "声音基线")
        invalid["资产类型"] = "声音"
        with self.assertRaisesRegex(REGISTRY.RegistryError, "声音资产不得携带图片Prompt来源"):
            self.register(invalid)

    def test_asset_types_route_to_unique_production_skills(self) -> None:
        expected = {
            "人物": "character-asset-production",
            "服装妆造": "character-asset-production",
            "场景": "location-spatial-production",
            "场景视图": "location-spatial-production",
            "光影": "location-spatial-production",
            "道具": "prop-vehicle-production",
            "载具": "prop-vehicle-production",
            "图案文字": "prop-vehicle-production",
            "生物怪物": "creature-monster-production",
            "VFX": "vfx-asset-production",
            "声音": "sound-voice-direction",
        }
        for asset_type, skill in expected.items():
            with self.subTest(asset_type=asset_type):
                self.assertEqual(REGISTRY._responsible_skill({"资产类型": asset_type}), skill)
        with self.assertRaisesRegex(REGISTRY.RegistryError, "没有唯一责任生产Skill"):
            REGISTRY._responsible_skill({"资产类型": "未知"})

    def test_responsibility_map_covers_formal_schema_and_real_skills(self) -> None:
        map_document = json.loads(
            REGISTRY.ASSET_RESPONSIBILITY_MAP_PATH.read_text(encoding="utf-8")
        )
        self.assertEqual(map_document["secondary_router"]["skill"], "world-asset-production")
        self.assertIs(map_document["secondary_router"]["may_produce_candidates"], False)
        schema_paths = (
            SKILL_ROOT / "assets/formal-asset.schema.json",
            SKILL_ROOT / "assets/callable-asset.schema.json",
            SKILL_ROOT.parent / "script-asset-breakdown/assets/asset-candidate.schema.json",
        )
        route_types = set(REGISTRY.ASSET_RESPONSIBILITY)
        for schema_path in schema_paths:
            with self.subTest(schema=schema_path.name):
                schema = json.loads(schema_path.read_text(encoding="utf-8"))
                self.assertEqual(route_types, set(schema["properties"]["资产类型"]["enum"]))
        skills_root = SKILL_ROOT.parent
        for skill in set(REGISTRY.ASSET_RESPONSIBILITY.values()):
            with self.subTest(skill=skill):
                self.assertTrue((skills_root / skill / "SKILL.md").is_file())
                self.assertNotEqual(skill, "world-asset-production")

    def test_rejects_pair_mismatch_outside_state_fields(self) -> None:
        formal = self.formal_row("CHR-001", "v001", "基础")
        callable_row = self.callable_row(formal)
        callable_row["声音类别"] = "角色声音参考音频"
        payload = {
            "项目ID": "PRJ-001",
            "传播事件ID": self.event_id(),
            "记录日期": "2026-08-13",
            "正式登记行": formal,
            "可调用行": callable_row,
        }
        with self.assertRaisesRegex(REGISTRY.RegistryError, "声音类别"):
            REGISTRY._register(payload, [], [], [])

    def test_new_parent_version_propagates_through_full_chain(self) -> None:
        self.build_chain()
        result = self.register(self.formal_row("CHR-001", "v002", "基础"))
        self.assertEqual(result["待复核派生资产"], ["CST-001@v001", "INT-001@v001", "STA-001@v001"])
        rows = {(row["正式资产ID"], row["版本"]): row for row in self.table("正式资产登记表.csv")}
        self.assertEqual(rows[("CHR-001", "v001")]["状态"], "历史")
        self.assertEqual(rows[("CHR-001", "v002")]["状态"], "可调用")
        self.assertEqual(rows[("CST-001", "v001")]["状态"], "待复核")
        self.assertEqual(rows[("STA-001", "v001")]["状态"], "待复核")
        self.assertEqual(rows[("INT-001", "v001")]["状态"], "待复核")
        self.assertEqual(rows[("PRP-001", "v001")]["状态"], "可调用")

    def test_confirm_compatible_preserves_production_basis(self) -> None:
        self.build_chain()
        self.register(self.formal_row("CHR-001", "v002", "基础"))
        self.confirm("CST-001", "v001", "CHR-001", "v001", "v002")
        rows = {(row["正式资产ID"], row["版本"]): row for row in self.table("正式资产登记表.csv")}
        costume = rows[("CST-001", "v001")]
        self.assertEqual(costume["状态"], "可调用")
        self.assertEqual(costume["生产依据父资产ID与版本"], "CHR-001@v001")
        self.assertEqual(costume["当前兼容依赖资产ID与版本"], "CHR-001@v002")
        self.assertEqual(rows[("STA-001", "v001")]["状态"], "待复核")

    def test_transitive_asset_is_released_against_its_direct_dependency(self) -> None:
        self.build_chain()
        self.register(self.formal_row("CHR-001", "v002", "基础"))
        self.confirm("CST-001", "v001", "CHR-001", "v001", "v002")
        result = self.confirm("STA-001", "v001", "CST-001", "v001", "v001")
        self.assertEqual(result["当前状态"], "可调用")
        rows = {(row["正式资产ID"], row["版本"]): row for row in self.table("正式资产登记表.csv")}
        state = rows[("STA-001", "v001")]
        self.assertEqual(state["生产依据父资产ID与版本"], "CST-001@v001")
        self.assertEqual(state["当前兼容依赖资产ID与版本"], "CST-001@v001")

    def test_each_changed_direct_dependency_requires_its_own_confirmation(self) -> None:
        self.register(self.formal_row("CHR-001", "v001", "基础"))
        self.register(self.formal_row("CST-A", "v001", "服装妆造", "CHR-001@v001"))
        self.register(self.formal_row("CST-B", "v001", "服装妆造", "CHR-001@v001"))
        self.register(self.formal_row("INT-001", "v001", "交互组合", "CST-A@v001", "CST-B@v001"))
        self.register(self.formal_row("CHR-001", "v002", "基础"))
        self.confirm("CST-A", "v001", "CHR-001", "v001", "v002")
        self.confirm("CST-B", "v001", "CHR-001", "v001", "v002")
        first = self.confirm("INT-001", "v001", "CST-A", "v001", "v001")
        self.assertEqual(first["当前状态"], "待复核")
        second = self.confirm("INT-001", "v001", "CST-B", "v001", "v001")
        self.assertEqual(second["当前状态"], "可调用")

    def test_cannot_confirm_against_a_pending_direct_dependency(self) -> None:
        self.build_chain()
        self.register(self.formal_row("CHR-001", "v002", "基础"))
        with self.assertRaisesRegex(REGISTRY.RegistryError, "新依赖版本不是可调用状态"):
            self.confirm("STA-001", "v001", "CST-001", "v001", "v001")

    def test_failed_transaction_keeps_original_tables(self) -> None:
        self.register(self.formal_row("CHR-001", "v001", "基础"))
        before = {name: (self.registry / name).read_bytes() for name in ("正式资产登记表.csv", "可调用资产表.csv", "资产状态传播表.csv")}
        invalid = self.formal_row("CST-001", "v001", "服装妆造", "CHR-001")
        with self.assertRaises(REGISTRY.RegistryError):
            self.register(invalid)
        after = {name: (self.registry / name).read_bytes() for name in before}
        self.assertEqual(before, after)

    def test_check_rejects_callable_asset_with_historical_dependency(self) -> None:
        self.build_chain()
        self.register(self.formal_row("CHR-001", "v002", "基础"))
        formal_path = self.registry / "正式资产登记表.csv"
        headers, rows = REGISTRY._read_csv(formal_path)
        for row in rows:
            if row["正式资产ID"] == "CST-001":
                row["状态"] = "可调用"
                row["状态依据"] = "错误手改"
        REGISTRY._write_csv(formal_path, headers, rows)
        with self.assertRaisesRegex(REGISTRY.RegistryError, "正式/可调用字段不一致|依赖非可调用"):
            REGISTRY._validate_staged(
                {
                    "formal": formal_path,
                    "callable": self.registry / "可调用资产表.csv",
                    "propagation": self.registry / "资产状态传播表.csv",
                },
                "PRJ-001",
            )

    def test_character_face_and_overview_card_use_distinct_dependency_chain(self) -> None:
        self.register(self.formal_row("CHR-FACE-001", "v001", "脸母图"))
        self.register(
            self.formal_row(
                "CHR-CARD-001",
                "v001",
                "五视图基础卡",
                "CHR-FACE-001@v001",
            )
        )
        rows = {(row["正式资产ID"], row["版本"]): row for row in self.table("正式资产登记表.csv")}
        self.assertEqual(rows[("CHR-FACE-001", "v001")]["状态"], "可调用")
        self.assertEqual(
            rows[("CHR-CARD-001", "v001")]["生产依据父资产ID与版本"],
            "CHR-FACE-001@v001",
        )

    def test_character_overview_card_rejects_non_face_parent(self) -> None:
        self.register(self.formal_row("CHR-BASE-001", "v001", "基础"))
        invalid = self.formal_row(
            "CHR-CARD-001",
            "v001",
            "五视图基础卡",
            "CHR-BASE-001@v001",
        )
        with self.assertRaisesRegex(REGISTRY.RegistryError, "父版本必须是已登记脸母图"):
            self.register(invalid)

    def test_character_face_rejects_dependencies(self) -> None:
        self.register(self.formal_row("CHR-BASE-001", "v001", "基础"))
        invalid = self.formal_row(
            "CHR-FACE-001",
            "v001",
            "脸母图",
            "CHR-BASE-001@v001",
        )
        with self.assertRaisesRegex(REGISTRY.RegistryError, "人物脸母图不得带生产依据或当前兼容依赖"):
            self.register(invalid)

    def test_character_face_requires_character_asset_type(self) -> None:
        invalid = self.formal_row("CST-FACE-001", "v001", "脸母图")
        with self.assertRaisesRegex(REGISTRY.RegistryError, "人物脸母图必须登记为人物资产"):
            self.register(invalid)

    def test_character_face_and_overview_card_cannot_share_asset_id(self) -> None:
        self.register(self.formal_row("CHR-001", "v001", "脸母图"))
        invalid = self.formal_row(
            "CHR-001",
            "v002",
            "五视图基础卡",
            "CHR-001@v001",
        )
        with self.assertRaisesRegex(REGISTRY.RegistryError, "必须使用不同正式资产ID"):
            self.register(invalid)

    def test_new_character_face_version_propagates_to_overview_and_variants(self) -> None:
        self.register(self.formal_row("CHR-FACE-001", "v001", "脸母图"))
        self.register(
            self.formal_row(
                "CHR-CARD-001",
                "v001",
                "五视图基础卡",
                "CHR-FACE-001@v001",
            )
        )
        self.register(
            self.formal_row(
                "CST-001",
                "v001",
                "服装妆造",
                "CHR-CARD-001@v001",
            )
        )
        result = self.register(self.formal_row("CHR-FACE-001", "v002", "脸母图"))
        self.assertEqual(
            result["待复核派生资产"],
            ["CHR-CARD-001@v001", "CST-001@v001"],
        )

    def test_location_master_view_and_lighting_use_exact_chain(self) -> None:
        self.register(self.spatial_row("SCN-MASTER-001", "v001", "场景", "场景母图"))
        self.register(
            self.spatial_row(
                "SCN-VIEW-001", "v001", "场景视图", "场景视图", "SCN-MASTER-001@v001"
            )
        )
        self.register(
            self.spatial_row(
                "LGT-001", "v001", "光影", "光影状态", "SCN-VIEW-001@v001"
            )
        )
        rows = {(row["正式资产ID"], row["版本"]): row for row in self.table("正式资产登记表.csv")}
        self.assertEqual(rows[("SCN-VIEW-001", "v001")]["生产依据父资产ID与版本"], "SCN-MASTER-001@v001")
        self.assertEqual(rows[("LGT-001", "v001")]["生产依据父资产ID与版本"], "SCN-VIEW-001@v001")

    def test_location_view_rejects_non_spatial_parent(self) -> None:
        self.register(self.formal_row("PRP-001", "v001", "独立对象"))
        invalid = self.spatial_row(
            "SCN-VIEW-001", "v001", "场景视图", "场景视图", "PRP-001@v001"
        )
        with self.assertRaisesRegex(REGISTRY.RegistryError, "父版本必须是已登记场景母图或场景状态"):
            self.register(invalid)

    def test_location_view_type_rejects_wrong_role(self) -> None:
        invalid = self.spatial_row("SCN-VIEW-001", "v001", "场景视图", "基础")
        with self.assertRaisesRegex(REGISTRY.RegistryError, "场景视图资产必须使用场景视图角色"):
            self.register(invalid)

    def test_location_master_rejects_parent_dependency(self) -> None:
        self.register(self.spatial_row("SCN-BASE-001", "v001", "场景", "基础"))
        invalid = self.spatial_row(
            "SCN-MASTER-001", "v001", "场景", "场景母图", "SCN-BASE-001@v001"
        )
        with self.assertRaisesRegex(REGISTRY.RegistryError, "场景母图不得带父资产"):
            self.register(invalid)

    def test_location_state_requires_location_master_or_state_parent(self) -> None:
        self.register(self.formal_row("CHR-001", "v001", "基础"))
        invalid = self.spatial_row(
            "SCN-STATE-001", "v001", "场景", "状态变体", "CHR-001@v001"
        )
        with self.assertRaisesRegex(REGISTRY.RegistryError, "场景状态变体的父版本必须是"):
            self.register(invalid)

    def test_lighting_state_rejects_non_spatial_parent(self) -> None:
        self.register(self.formal_row("CHR-001", "v001", "基础"))
        invalid = self.spatial_row("LGT-001", "v001", "光影", "光影状态", "CHR-001@v001")
        with self.assertRaisesRegex(REGISTRY.RegistryError, "父版本必须是已登记场景母图、场景状态或场景视图"):
            self.register(invalid)

    def test_lighting_type_rejects_wrong_role(self) -> None:
        invalid = self.spatial_row("LGT-001", "v001", "光影", "基础")
        with self.assertRaisesRegex(REGISTRY.RegistryError, "光影资产必须使用光影状态角色"):
            self.register(invalid)

    def test_new_location_master_propagates_to_view_and_lighting(self) -> None:
        self.register(self.spatial_row("SCN-MASTER-001", "v001", "场景", "场景母图"))
        self.register(
            self.spatial_row(
                "SCN-VIEW-001", "v001", "场景视图", "场景视图", "SCN-MASTER-001@v001"
            )
        )
        self.register(
            self.spatial_row("LGT-001", "v001", "光影", "光影状态", "SCN-VIEW-001@v001")
        )
        result = self.register(self.spatial_row("SCN-MASTER-001", "v002", "场景", "场景母图"))
        self.assertEqual(result["待复核派生资产"], ["LGT-001@v001", "SCN-VIEW-001@v001"])

    def test_object_surface_application_uses_object_parent_and_graphic_extra(self) -> None:
        self.register(self.object_row("PRP-BASE-001", "v001", "道具", "独立对象"))
        self.register(self.object_row("GFX-001", "v001", "图案文字", "图案文字母版"))
        self.register(
            self.object_row(
                "PRP-SURFACE-001",
                "v001",
                "道具",
                "对象表面应用",
                "PRP-BASE-001@v001",
                "GFX-001@v001",
            )
        )
        rows = {(row["正式资产ID"], row["版本"]): row for row in self.table("正式资产登记表.csv")}
        self.assertEqual(rows[("PRP-SURFACE-001", "v001")]["生产依据父资产ID与版本"], "PRP-BASE-001@v001")
        self.assertEqual(rows[("PRP-SURFACE-001", "v001")]["生产依据附加资产ID与版本"], "GFX-001@v001")

    def test_object_surface_application_rejects_non_graphic_extra(self) -> None:
        self.register(self.object_row("PRP-BASE-001", "v001", "道具", "独立对象"))
        self.register(self.object_row("PRP-EXTRA-001", "v001", "道具", "独立对象"))
        invalid = self.object_row(
            "PRP-SURFACE-001",
            "v001",
            "道具",
            "对象表面应用",
            "PRP-BASE-001@v001",
            "PRP-EXTRA-001@v001",
        )
        with self.assertRaisesRegex(REGISTRY.RegistryError, "附加版本必须全部是图案文字母版"):
            self.register(invalid)

    def test_object_state_requires_same_type_object_parent(self) -> None:
        self.register(self.object_row("VEH-BASE-001", "v001", "载具", "独立对象"))
        invalid = self.object_row(
            "PRP-STATE-001", "v001", "道具", "状态变体", "VEH-BASE-001@v001"
        )
        with self.assertRaisesRegex(REGISTRY.RegistryError, "父版本必须是已登记同类型对象"):
            self.register(invalid)

    def test_object_assembly_requires_registered_object_extras(self) -> None:
        self.register(self.object_row("VEH-BASE-001", "v001", "载具", "独立对象"))
        self.register(self.object_row("PRP-MOUNT-001", "v001", "道具", "独立对象"))
        self.register(
            self.object_row(
                "VEH-ASSEMBLY-001",
                "v001",
                "载具",
                "对象装配",
                "VEH-BASE-001@v001",
                "PRP-MOUNT-001@v001",
            )
        )

    def test_object_and_graphic_types_reject_wrong_roles(self) -> None:
        with self.assertRaisesRegex(REGISTRY.RegistryError, "道具/载具资产角色不符合对象生产链"):
            self.register(self.object_row("PRP-BASE-001", "v001", "道具", "基础"))
        with self.assertRaisesRegex(REGISTRY.RegistryError, "图案文字资产必须使用图案文字母版角色"):
            self.register(self.object_row("GFX-001", "v001", "图案文字", "独立对象"))

    def test_independent_object_rejects_production_dependencies(self) -> None:
        self.register(self.object_row("PRP-OLDER-001", "v001", "道具", "独立对象"))
        invalid = self.object_row(
            "PRP-BASE-001", "v001", "道具", "独立对象", "PRP-OLDER-001@v001"
        )
        with self.assertRaisesRegex(REGISTRY.RegistryError, "基础道具/载具不得带生产依据"):
            self.register(invalid)

    def test_graphic_master_rejects_production_dependencies(self) -> None:
        self.register(self.object_row("GFX-OLDER-001", "v001", "图案文字", "图案文字母版"))
        invalid = self.object_row(
            "GFX-001", "v001", "图案文字", "图案文字母版", "GFX-OLDER-001@v001"
        )
        with self.assertRaisesRegex(REGISTRY.RegistryError, "图案文字母版必须是无依赖的图案文字资产"):
            self.register(invalid)

    def test_object_assembly_rejects_graphic_extra(self) -> None:
        self.register(self.object_row("VEH-BASE-001", "v001", "载具", "独立对象"))
        self.register(self.object_row("GFX-001", "v001", "图案文字", "图案文字母版"))
        invalid = self.object_row(
            "VEH-ASSEMBLY-001",
            "v001",
            "载具",
            "对象装配",
            "VEH-BASE-001@v001",
            "GFX-001@v001",
        )
        with self.assertRaisesRegex(REGISTRY.RegistryError, "附加版本必须全部是已登记道具/载具"):
            self.register(invalid)

    def test_new_graphic_version_propagates_to_surface_application(self) -> None:
        self.register(self.object_row("PRP-BASE-001", "v001", "道具", "独立对象"))
        self.register(self.object_row("GFX-001", "v001", "图案文字", "图案文字母版"))
        self.register(
            self.object_row(
                "PRP-SURFACE-001",
                "v001",
                "道具",
                "对象表面应用",
                "PRP-BASE-001@v001",
                "GFX-001@v001",
            )
        )
        result = self.register(self.object_row("GFX-001", "v002", "图案文字", "图案文字母版"))
        self.assertEqual(result["待复核派生资产"], ["PRP-SURFACE-001@v001"])

    def test_new_graphic_version_propagates_across_carrier_skills(self) -> None:
        self.register(self.formal_row("CHR-001", "v001", "基础"))
        self.register(self.spatial_row("SCN-MASTER-001", "v001", "场景", "场景母图"))
        self.register(self.object_row("GFX-001", "v001", "图案文字", "图案文字母版"))
        costume = self.formal_row(
            "COSTUME-001",
            "v001",
            "服装妆造",
            "CHR-001@v001",
            "GFX-001@v001",
        )
        costume["资产类型"] = "服装妆造"
        self.register(costume)
        self.register(
            self.spatial_row(
                "SCN-STATE-001",
                "v001",
                "场景",
                "状态变体",
                "SCN-MASTER-001@v001",
                "GFX-001@v001",
            )
        )
        result = self.register(self.object_row("GFX-001", "v002", "图案文字", "图案文字母版"))
        self.assertEqual(
            result["待复核派生资产"],
            ["COSTUME-001@v001", "SCN-STATE-001@v001"],
        )

    def test_new_vehicle_version_propagates_to_cabin_scene_and_views(self) -> None:
        self.register(self.object_row("VEH-001", "v001", "载具", "独立对象"))
        self.register(
            self.spatial_row(
                "SCN-CABIN-001", "v001", "场景", "场景母图", extras="VEH-001@v001"
            )
        )
        self.register(
            self.spatial_row(
                "SCN-CABIN-VIEW-001",
                "v001",
                "场景视图",
                "场景视图",
                "SCN-CABIN-001@v001",
            )
        )
        self.register(
            self.spatial_row(
                "LGT-CABIN-001",
                "v001",
                "光影",
                "光影状态",
                "SCN-CABIN-VIEW-001@v001",
            )
        )
        result = self.register(self.object_row("VEH-001", "v002", "载具", "独立对象"))
        self.assertEqual(
            result["待复核派生资产"],
            ["LGT-CABIN-001@v001", "SCN-CABIN-001@v001", "SCN-CABIN-VIEW-001@v001"],
        )

    def test_character_state_and_interaction_chain_still_accepts_generic_roles(self) -> None:
        self.build_chain()
        rows = {(row["正式资产ID"], row["版本"]): row for row in self.table("正式资产登记表.csv")}
        self.assertEqual(rows[("STA-001", "v001")]["资产角色"], "状态变体")
        self.assertEqual(rows[("INT-001", "v001")]["资产角色"], "交互组合")

    def test_creature_shape_state_and_interaction_chain(self) -> None:
        self.register(self.creature_row("CRT-BASE-001", "v001", "生物基础形态"))
        self.register(
            self.creature_row(
                "CRT-STRUCT-001",
                "v001",
                "生物结构变体",
                "CRT-BASE-001@v001",
            )
        )
        self.register(
            self.creature_row(
                "CRT-STATE-001",
                "v001",
                "生物状态变体",
                "CRT-STRUCT-001@v001",
            )
        )
        self.register(self.object_row("PRP-HARNESS-001", "v001", "道具", "独立对象"))
        self.register(
            self.creature_row(
                "CRT-INTERACT-001",
                "v001",
                "生物交互组合",
                "CRT-STATE-001@v001",
                "PRP-HARNESS-001@v001",
            )
        )
        rows = {(row["正式资产ID"], row["版本"]): row for row in self.table("正式资产登记表.csv")}
        self.assertEqual(rows[("CRT-STRUCT-001", "v001")]["生产依据父资产ID与版本"], "CRT-BASE-001@v001")
        self.assertEqual(rows[("CRT-INTERACT-001", "v001")]["生产依据附加资产ID与版本"], "PRP-HARNESS-001@v001")

    def test_creature_base_rejects_dependencies_and_wrong_role(self) -> None:
        self.register(self.creature_row("CRT-OLDER-001", "v001", "生物基础形态"))
        with self.assertRaisesRegex(REGISTRY.RegistryError, "生物基础形态不得带生产依据"):
            self.register(
                self.creature_row(
                    "CRT-BASE-001",
                    "v001",
                    "生物基础形态",
                    "CRT-OLDER-001@v001",
                )
            )
        with self.assertRaisesRegex(REGISTRY.RegistryError, "生物怪物资产角色不符合生命体生产链"):
            self.register(self.creature_row("CRT-LEGACY-001", "v001", "基础"))

    def test_creature_structure_rejects_state_parent(self) -> None:
        self.register(self.creature_row("CRT-BASE-001", "v001", "生物基础形态"))
        self.register(
            self.creature_row(
                "CRT-STATE-001", "v001", "生物状态变体", "CRT-BASE-001@v001"
            )
        )
        invalid = self.creature_row(
            "CRT-STRUCT-001", "v001", "生物结构变体", "CRT-STATE-001@v001"
        )
        with self.assertRaisesRegex(REGISTRY.RegistryError, "父版本必须是已登记基础或结构形态"):
            self.register(invalid)

    def test_creature_state_rejects_object_parent(self) -> None:
        self.register(self.object_row("PRP-001", "v001", "道具", "独立对象"))
        invalid = self.creature_row(
            "CRT-STATE-001", "v001", "生物状态变体", "PRP-001@v001"
        )
        with self.assertRaisesRegex(REGISTRY.RegistryError, "父版本必须是已登记基础、结构或上一状态"):
            self.register(invalid)

    def test_creature_interaction_rejects_graphic_or_prior_interaction(self) -> None:
        self.register(self.creature_row("CRT-BASE-001", "v001", "生物基础形态"))
        self.register(self.object_row("GFX-001", "v001", "图案文字", "图案文字母版"))
        invalid_extra = self.creature_row(
            "CRT-INTERACT-001",
            "v001",
            "生物交互组合",
            "CRT-BASE-001@v001",
            "GFX-001@v001",
        )
        with self.assertRaisesRegex(REGISTRY.RegistryError, "附加版本必须全部是已登记道具/载具"):
            self.register(invalid_extra)
        self.register(self.object_row("PRP-001", "v001", "道具", "独立对象"))
        self.register(
            self.creature_row(
                "CRT-INTERACT-001",
                "v001",
                "生物交互组合",
                "CRT-BASE-001@v001",
                "PRP-001@v001",
            )
        )
        invalid_parent = self.creature_row(
            "CRT-INTERACT-002",
            "v001",
            "生物交互组合",
            "CRT-INTERACT-001@v001",
            "PRP-001@v001",
        )
        with self.assertRaisesRegex(REGISTRY.RegistryError, "父版本必须是已登记生命体"):
            self.register(invalid_parent)

    def test_creature_base_version_propagates_transitively(self) -> None:
        self.register(self.creature_row("CRT-BASE-001", "v001", "生物基础形态"))
        self.register(
            self.creature_row(
                "CRT-STRUCT-001", "v001", "生物结构变体", "CRT-BASE-001@v001"
            )
        )
        self.register(
            self.creature_row(
                "CRT-STATE-001", "v001", "生物状态变体", "CRT-STRUCT-001@v001"
            )
        )
        self.register(self.object_row("PRP-001", "v001", "道具", "独立对象"))
        self.register(
            self.creature_row(
                "CRT-INTERACT-001",
                "v001",
                "生物交互组合",
                "CRT-STATE-001@v001",
                "PRP-001@v001",
            )
        )
        result = self.register(self.creature_row("CRT-BASE-001", "v002", "生物基础形态"))
        self.assertEqual(
            result["待复核派生资产"],
            ["CRT-INTERACT-001@v001", "CRT-STATE-001@v001", "CRT-STRUCT-001@v001"],
        )

    def test_object_version_propagates_to_creature_interaction_only(self) -> None:
        self.register(self.creature_row("CRT-BASE-001", "v001", "生物基础形态"))
        self.register(self.object_row("PRP-001", "v001", "道具", "独立对象"))
        self.register(
            self.creature_row(
                "CRT-INTERACT-001",
                "v001",
                "生物交互组合",
                "CRT-BASE-001@v001",
                "PRP-001@v001",
            )
        )
        result = self.register(self.object_row("PRP-001", "v002", "道具", "独立对象"))
        self.assertEqual(result["待复核派生资产"], ["CRT-INTERACT-001@v001"])

    def test_vfx_master_state_and_contact_chain(self) -> None:
        self.register(self.object_row("PRP-SOURCE-001", "v001", "道具", "独立对象"))
        self.register(
            self.vfx_row(
                "VFX-MASTER-001", "v001", "VFX视觉母版", extras="PRP-SOURCE-001@v001"
            )
        )
        self.register(
            self.vfx_row(
                "VFX-STATE-001", "v001", "VFX状态变体", "VFX-MASTER-001@v001"
            )
        )
        self.register(self.spatial_row("SCN-001", "v001", "场景", "场景母图"))
        self.register(
            self.vfx_row(
                "VFX-CONTACT-001",
                "v001",
                "VFX接触参考",
                "VFX-STATE-001@v001",
                "SCN-001@v001",
            )
        )
        rows = {(row["正式资产ID"], row["版本"]): row for row in self.table("正式资产登记表.csv")}
        self.assertEqual(rows[("VFX-MASTER-001", "v001")]["生产依据附加资产ID与版本"], "PRP-SOURCE-001@v001")
        self.assertEqual(rows[("VFX-CONTACT-001", "v001")]["生产依据父资产ID与版本"], "VFX-STATE-001@v001")

    def test_vfx_rejects_wrong_roles_and_dependencies(self) -> None:
        with self.assertRaisesRegex(REGISTRY.RegistryError, "VFX资产角色不符合VFX生产链"):
            self.register(self.vfx_row("VFX-LEGACY-001", "v001", "基础"))
        self.register(self.vfx_row("VFX-MASTER-001", "v001", "VFX视觉母版"))
        with self.assertRaisesRegex(REGISTRY.RegistryError, "VFX视觉母版不得带父资产"):
            self.register(
                self.vfx_row(
                    "VFX-MASTER-002", "v001", "VFX视觉母版", "VFX-MASTER-001@v001"
                )
            )
        self.register(self.object_row("PRP-001", "v001", "道具", "独立对象"))
        with self.assertRaisesRegex(REGISTRY.RegistryError, "VFX状态变体的父版本必须是"):
            self.register(
                self.vfx_row(
                    "VFX-STATE-001", "v001", "VFX状态变体", "PRP-001@v001"
                )
            )

    def test_vfx_contact_rejects_missing_context_or_prior_contact_parent(self) -> None:
        self.register(self.vfx_row("VFX-MASTER-001", "v001", "VFX视觉母版"))
        with self.assertRaisesRegex(REGISTRY.RegistryError, "至少一个接触实体"):
            self.register(
                self.vfx_row(
                    "VFX-CONTACT-001", "v001", "VFX接触参考", "VFX-MASTER-001@v001"
                )
            )
        self.register(self.object_row("PRP-001", "v001", "道具", "独立对象"))
        self.register(
            self.vfx_row(
                "VFX-CONTACT-001",
                "v001",
                "VFX接触参考",
                "VFX-MASTER-001@v001",
                "PRP-001@v001",
            )
        )
        with self.assertRaisesRegex(REGISTRY.RegistryError, "父版本必须是已登记视觉母版或状态"):
            self.register(
                self.vfx_row(
                    "VFX-CONTACT-002",
                    "v001",
                    "VFX接触参考",
                    "VFX-CONTACT-001@v001",
                    "PRP-001@v001",
                )
            )

    def test_vfx_source_version_propagates_transitively(self) -> None:
        self.register(self.object_row("PRP-SOURCE-001", "v001", "道具", "独立对象"))
        self.register(
            self.vfx_row(
                "VFX-MASTER-001", "v001", "VFX视觉母版", extras="PRP-SOURCE-001@v001"
            )
        )
        self.register(
            self.vfx_row(
                "VFX-STATE-001", "v001", "VFX状态变体", "VFX-MASTER-001@v001"
            )
        )
        self.register(self.spatial_row("SCN-001", "v001", "场景", "场景母图"))
        self.register(
            self.vfx_row(
                "VFX-CONTACT-001",
                "v001",
                "VFX接触参考",
                "VFX-STATE-001@v001",
                "SCN-001@v001",
            )
        )
        source_result = self.register(self.object_row("PRP-SOURCE-001", "v002", "道具", "独立对象"))
        self.assertEqual(
            source_result["待复核派生资产"],
            ["VFX-CONTACT-001@v001", "VFX-MASTER-001@v001", "VFX-STATE-001@v001"],
        )

    def test_vfx_master_version_propagates_to_state_and_contact(self) -> None:
        self.register(self.vfx_row("VFX-MASTER-001", "v001", "VFX视觉母版"))
        self.register(
            self.vfx_row(
                "VFX-STATE-001", "v001", "VFX状态变体", "VFX-MASTER-001@v001"
            )
        )
        self.register(self.spatial_row("SCN-001", "v001", "场景", "场景母图"))
        self.register(
            self.vfx_row(
                "VFX-CONTACT-001",
                "v001",
                "VFX接触参考",
                "VFX-STATE-001@v001",
                "SCN-001@v001",
            )
        )
        result = self.register(self.vfx_row("VFX-MASTER-001", "v002", "VFX视觉母版"))
        self.assertEqual(result["待复核派生资产"], ["VFX-CONTACT-001@v001", "VFX-STATE-001@v001"])

    def test_vfx_contact_context_version_propagates_only_to_contact(self) -> None:
        self.register(self.vfx_row("VFX-MASTER-001", "v001", "VFX视觉母版"))
        self.register(self.spatial_row("SCN-001", "v001", "场景", "场景母图"))
        self.register(
            self.vfx_row(
                "VFX-CONTACT-001",
                "v001",
                "VFX接触参考",
                "VFX-MASTER-001@v001",
                "SCN-001@v001",
            )
        )
        result = self.register(self.spatial_row("SCN-001", "v002", "场景", "场景母图"))
        self.assertEqual(result["待复核派生资产"], ["VFX-CONTACT-001@v001"])


if __name__ == "__main__":
    unittest.main()
