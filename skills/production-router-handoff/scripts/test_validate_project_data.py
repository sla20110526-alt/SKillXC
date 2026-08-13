#!/usr/bin/env python3
"""Regression tests for validate_project_data.py without third-party packages."""

from __future__ import annotations

import csv
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("validate_project_data.py")
SPEC = importlib.util.spec_from_file_location("validate_project_data", MODULE_PATH)
assert SPEC and SPEC.loader
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "测试记录",
    "type": "object",
    "required": ["项目ID", "状态", "数量"],
    "properties": {
        "项目ID": {"type": "string", "minLength": 1},
        "状态": {"type": "string", "enum": ["通过", "暂停"]},
        "数量": {"type": "integer", "minimum": 1},
        "备注": {"type": ["string", "null"]},
    },
    "additionalProperties": False,
}


class ValidatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.schema_path = self.root / "test.schema.json"
        self.schema_path.write_text(json.dumps(SCHEMA, ensure_ascii=False), encoding="utf-8")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def write_csv(self, headers: list[str], rows: list[list[str]]) -> Path:
        path = self.root / "test.csv"
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(headers)
            writer.writerows(rows)
        return path

    def test_valid_row_passes_and_coerces_number(self) -> None:
        path = self.write_csv(["项目ID", "状态", "数量", "备注"], [["PRJ-001", "通过", "2", ""]])
        result = VALIDATOR._check_pair(path, self.schema_path, "PRJ-001")
        self.assertEqual(result["rows"], 1)
        self.assertEqual(result["errors"], [])

    def test_wrong_project_id_is_rejected(self) -> None:
        path = self.write_csv(["项目ID", "状态", "数量", "备注"], [["PRJ-002", "通过", "2", ""]])
        result = VALIDATOR._check_pair(path, self.schema_path, "PRJ-001")
        self.assertTrue(any("--project-id" not in error and "项目ID" in error for error in result["errors"]))

    def test_invalid_enum_and_minimum_are_rejected(self) -> None:
        path = self.write_csv(["项目ID", "状态", "数量", "备注"], [["PRJ-001", "未知", "0", ""]])
        result = VALIDATOR._check_pair(path, self.schema_path, "PRJ-001")
        self.assertTrue(any("允许集合" in error for error in result["errors"]))
        self.assertTrue(any("大于等于 1" in error for error in result["errors"]))

    def test_missing_or_reordered_header_is_rejected(self) -> None:
        path = self.write_csv(["状态", "项目ID", "备注"], [["通过", "PRJ-001", ""]])
        result = VALIDATOR._check_pair(path, self.schema_path, "PRJ-001")
        self.assertTrue(any("表头与 Schema" in error for error in result["errors"]))
        self.assertTrue(any("缺少必填字段" in error for error in result["errors"]))

    def test_report_preserves_structure_vs_business_boundary(self) -> None:
        path = self.write_csv(["项目ID", "状态", "数量", "备注"], [["PRJ-001", "通过", "2", ""]])
        result = VALIDATOR._check_pair(path, self.schema_path, "PRJ-001")
        report = VALIDATOR._render_report([result], "PRJ-001")
        self.assertIn("结论：通过", report)
        self.assertIn("通过行数：1", report)
        self.assertIn("失败行数：0", report)
        self.assertIn("不代替批准授权", report)

    def test_unsupported_schema_keyword_is_rejected(self) -> None:
        schema = json.loads(json.dumps(SCHEMA, ensure_ascii=False))
        schema["properties"]["项目ID"]["format"] = "uuid"
        self.schema_path.write_text(json.dumps(schema, ensure_ascii=False), encoding="utf-8")
        path = self.write_csv(["项目ID", "状态", "数量", "备注"], [["PRJ-001", "通过", "2", ""]])
        result = VALIDATOR._check_pair(path, self.schema_path, "PRJ-001")
        self.assertTrue(any("不支持关键字" in error for error in result["errors"]))

    def test_missing_markdown_card_is_rejected(self) -> None:
        path = self.write_csv(["项目ID", "状态", "数量", "备注"], [])
        result = VALIDATOR._check_pair(
            path,
            self.schema_path,
            None,
            self.root / "missing.md",
            True,
        )
        self.assertTrue(any("卡片模板不存在" in error for error in result["errors"]))

    def test_card_without_contract_markers_is_rejected(self) -> None:
        path = self.write_csv(["项目ID", "状态", "数量", "备注"], [])
        card_path = self.root / "card.md"
        card_path.write_text("# 测试卡\n", encoding="utf-8")
        result = VALIDATOR._check_pair(path, self.schema_path, None, card_path, True)
        self.assertTrue(any("缺少三层契约标记" in error for error in result["errors"]))
        self.assertTrue(any("未引用对应 Schema" in error for error in result["errors"]))

    def test_cli_requires_project_id_for_single_project_file(self) -> None:
        path = self.write_csv(["项目ID", "状态", "数量", "备注"], [])
        completed = subprocess.run(
            [sys.executable, str(MODULE_PATH), "--input", str(path), "--schema", str(self.schema_path)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(completed.returncode, 2)
        self.assertIn("必须提供 --project-id", completed.stderr)

    def test_cli_validates_multiple_pairs_in_one_report(self) -> None:
        first = self.write_csv(["项目ID", "状态", "数量", "备注"], [["PRJ-001", "通过", "2", ""]])
        second = self.root / "second.csv"
        second.write_text(first.read_text(encoding="utf-8"), encoding="utf-8")
        report_path = self.root / "report.md"
        completed = subprocess.run(
            [
                sys.executable,
                str(MODULE_PATH),
                "--input",
                str(first),
                "--schema",
                str(self.schema_path),
                "--pair",
                str(second),
                str(self.schema_path),
                "--project-id",
                "PRJ-001",
                "--report",
                str(report_path),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        report = report_path.read_text(encoding="utf-8")
        self.assertIn("检查配对数：2", report)
        self.assertIn("通过行数：2", report)


class ManifestRegressionTests(unittest.TestCase):
    @staticmethod
    def sample_value(field: str, spec: dict[str, object]) -> str:
        enum = spec.get("enum")
        if isinstance(enum, list) and enum:
            return str(enum[0])
        types = spec.get("type")
        type_list = [types] if isinstance(types, str) else list(types or [])
        if "integer" in type_list:
            minimum = int(spec.get("minimum", 1))
            return str(max(1, minimum))
        if "number" in type_list:
            minimum = float(spec.get("minimum", spec.get("exclusiveMinimum", 0)))
            if "exclusiveMinimum" in spec:
                minimum += 1
            return str(max(1, minimum))
        pattern = spec.get("pattern")
        if isinstance(pattern, str) and pattern == "^v[0-9]{3,}$":
            return "v001"
        if isinstance(pattern, str) and pattern == "^v[0-9]+\\.[0-9]+$":
            return "v0.1"
        if isinstance(pattern, str) and pattern == "^ASP-[A-Z0-9-]+$":
            return "ASP-TEST-001"
        if field == "项目ID":
            return "PRJ-TEST"
        return "测试值" if int(spec.get("minLength", 0)) > 0 else ""

    def test_every_manifest_package_accepts_a_minimal_valid_row(self) -> None:
        repo_root = Path(__file__).resolve().parents[3]
        manifest_path = repo_root / "skills/production-router-handoff/assets/data-contract-map.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as temp_dir:
            for item in manifest["pairs"]:
                schema_path = repo_root / item["schema"]
                card_path = repo_root / item["card"]
                schema = json.loads(schema_path.read_text(encoding="utf-8"))
                headers = list(schema["properties"])
                values = [self.sample_value(field, schema["properties"][field]) for field in headers]
                csv_path = Path(temp_dir) / Path(item["template"]).name
                with csv_path.open("w", encoding="utf-8", newline="") as handle:
                    writer = csv.writer(handle)
                    writer.writerow(headers)
                    writer.writerow(values)
                result = VALIDATOR._check_pair(csv_path, schema_path, "PRJ-TEST", card_path, True)
                self.assertEqual(result["errors"], [], item["template"])
                self.assertEqual(result["passed_rows"], 1, item["template"])
                self.assertEqual(result["failed_rows"], 0, item["template"])


if __name__ == "__main__":
    unittest.main()
