from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("validate_control_sources.py")
SPEC = importlib.util.spec_from_file_location("validate_control_sources", MODULE_PATH)
assert SPEC and SPEC.loader
SOURCES = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SOURCES)


class SourceCatalogTests(unittest.TestCase):
    def test_repository_source_catalog_is_valid(self) -> None:
        self.assertEqual(SOURCES.validate(), [])


if __name__ == "__main__":
    unittest.main()
