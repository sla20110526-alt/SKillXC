#!/usr/bin/env python3
"""Tests for the SKillXC interaction-mode contract."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import validate_interaction_modes as validator


ROOT = Path(__file__).resolve().parents[1]


class InteractionModeTests(unittest.TestCase):
    def test_repository_contract_passes(self) -> None:
        self.assertEqual(validator.validate(ROOT), [])

    def test_lightweight_template_cannot_expose_fingerprint(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self._copy_surface(Path(temp))
            path = root / "skills/production-router-handoff/assets/轻量生产回显模板.md"
            path.write_text(path.read_text(encoding="utf-8") + "\n内容指纹SHA256：\n", encoding="utf-8")
            self.assertTrue(any("泄露后台字段" in item for item in validator.validate(root)))

    def test_short_package_must_locate_full_task(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self._copy_surface(Path(temp))
            path = root / "skills/production-router-handoff/assets/短交接包模板.md"
            text = path.read_text(encoding="utf-8").replace("完整任务单路径", "后台位置")
            path.write_text(text, encoding="utf-8")
            self.assertTrue(any("完整任务单路径" in item for item in validator.validate(root)))

    def test_simulation_must_not_turn_candidate_into_registration(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self._copy_surface(Path(temp))
            path = root / "skills/production-router-handoff/references/s05-simulated-production-round.md"
            text = path.read_text(encoding="utf-8").replace("没有触发正式登记", "已经触发正式登记")
            path.write_text(text, encoding="utf-8")
            self.assertTrue(any("候选/登记边界" in item for item in validator.validate(root)))

    def test_continuity_entry_cannot_default_to_formal_record(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self._copy_surface(Path(temp))
            path = root / "skills/continuity-readiness-audit/agents/openai.yaml"
            text = path.read_text(encoding="utf-8").replace(
                "默认轻量检查", "默认写正式审计"
            )
            path.write_text(text, encoding="utf-8")
            self.assertTrue(
                any("入口元数据" in item for item in validator.validate(root))
            )

    @staticmethod
    def _copy_surface(target: Path) -> Path:
        relatives = (
            "skills/production-router-handoff/references/interaction-modes.md",
            "skills/production-router-handoff/SKILL.md",
            "skills/production-router-handoff/assets/短交接包模板.md",
            "skills/production-router-handoff/assets/轻量生产回显模板.md",
            "skills/production-router-handoff/references/s05-simulated-production-round.md",
            "skills/continuity-readiness-audit/SKILL.md",
            "skills/continuity-readiness-audit/agents/openai.yaml",
            *validator.STRICT_ACTIVATION_FILES,
        )
        for relative in relatives:
            source = ROOT / relative
            destination = target / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(source.read_bytes())
        return target


if __name__ == "__main__":
    unittest.main()
