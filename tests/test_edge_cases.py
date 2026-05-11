"""测试边缘用例 — 错误路径 / 边界条件 / I/O 完整性

R189: 桥的结构加固 — 测试不再只覆盖理想路径。
验证在边界输入、HTTP错误、文件I/O场景下的行为。

覆盖范围:
- 边界条件: 空输入 / 超长输入 / Unicode / 特殊字符
- 错误路径: HTTP 401/403/500/超时 / 格式错误响应 / 配置不完整
- I/O完整性: JSON导出→导入往返 / 文件不存在 / 路径权限
"""

import os
import sys
import json
import tempfile
import unittest
from unittest.mock import patch, MagicMock
from io import StringIO

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from thinktank_protocol.core import DualCritiqueEngine, CritiqueResult, CritiquePoint
from thinktank_protocol.config import (
    call_openai_compatible,
    create_dual_api_critique,
    load_config,
)


# ============================================================
# 边界条件测试
# ============================================================
class TestBoundaryConditions(unittest.TestCase):
    """验证引擎在边界输入下的行为"""

    def setUp(self):
        self.engine = DualCritiqueEngine()

    def test_empty_claim(self):
        """空主张不会崩溃 — 返回结果"""
        result = self.engine.critique("")
        self.assertIsInstance(result, CritiqueResult)
        self.assertIsNotNone(result.claim)

    def test_single_char_claim(self):
        """单字符主张"""
        result = self.engine.critique("A")
        self.assertIsInstance(result, CritiqueResult)

    def test_very_long_claim(self):
        """超长主张 (10KB) — 不崩溃"""
        long_claim = "长" * 10240
        result = self.engine.critique(long_claim)
        self.assertIsInstance(result, CritiqueResult)

    def test_unicode_multilingual_claim(self):
        """多语言Unicode主张 — 编码不破坏"""
        claim = "智能度量 🤖 | mesurer l'intelligence |  인공지능 측정 | قياس الذكاء | измерение интеллекта"
        result = self.engine.critique(claim)
        self.assertIsInstance(result, CritiqueResult)

    def test_claim_with_only_whitespace(self):
        """仅空白字符主张"""
        result = self.engine.critique("   \n\t  ")
        self.assertIsInstance(result, CritiqueResult)

    def test_claim_with_special_chars(self):
        """特殊字符主张 — 不破坏解析"""
        claim = "test<>\"'&`|\\/;{}$%#@!"
        result = self.engine.critique(claim)
        self.assertIsInstance(result, CritiqueResult)

    def test_repeated_identical_claims(self):
        """重复相同主张 — 应产生不同session_hash"""
        r1 = self.engine.critique("测试")
        r2 = self.engine.critique("测试")
        self.assertNotEqual(r1.session_hash, r2.session_hash,
                            "相同主张的不同调用应有不同session_hash (时间戳参与哈希)")

    def test_context_long_string(self):
        """超长context不崩溃"""
        long_ctx = "上下文" * 5000
        result = self.engine.critique("测试", context=long_ctx)
        self.assertIsInstance(result, CritiqueResult)


# ============================================================
# HTTP 错误路径测试 — Config模块
# ============================================================
class TestHttpErrorPaths(unittest.TestCase):
    """验证API调用器在HTTP错误下的行为"""

    def setUp(self):
        self.config = {
            "api_key": "test-key",
            "base_url": "https://test-api.example.com/v1",
            "model_engineering": "qwen-plus",
            "temperature": 0.7,
            "max_tokens": 2048,
            "timeout": 5,
        }

    def test_http_401_unauthorized_raises(self):
        """HTTP 401 应抛出 RuntimeError"""
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = __import__("urllib.error").error.HTTPError(
                url="https://test", code=401, msg="Unauthorized",
                hdrs={}, fp=StringIO('{"error":"invalid api key"}')
            )
            with self.assertRaises(RuntimeError) as ctx:
                call_openai_compatible("sys", "user", self.config)
            self.assertIn("401", str(ctx.exception))

    def test_http_403_forbidden_raises(self):
        """HTTP 403 应抛出 RuntimeError"""
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = __import__("urllib.error").error.HTTPError(
                url="https://test", code=403, msg="Forbidden",
                hdrs={}, fp=StringIO("{}")
            )
            with self.assertRaises(RuntimeError):
                call_openai_compatible("sys", "user", self.config)

    def test_http_500_server_error_raises(self):
        """HTTP 500 应抛出 RuntimeError"""
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = __import__("urllib.error").error.HTTPError(
                url="https://test", code=500, msg="Internal Server Error",
                hdrs={}, fp=StringIO("{}")
            )
            with self.assertRaises(RuntimeError):
                call_openai_compatible("sys", "user", self.config)

    def test_http_timeout_raises(self):
        """超时应抛出 RuntimeError"""
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = TimeoutError("connection timed out")
            with self.assertRaises(RuntimeError) as ctx:
                call_openai_compatible("sys", "user", self.config)
            self.assertIn("超时", str(ctx.exception).lower() or
                          "timeout", str(ctx.exception).lower() or "API")

    def test_network_failure_raises(self):
        """网络不可达应抛出 RuntimeError"""
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = OSError("network unreachable")
            with self.assertRaises(RuntimeError):
                call_openai_compatible("sys", "user", self.config)

    def test_malformed_json_response_raises(self):
        """格式错误的JSON响应应抛出异常"""
        import urllib.error
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = b"this is not json{{{"
            mock_ctx = MagicMock()
            mock_ctx.__enter__.return_value = mock_resp
            mock_urlopen.return_value = mock_ctx
            with self.assertRaises((json.JSONDecodeError, KeyError, RuntimeError)):
                call_openai_compatible("sys", "user", self.config)

    def test_empty_response_body(self):
        """空响应体应抛出异常"""
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = b""
            mock_ctx = MagicMock()
            mock_ctx.__enter__.return_value = mock_resp
            mock_urlopen.return_value = mock_ctx
            with self.assertRaises((json.JSONDecodeError, RuntimeError)):
                call_openai_compatible("sys", "user", self.config)


# ============================================================
# I/O 完整性测试
# ============================================================
class TestIOIntegrity(unittest.TestCase):
    """验证文件I/O操作的完整性"""

    def setUp(self):
        self.engine = DualCritiqueEngine()
        self.engine.critique("测试主张A")
        self.engine.critique("测试主张B — 不同内容")

    def test_export_to_json_creates_file(self):
        """导出创建 JSON 文件"""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            filepath = f.name
        try:
            self.engine.export_session(filepath)
            self.assertTrue(os.path.exists(filepath))
            self.assertTrue(os.path.getsize(filepath) > 0)
        finally:
            os.unlink(filepath)

    def test_export_json_is_valid_json(self):
        """导出内容为有效 JSON"""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            filepath = f.name
        try:
            self.engine.export_session(filepath)
            with open(filepath, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            self.assertIsInstance(data, list)
        finally:
            os.unlink(filepath)

    def test_export_json_roundtrip(self):
        """导出→读取→结构完整性验证"""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            filepath = f.name
        try:
            self.engine.export_session(filepath)
            with open(filepath, "r", encoding="utf-8") as fh:
                data = json.load(fh)

            self.assertEqual(len(data), 2, "应导出2轮会话")
            for entry in data:
                self.assertIn("claim", entry)
                self.assertIn("timestamp", entry)
                self.assertIn("eng_points", entry)
                self.assertIn("ont_points", entry)
                self.assertIn("zero_overlap_rate", entry)
                self.assertIn("meta_verdict", entry)
                self.assertIsInstance(entry["zero_overlap_rate"], float)
        finally:
            os.unlink(filepath)

    def test_export_empty_session(self):
        """空会话导出不崩溃"""
        empty_engine = DualCritiqueEngine()
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            filepath = f.name
        try:
            empty_engine.export_session(filepath)
            with open(filepath, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            self.assertEqual(len(data), 0, "空会话应导出空列表")
        finally:
            os.unlink(filepath)

    def test_export_unicode_claim_preserves_encoding(self):
        """Unicode主张经JSON导出后编码不丢失"""
        engine = DualCritiqueEngine()
        unicode_claim = "智能是向量🧠 — 衡量认知温差Δ"
        engine.critique(unicode_claim)

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            filepath = f.name
        try:
            engine.export_session(filepath)
            with open(filepath, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            self.assertEqual(data[0]["claim"], unicode_claim,
                             "Unicode主张经JSON导出后应无损")
        finally:
            os.unlink(filepath)

    def test_export_to_nonexistent_directory(self):
        """导出到不存在的目录应抛出 FileNotFoundError"""
        with self.assertRaises((FileNotFoundError, OSError)):
            self.engine.export_session("/nonexistent_path_xyz123/test.json")

    def test_config_load_nonexistent_file(self):
        """配置文件不存在时不崩溃 — 返回默认配置"""
        config = load_config("/nonexistent_config_file_789.json")
        self.assertEqual(config["backend"], "openai")
        self.assertEqual(config["model_engineering"], "qwen-plus")


# ============================================================
# 单点输入测试 — 零批判点的边界行为
# ============================================================
class TestSinglePointEdgeCase(unittest.TestCase):
    """验证仅有单个批判点时的计算行为"""

    def setUp(self):
        self.engine = DualCritiqueEngine()

    def test_single_eng_point_single_ont_point(self):
        """单点vs单点: _compute_zero_overlap 不崩溃"""
        ep = [CritiquePoint(id="E1", severity="★",
                            layer="工程/系统架构", content="测试", source="eng")]
        op = [CritiquePoint(id="O1", severity="★",
                            layer="本体论/免疫装置", content="测试", source="ont")]
        rate, analysis = self.engine._compute_zero_overlap(ep, op)
        self.assertIsInstance(rate, float)
        self.assertIsInstance(analysis, str)

    def test_empty_eng_points(self):
        """工程批判者零产出"""
        op = [CritiquePoint(id="O1", severity="严重",
                            layer="本体论/免疫装置", content="测试", source="ont")]
        rate, _ = self.engine._compute_zero_overlap([], op)
        self.assertEqual(rate, 1.0, "一方零产出时零重叠率应为1.0")

    def test_empty_ont_points(self):
        """本体批判者零产出"""
        ep = [CritiquePoint(id="E1", severity="严重",
                            layer="工程/系统架构", content="测试", source="eng")]
        rate, _ = self.engine._compute_zero_overlap(ep, [])
        self.assertEqual(rate, 1.0, "一方零产出时零重叠率应为1.0")

    def test_both_empty(self):
        """双方零产出"""
        rate, _ = self.engine._compute_zero_overlap([], [])
        self.assertEqual(rate, 1.0)

    def test_identical_content_points(self):
        """相同内容但不同来源 — 关键词语义重叠应被检测"""
        p1 = [CritiquePoint(id="E1", severity="★",
                            layer="测量学/信号检测",
                            content="测试的度量标准缺乏操作化定义",
                            source="eng")]
        p2 = [CritiquePoint(id="O1", severity="★",
                            layer="制度哲学/存在论",
                            content="测试的度量标准缺乏操作化定义",
                            source="ont")]
        rate, analysis = self.engine._compute_zero_overlap(p1, p2)
        # 内容相同 → 关键词高重叠 → 零重叠率应低于0.5
        self.assertLess(rate, 0.5,
                        f"相同内容应产生显著重叠, 实际: {rate}")


# ============================================================
# API适配器错误路径
# ============================================================
class TestApiAdapterErrorPaths(unittest.TestCase):
    """验证 create_dual_api_critique 在配置不完整时的行为"""

    def test_empty_api_key_in_config(self):
        """空 api_key — 适配器创建不崩溃(错误在API调用时抛出)"""
        config = {
            "api_key": "",
            "base_url": "https://test.example.com/v1",
            "model_engineering": "qwen-plus",
            "model_ontological": "glm-4-plus",
        }
        eng_cb, ont_cb = create_dual_api_critique(config)
        self.assertTrue(callable(eng_cb))
        self.assertTrue(callable(ont_cb))

    def test_missing_models_in_config(self):
        """缺失 model 键 — 回退到 gpt-4"""
        config = {
            "api_key": "test-key",
            "base_url": "https://test.example.com/v1",
        }
        eng_cb, ont_cb = create_dual_api_critique(config)
        self.assertTrue(callable(eng_cb))
        self.assertTrue(callable(ont_cb))

    def test_trailing_slash_in_base_url(self):
        """base_url 以 / 结尾 — call_openai_compatible 处理正确"""
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps({
                "choices": [{"message": {"content": "ok"}}]
            }).encode("utf-8")
            mock_ctx = MagicMock()
            mock_ctx.__enter__.return_value = mock_resp
            mock_urlopen.return_value = mock_ctx

            config_with_trailing = {**self._base_config(),
                                    "base_url": "https://api.example.com/v1/"}
            call_openai_compatible("sys", "user", config_with_trailing)

            # 验证URL不含双斜杠
            call_args = mock_urlopen.call_args[0][0]
            self.assertNotIn("v1//chat", call_args.full_url)

    def test_no_trailing_slash_in_base_url(self):
        """base_url 不以 / 结尾 — 同样正确处理"""
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps({
                "choices": [{"message": {"content": "ok"}}]
            }).encode("utf-8")
            mock_ctx = MagicMock()
            mock_ctx.__enter__.return_value = mock_resp
            mock_urlopen.return_value = mock_ctx

            config_no_trailing = {**self._base_config(),
                                  "base_url": "https://api.example.com/v1"}
            call_openai_compatible("sys", "user", config_no_trailing)
            call_args = mock_urlopen.call_args[0][0]
            # URL末尾应为 /chat/completions
            self.assertTrue(call_args.full_url.endswith("/chat/completions"))

    @staticmethod
    def _base_config():
        return {
            "api_key": "test-key",
            "base_url": "https://api.example.com/v1",
            "model_engineering": "qwen-plus",
            "temperature": 0.7,
            "max_tokens": 2048,
            "timeout": 5,
        }


if __name__ == "__main__":
    unittest.main()
