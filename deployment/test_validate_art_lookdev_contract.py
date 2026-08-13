#!/usr/bin/env python3
"""Tests for the C01 art and LookDev contract."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import validate_art_lookdev_contract as validator


ROOT = Path(__file__).resolve().parents[1]


class ArtLookdevContractTests(unittest.TestCase):
    def test_repository_contract_passes(self) -> None:
        self.assertEqual(validator.validate(ROOT), [])

    def test_baseline_cannot_lose_motif_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self._copy_surface(Path(temp))
            path = root / "skills/art-lookdev-direction/assets/美术LookDev基线卡模板.md"
            path.write_text(
                path.read_text(encoding="utf-8").replace("视觉母题（物质载体→出现条件→变化方式→使用上限）：", "主题气氛："),
                encoding="utf-8",
            )
            self.assertTrue(any("视觉母题" in item for item in validator.validate(root)))

    def test_handoff_cannot_become_batch_release(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self._copy_surface(Path(temp))
            path = root / "skills/art-lookdev-direction/assets/美术执行交接包模板.md"
            path.write_text(
                path.read_text(encoding="utf-8").replace("不是长期基线、正式资产、风格评审或批量放行", "可以直接作为批量放行"),
                encoding="utf-8",
            )
            self.assertTrue(any("批量放行" in item for item in validator.validate(root)))

    def test_simulation_cannot_hide_blocking_fact_gap(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self._copy_surface(Path(temp))
            path = root / "skills/art-lookdev-direction/references/c01-simulated-lookdev-task.md"
            path.write_text(
                path.read_text(encoding="utf-8").replace("必要缺口：", "补充说明："),
                encoding="utf-8",
            )
            self.assertTrue(any("必要缺口" in item for item in validator.validate(root)))

    def test_skill_cannot_write_assets_or_registration(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self._copy_surface(Path(temp))
            path = root / "skills/art-lookdev-direction/SKILL.md"
            path.write_text(
                path.read_text(encoding="utf-8").replace(
                    "不得直接生产资产图片、Prompt 或登记申请",
                    "可以直接生产资产图片、Prompt 和登记申请",
                ),
                encoding="utf-8",
            )
            self.assertTrue(any("不得直接生产" in item for item in validator.validate(root)))

    def test_simulation_must_keep_one_decision(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self._copy_surface(Path(temp))
            path = root / "skills/art-lookdev-direction/references/c01-simulated-lookdev-task.md"
            text = path.read_text(encoding="utf-8").replace(
                "下一步：确认后生成", "现在请你决定：是否先做灯光？\n\n下一步：确认后生成"
            )
            path.write_text(text, encoding="utf-8")
            self.assertTrue(any("一个决定点" in item for item in validator.validate(root)))

    def test_catalog_must_publish_current_v003(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self._copy_surface(Path(temp))
            path = root / "skills/creative-control-versioning/references/control-source-catalog.json"
            payload = json.loads(path.read_text(encoding="utf-8"))
            art = next(
                item for item in payload["sources"]
                if item["source_id"] == "CCS-ART-LOOKDEV"
            )
            art["current_version"] = "v002"
            path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            self.assertTrue(any("连续v003" in item for item in validator.validate(root)))

    @staticmethod
    def _copy_surface(target: Path) -> Path:
        relatives = (
            "skills/art-lookdev-direction/SKILL.md",
            "skills/art-lookdev-direction/assets/美术LookDev基线卡模板.md",
            "skills/art-lookdev-direction/assets/美术执行交接包模板.md",
            "skills/art-lookdev-direction/references/art-lookdev-decision-contract.md",
            "skills/art-lookdev-direction/references/c01-simulated-lookdev-task.md",
            "skills/production-router-handoff/SKILL.md",
            "skills/production-router-handoff/assets/创作任务单模板.md",
            "skills/style-lock-director/SKILL.md",
            "skills/creative-control-versioning/references/control-source-catalog.json",
        )
        for relative in relatives:
            source = ROOT / relative
            destination = target / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(source.read_bytes())
        return target


if __name__ == "__main__":
    unittest.main()
