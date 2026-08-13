#!/usr/bin/env python3
"""Regression tests for the active-rule archive boundary."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("validate_active_rule_boundary.py")
SPEC = importlib.util.spec_from_file_location("validate_active_rule_boundary", MODULE_PATH)
assert SPEC and SPEC.loader
BOUNDARY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BOUNDARY)
REPO_ROOT = Path(__file__).resolve().parents[1]


class ActiveRuleBoundaryTests(unittest.TestCase):
    def fixture(self) -> tuple[tempfile.TemporaryDirectory[str], Path]:
        temp_dir = tempfile.TemporaryDirectory()
        root = Path(temp_dir.name)
        (root / "docs").mkdir()
        (root / "skills/example").mkdir(parents=True)
        (root / ".codex-plugin").mkdir()
        files = {
            "AGENTS.md": "ARCHIVE_EXPLICIT_ONLY：只读现行规则。\n",
            "README.md": "# current\n",
            "docs/真人写实AI影视生产总流程_v0.1.md": "# flow\n",
            "docs/Skill清单与交接矩阵_v0.1.md": "# matrix\n",
            "skills/example/SKILL.md": "# skill\n",
            ".codex-plugin/plugin.json": "{}\n",
        }
        for relative, text in files.items():
            (root / relative).write_text(text, encoding="utf-8")
        manifest = {
            "authority_order": [
                {"path": "AGENTS.md", "load_policy": "automatic-instruction"},
                {"path": BOUNDARY.MANIFEST_NAME, "load_policy": "manifest-only"},
                {"path": "README.md", "load_policy": "on-demand-current-summary"},
                {
                    "path": "docs/真人写实AI影视生产总流程_v0.1.md",
                    "load_policy": "on-demand-current-rule",
                },
                {
                    "path": "docs/Skill清单与交接矩阵_v0.1.md",
                    "load_policy": "on-demand-current-rule",
                },
                {"path": "skills", "load_policy": "skill-metadata-then-explicit-activation"},
                {"path": ".codex-plugin/plugin.json", "load_policy": "discovery-metadata-only"},
            ],
            "support_documents": [],
            "historical_access_policy": "只有用户在当前指令明确要求时访问。",
        }
        (root / BOUNDARY.MANIFEST_NAME).write_text(
            json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
        )
        return temp_dir, root

    def test_repository_passes(self) -> None:
        self.assertEqual(BOUNDARY.validate(REPO_ROOT), [])

    def test_historical_transcript_in_docs_is_rejected(self) -> None:
        temp_dir, root = self.fixture()
        try:
            (root / "docs/项目_对话接续记录_2099.md").write_text("old", encoding="utf-8")
            self.assertTrue(any("包含历史讨论文件" in item for item in BOUNDARY.validate(root)))
        finally:
            temp_dir.cleanup()

    def test_reference_to_deleted_transcript_is_rejected(self) -> None:
        temp_dir, root = self.fixture()
        try:
            (root / "README.md").write_text(
                "[旧记录](docs/AI影视生产系统_对话接续记录_2026.md)", encoding="utf-8"
            )
            self.assertTrue(any("引用了历史讨论材料" in item for item in BOUNDARY.validate(root)))
        finally:
            temp_dir.cleanup()

    def test_disguised_unclassified_doc_is_rejected(self) -> None:
        temp_dir, root = self.fixture()
        try:
            (root / "docs/notes.md").write_text("old discussion", encoding="utf-8")
            self.assertTrue(any("未分类或缺失文档" in item for item in BOUNDARY.validate(root)))
        finally:
            temp_dir.cleanup()

    def test_missing_agents_sentinel_is_rejected(self) -> None:
        temp_dir, root = self.fixture()
        try:
            (root / "AGENTS.md").write_text("# rules\n", encoding="utf-8")
            self.assertTrue(any("历史隔离哨兵" in item for item in BOUNDARY.validate(root)))
        finally:
            temp_dir.cleanup()

    def test_non_utf8_text_cannot_bypass_reference_scan(self) -> None:
        temp_dir, root = self.fixture()
        try:
            (root / "notes.txt").write_bytes(b"\x81\x81\x81")
            self.assertTrue(any("无法按UTF-8读取" in item for item in BOUNDARY.validate(root)))
        finally:
            temp_dir.cleanup()

    def test_skills_cannot_be_marked_for_eager_loading(self) -> None:
        temp_dir, root = self.fixture()
        try:
            manifest_path = root / BOUNDARY.MANIFEST_NAME
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            next(item for item in manifest["authority_order"] if item["path"] == "skills")[
                "load_policy"
            ] = "automatic-instruction"
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
            self.assertTrue(any("skills 的 load_policy" in item for item in BOUNDARY.validate(root)))
        finally:
            temp_dir.cleanup()


if __name__ == "__main__":
    unittest.main()
