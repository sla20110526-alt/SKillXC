#!/usr/bin/env python3
"""Regression tests for the film Profile library validator."""

from __future__ import annotations

import importlib.util
import shutil
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("validate_profiles.py")
SPEC = importlib.util.spec_from_file_location("validate_profiles", MODULE_PATH)
assert SPEC and SPEC.loader
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)
LIBRARY_ROOT = Path(__file__).resolve().parents[1]


class ProfileLibraryTests(unittest.TestCase):
    def copy_library(self) -> tuple[tempfile.TemporaryDirectory[str], Path]:
        temp_dir = tempfile.TemporaryDirectory()
        root = Path(temp_dir.name) / "film-profile-library"
        shutil.copytree(LIBRARY_ROOT, root)
        return temp_dir, root

    def test_repository_library_passes(self) -> None:
        result = VALIDATOR.validate_library(LIBRARY_ROOT)
        self.assertEqual(result["profiles"], 27)
        self.assertEqual(result["catalog_rows"], 27)
        self.assertEqual(result["history_rows"], 27)
        self.assertEqual(result["errors"], [])

    def test_unregistered_profile_version_is_rejected(self) -> None:
        temp_dir, root = self.copy_library()
        try:
            history = root / "references/profile-version-history.json"
            text = history.read_text(encoding="utf-8")
            history.write_text(
                text.replace(
                    '{"profile_id": "FP-DIR-DAVID-FINCHER", "available_versions": ["v1.0"]}',
                    '{"profile_id": "FP-DIR-DAVID-FINCHER", "available_versions": ["v0.9"]}',
                ),
                encoding="utf-8",
            )
            result = VALIDATOR.validate_library(root)
            self.assertTrue(any("最后版本必须等于当前卡片版本" in error for error in result["errors"]))
        finally:
            temp_dir.cleanup()

    def test_missing_section_is_rejected(self) -> None:
        temp_dir, root = self.copy_library()
        try:
            card = root / "references/director-david-fincher.md"
            text = card.read_text(encoding="utf-8")
            card.write_text(text.replace("## 部门交接", "## 错误章节"), encoding="utf-8")
            result = VALIDATOR.validate_library(root)
            self.assertTrue(any("章节名称或顺序" in error for error in result["errors"]))
        finally:
            temp_dir.cleanup()

    def test_maturity_status_mismatch_is_rejected(self) -> None:
        temp_dir, root = self.copy_library()
        try:
            card = root / "references/director-david-fincher.md"
            text = card.read_text(encoding="utf-8")
            card.write_text(text.replace("- 当前状态：受限可选", "- 当前状态：可选择"), encoding="utf-8")
            result = VALIDATOR.validate_library(root)
            self.assertTrue(any("不允许状态" in error for error in result["errors"]))
        finally:
            temp_dir.cleanup()

    def test_unknown_source_is_rejected(self) -> None:
        temp_dir, root = self.copy_library()
        try:
            card = root / "references/director-david-fincher.md"
            text = card.read_text(encoding="utf-8")
            card.write_text(text.replace("SRC-DRAFT-001", "SRC-MISSING-001"), encoding="utf-8")
            result = VALIDATOR.validate_library(root)
            self.assertTrue(any("来源ID未在" in error for error in result["errors"]))
        finally:
            temp_dir.cleanup()

    def test_catalog_card_mismatch_is_rejected(self) -> None:
        temp_dir, root = self.copy_library()
        try:
            catalog = root / "references/catalog.md"
            text = catalog.read_text(encoding="utf-8")
            catalog.write_text(text.replace("FP-DIR-DAVID-FINCHER | 大卫・芬奇", "FP-DIR-DAVID-FINCHER | 测试姓名"), encoding="utf-8")
            result = VALIDATOR.validate_library(root)
            self.assertTrue(any("主体名称" in error and "catalog.md" in error for error in result["errors"]))
        finally:
            temp_dir.cleanup()

    def test_cinematography_lifecycle_is_rejected_outside_baseline(self) -> None:
        temp_dir, root = self.copy_library()
        try:
            card = root / "references/cinematographer-roger-deakins.md"
            text = card.read_text(encoding="utf-8")
            card.write_text(text.replace("- 适用阶段：全片摄影基线", "- 适用阶段：逐镜摄影审核"), encoding="utf-8")
            result = VALIDATOR.validate_library(root)
            self.assertTrue(any("适用阶段必须为" in error for error in result["errors"]))
        finally:
            temp_dir.cleanup()

    def test_verified_card_cannot_keep_analytic_methods(self) -> None:
        temp_dir, root = self.copy_library()
        try:
            card = root / "references/director-david-fincher.md"
            text = card.read_text(encoding="utf-8")
            text = text.replace("- 当前状态：受限可选", "- 当前状态：可选择")
            text = text.replace("- 资料成熟度：初版", "- 资料成熟度：已核验")
            card.write_text(text, encoding="utf-8")
            result = VALIDATOR.validate_library(root)
            self.assertTrue(any("仍含未核验方法" in error for error in result["errors"]))
        finally:
            temp_dir.cleanup()


if __name__ == "__main__":
    unittest.main()
