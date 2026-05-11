"""测试双批判引擎核心 — 验证 mock 模式行为 + 免疫装置透明化

验证目标:
1. DualCritiqueEngine 正确执行双批判
2. _parse_critique 正确解析批判文本
3. _compute_zero_overlap 在 mock 模式下诚实报告
4. Mock 免疫装置已被打破 — 零重叠率不再是恒定的 1.0
5. Session 历史正确记录
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from thinktank_protocol.core import DualCritiqueEngine, CritiqueResult


class TestMockModeCritique(unittest.TestCase):
    """验证 mock 模式下的双批判行为"""

    def setUp(self):
        self.engine = DualCritiqueEngine()

    def test_critique_returns_result_with_correct_structure(self):
        """双批判返回结构完整的 CritiqueResult"""
        result = self.engine.critique("敏捷开发优于瀑布开发")
        self.assertIsInstance(result, CritiqueResult)
        self.assertIsNotNone(result.claim)
        self.assertIsNotNone(result.session_hash)
        self.assertIsNotNone(result.timestamp)

    def test_both_critiques_produced(self):
        """两个批判者均产出批判点"""
        result = self.engine.critique("测试主张")
        self.assertGreater(len(result.engineering_critique), 0,
                           "工程批判者应产出≥0个批判点")
        self.assertGreater(len(result.ontological_critique), 0,
                           "本体批判者应产出≥0个批判点")

    def test_zero_overlap_rate_in_valid_range(self):
        """零重叠率在 [0, 1] 范围内"""
        result = self.engine.critique("测试主张")
        self.assertGreaterEqual(result.zero_overlap_rate, 0.0)
        self.assertLessEqual(result.zero_overlap_rate, 1.0)

    def test_zero_overlap_not_always_one(self):
        """Mock免疫装置已打破: 零重叠率不总是 1.0"""
        claims = [
            "敏捷开发优于瀑布开发",
            "AI安全研究需要全球协作",
            "量子的纠缠态可用于计算",
            "自由意志是一种幻觉",
            "语言决定了思维的边界",
        ]
        rates = []
        for claim in claims:
            result = self.engine.critique(claim)
            rates.append(result.zero_overlap_rate)

        # 在不同主张间零重叠率应有所变化
        unique_rates = set(rates)
        self.assertGreater(len(unique_rates), 1,
                           f"Mock免疫装置未打破: 所有5条不同主张的零重叠率完全相同 ({rates[0]})")

        # 至少有一条不是精确的 1.0
        has_non_one = any(r < 1.0 for r in rates)
        self.assertTrue(has_non_one,
                        f"Mock免疫装置未打破: 所有5条主张零重叠率均为1.0: {rates}")

    def test_different_claims_produce_different_critique_text(self):
        """不同主张应产生不同的批判文本（非完全预置）"""
        r1 = self.engine.critique("Python是最好的编程语言")
        r2 = self.engine.critique("Rust在系统编程中更优")

        e1_content = " ".join(p.content for p in r1.engineering_critique)
        e2_content = " ".join(p.content for p in r2.engineering_critique)
        self.assertNotEqual(e1_content, e2_content,
                            "不同主张产生完全相同预置文本 — Mock免疫装置未破")


class TestCritiqueParsing(unittest.TestCase):
    """验证批判文本解析"""

    def setUp(self):
        self.engine = DualCritiqueEngine()

    def test_parse_severity_markers(self):
        """正确解析 ★ / 严重 / 一般 严重性标记"""
        raw = """★ 工程/系统架构: 致命缺陷
严重 测量学/信号检测: 严重缺陷
一般 工程/信息架构: 一般问题"""
        points = self.engine._parse_critique(raw, "工程批判者")
        severities = [p.severity for p in points]
        self.assertEqual(severities, ["★", "严重", "一般"])

    def test_parse_layer_detection(self):
        """正确检测已知层次"""
        raw = """严重 测量学/可重复性: 无法复现
★ 本体论/免疫装置: 自证结构
一般 工程/系统架构: 缺少接口"""
        points = self.engine._parse_critique(raw, "测试")
        # 所有3行因包含已知层次关键词被正确分类
        layers = [p.layer for p in points]
        self.assertIn("测量学", layers[0])
        self.assertIn("本体论", layers[1])
        self.assertIn("工程", layers[2])

    def test_parse_empty_input(self):
        """空输入返回空列表"""
        points = self.engine._parse_critique("", "测试")
        self.assertEqual(len(points), 0)


class TestSessionManagement(unittest.TestCase):
    """验证会话管理和导出"""

    def setUp(self):
        self.engine = DualCritiqueEngine()

    def test_round_history_accumulates(self):
        """轮次历史正确累积"""
        self.engine.critique("第一轮")
        self.engine.critique("第二轮")
        self.assertEqual(len(self.engine.round_history), 2)

    def test_history_summary(self):
        """历史摘要结构正确"""
        self.engine.critique("测试")
        summary = self.engine.get_history_summary()
        self.assertEqual(summary["rounds"], 1)
        self.assertIn("avg_zero_overlap", summary)
        self.assertIn("total_engineering_points", summary)
        self.assertIn("total_ontological_points", summary)


if __name__ == "__main__":
    unittest.main()
