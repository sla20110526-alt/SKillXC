from __future__ import annotations

import csv
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("update_control_index.py")
SPEC = importlib.util.spec_from_file_location("update_control_index", MODULE_PATH)
assert SPEC and SPEC.loader
CONTROL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CONTROL)


class ControlVersionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.index = self.root / "creative-control/项目创作基线索引.csv"
        self.index.parent.mkdir(parents=True)
        template = CONTROL.SKILL_ROOT / "assets/项目创作基线索引模板.csv"
        self.index.write_text(template.read_text(encoding="utf-8-sig"), encoding="utf-8")
        self.sequence = 0

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def transaction_id(self) -> str:
        self.sequence += 1
        return f"CCV-TEST-{self.sequence:03d}"

    def card(self, card_id: str, version: str, body: str, source: str = "CCS-STYLE-LOCK@v001") -> str:
        relative = f"creative-control/baselines/{card_id}@{version}.md"
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        previous = "不适用" if version == "v001" else f"v{int(version[1:]) - 1:03d}"
        path.write_text(
            "\n".join(
                (
                    "# 项目控制卡",
                    "项目ID：PRJ-001",
                    f"控制卡ID：{card_id}",
                    f"项目卡版本：{version}",
                    f"上一项目卡版本：{previous}",
                    "控制卡状态：待确认",
                    "当前有效：否",
                    f"源定义引用：{source}",
                    f"执行规则：{body}",
                    "状态依据类型：系统草案",
                    "状态依据原文：系统草案",
                    "生效依据原文：不适用",
                    "记录日期：2026-08-13",
                    "生效日期：不适用",
                    f"控制卡路径：{relative}",
                    "内容指纹SHA256：由脚本计算",
                    "校验报告路径：不适用",
                    "校验结论：待检查",
                    "",
                )
            ),
            encoding="utf-8",
        )
        return relative

    def row(
        self,
        card_id: str,
        version: str,
        body: str,
        source: str = "CCS-STYLE-LOCK@v001",
        control_object: str = "全项目",
        control_type: str = "项目风格锁定基线",
        input_refs: str = "无",
    ) -> dict[str, str]:
        previous = "不适用" if version == "v001" else f"v{int(version[1:]) - 1:03d}"
        return {
            "项目ID": "PRJ-001",
            "控制卡ID": card_id,
            "控制类型": control_type,
            "控制对象": control_object,
            "项目卡版本": version,
            "上一项目卡版本": previous,
            "控制卡状态": "待确认",
            "当前有效": "否",
            "适用范围": "全项目",
            "项目锁定卡版本": "v001",
            "剧本内容版本": "script-v1",
            "源定义引用": source,
            "Profile引用集合": "无",
            "输入控制卡引用集合": input_refs,
            "控制卡路径": self.card(card_id, version, body, source),
            "内容指纹SHA256": "",
            "内容变更摘要": body,
            "状态依据类型": "系统草案",
            "状态依据原文": "系统草案",
            "生效依据原文": "不适用",
            "记录日期": "2026-08-13",
            "生效日期": "不适用",
        }

    def execute(self, command: str, payload: dict[str, object] | None = None) -> dict[str, object]:
        values: dict[str, object] = {
            "command": command,
            "kind": "baseline",
            "project_root": str(self.root),
            "index": None,
        }
        if command in {"init", "check"}:
            values["project_id"] = "PRJ-001"
        else:
            assert payload is not None
            payload_path = self.root / f"{command}-{self.sequence}.json"
            payload_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            values["payload"] = str(payload_path)
        return CONTROL._run(type("Args", (), values)())

    def execute_kind(
        self,
        kind: str,
        command: str,
        payload: dict[str, object] | None = None,
    ) -> dict[str, object]:
        values: dict[str, object] = {
            "command": command,
            "kind": kind,
            "project_root": str(self.root),
            "index": None,
        }
        if command in {"init", "check"}:
            values["project_id"] = "PRJ-001"
        else:
            assert payload is not None
            payload_path = self.root / f"{kind}-{command}-{self.sequence}.json"
            payload_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            values["payload"] = str(payload_path)
        return CONTROL._run(type("Args", (), values)())

    def detailed_control_row(self, kind: str, body: str) -> dict[str, str]:
        config = CONTROL.KINDS[kind]
        schema = json.loads(Path(config["schema"]).read_text(encoding="utf-8-sig"))
        row: dict[str, str] = {}
        for field, spec in schema["properties"].items():
            row[field] = str(spec.get("enum", ["测试"])[0])
        for field in ("关联人物正式资产ID与版本", "关联生物怪物正式资产ID与版本"):
            if field in row:
                row[field] = "无"
        card_id = "AM-001" if kind == "acting" else "VI-001"
        subject_field = config["subject"][0]
        source = config["expected_source"] + "@v001"
        relative = f"creative-control/{kind}/cards/{card_id}@v001.md"
        card = self.root / relative
        card.parent.mkdir(parents=True, exist_ok=True)
        card.write_text(
            "\n".join(
                (
                    "# 详细创作控制卡",
                    f"{config['id']}：{card_id}",
                    f"{config['version']}：v001",
                    f"{config['previous']}：不适用",
                    f"{config['status_label']}：待确认",
                    "当前有效：否",
                    f"源定义引用：{source}",
                    f"稳定规则：{body}",
                    "状态依据类型：系统草案",
                    "状态依据原文：系统草案",
                    "生效依据原文：不适用",
                    "记录日期：2026-08-13",
                    "生效日期：不适用",
                    f"{config['path']}：{relative}",
                    "内容指纹SHA256：由脚本计算",
                    "",
                )
            ),
            encoding="utf-8",
        )
        row.update(
            {
                "项目ID": "PRJ-001",
                config["id"]: card_id,
                subject_field: "CHAR-001",
                config["version"]: "v001",
                config["previous"]: "不适用",
                config["status"]: "待确认",
                "当前有效": "否",
                "项目锁定卡版本": "v001",
                "剧本内容版本": "script-v1",
                config["source"]: source,
                config["path"]: relative,
                config["fingerprint"]: "",
                "状态依据类型": "系统草案",
                "状态依据原文": "系统草案",
                "生效依据原文": "不适用",
                "记录日期": "2026-08-13",
                "生效日期": "不适用",
            }
        )
        return row

    def draft(self, *rows: dict[str, str]) -> dict[str, object]:
        return self.execute(
            "draft",
            {
                "项目ID": "PRJ-001",
                "事务ID": self.transaction_id(),
                "操作日期": "2026-08-13",
                "记录": list(rows),
            },
        )

    def state(self, command: str, card_id: str, version: str, text: str) -> dict[str, object]:
        return self.execute(
            command,
            {
                "项目ID": "PRJ-001",
                "事务ID": self.transaction_id(),
                "操作日期": "2026-08-14",
                "目标": [{"卡片ID": card_id, "版本": version}],
                "用户操作原文": text,
            },
        )

    def rows(self) -> list[dict[str, str]]:
        with self.index.open("r", encoding="utf-8-sig", newline="") as handle:
            return list(csv.DictReader(handle))

    def test_draft_then_activate(self) -> None:
        self.draft(self.row("CC-STYLE-001", "v001", "保持冷静写实"))
        self.assertEqual(self.rows()[0]["控制卡状态"], "待确认")
        result = self.state("activate", "CC-STYLE-001", "v001", "确认这版项目风格基线")
        self.assertEqual(result["已生效版本"], ["CC-STYLE-001@v001"])
        row = self.rows()[0]
        self.assertEqual((row["控制卡状态"], row["当前有效"]), ("已生效", "是"))
        self.assertEqual(row["生效依据原文"], "确认这版项目风格基线")
        self.assertRegex(row["内容指纹SHA256"], r"^[a-f0-9]{64}$")
        card = (self.root / row["控制卡路径"]).read_text(encoding="utf-8")
        self.assertIn("控制卡状态：已生效", card)
        self.assertIn("生效依据原文：确认这版项目风格基线", card)

    def test_init_creates_only_requested_empty_index(self) -> None:
        self.index.unlink()
        result = self.execute("init")
        self.assertEqual(result["初始化结论"], "已初始化空索引")
        self.assertTrue(self.index.is_file())
        self.assertFalse((self.root / "creative-control/acting/角色表演母档表.csv").exists())

    def test_new_draft_does_not_replace_until_activation(self) -> None:
        self.draft(self.row("CC-STYLE-001", "v001", "规则A"))
        self.state("activate", "CC-STYLE-001", "v001", "确认v001")
        self.draft(self.row("CC-STYLE-001", "v002", "规则B"))
        rows = {row["项目卡版本"]: row for row in self.rows()}
        self.assertEqual((rows["v001"]["控制卡状态"], rows["v001"]["当前有效"]), ("已生效", "是"))
        self.assertEqual((rows["v002"]["控制卡状态"], rows["v002"]["当前有效"]), ("待确认", "否"))
        self.state("activate", "CC-STYLE-001", "v002", "确认v002")
        rows = {row["项目卡版本"]: row for row in self.rows()}
        self.assertEqual((rows["v001"]["控制卡状态"], rows["v001"]["当前有效"]), ("已替代", "否"))
        self.assertEqual((rows["v002"]["控制卡状态"], rows["v002"]["当前有效"]), ("已生效", "是"))
        self.assertEqual(rows["v001"]["生效依据原文"], "确认v001")

    def test_same_semantic_content_cannot_create_new_version(self) -> None:
        self.draft(self.row("CC-STYLE-001", "v001", "相同规则"))
        before = self.index.read_bytes()
        with self.assertRaisesRegex(CONTROL.ControlVersionError, "语义内容未变化"):
            self.draft(self.row("CC-STYLE-001", "v002", "相同规则"))
        self.assertEqual(self.index.read_bytes(), before)

    def test_same_subject_cannot_change_stable_id(self) -> None:
        self.draft(self.row("CC-STYLE-001", "v001", "规则A"))
        before = self.index.read_bytes()
        with self.assertRaisesRegex(CONTROL.ControlVersionError, "不同稳定ID"):
            self.draft(self.row("CC-STYLE-999", "v001", "规则B"))
        self.assertEqual(self.index.read_bytes(), before)

    def test_invalidate_does_not_restore_old_version(self) -> None:
        self.draft(self.row("CC-STYLE-001", "v001", "规则A"))
        self.state("activate", "CC-STYLE-001", "v001", "确认v001")
        self.draft(self.row("CC-STYLE-001", "v002", "规则B"))
        self.state("activate", "CC-STYLE-001", "v002", "确认v002")
        result = self.state("invalidate", "CC-STYLE-001", "v002", "明确停用这版")
        self.assertEqual(result["自动恢复旧版"], [])
        rows = {row["项目卡版本"]: row for row in self.rows()}
        self.assertEqual(rows["v001"]["当前有效"], "否")
        self.assertEqual((rows["v002"]["控制卡状态"], rows["v002"]["当前有效"]), ("已失效", "否"))

    def test_rejects_unknown_source_and_future_profile(self) -> None:
        with self.assertRaisesRegex(CONTROL.ControlVersionError, "中央源引用不存在"):
            self.draft(self.row("CC-STYLE-001", "v001", "规则", "CCS-NOT-FOUND@v001"))
        row = self.row("CC-STYLE-001", "v001", "规则")
        row["Profile引用集合"] = "FP-DIR-DAVID-FINCHER@v9.9"
        with self.assertRaisesRegex(CONTROL.ControlVersionError, "没有历史记录"):
            self.draft(row)

    def test_rejects_source_for_another_control_type(self) -> None:
        with self.assertRaisesRegex(CONTROL.ControlVersionError, "控制类型与中央源定义不对应"):
            self.draft(self.row("CC-STYLE-001", "v001", "规则", "CCS-LIGHTING@v001"))

    def test_rejects_profile_from_wrong_department(self) -> None:
        row = self.row("CC-STYLE-001", "v001", "规则")
        row["Profile引用集合"] = "FP-CIN-ROGER-DEAKINS@v1.0"
        with self.assertRaisesRegex(CONTROL.ControlVersionError, "Profile专业部门不匹配"):
            self.draft(row)

    def test_downstream_baseline_requires_current_active_upstream(self) -> None:
        self.draft(self.row("CC-STYLE-001", "v001", "风格规则"))
        art = self.row(
            "CC-ART-001",
            "v001",
            "美术规则",
            source="CCS-ART-LOOKDEV@v001",
            control_type="美术LookDev基线",
            input_refs="CC-STYLE-001@v001",
        )
        self.draft(art)
        with self.assertRaisesRegex(CONTROL.ControlVersionError, "非当前生效的上游版本"):
            self.state("activate", "CC-ART-001", "v001", "错误地单独确认下游")
        self.state("activate", "CC-STYLE-001", "v001", "确认风格基线")
        self.state("activate", "CC-ART-001", "v001", "确认美术基线")
        self.assertEqual(len(self.rows()), 2)

    def test_upstream_baseline_cannot_reference_downstream(self) -> None:
        self.draft(self.row("CC-STYLE-001", "v001", "风格规则"))
        self.state("activate", "CC-STYLE-001", "v001", "确认风格基线")
        self.draft(
            self.row(
                "CC-ART-001",
                "v001",
                "美术规则",
                source="CCS-ART-LOOKDEV@v001",
                control_type="美术LookDev基线",
                input_refs="CC-STYLE-001@v001",
            )
        )
        self.state("activate", "CC-ART-001", "v001", "确认美术基线")
        circular = self.row(
            "CC-STYLE-001",
            "v002",
            "错误循环引用",
            input_refs="CC-ART-001@v001",
        )
        with self.assertRaisesRegex(CONTROL.ControlVersionError, "下游或不允许"):
            self.draft(circular)

    def test_upstream_change_requires_atomic_activation_with_active_downstream(self) -> None:
        self.draft(self.row("CC-STYLE-001", "v001", "风格A"))
        self.state("activate", "CC-STYLE-001", "v001", "确认风格v001")
        self.draft(
            self.row(
                "CC-ART-001",
                "v001",
                "美术A",
                source="CCS-ART-LOOKDEV@v001",
                control_type="美术LookDev基线",
                input_refs="CC-STYLE-001@v001",
            )
        )
        self.state("activate", "CC-ART-001", "v001", "确认美术v001")
        self.draft(self.row("CC-STYLE-001", "v002", "风格B"))
        self.draft(
            self.row(
                "CC-ART-001",
                "v002",
                "美术B",
                source="CCS-ART-LOOKDEV@v001",
                control_type="美术LookDev基线",
                input_refs="CC-STYLE-001@v002",
            )
        )
        before = self.index.read_bytes()
        with self.assertRaisesRegex(CONTROL.ControlVersionError, "非当前生效的上游版本"):
            self.state("activate", "CC-STYLE-001", "v002", "错误地只确认上游")
        self.assertEqual(self.index.read_bytes(), before)
        self.execute(
            "activate",
            {
                "项目ID": "PRJ-001",
                "事务ID": self.transaction_id(),
                "操作日期": "2026-08-14",
                "目标": [
                    {"卡片ID": "CC-STYLE-001", "版本": "v002"},
                    {"卡片ID": "CC-ART-001", "版本": "v002"},
                ],
                "用户操作原文": "确认风格与美术新链一起生效",
            },
        )
        active = [row for row in self.rows() if row["当前有效"] == "是"]
        self.assertEqual(
            {(row["控制卡ID"], row["项目卡版本"]) for row in active},
            {("CC-STYLE-001", "v002"), ("CC-ART-001", "v002")},
        )

    def test_acting_and_voice_use_same_version_transaction(self) -> None:
        for kind in ("acting", "voice"):
            self.execute_kind(kind, "init")
            row = self.detailed_control_row(kind, f"{kind}稳定规则")
            self.execute_kind(
                kind,
                "draft",
                {
                    "项目ID": "PRJ-001",
                    "事务ID": self.transaction_id(),
                    "操作日期": "2026-08-13",
                    "记录": [row],
                },
            )
            card_id = row[CONTROL.KINDS[kind]["id"]]
            self.execute_kind(
                kind,
                "activate",
                {
                    "项目ID": "PRJ-001",
                    "事务ID": self.transaction_id(),
                    "操作日期": "2026-08-14",
                    "目标": [{"卡片ID": card_id, "版本": "v001"}],
                    "用户操作原文": f"确认{kind}控制卡",
                },
            )
            index_path = self.root / CONTROL.KINDS[kind]["default_index"]
            with index_path.open("r", encoding="utf-8-sig", newline="") as handle:
                saved = list(csv.DictReader(handle))[0]
            self.assertEqual((saved[CONTROL.KINDS[kind]["status"]], saved["当前有效"]), ("已生效", "是"))

    def test_voice_rejects_simultaneous_person_and_creature_asset_links(self) -> None:
        self.execute_kind("voice", "init")
        row = self.detailed_control_row("voice", "非人说话者稳定规则")
        row["关联人物正式资产ID与版本"] = "CHR-001@v001"
        row["关联生物怪物正式资产ID与版本"] = "CRT-001@v001"
        with self.assertRaisesRegex(CONTROL.ControlVersionError, "不能同时关联人物和生物怪物"):
            self.execute_kind(
                "voice",
                "draft",
                {
                    "项目ID": "PRJ-001",
                    "事务ID": self.transaction_id(),
                    "操作日期": "2026-08-13",
                    "记录": [row],
                },
            )


if __name__ == "__main__":
    unittest.main()
