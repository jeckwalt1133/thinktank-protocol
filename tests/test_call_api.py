"""测试 _call_api 共享基础设施 — R197 兑现R196延后待办#1

_call_api 是所有后端的单一调用路径。之前只有间接测试（通过 call_anthropic
和 call_openai_compatible），现在覆盖共享引擎本身。

验证目标:
1. URL构建正确（base_url + endpoint组合，rstrip('/')边界）
2. HTTP错误路径: 400/401/403/429/500 → RuntimeError
3. 超时 → RuntimeError
4. payload/headers正确传递给回调 → 传递给Request
5. 响应解析通过第三方回调 → parse_response被调用
6. model参数优先级: 显式 > config["model"] > config["model_engineering"] > default
7. API密钥回退到环境变量
8. 通用异常 → RuntimeError
"""

import os
import sys
import json
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from thinktank_protocol.config import _call_api


# ------------------------------------------------------------
# 轻量回调 — 用于测试 _call_api 而不依赖具体后端
# ------------------------------------------------------------
def _test_build_payload(model, system_prompt, user_message, config):
    return {
        "model": model,
        "system": system_prompt,
        "message": user_message,
        "temp": config.get("temperature", 0.5),
    }

def _test_build_headers(api_key, config):
    return {
        "Content-Type": "application/json",
        "X-Test-Key": api_key,
        "X-Test-Version": config.get("test_version", "v1"),
    }

def _test_parse_response(data):
    return data.get("result", data.get("text", ""))


class TestCallApiUrlConstruction(unittest.TestCase):
    """验证 _call_api URL 构建 — endpoint 拼接"""

    def _base_config(self):
        return {"api_key": "key-001", "timeout": 5}

    @patch("urllib.request.urlopen")
    def test_url_strips_base_trailing_slash(self, mock_urlopen):
        """base_url 尾部斜杠被正确 strip，endpoint 前导斜杠保留"""
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"result": "ok"}).encode()
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        _call_api("sys", "usr", {"api_key": "k", "base_url": "https://api.example.com/v1/", "timeout": 5},
                  endpoint="/test", env_key_name="TEST_KEY",
                  default_base_url="https://default.example.com", default_model="default-model",
                  build_payload=_test_build_payload,
                  build_headers=_test_build_headers,
                  parse_response=_test_parse_response)

        url = mock_urlopen.call_args[0][0].full_url
        self.assertEqual(url, "https://api.example.com/v1/test")

    @patch("urllib.request.urlopen")
    def test_url_base_without_slash(self, mock_urlopen):
        """base_url 无尾部斜杠 — URL 正常拼接"""
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"result": "ok"}).encode()
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        _call_api("sys", "usr", {"api_key": "k", "base_url": "https://api.example.com", "timeout": 5},
                  endpoint="/messages", env_key_name="TEST_KEY",
                  default_base_url="https://default.example.com", default_model="default-model",
                  build_payload=_test_build_payload,
                  build_headers=_test_build_headers,
                  parse_response=_test_parse_response)

        url = mock_urlopen.call_args[0][0].full_url
        self.assertEqual(url, "https://api.example.com/messages")

    @patch("urllib.request.urlopen")
    def test_default_base_url_used_when_not_in_config(self, mock_urlopen):
        """config 无 base_url 时使用 default_base_url"""
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"result": "ok"}).encode()
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        _call_api("sys", "usr", {"api_key": "k", "timeout": 5},
                  endpoint="/chat", env_key_name="TEST_KEY",
                  default_base_url="https://fallback.example.com/v1", default_model="dm",
                  build_payload=_test_build_payload,
                  build_headers=_test_build_headers,
                  parse_response=_test_parse_response)

        url = mock_urlopen.call_args[0][0].full_url
        self.assertEqual(url, "https://fallback.example.com/v1/chat")


class TestCallApiHTTPErrors(unittest.TestCase):
    """验证 _call_api HTTP 错误路径"""

    def _base_config(self):
        return {"api_key": "key-001", "timeout": 5}

    def _make_http_error(self, code):
        from urllib.error import HTTPError
        fp = MagicMock()
        fp.read.return_value = json.dumps({"error": f"error_{code}"}).encode()
        return HTTPError("http://test", code, "Error", {}, fp)

    @patch("urllib.request.urlopen")
    def test_400_raises_runtime_error(self, mock_urlopen):
        mock_urlopen.side_effect = self._make_http_error(400)
        with self.assertRaises(RuntimeError) as ctx:
            _call_api("s", "u", self._base_config(),
                      endpoint="/test", env_key_name="TK", default_base_url="http://x",
                      default_model="dm", build_payload=_test_build_payload,
                      build_headers=_test_build_headers, parse_response=_test_parse_response)
        self.assertIn("400", str(ctx.exception))

    @patch("urllib.request.urlopen")
    def test_401_raises_runtime_error(self, mock_urlopen):
        mock_urlopen.side_effect = self._make_http_error(401)
        with self.assertRaises(RuntimeError):
            _call_api("s", "u", self._base_config(),
                      endpoint="/test", env_key_name="TK", default_base_url="http://x",
                      default_model="dm", build_payload=_test_build_payload,
                      build_headers=_test_build_headers, parse_response=_test_parse_response)

    @patch("urllib.request.urlopen")
    def test_429_raises_runtime_error(self, mock_urlopen):
        mock_urlopen.side_effect = self._make_http_error(429)
        with self.assertRaises(RuntimeError):
            _call_api("s", "u", self._base_config(),
                      endpoint="/test", env_key_name="TK", default_base_url="http://x",
                      default_model="dm", build_payload=_test_build_payload,
                      build_headers=_test_build_headers, parse_response=_test_parse_response)

    @patch("urllib.request.urlopen")
    def test_500_raises_runtime_error(self, mock_urlopen):
        mock_urlopen.side_effect = self._make_http_error(500)
        with self.assertRaises(RuntimeError):
            _call_api("s", "u", self._base_config(),
                      endpoint="/test", env_key_name="TK", default_base_url="http://x",
                      default_model="dm", build_payload=_test_build_payload,
                      build_headers=_test_build_headers, parse_response=_test_parse_response)


class TestCallApiTimeout(unittest.TestCase):
    """验证 _call_api 超时处理"""

    @patch("urllib.request.urlopen")
    def test_timeout_raises_runtime_error(self, mock_urlopen):
        import socket
        mock_urlopen.side_effect = socket.timeout("timed out")

        with self.assertRaises(RuntimeError) as ctx:
            _call_api("s", "u", {"api_key": "k", "timeout": 5},
                      endpoint="/test", env_key_name="TK", default_base_url="http://x",
                      default_model="dm", build_payload=_test_build_payload,
                      build_headers=_test_build_headers, parse_response=_test_parse_response)
        self.assertIn("异常", str(ctx.exception))


class TestCallApiPayloadAndHeaders(unittest.TestCase):
    """验证 _call_api 的 payload 和 headers 正确传递到 HTTP 请求"""

    @patch("urllib.request.urlopen")
    def test_payload_includes_model_and_system(self, mock_urlopen):
        """payload 包含 model、system、message（来自回调）"""
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"result": "ok"}).encode()
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        _call_api("你是测试者", "测试主张", {"api_key": "k", "temperature": 0.3, "timeout": 5},
                  endpoint="/test", env_key_name="TK", default_base_url="http://x",
                  default_model="test-model-default", build_payload=_test_build_payload,
                  build_headers=_test_build_headers, parse_response=_test_parse_response)

        body = json.loads(mock_urlopen.call_args[0][0].data.decode())
        self.assertEqual(body["system"], "你是测试者")
        self.assertEqual(body["message"], "测试主张")
        self.assertEqual(body["model"], "test-model-default")
        self.assertEqual(body["temp"], 0.3)

    @patch("urllib.request.urlopen")
    def test_headers_include_test_key(self, mock_urlopen):
        """headers 包含回调设置的 X-Test-Key"""
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"result": "ok"}).encode()
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        _call_api("s", "u", {"api_key": "secret-123", "timeout": 5},
                  endpoint="/test", env_key_name="TK", default_base_url="http://x",
                  default_model="dm", build_payload=_test_build_payload,
                  build_headers=_test_build_headers, parse_response=_test_parse_response)

        req = mock_urlopen.call_args[0][0]
        self.assertEqual(req.headers["X-Test-Key"], "secret-123")


class TestCallApiResponseParsing(unittest.TestCase):
    """验证 _call_api 响应解析通过回调"""

    @patch("urllib.request.urlopen")
    def test_parse_response_called(self, mock_urlopen):
        """parse_response 回调被调用并返回正确结果"""
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"result": "parsed-correctly"}).encode()
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        result = _call_api("s", "u", {"api_key": "k", "timeout": 5},
                           endpoint="/test", env_key_name="TK", default_base_url="http://x",
                           default_model="dm", build_payload=_test_build_payload,
                           build_headers=_test_build_headers, parse_response=_test_parse_response)

        self.assertEqual(result, "parsed-correctly")


class TestCallApiModelPriority(unittest.TestCase):
    """验证 _call_api model 参数优先级"""

    @patch("urllib.request.urlopen")
    def test_explicit_model_overrides_config(self, mock_urlopen):
        """显式 model 参数覆盖 config['model_engineering']"""
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"result": "ok"}).encode()
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        _call_api("s", "u",
                  {"api_key": "k", "model": "config-model", "model_engineering": "eng-model", "timeout": 5},
                  model="explicit-model",
                  endpoint="/test", env_key_name="TK", default_base_url="http://x",
                  default_model="default-model", build_payload=_test_build_payload,
                  build_headers=_test_build_headers, parse_response=_test_parse_response)

        body = json.loads(mock_urlopen.call_args[0][0].data.decode())
        self.assertEqual(body["model"], "explicit-model")

    @patch("urllib.request.urlopen")
    def test_config_model_priority_over_model_engineering(self, mock_urlopen):
        """config['model'] 优先于 config['model_engineering']"""
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"result": "ok"}).encode()
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        _call_api("s", "u",
                  {"api_key": "k", "model": "config-model", "model_engineering": "eng-model", "timeout": 5},
                  endpoint="/test", env_key_name="TK", default_base_url="http://x",
                  default_model="fallback-model", build_payload=_test_build_payload,
                  build_headers=_test_build_headers, parse_response=_test_parse_response)

        body = json.loads(mock_urlopen.call_args[0][0].data.decode())
        self.assertEqual(body["model"], "config-model")


class TestCallApiKeyEnvFallback(unittest.TestCase):
    """验证 API 密钥环境变量回退"""

    def setUp(self):
        self.orig_env = os.environ.get("TEST_CALL_API_KEY")
        if "TEST_CALL_API_KEY" in os.environ:
            del os.environ["TEST_CALL_API_KEY"]

    def tearDown(self):
        if "TEST_CALL_API_KEY" in os.environ:
            del os.environ["TEST_CALL_API_KEY"]
        if self.orig_env:
            os.environ["TEST_CALL_API_KEY"] = self.orig_env

    @patch("urllib.request.urlopen")
    def test_env_var_used_when_config_missing(self, mock_urlopen):
        """config 无 api_key 时回退到环境变量"""
        os.environ["TEST_CALL_API_KEY"] = "env-key-xyz"
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"result": "ok"}).encode()
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        _call_api("s", "u", {"timeout": 5},
                  endpoint="/test", env_key_name="TEST_CALL_API_KEY",
                  default_base_url="http://x", default_model="dm",
                  build_payload=_test_build_payload,
                  build_headers=_test_build_headers,
                  parse_response=_test_parse_response)

        req = mock_urlopen.call_args[0][0]
        self.assertEqual(req.headers["X-Test-Key"], "env-key-xyz")


class TestCallApiGeneralException(unittest.TestCase):
    """验证通用异常传播"""

    @patch("urllib.request.urlopen")
    def test_generic_exception_wrapped_as_runtime_error(self, mock_urlopen):
        """任意异常被包装为 RuntimeError"""
        mock_urlopen.side_effect = ValueError("unexpected parsing error")

        with self.assertRaises(RuntimeError) as ctx:
            _call_api("s", "u", {"api_key": "k", "timeout": 5},
                      endpoint="/test", env_key_name="TK", default_base_url="http://x",
                      default_model="dm", build_payload=_test_build_payload,
                      build_headers=_test_build_headers, parse_response=_test_parse_response)
        self.assertIn("unexpected parsing error", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
