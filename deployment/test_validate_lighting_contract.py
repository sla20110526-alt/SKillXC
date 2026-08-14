#!/usr/bin/env python3
"""Tests for the C02 lighting-direction contract."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import validate_lighting_contract as validator


ROOT = Path(__file__).resolve().parents[1]


class LightingContractTests(unittest.TestCase):
    def test_repository_contract_passes(self) -> None:
        self.assertEqual(validator.validate(ROOT), [])

    def test_map_cannot_lose_negative_fill_role(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self._copy_surface(Path(temp))
            path = root / "skills/lighting-direction/assets/lighting-source-map.schema.json"
            path.write_text(path.read_text(encoding="utf-8").replace("负补光", "暗部控制"), encoding="utf-8")
            self.assertTrue(any("负补光" in item for item in validator.validate(root)))

    def test_map_header_must_match_schema(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self._copy_surface(Path(temp))
            path = root / "skills/lighting-direction/assets/场景光源地图模板.csv"
            path.write_text(path.read_text(encoding="utf-8").replace("光角色", "灯光角色", 1), encoding="utf-8")
            self.assertTrue(any("表头与Schema" in item for item in validator.validate(root)))

    def test_location_cannot_reclaim_source_map(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self._copy_surface(Path(temp))
            path = root / "skills/location-spatial-production/SKILL.md"
            path.write_text(
                path.read_text(encoding="utf-8").replace("光源地图由 `lighting-direction` 唯一写入", "光源地图由场景Skill写入"),
                encoding="utf-8",
            )
            self.assertTrue(any("唯一写入权" in item for item in validator.validate(root)))

    def test_spatial_bible_cannot_depend_on_downstream_map(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self._copy_surface(Path(temp))
            path = root / "skills/location-spatial-production/references/spatial-bible.md"
            path.write_text(
                path.read_text(encoding="utf-8").replace(
                    "不得反向引用以它为上游的光源地图",
                    "保存当前光源地图引用",
                ),
                encoding="utf-8",
            )
            self.assertTrue(any("双向版本依赖" in item for item in validator.validate(root)))

    def test_shot_card_cannot_become_full_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self._copy_surface(Path(temp))
            path = root / "skills/lighting-direction/assets/镜头灯光短执行卡模板.md"
            path.write_text(path.read_text(encoding="utf-8").replace("不是完整Prompt", "就是完整Prompt"), encoding="utf-8")
            self.assertTrue(any("不是完整Prompt" in item for item in validator.validate(root)))

    def test_multiview_must_keep_world_and_screen_directions_separate(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self._copy_surface(Path(temp))
            path = root / "skills/lighting-direction/assets/多视图灯光继承卡模板.md"
            path.write_text(path.read_text(encoding="utf-8").replace("不得替代世界方向", "等同世界方向"), encoding="utf-8")
            self.assertTrue(any("不得替代世界方向" in item for item in validator.validate(root)))

    def test_simulation_must_keep_one_decision(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self._copy_surface(Path(temp))
            path = root / "skills/lighting-direction/references/c02-simulated-lighting-task.md"
            text = path.read_text(encoding="utf-8").replace(
                "下一步：确认后建立", "现在请你决定：台灯亮度。\n\n下一步：确认后建立"
            )
            path.write_text(text, encoding="utf-8")
            self.assertTrue(any("一个决定点" in item for item in validator.validate(root)))

    def test_simulation_cannot_hide_blocking_orientation_gap(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self._copy_surface(Path(temp))
            path = root / "skills/lighting-direction/references/c02-simulated-lighting-task.md"
            path.write_text(path.read_text(encoding="utf-8").replace("必要缺口：", "补充说明："), encoding="utf-8")
            self.assertTrue(any("必要缺口" in item for item in validator.validate(root)))

    def test_new_light_state_cannot_overwrite_base_map(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self._copy_surface(Path(temp))
            path = root / "skills/lighting-direction/references/lighting-decision-contract.md"
            path.write_text(
                path.read_text(encoding="utf-8").replace(
                    "时间、天气、灯具开关、主光条件或VFX阶段改变",
                    "所有变化",
                ),
                encoding="utf-8",
            )
            self.assertTrue(any("灯具开关" in item for item in validator.validate(root)))

    def test_catalog_must_publish_current_v003(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self._copy_surface(Path(temp))
            path = root / "skills/creative-control-versioning/references/control-source-catalog.json"
            payload = json.loads(path.read_text(encoding="utf-8"))
            lighting = next(item for item in payload["sources"] if item["source_id"] == "CCS-LIGHTING")
            lighting["current_version"] = "v002"
            path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            self.assertTrue(any("连续v003" in item for item in validator.validate(root)))

    @staticmethod
    def _copy_surface(target: Path) -> Path:
        relatives = (
            "skills/lighting-direction/SKILL.md",
            "skills/lighting-direction/assets/项目灯光基线卡模板.md",
            "skills/lighting-direction/assets/场景光源地图说明卡模板.md",
            "skills/lighting-direction/assets/场景光源地图模板.csv",
            "skills/lighting-direction/assets/lighting-source-map.schema.json",
            "skills/lighting-direction/assets/人物受光卡模板.md",
            "skills/lighting-direction/assets/多视图灯光继承卡模板.md",
            "skills/lighting-direction/assets/镜头灯光短执行卡模板.md",
            "skills/lighting-direction/references/lighting-decision-contract.md",
            "skills/lighting-direction/references/c02-simulated-lighting-task.md",
            "skills/production-router-handoff/SKILL.md",
            "skills/production-router-handoff/assets/创作任务单模板.md",
            "skills/production-router-handoff/assets/data-contract-map.json",
            "skills/location-spatial-production/SKILL.md",
            "skills/location-spatial-production/references/spatial-bible.md",
            "skills/image-prompt-production/SKILL.md",
            "skills/video-prompt-production/SKILL.md",
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
