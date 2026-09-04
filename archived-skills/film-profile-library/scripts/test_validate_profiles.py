#!/usr/bin/env python3
"""Regression tests for the film Profile library validator."""

from __future__ import annotations

import importlib.util
import json
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
            payload = json.loads(history.read_text(encoding="utf-8"))
            record = next(item for item in payload["profiles"] if item["profile_id"] == "FP-DIR-DAVID-FINCHER")
            record["available_versions"] = ["v1.0"]
            record["definition_paths"] = {"v1.0": "history/FP-DIR-DAVID-FINCHER@v1.0.md"}
            history.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
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
            card.write_text(
                text.replace(
                    "- 适用阶段：全片摄影基线；用户明确确认的限时场戏摄影例外",
                    "- 适用阶段：逐镜摄影审核",
                ),
                encoding="utf-8",
            )
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

    def test_director_must_declare_both_separately_confirmed_stages(self) -> None:
        temp_dir, root = self.copy_library()
        try:
            card = root / "references/director-david-fincher.md"
            text = card.read_text(encoding="utf-8")
            card.write_text(
                text.replace(
                    "- 适用阶段：项目风格意图基线；导演与人物调度",
                    "- 适用阶段：导演与人物调度",
                ),
                encoding="utf-8",
            )
            result = VALIDATOR.validate_library(root)
            self.assertTrue(any("适用阶段必须为" in error for error in result["errors"]))
        finally:
            temp_dir.cleanup()

    def test_cross_stage_inheritance_must_be_department_slice(self) -> None:
        temp_dir, root = self.copy_library()
        try:
            card = root / "references/editor-walter-murch.md"
            text = card.read_text(encoding="utf-8")
            card.write_text(
                text.replace(
                    "- 可跨阶段继承：仅剪辑节奏卡中的镜头关系、时长、切点、动作/声音接点与生成单元切片；不得继承Profile本体、姓名、片名或未采用方法",
                    "- 可跨阶段继承：完整Profile",
                ),
                encoding="utf-8",
            )
            result = VALIDATOR.validate_library(root)
            self.assertTrue(any("可跨阶段继承必须为" in error for error in result["errors"]))
        finally:
            temp_dir.cleanup()

    def test_dual_stage_profile_requires_routing_explanation(self) -> None:
        temp_dir, root = self.copy_library()
        try:
            card = root / "references/director-david-fincher.md"
            text = card.read_text(encoding="utf-8")
            card.write_text(
                "\n".join(line for line in text.splitlines() if not line.startswith("- 双入口分流：")) + "\n",
                encoding="utf-8",
            )
            result = VALIDATOR.validate_library(root)
            self.assertTrue(any("缺少双入口分流说明" in error for error in result["errors"]))
        finally:
            temp_dir.cleanup()

    def test_phase_route_must_match_calling_skill(self) -> None:
        temp_dir, root = self.copy_library()
        try:
            routing = root / "references/phase-routing.md"
            text = routing.read_text(encoding="utf-8")
            routing.write_text(
                text.replace("`style-lock-director` 模式 A", "`directing-blocking` 模式 A"),
                encoding="utf-8",
            )
            result = VALIDATOR.validate_library(root)
            self.assertTrue(any("责任Skill映射不完整或不一致" in error for error in result["errors"]))
        finally:
            temp_dir.cleanup()

    def test_card_source_requires_repository_snapshot(self) -> None:
        temp_dir, root = self.copy_library()
        try:
            sources = root / "references/sources.md"
            text = sources.read_text(encoding="utf-8")
            sources.write_text(
                text.replace(
                    "- 仓库快照：[SRC-USER-001](source-snapshots/SRC-USER-001.md)。",
                    "- 说明：来源尚未保存。",
                ),
                encoding="utf-8",
            )
            result = VALIDATOR.validate_library(root)
            self.assertTrue(any("缺少仓库快照" in error for error in result["errors"]))
        finally:
            temp_dir.cleanup()

    def test_historical_definition_is_required_and_must_match(self) -> None:
        temp_dir, root = self.copy_library()
        try:
            history = root / "references/history/FP-DIR-DAVID-FINCHER@v1.0.md"
            history.unlink()
            result = VALIDATOR.validate_library(root)
            self.assertTrue(any("定义文件不存在" in error for error in result["errors"]))
        finally:
            temp_dir.cleanup()

    def test_historical_definition_reference_must_match_version(self) -> None:
        temp_dir, root = self.copy_library()
        try:
            history = root / "references/history/FP-DIR-DAVID-FINCHER@v1.0.md"
            text = history.read_text(encoding="utf-8")
            history.write_text(
                text.replace(
                    "- Profile引用：`FP-DIR-DAVID-FINCHER@v1.0`",
                    "- Profile引用：`FP-DIR-DAVID-FINCHER@v1.1`",
                ),
                encoding="utf-8",
            )
            result = VALIDATOR.validate_library(root)
            self.assertTrue(any("短执行卡Profile引用不一致" in error for error in result["errors"]))
        finally:
            temp_dir.cleanup()

    def test_sources_cannot_require_external_history_lookup(self) -> None:
        temp_dir, root = self.copy_library()
        try:
            sources = root / "references/sources.md"
            text = sources.read_text(encoding="utf-8")
            sources.write_text(text + "\n定位：请搜索聊天记录或旧提交。\n", encoding="utf-8")
            result = VALIDATOR.validate_library(root)
            self.assertTrue(any("外部历史定位要求" in error for error in result["errors"]))
        finally:
            temp_dir.cleanup()

    def test_all_unverified_cards_remain_initial_and_restricted(self) -> None:
        result = VALIDATOR.validate_library(LIBRARY_ROOT)
        self.assertEqual(result["errors"], [])
        references = LIBRARY_ROOT / "references"
        for path in VALIDATOR._profile_files(references):
            record, _, errors = VALIDATOR._extract_record(path.read_text(encoding="utf-8"), path.name)
            self.assertEqual(errors, [])
            self.assertEqual(record["资料成熟度"], "初版")
            self.assertEqual(record["当前状态"], "受限可选")
            self.assertEqual(record["方法证据状态"], "分析性归纳")


if __name__ == "__main__":
    unittest.main()
