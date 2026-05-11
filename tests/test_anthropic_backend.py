"""测试 Anthropic Messages API 后端 — 验证 R193 call_anthropic 函数

验证目标:
1. call_anthropic() 成功路径响应解析 (content[].text 提取)
2. HTTP 错误路径: 401/403/500 → RuntimeError
3. 超时 → RuntimeError
4. 畸形响应: 空 content / 无 text 块 → RuntimeError
5. model 参数优先级
6. create_dual_api_critique backend="anthropic" 路由
"""

import os
import sys
import json
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from thinktank_protocol.config import (
    call_anthropic,
    create_dual_api_critique,
)


def _make_anthropic_mock(text_content: str) -> MagicMock:
    """构造模拟的 Anthropic Messages API 成功响应"""
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps({
        "id": "msg_01A",
        "type": "message",
        "role": "assistant",
        "content": [{"type": "text", "text": text_content}],
        "model": "claude-sonnet-4-20250514",
        "stop_reason": "end_turn",
    }).encode("utf-8")
    return mock_resp


class TestAnthropicSuccessPath(unittest.TestCase):
    """验证 call_anthropic 成功路径 — 响应解析"""

    def setUp(self):
        self.config = {
            "api_key": "test-key",
            "base_url": "https://api.anthropic.com/v1",
            "model_engineering": "claude-sonnet-4-20250514",
            "temperature": 0.7,
            "max_tokens": 2048,
            "timeout": 10,
        }

    @patch("urllib.request.urlopen")
    def test_successful_call_returns_text(self, mock_urlopen):
        """成功调用返回 content[0].text"""
        mock_resp = _make_anthropic_mock("批判内容：该主张缺乏可操作化定义。")
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        result = call_anthropic("system prompt", "user message", self.config)

        self.assertIn("缺乏可操作化定义", result)
        self.assertIsInstance(result, str)

    @patch("urllib.request.urlopen")
    def test_request_uses_correct_headers(self, mock_urlopen):
        """请求头包含 x-api-key 和 anthropic-version"""
        mock_resp = _make_anthropic_mock("ok")
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        call_anthropic("system", "user", self.config)

        req = mock_urlopen.call_args[0][0]
        self.assertEqual(req.headers["Content-type"], "application/json")
        self.assertEqual(req.headers["X-api-key"], "test-key")
        self.assertIn("anthropic-version", req.headers)

    @patch("urllib.request.urlopen")
    def test_payload_includes_system_and_messages(self, mock_urlopen):
        """payload 包含 system 顶层字段和 messages 数组"""
        mock_resp = _make_anthropic_mock("ok")
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        call_anthropic("你是一个批判者", "主张：X", self.config)

        body = json.loads(mock_urlopen.call_args[0][0].data.decode("utf-8"))
        self.assertEqual(body["system"], "你是一个批判者")
        self.assertEqual(body["messages"][0]["role"], "user")
        self.assertEqual(body["messages"][0]["content"], "主张：X")


class TestAnthropicHTTPErrors(unittest.TestCase):
    """验证 call_anthropic HTTP 错误路径"""

    def setUp(self):
        self.config = {
            "api_key": "test-key",
            "timeout": 10,
        }

    def _make_http_error(self, code: int):
        """构造模拟 HTTPError"""
        from urllib.error import HTTPError
        fp = MagicMock()
        fp.read.return_value = json.dumps({
            "error": {"type": "authentication_error", "message": "invalid key"}
        }).encode("utf-8")
        return HTTPError(
            "https://api.anthropic.com/v1/messages", code,
            "Error", {}, fp
        )

    @patch("urllib.request.urlopen")
    def test_401_raises_runtime_error(self, mock_urlopen):
        """401 未授权 → RuntimeError"""
        mock_urlopen.side_effect = self._make_http_error(401)

        with self.assertRaises(RuntimeError) as ctx:
            call_anthropic("system", "user", self.config)
        self.assertIn("401", str(ctx.exception))

    @patch("urllib.request.urlopen")
    def test_403_raises_runtime_error(self, mock_urlopen):
        """403 禁止 → RuntimeError"""
        mock_urlopen.side_effect = self._make_http_error(403)

        with self.assertRaises(RuntimeError) as ctx:
            call_anthropic("system", "user", self.config)
        self.assertIn("403", str(ctx.exception))

    @patch("urllib.request.urlopen")
    def test_500_raises_runtime_error(self, mock_urlopen):
        """500 服务器错误 → RuntimeError"""
        mock_urlopen.side_effect = self._make_http_error(500)

        with self.assertRaises(RuntimeError) as ctx:
            call_anthropic("system", "user", self.config)
        self.assertIn("500", str(ctx.exception))


class TestAnthropicEdgeCases(unittest.TestCase):
    """验证 call_anthropic 边界条件"""

    def setUp(self):
        self.config = {
            "api_key": "test-key",
            "timeout": 10,
        }

    @patch("urllib.request.urlopen")
    def test_timeout_raises_runtime_error(self, mock_urlopen):
        """超时 → RuntimeError"""
        import socket
        mock_urlopen.side_effect = socket.timeout("timed out")

        with self.assertRaises(RuntimeError) as ctx:
            call_anthropic("system", "user", self.config)
        self.assertIn("异常", str(ctx.exception))

    @patch("urllib.request.urlopen")
    def test_empty_content_raises_runtime_error(self, mock_urlopen):
        """空 content 数组 → RuntimeError"""
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "id": "msg_01B",
            "type": "message",
            "role": "assistant",
            "content": [],
            "model": "claude-sonnet-4-20250514",
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        with self.assertRaises(RuntimeError) as ctx:
            call_anthropic("system", "user", self.config)
        self.assertIn("无文本块", str(ctx.exception))

    @patch("urllib.request.urlopen")
    def test_no_text_blocks_raises_runtime_error(self, mock_urlopen):
        """content 无 text 类型块 → RuntimeError"""
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "id": "msg_01C",
            "type": "message",
            "role": "assistant",
            "content": [{"type": "tool_use", "id": "tu_01", "name": "get_weather"}],
            "model": "claude-sonnet-4-20250514",
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        with self.assertRaises(RuntimeError) as ctx:
            call_anthropic("system", "user", self.config)
        self.assertIn("无文本块", str(ctx.exception))


class TestAnthropicModelPriority(unittest.TestCase):
    """验证 call_anthropic model 参数优先级"""

    def setUp(self):
        self.config = {
            "api_key": "test-key",
            "model_engineering": "claude-sonnet-4-20250514",
            "timeout": 10,
        }

    @patch("urllib.request.urlopen")
    def test_explicit_model_overrides_config(self, mock_urlopen):
        """显式 model 参数优先于 config['model'] 和 config['model_engineering']"""
        mock_resp = _make_anthropic_mock("ok")
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        call_anthropic("sys", "usr", self.config, model="claude-opus-4-20250514")

        body = json.loads(mock_urlopen.call_args[0][0].data.decode("utf-8"))
        self.assertEqual(body["model"], "claude-opus-4-20250514")


class TestAnthropicDualApiRouting(unittest.TestCase):
    """验证 backend="anthropic" 时 create_dual_api_critique 路由"""

    def setUp(self):
        self.config = {
            "backend": "anthropic",
            "api_key": "test-key",
            "model_engineering": "claude-sonnet-4-20250514",
            "model_ontological": "claude-opus-4-20250514",
            "temperature": 0.7,
            "max_tokens": 2048,
            "timeout": 10,
        }

    @patch("urllib.request.urlopen")
    def test_backend_anthropic_routes_to_call_anthropic(self, mock_urlopen):
        """backend='anthropic' 时回调使用 Anthropic Messages API 格式"""
        mock_resp = _make_anthropic_mock("engineering critique")
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        eng_cb, onto_cb = create_dual_api_critique(self.config)
        result = eng_cb("system", "test claim", "")

        # 验证使用了 Messages API 端点
        url = mock_urlopen.call_args[0][0].full_url
        self.assertIn("/messages", url)
        self.assertEqual(result, "engineering critique")

    @patch("urllib.request.urlopen")
    def test_two_models_differ_with_anthropic_backend(self, mock_urlopen):
        """两个回调使用不同 Anthropic 模型"""
        models_used = []

        def side_effect(req, *args, **kwargs):
            body = json.loads(req.data.decode("utf-8"))
            models_used.append(body["model"])
            mock_resp = _make_anthropic_mock("critique")
            mock_ctx = MagicMock()
            mock_ctx.__enter__.return_value = mock_resp
            return mock_ctx

        mock_urlopen.side_effect = side_effect

        eng_cb, onto_cb = create_dual_api_critique(self.config)
        eng_cb("sys", "claim", "")
        onto_cb("sys", "claim", "")

        self.assertEqual(len(models_used), 2)
        self.assertNotEqual(models_used[0], models_used[1],
                            "两个回调必须使用不同模型")


if __name__ == "__main__":
    unittest.main()
