#!/usr/bin/env python3
"""Regression tests for task-artifact index transactions."""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("update_task_artifact_index.py")
SPEC = importlib.util.spec_from_file_location("update_task_artifact_index", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class TaskArtifactTransactionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.tasks = self.root / "tasks"
        self.outputs = self.root / "outputs"
        self.tasks.mkdir()
        self.outputs.mkdir()
        self.task_index = self.tasks / "任务索引.csv"
        self.artifact_index = self.tasks / "任务成果索引.csv"
        self._write_csv(
            self.task_index,
            [
                "项目ID", "任务ID", "任务单版本", "项目数据绑定卡版本", "当前阶段",
                "责任Skill", "需求槽位场次镜头范围", "任务状态", "任务单路径", "创建日期",
            ],
            [{
                "项目ID": "PRJ-TEST", "任务ID": "TASK-001", "任务单版本": "v001",
                "项目数据绑定卡版本": "v001", "当前阶段": "场戏创作",
                "责任Skill": "dramaturgy-scene-beats", "需求槽位场次镜头范围": "SCN-001",
                "任务状态": "已返回", "任务单路径": "tasks/TASK-001@v001.md", "创建日期": "2026-08-13",
            }],
        )
        self.artifact_headers = [
            "项目ID", "成果ID", "成果版本", "上一成果版本", "成果类别", "成果类型", "成果名称",
            "责任Skill", "来源任务ID", "来源任务单版本", "适用范围", "成果状态", "当前有效",
            "成果路径", "上游精确引用集合", "内容指纹SHA256", "内容变更摘要", "状态依据",
            "记录日期", "复核日期",
        ]
        self._write_csv(self.artifact_index, self.artifact_headers, [])
        self.control_index = self.root / "creative-control/项目创作基线索引.csv"
        self.control_index.parent.mkdir()
        control_schema = json.loads(MODULE.CONTROL_SCHEMA_PATH.read_text(encoding="utf-8-sig"))
        control_headers = list(control_schema["properties"])
        controls: list[dict[str, str]] = []
        for card_id, control_type, source, input_refs in (
            ("CC-STYLE-001", "项目风格锁定基线", "CCS-STYLE-LOCK@v003", "无"),
            ("CC-ART-001", "美术LookDev基线", "CCS-ART-LOOKDEV@v002", "CC-STYLE-001@v001"),
            ("CC-CIN-001", "全片摄影规则", "CCS-CINEMATOGRAPHY@v002", "CC-ART-001@v001"),
            ("CC-LGT-001", "项目灯光基线", "CCS-LIGHTING@v002", "CC-CIN-001@v001"),
        ):
            controls.append({
                "项目ID": "PRJ-TEST", "控制卡ID": card_id, "控制类型": control_type,
                "控制对象": "全项目", "项目卡版本": "v001", "上一项目卡版本": "不适用",
                "控制卡状态": "已生效", "当前有效": "是", "适用范围": "全项目",
                "项目锁定卡版本": "v001", "剧本内容版本": "script-v1", "源定义引用": source,
                "Profile引用集合": "无", "输入控制卡引用集合": input_refs,
                "顾问任务成果引用集合": "无", "控制卡路径": f"creative-control/{card_id}@v001.md",
                "内容指纹SHA256": "0" * 64, "内容变更摘要": "测试",
                "状态依据类型": "用户明确确认", "状态依据原文": "确认",
                "生效依据原文": "确认", "记录日期": "2026-08-13", "生效日期": "2026-08-13",
            })
        self._write_csv(self.control_index, control_headers, controls)
        self.transaction_number = 0

    def tearDown(self) -> None:
        self.temp.cleanup()

    @staticmethod
    def _write_csv(path: Path, headers: list[str], rows: list[dict[str, str]]) -> None:
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=headers)
            writer.writeheader()
            writer.writerows(rows)

    @staticmethod
    def _read_csv(path: Path) -> list[dict[str, str]]:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return list(csv.DictReader(handle))

    def _artifact_file(self, name: str, content: str) -> Path:
        path = self.outputs / name
        path.write_text(content, encoding="utf-8")
        return path

    def _row(
        self,
        artifact_id: str,
        version: str,
        path: Path,
        *,
        previous: str = "不适用",
        upstream: str = "无",
        status: str = "草案",
        current: str = "否",
    ) -> dict[str, str]:
        return {
            "项目ID": "PRJ-TEST", "成果ID": artifact_id, "成果版本": version,
            "上一成果版本": previous, "成果类别": "创作短卡", "成果类型": "场戏节拍卡",
            "成果名称": f"测试成果{artifact_id}", "责任Skill": "dramaturgy-scene-beats",
            "来源任务ID": "TASK-001", "来源任务单版本": "v001", "适用范围": "SCN-001",
            "成果状态": status, "当前有效": current,
            "成果路径": path.relative_to(self.root).as_posix(), "上游精确引用集合": upstream,
            "内容指纹SHA256": MODULE._fingerprint(path), "内容变更摘要": "测试版本",
            "状态依据": "自动测试", "记录日期": "2026-08-13", "复核日期": "不适用",
        }

    def _payload(self, body: dict[str, object]) -> Path:
        self.transaction_number += 1
        payload = {
            "项目ID": "PRJ-TEST",
            "事务ID": f"TAI-TEST-{self.transaction_number:03d}",
            "操作日期": "2026-08-13",
            "操作依据": "自动测试",
            **body,
        }
        path = self.root / f"payload-{self.transaction_number:03d}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return path

    def _run(self, command: str, **kwargs: object) -> dict[str, object]:
        values: dict[str, object] = {
            "command": command, "project_root": str(self.root), "index": None, "task_index": None,
        }
        values.update(kwargs)
        return MODULE._run(argparse.Namespace(**values))

    def _draft(self, *rows: dict[str, str]) -> dict[str, object]:
        return self._run("draft", payload=str(self._payload({"记录": list(rows)})))

    def _status(self, command: str, *targets: tuple[str, str]) -> dict[str, object]:
        target_rows = [{"成果ID": artifact_id, "成果版本": version} for artifact_id, version in targets]
        return self._run(command, payload=str(self._payload({"目标": target_rows})))

    def _status_with_basis(
        self, command: str, basis: str, *targets: tuple[str, str]
    ) -> dict[str, object]:
        target_rows = [{"成果ID": artifact_id, "成果版本": version} for artifact_id, version in targets]
        payload_path = self._payload({"目标": target_rows})
        payload = json.loads(payload_path.read_text(encoding="utf-8"))
        payload["操作依据"] = basis
        payload_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return self._run(command, payload=str(payload_path))

    def test_one_task_can_atomically_deliver_multiple_current_artifacts(self) -> None:
        first = self._row("ART-BEAT-001", "v001", self._artifact_file("beat@v001.md", "节拍"))
        second = self._row("ART-BLOCK-001", "v001", self._artifact_file("block@v001.md", "调度"))
        self._draft(first, second)
        self._status("activate", ("ART-BEAT-001", "v001"), ("ART-BLOCK-001", "v001"))
        result = self._run("check", project_id="PRJ-TEST")
        rows = self._read_csv(self.artifact_index)
        self.assertEqual(result["检查结论"], "通过")
        self.assertEqual({row["来源任务ID"] for row in rows}, {"TASK-001"})
        self.assertTrue(all(row["成果状态"] == "可交接" and row["当前有效"] == "是" for row in rows))

    def test_style_review_requires_review_category_four_cards_and_conclusion(self) -> None:
        review_path = self._artifact_file(
            "style-review@v001.md",
            "\n".join((
                "# 风格测试与评审卡", "评审业务状态：已通过", "四卡依赖检查：通过",
                "四卡依赖形状：风格→美术→摄影→灯光，且每张下游只引用直接上游",
                "Profile阶段状态：完整Profile均已关闭，仅使用四卡转译决定",
                "必做测试是否全部通过：是", "待处理专业冲突：无", "顾问硬事实缺口：无", "",
            )),
        )
        row = self._row(
            "SLR-PRJ-TEST", "v001", review_path,
            upstream="CC-STYLE-001@v001；CC-ART-001@v001；CC-CIN-001@v001；CC-LGT-001@v001",
        )
        row["成果类别"] = "审查记录"
        row["成果类型"] = "风格测试与评审卡"
        self._draft(row)
        self._status("activate", ("SLR-PRJ-TEST", "v001"))
        self.assertEqual(self._read_csv(self.artifact_index)[0]["成果状态"], "可交接")

    def test_p0_review_plan_can_be_handed_off_before_generation(self) -> None:
        review_path = self._artifact_file(
            "style-review-plan@v001.md",
            "\n".join((
                "# 风格测试与评审卡", "评审业务状态：待执行", "四卡依赖检查：通过",
                "四卡依赖形状：风格→美术→摄影→灯光，且每张下游只引用直接上游",
                "Profile阶段状态：完整Profile均已关闭，仅使用四卡转译决定", "",
            )),
        )
        row = self._row(
            "SLR-PRJ-TEST", "v001", review_path,
            upstream="CC-STYLE-001@v001；CC-ART-001@v001；CC-CIN-001@v001；CC-LGT-001@v001",
        )
        row["成果类别"] = "审查记录"
        row["成果类型"] = "风格测试与评审卡"
        self._draft(row)
        self._status("activate", ("SLR-PRJ-TEST", "v001"))
        saved = self._read_csv(self.artifact_index)[0]
        self.assertEqual((saved["成果状态"], saved["当前有效"]), ("可交接", "是"))

    def test_style_package_requires_release_gate(self) -> None:
        review_path = self._artifact_file(
            "style-review-for-package@v001.md",
            "\n".join((
                "# 风格测试与评审卡", "评审业务状态：已通过", "四卡依赖检查：通过",
                "四卡依赖形状：风格→美术→摄影→灯光，且每张下游只引用直接上游",
                "Profile阶段状态：完整Profile均已关闭，仅使用四卡转译决定", "",
            )),
        )
        review = self._row(
            "SLR-PRJ-TEST", "v001", review_path,
            upstream="CC-STYLE-001@v001；CC-ART-001@v001；CC-CIN-001@v001；CC-LGT-001@v001",
        )
        review["成果类别"] = "审查记录"
        review["成果类型"] = "风格测试与评审卡"
        self._draft(review)
        self._status("activate", ("SLR-PRJ-TEST", "v001"))
        package_path = self._artifact_file(
            "style-package@v001.md",
            "\n".join((
                "# 风格锁定包交付卡",
                "风格包状态：可用于批量生产",
                "四卡有效且依赖闭合：是",
                "P0测试全部通过：否",
                "无未决冲突与硬事实缺口：是",
                "完整Profile状态：全部已关闭",
                "最终结论：不可放行",
                "",
            )),
        )
        row = self._row(
            "SLP-PRJ-TEST", "v001", package_path,
            upstream="CC-STYLE-001@v001；CC-ART-001@v001；CC-CIN-001@v001；CC-LGT-001@v001；SLR-PRJ-TEST@v001",
        )
        row["成果类别"] = "组合快照"
        row["成果类型"] = "风格锁定包"
        self._draft(row)
        before = self.artifact_index.read_bytes()
        with self.assertRaisesRegex(MODULE.TaskArtifactError, "未满足批量放行业务门"):
            self._status("activate", ("SLP-PRJ-TEST", "v001"))
        self.assertEqual(self.artifact_index.read_bytes(), before)

    def test_style_package_requires_passing_review_evidence(self) -> None:
        review_path = self._artifact_file(
            "style-review-returned@v001.md",
            "\n".join((
                "# 风格测试与评审卡", "评审业务状态：需返工", "四卡依赖检查：通过",
                "四卡依赖形状：风格→美术→摄影→灯光，且每张下游只引用直接上游",
                "Profile阶段状态：完整Profile均已关闭，仅使用四卡转译决定",
                "必做测试是否全部通过：否", "待处理专业冲突：无", "顾问硬事实缺口：无", "",
            )),
        )
        review = self._row(
            "SLR-PRJ-TEST", "v001", review_path,
            upstream="CC-STYLE-001@v001；CC-ART-001@v001；CC-CIN-001@v001；CC-LGT-001@v001",
        )
        review["成果类别"] = "审查记录"
        review["成果类型"] = "风格测试与评审卡"
        self._draft(review)
        self._status("activate", ("SLR-PRJ-TEST", "v001"))
        package_path = self._artifact_file(
            "style-package-false-claim@v001.md",
            "\n".join((
                "# 风格锁定包交付卡", "风格包状态：可用于批量生产",
                "四卡有效且依赖闭合：是", "P0测试全部通过：是",
                "无未决冲突与硬事实缺口：是", "完整Profile状态：全部已关闭",
                "最终结论：可用于批量生产", "",
            )),
        )
        package = self._row(
            "SLP-PRJ-TEST", "v001", package_path,
            upstream="CC-STYLE-001@v001；CC-ART-001@v001；CC-CIN-001@v001；CC-LGT-001@v001；SLR-PRJ-TEST@v001",
        )
        package["成果类别"] = "组合快照"
        package["成果类型"] = "风格锁定包"
        self._draft(package)
        before = self.artifact_index.read_bytes()
        with self.assertRaisesRegex(MODULE.TaskArtifactError, "尚未满足批量放行证据门"):
            self._status("activate", ("SLP-PRJ-TEST", "v001"))
        self.assertEqual(self.artifact_index.read_bytes(), before)

    def test_style_package_source_change_marks_old_snapshot_review(self) -> None:
        review_path = self._artifact_file(
            "style-review-current@v001.md",
            "\n".join((
                "# 风格测试与评审卡", "评审业务状态：已通过", "四卡依赖检查：通过",
                "四卡依赖形状：风格→美术→摄影→灯光，且每张下游只引用直接上游",
                "Profile阶段状态：完整Profile均已关闭，仅使用四卡转译决定",
                "必做测试是否全部通过：是", "待处理专业冲突：无", "顾问硬事实缺口：无", "",
            )),
        )
        review = self._row(
            "SLR-PRJ-TEST", "v001", review_path,
            upstream="CC-STYLE-001@v001；CC-ART-001@v001；CC-CIN-001@v001；CC-LGT-001@v001",
        )
        review["成果类别"] = "审查记录"
        review["成果类型"] = "风格测试与评审卡"
        self._draft(review)
        self._status("activate", ("SLR-PRJ-TEST", "v001"))
        package_path = self._artifact_file(
            "style-package-valid@v001.md",
            "\n".join((
                "# 风格锁定包交付卡",
                "风格包状态：可用于批量生产",
                "四卡有效且依赖闭合：是",
                "P0测试全部通过：是",
                "无未决冲突与硬事实缺口：是",
                "完整Profile状态：全部已关闭",
                "最终结论：可用于批量生产",
                "",
            )),
        )
        row = self._row(
            "SLP-PRJ-TEST", "v001", package_path,
            upstream="CC-STYLE-001@v001；CC-ART-001@v001；CC-CIN-001@v001；CC-LGT-001@v001；SLR-PRJ-TEST@v001",
        )
        row["成果类别"] = "组合快照"
        row["成果类型"] = "风格锁定包"
        self._draft(row)
        self._status("activate", ("SLP-PRJ-TEST", "v001"))
        controls = self._read_csv(self.control_index)
        art = next(item for item in controls if item["控制卡ID"] == "CC-ART-001")
        art["控制卡状态"] = "已替代"
        art["当前有效"] = "否"
        art_v002 = dict(art)
        art_v002.update({
            "项目卡版本": "v002", "上一项目卡版本": "v001",
            "控制卡状态": "已生效", "当前有效": "是",
        })
        controls.append(art_v002)
        cinema = next(item for item in controls if item["控制卡ID"] == "CC-CIN-001")
        cinema["输入控制卡引用集合"] = "CC-ART-001@v002"
        self._write_csv(self.control_index, list(controls[0]), controls)
        with self.assertRaisesRegex(MODULE.TaskArtifactError, "旧成果不得用于新任务"):
            self._run("check", project_id="PRJ-TEST")
        impact = self._run(
            "impact", project_id="PRJ-TEST", upstream_ref="CC-ART-001@v001",
        )
        self.assertEqual(
            [item["成果"] for item in impact["潜在受影响成果"]],
            ["SLR-PRJ-TEST@v001", "SLP-PRJ-TEST@v001"],
        )
        self._status(
            "mark-review",
            ("SLR-PRJ-TEST", "v001"),
            ("SLP-PRJ-TEST", "v001"),
        )
        saved = self._read_csv(self.artifact_index)
        self.assertTrue(
            all((row["成果状态"], row["当前有效"]) == ("待复核", "否") for row in saved)
        )
        with self.assertRaisesRegex(MODULE.TaskArtifactError, "旧成果不得用于新任务"):
            self._status("confirm-review", ("SLP-PRJ-TEST", "v001"))

    def test_style_artifact_rejects_malformed_current_control_chain(self) -> None:
        controls = self._read_csv(self.control_index)
        cinema = next(item for item in controls if item["控制类型"] == "全片摄影规则")
        cinema["输入控制卡引用集合"] = "CC-STYLE-001@v001；CC-ART-001@v001"
        self._write_csv(self.control_index, list(controls[0]), controls)
        review_path = self._artifact_file(
            "bad-chain-review@v001.md",
            "\n".join((
                "# 风格测试与评审卡", "评审业务状态：已通过", "四卡依赖检查：通过",
                "四卡依赖形状：风格→美术→摄影→灯光，且每张下游只引用直接上游",
                "Profile阶段状态：完整Profile均已关闭，仅使用四卡转译决定", "",
            )),
        )
        row = self._row(
            "SLR-BAD-CHAIN", "v001", review_path,
            upstream="CC-STYLE-001@v001；CC-ART-001@v001；CC-CIN-001@v001；CC-LGT-001@v001",
        )
        row["成果类别"] = "审查记录"
        row["成果类型"] = "风格测试与评审卡"
        with self.assertRaisesRegex(MODULE.TaskArtifactError, "唯一直接上游链"):
            self._draft(row)

    def test_init_creates_an_empty_valid_artifact_index(self) -> None:
        self.artifact_index.unlink()
        result = self._run("init", project_id="PRJ-TEST")
        self.assertEqual(result["初始化结论"], "已初始化空索引")
        self.assertEqual(self._read_csv(self.artifact_index), [])
        self.assertEqual(self._run("check", project_id="PRJ-TEST")["检查结论"], "通过")

    def test_duplicate_current_versions_are_rejected(self) -> None:
        first_path = self._artifact_file("dup@v001.md", "第一版")
        second_path = self._artifact_file("dup@v002.md", "第二版")
        rows = [
            self._row("ART-DUP-001", "v001", first_path, status="可交接", current="是"),
            self._row("ART-DUP-001", "v002", second_path, previous="v001", status="可交接", current="是"),
        ]
        self._write_csv(self.artifact_index, self.artifact_headers, rows)
        with self.assertRaises(MODULE.TaskArtifactError):
            self._run("check", project_id="PRJ-TEST")

    def test_invalid_next_version_fails_without_modifying_index(self) -> None:
        before = self.artifact_index.read_bytes()
        invalid = self._row(
            "ART-GAP-001", "v002", self._artifact_file("gap@v002.md", "跳号"), previous="v001"
        )
        with self.assertRaises(MODULE.TaskArtifactError):
            self._draft(invalid)
        self.assertEqual(self.artifact_index.read_bytes(), before)

    def test_cross_project_task_index_is_rejected(self) -> None:
        rows = self._read_csv(self.task_index)
        rows[0]["项目ID"] = "PRJ-OTHER"
        self._write_csv(self.task_index, list(rows[0]), rows)
        with self.assertRaises(MODULE.TaskArtifactError):
            self._run("check", project_id="PRJ-TEST")

    def test_missing_artifact_file_is_rejected(self) -> None:
        path = self._artifact_file("missing@v001.md", "将删除")
        row = self._row("ART-MISSING-001", "v001", path)
        path.unlink()
        self._write_csv(self.artifact_index, self.artifact_headers, [row])
        with self.assertRaises(MODULE.TaskArtifactError):
            self._run("check", project_id="PRJ-TEST")

    def test_impact_analysis_is_transitive_and_read_only(self) -> None:
        first = self._row(
            "ART-CHAIN-A", "v001", self._artifact_file("chain-a@v001.md", "A"),
            upstream="CC-LOOK-001@v001", status="可交接", current="是",
        )
        second = self._row(
            "ART-CHAIN-B", "v001", self._artifact_file("chain-b@v001.md", "B"),
            upstream="ART-CHAIN-A@v001", status="可交接", current="是",
        )
        self._write_csv(self.artifact_index, self.artifact_headers, [first, second])
        before = self.artifact_index.read_bytes()
        result = self._run("impact", project_id="PRJ-TEST", upstream_ref="CC-LOOK-001@v001")
        affected = result["潜在受影响成果"]
        self.assertEqual([item["成果"] for item in affected], ["ART-CHAIN-A@v001", "ART-CHAIN-B@v001"])
        self.assertEqual(affected[1]["影响链"], ["CC-LOOK-001@v001", "ART-CHAIN-A@v001", "ART-CHAIN-B@v001"])
        self.assertEqual(self.artifact_index.read_bytes(), before)

    def test_review_never_restores_old_version_and_can_confirm_latest(self) -> None:
        v1 = self._row("ART-REV-001", "v001", self._artifact_file("review@v001.md", "旧版"))
        self._draft(v1)
        self._status("activate", ("ART-REV-001", "v001"))
        v2 = self._row(
            "ART-REV-001", "v002", self._artifact_file("review@v002.md", "新版"), previous="v001"
        )
        self._draft(v2)
        self._status("activate", ("ART-REV-001", "v002"))
        self._status("mark-review", ("ART-REV-001", "v002"))
        review_rows = self._read_csv(self.artifact_index)
        self.assertFalse(any(row["当前有效"] == "是" for row in review_rows))
        self._status("confirm-review", ("ART-REV-001", "v002"))
        final_rows = self._read_csv(self.artifact_index)
        current = [row for row in final_rows if row["当前有效"] == "是"]
        self.assertEqual([(row["成果版本"], row["成果状态"]) for row in current], [("v002", "可交接")])

    def test_reviewed_current_version_can_be_confirmed_while_newer_draft_exists(self) -> None:
        v1 = self._row("ART-REVIEW-DRAFT", "v001", self._artifact_file("review-draft@v001.md", "当前"))
        self._draft(v1)
        self._status("activate", ("ART-REVIEW-DRAFT", "v001"))
        self._status("mark-review", ("ART-REVIEW-DRAFT", "v001"))
        v2 = self._row(
            "ART-REVIEW-DRAFT", "v002", self._artifact_file("review-draft@v002.md", "提案"), previous="v001"
        )
        self._draft(v2)
        self._status("confirm-review", ("ART-REVIEW-DRAFT", "v001"))
        rows = self._read_csv(self.artifact_index)
        current = [row for row in rows if row["当前有效"] == "是"]
        self.assertEqual([(row["成果版本"], row["成果状态"]) for row in current], [("v001", "可交接")])
        self.assertEqual(next(row for row in rows if row["成果版本"] == "v002")["成果状态"], "草案")

    def test_old_draft_cannot_replace_a_newer_version(self) -> None:
        first_path = self._artifact_file("old@v001.md", "第一版")
        second_path = self._artifact_file("old@v002.md", "第二版")
        rows = [
            self._row("ART-OLD-001", "v001", first_path),
            self._row("ART-OLD-001", "v002", second_path, previous="v001", status="可交接", current="是"),
        ]
        self._write_csv(self.artifact_index, self.artifact_headers, rows)
        before = self.artifact_index.read_bytes()
        with self.assertRaises(MODULE.TaskArtifactError):
            self._status("activate", ("ART-OLD-001", "v001"))
        self.assertEqual(self.artifact_index.read_bytes(), before)

    def test_local_artifact_dependency_cycle_is_rejected(self) -> None:
        first = self._row(
            "ART-CYCLE-A", "v001", self._artifact_file("cycle-a@v001.md", "A"),
            upstream="ART-CYCLE-B@v001",
        )
        second = self._row(
            "ART-CYCLE-B", "v001", self._artifact_file("cycle-b@v001.md", "B"),
            upstream="ART-CYCLE-A@v001",
        )
        self._write_csv(self.artifact_index, self.artifact_headers, [first, second])
        with self.assertRaises(MODULE.TaskArtifactError):
            self._run("check", project_id="PRJ-TEST")

    def test_profile_semver_is_a_valid_external_exact_reference(self) -> None:
        row = self._row(
            "ART-PROFILE-001", "v001", self._artifact_file("profile@v001.md", "引用Profile"),
            upstream="FP-CIN-TEST@v1.0",
        )
        self._write_csv(self.artifact_index, self.artifact_headers, [row])
        result = self._run("check", project_id="PRJ-TEST")
        self.assertEqual(result["检查结论"], "通过")

    def test_cancelled_task_cannot_be_used_as_an_artifact_source(self) -> None:
        tasks = self._read_csv(self.task_index)
        tasks[0]["任务状态"] = "已取消"
        self._write_csv(self.task_index, list(tasks[0]), tasks)
        row = self._row("ART-CANCEL-001", "v001", self._artifact_file("cancel@v001.md", "取消"))
        before = self.artifact_index.read_bytes()
        with self.assertRaises(MODULE.TaskArtifactError):
            self._draft(row)
        self.assertEqual(self.artifact_index.read_bytes(), before)

    def test_duplicate_cancelled_task_versions_are_still_rejected(self) -> None:
        tasks = self._read_csv(self.task_index)
        tasks[0]["任务状态"] = "已取消"
        self._write_csv(self.task_index, list(tasks[0]), [tasks[0], dict(tasks[0])])
        with self.assertRaises(MODULE.TaskArtifactError):
            self._run("check", project_id="PRJ-TEST")

    def test_prompt_activation_requires_user_wording(self) -> None:
        row = self._row("IPR-TEST-001", "v001", self._artifact_file("prompt@v001.md", "Prompt正文"))
        row["成果类别"] = "Prompt"
        row["成果类型"] = "图片Prompt"
        self._draft(row)
        before = self.artifact_index.read_bytes()
        with self.assertRaises(MODULE.TaskArtifactError):
            self._status("activate", ("IPR-TEST-001", "v001"))
        self.assertEqual(self.artifact_index.read_bytes(), before)
        self._status_with_basis("activate", "用户原文：这版Prompt通过，我去生成", ("IPR-TEST-001", "v001"))
        current = [item for item in self._read_csv(self.artifact_index) if item["当前有效"] == "是"]
        self.assertEqual(current[0]["状态依据"], "用户原文：这版Prompt通过，我去生成")


if __name__ == "__main__":
    unittest.main()
