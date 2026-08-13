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


if __name__ == "__main__":
    unittest.main()
