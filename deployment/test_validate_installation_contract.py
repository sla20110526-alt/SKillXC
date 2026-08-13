#!/usr/bin/env python3
"""Tests for the SKillXC installation contract validator."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import validate_installation_contract as validator


ROOT = Path(__file__).resolve().parents[1]


class InstallationContractTests(unittest.TestCase):
    def test_repository_contract_has_exact_runtime_policy(self) -> None:
        self.assertEqual(validator.validate(ROOT), [])
        manifest = json.loads(
            (ROOT / "deployment/windows/install-manifest.json").read_text(encoding="utf-8")
        )
        activation = manifest["skillxc_activation"]
        self.assertEqual(len(activation["central_skill_names"]), 30)
        self.assertEqual(activation["implicit_skill_names"], ["production-router-handoff"])
        self.assertEqual(len(activation["explicit_only_skill_names"]), 29)

    def test_duplicate_name_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self._copy_contract_files(Path(temp))
            manifest_path = root / "deployment/windows/install-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["skillxc_activation"]["central_skill_names"].append("acting-direction")
            manifest["central_skill_count"] += 1
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
            self.assertTrue(any("重复名称" in error for error in validator.validate(root)))

    def test_second_implicit_skill_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self._copy_contract_files(Path(temp))
            manifest_path = root / "deployment/windows/install-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            activation = manifest["skillxc_activation"]
            activation["implicit_skill_names"].append("acting-direction")
            activation["explicit_only_skill_names"].remove("acting-direction")
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
            self.assertTrue(any("只能允许" in error for error in validator.validate(root)))

    def test_plugin_install_requirement_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self._copy_contract_files(Path(temp))
            manifest_path = root / "deployment/windows/install-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["skillxc_activation"]["plugin_must_be_installed"] = True
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
            self.assertTrue(any("保持未安装" in error for error in validator.validate(root)))

    @staticmethod
    def _copy_contract_files(target: Path) -> Path:
        for relative in (
            "deployment/windows/install-manifest.json",
            ".codex-plugin/plugin.json",
        ):
            source = ROOT / relative
            destination = target / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(source.read_bytes())
        for skill_root in (ROOT / "skills").iterdir():
            if not skill_root.is_dir():
                continue
            for relative in ("SKILL.md", "agents/openai.yaml"):
                source = skill_root / relative
                destination = target / "skills" / skill_root.name / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(source.read_bytes())
        return target


if __name__ == "__main__":
    unittest.main()
