#!/usr/bin/env python3
"""Tests for the C07 Seedance video Prompt contract validator."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "deployment/validate_video_prompt_contract.py"
SPEC = importlib.util.spec_from_file_location("validate_video_prompt_contract", MODULE_PATH)
assert SPEC and SPEC.loader
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


def valid_reference() -> dict[str, object]:
    return {
        "项目ID": "DEMO",
        "参考映射数据集ID": "VRM-DEMO-GU002",
        "映射版本": "v001",
        "生成单元ID": "GU-DEMO-002",
        "分镜组ID与版本": "SBG-DEMO-012@v003",
        "参考序号": 1,
        "平台引用名": "人物参考A",
        "参考类型": "人物五视图总览卡",
        "主体或对象ID": "CHAR-LINZHOU",
        "正式来源ID与版本或用户参考定位": "CHAR-LINZHOU-FIVEVIEW@v002",
        "当前服装状态或阶段": "深灰外套；无伤",
        "适用镜头ID与版本集合": "SH-001@v002；SH-002@v001",
        "唯一用途": "锁定林舟身份、深灰外套与无伤起始状态",
        "允许继承": "面部、发型、体型、深灰外套、无伤状态",
        "禁止继承": "卡片排版、白底、面板边界、静止姿态",
        "平台处理方式": "直接上传（本次已核对）",
        "平台能力核对状态": "已核对",
        "来源状态": "正式可调用资产",
        "备注": "",
    }


def valid_body(single: bool = True) -> str:
    prefix = "连续单镜头，总时长3.2秒。" if single else "总时长7.2秒，共2个镜头；不合并成一镜到底。"
    return (
        "参考绑定：人物参考A只锁人物身份与当前服装。"
        + prefix
        + "空间与摄影：办公室门、椅子和桌形成明确纵深。"
        + "第一帧：林舟站在访客椅外侧，视线看向主任。"
        + "动作与表演：命令结束后短暂停顿，再迈步绕椅。"
        + "物理接触：鞋底受力，重心前移，手掌最后接触信封。"
        + "台词与声音：主任说‘坐’，林舟不说话，房间底噪保持。"
        + "光影执行：窗侧来源保持，人物眼睛有微弱自然反射。"
        + "稳定结束状态：林舟停在桌边，信封平放，摄影机停稳。"
    )


def valid_package(mode: str = "单镜头正式Prompt装配") -> dict[str, object]:
    single = mode == "单镜头正式Prompt装配"
    shots = [{"时长": 3.2, "CUT": "单元结束", "第一帧": "站定", "稳定结束": "停稳"}]
    total = 3.2
    if not single:
        shots = [
            {"时长": 2.8, "CUT": "CUT-001", "第一帧": "站定", "稳定结束": "右脚启动"},
            {"时长": 4.4, "CUT": "单元结束", "第一帧": "右脚承接", "稳定结束": "桌边停稳"},
        ]
        total = 7.2
    return {
        "工作模式": mode,
        "生成单元ID": "GU-DEMO-002",
        "分镜组ID与版本": "SBG-DEMO-012@v003",
        "镜头ID与版本集合": "SH-001@v002；SH-002@v001" if not single else "SH-001@v002",
        "VRM精确引用": "VRM-DEMO-GU002@v001",
        "ERT与ERC精确引用": "ERT-DEMO-SBG012@v002；ERC-DEMO-SBG012@v002",
        "逐镜摄影审核": "CAM-AUDIT-DEMO@v001",
        "生成就绪结论": "可继续",
        "仍待核对能力": "无",
        "分镜写回状态": "全部完成",
        "生成单元总时长": total,
        "逐镜": shots,
        "直接参考别名": ["人物参考A"],
        "Prompt正文": valid_body(single),
    }


class VideoPromptContractTests(unittest.TestCase):
    def test_repository_contract_is_complete(self) -> None:
        self.assertEqual(validator.validate(ROOT), [])

    def test_positive_reference_passes(self) -> None:
        self.assertEqual(validator.validate_reference_record(valid_reference()), [])

    def test_missing_source_and_pending_platform_fail(self) -> None:
        record = valid_reference()
        record["正式来源ID与版本或用户参考定位"] = ""
        record["平台能力核对状态"] = "待核对"
        record["平台处理方式"] = "使用时待核对"
        errors = validator.validate_reference_record(record)
        self.assertTrue(any("正式来源" in item or "必填" in item for item in errors))
        self.assertTrue(any("平台能力" in item for item in errors))

    def test_vague_or_multi_role_reference_purpose_fails(self) -> None:
        record = valid_reference()
        record["唯一用途"] = "全部参考人物和场景"
        errors = validator.validate_reference_record(record)
        self.assertTrue(any("用途含糊" in item for item in errors))
        self.assertTrue(any("一个主要用途" in item for item in errors))

    def test_motion_reference_must_forbid_unrelated_inheritance(self) -> None:
        record = valid_reference()
        record["参考类型"] = "动作或运镜视频参考"
        record["来源状态"] = "用户确认的一次性参考"
        record["正式来源ID与版本或用户参考定位"] = "用户上传动作参考001.mp4"
        record["禁止继承"] = "人物身份"
        errors = validator.validate_reference_record(record)
        self.assertTrue(any("服装" in item for item in errors))
        self.assertTrue(any("场景" in item for item in errors))
        self.assertTrue(any("光线" in item for item in errors))

    def test_same_character_cannot_use_two_overview_cards(self) -> None:
        first = valid_reference()
        second = valid_reference()
        second["参考序号"] = 2
        second["平台引用名"] = "人物参考B"
        second["唯一用途"] = "锁定林舟另一张面部剧照"
        errors = validator.validate_reference_sequence([first, second])
        self.assertTrue(any("只能调用一张" in item for item in errors))

    def test_character_reference_must_match_current_state(self) -> None:
        errors = validator.validate_reference_sequence(
            [valid_reference()], {"CHAR-LINZHOU": "深灰外套；额头流血"}
        )
        self.assertTrue(any("服装/状态不匹配" in item for item in errors))

    def test_reference_order_and_alias_must_be_unique(self) -> None:
        first = valid_reference()
        second = valid_reference()
        second["主体或对象ID"] = "CHAR-DIRECTOR"
        second["唯一用途"] = "锁定主任身份与深色西装"
        errors = validator.validate_reference_sequence([first, second])
        self.assertTrue(any("重复参考序号" in item for item in errors))
        self.assertTrue(any("重复平台引用名" in item for item in errors))

    def test_positive_single_shot_package_passes(self) -> None:
        self.assertEqual(validator.validate_prompt_package(valid_package()), [])

    def test_positive_shot_group_package_passes(self) -> None:
        self.assertEqual(validator.validate_prompt_package(valid_package("镜头组正式Prompt装配")), [])

    def test_shot_group_duration_and_boundaries_are_required(self) -> None:
        package = valid_package("镜头组正式Prompt装配")
        package["生成单元总时长"] = 8.0
        package["逐镜"][1]["CUT"] = ""
        errors = validator.validate_prompt_package(package)
        self.assertTrue(any("时长之和" in item for item in errors))
        self.assertTrue(any("CUT" in item for item in errors))

    def test_prompt_body_order_and_management_leak_fail(self) -> None:
        package = valid_package()
        package["Prompt正文"] = valid_body().replace("第一帧", "开始画面") + "读取某卡 @v001"
        errors = validator.validate_prompt_package(package)
        self.assertTrue(any("缺少装配段落" in item for item in errors))
        self.assertTrue(any("管理语言" in item for item in errors))

    def test_quality_slogan_stack_fails(self) -> None:
        body = valid_body() + "8K IMAX 电影级 超真实 非3D"
        self.assertTrue(any("质量口号" in item for item in validator.validate_prompt_body(body)))

    def test_direct_reference_alias_must_be_bound_in_body(self) -> None:
        body = valid_body().replace("人物参考A", "人物卡")
        errors = validator.validate_prompt_body(body, ["人物参考A"])
        self.assertTrue(any("没有在正文绑定" in item for item in errors))

    def test_readiness_and_platform_unknown_block_delivery(self) -> None:
        package = valid_package()
        package["生成就绪结论"] = "暂停"
        package["仍待核对能力"] = "参考视频加载方式"
        errors = validator.validate_prompt_package(package)
        self.assertTrue(any("生成就绪暂停" in item for item in errors))
        self.assertTrue(any("能力待核对" in item for item in errors))

    def test_vrm_cannot_depend_on_prompt(self) -> None:
        errors = validator.validate_dependency_direction(
            "SBG-DEMO-012@v003；VPR-DEMO-GU002@v001",
            "SBG-DEMO-012@v003",
        )
        self.assertTrue(any("反向引用" in item for item in errors))
        self.assertTrue(any("精确引用当前VRM" in item for item in errors))

    def test_version_rules_separate_mapping_prompt_and_rerun(self) -> None:
        self.assertTrue(validator.requires_new_vrm_version({"参考顺序"}))
        self.assertFalse(validator.requires_new_vrm_version({"Prompt正文"}))
        self.assertTrue(validator.requires_new_prompt_version({"Prompt正文"}))
        self.assertTrue(validator.requires_new_prompt_version({"平台处理方式"}))
        self.assertFalse(validator.requires_new_prompt_version({"相同输入原样再生成"}))

    def test_generation_unit_change_creates_new_identity_chain(self) -> None:
        self.assertEqual(validator.identity_decision(True), "新生成单元+新VRM+新VPR身份")
        self.assertEqual(validator.identity_decision(False), "保留身份，按内容决定版本")

    def test_external_node_rejects_submit_query_download(self) -> None:
        errors = validator.validate_external_actions(["提交生成任务", "查询生成进度", "下载视频"])
        self.assertEqual(len(errors), 3)
        self.assertEqual(validator.validate_external_actions(["交付用户手工复制", "记录轻量检查点"]), [])

    def test_simulation_must_keep_one_decision(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self._copy_surface(Path(temp))
            path = root / "skills/video-prompt-production/references/c07-simulated-prompt-task.md"
            text = path.read_text(encoding="utf-8").replace(
                "下一步：按你的决定完成",
                "现在请你决定：是否记录失败？\n\n下一步：按你的决定完成",
            )
            path.write_text(text, encoding="utf-8")
            self.assertTrue(any("一个用户决定点" in item for item in validator.validate(root)))

    def test_schema_cannot_lose_unique_purpose_field(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self._copy_surface(Path(temp))
            path = root / "skills/video-prompt-production/assets/video-prompt-reference.schema.json"
            schema = json.loads(path.read_text(encoding="utf-8"))
            schema["required"].remove("唯一用途")
            path.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            self.assertTrue(any("必填字段不完整" in item for item in validator.validate(root)))

    @staticmethod
    def _copy_surface(target: Path) -> Path:
        for relative in validator.CONTRACT_FILES:
            source = ROOT / relative
            destination = target / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(source.read_bytes())
        return target


if __name__ == "__main__":
    unittest.main()
