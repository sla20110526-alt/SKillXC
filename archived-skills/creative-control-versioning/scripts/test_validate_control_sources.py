from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = Path(__file__).with_name("validate_control_sources.py")
SPEC = importlib.util.spec_from_file_location("validate_control_sources", MODULE_PATH)
assert SPEC and SPEC.loader
SOURCES = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SOURCES)


class SourceCatalogTests(unittest.TestCase):
    def test_repository_source_catalog_is_valid(self) -> None:
        self.assertEqual(SOURCES.validate(), [])

    def test_every_published_source_version_needs_a_definition(self) -> None:
        payload = json.loads(SOURCES.CATALOG.read_text(encoding="utf-8-sig"))
        payload["sources"][0]["definition_paths"] = [
            "skills/style-lock-director/assets/项目风格锁定基线卡模板.md"
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            catalog = Path(temp_dir) / "control-source-catalog.json"
            catalog.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            with patch.object(SOURCES, "CATALOG", catalog):
                errors = SOURCES.validate()
        self.assertTrue(
            any("CCS-STYLE-LOCK@v001" in error for error in errors),
            errors,
        )

    def test_replaced_source_needs_complete_read_only_definition(self) -> None:
        payload = json.loads(SOURCES.CATALOG.read_text(encoding="utf-8-sig"))
        with tempfile.TemporaryDirectory(dir=SOURCES.REPO_ROOT) as temp_dir:
            relative = Path(temp_dir).resolve().relative_to(SOURCES.REPO_ROOT).as_posix()
            incomplete = Path(temp_dir) / "CCS-STYLE-LOCK@v002.md"
            incomplete.write_text("# CCS-STYLE-LOCK@v002\n", encoding="utf-8")
            payload["sources"][0]["definition_paths"] = [
                "skills/style-lock-director/references/CCS-STYLE-LOCK@v001.md",
                f"{relative}/CCS-STYLE-LOCK@v002.md",
                "skills/style-lock-director/assets/项目风格锁定基线卡模板.md",
            ]
            catalog = Path(temp_dir) / "control-source-catalog.json"
            catalog.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            with patch.object(SOURCES, "CATALOG", catalog):
                errors = SOURCES.validate()
        self.assertTrue(any("旧源定义不完整" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
