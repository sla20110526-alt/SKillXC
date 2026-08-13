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
        self.assertEqual(len(self.table("正式资产登记表.csv")), 1)
        self.assertEqual(len(self.table("可调用资产表.csv")), 1)
        events = self.table("资产状态传播表.csv")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["传播对象"], "新登记版本")

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


if __name__ == "__main__":
    unittest.main()
