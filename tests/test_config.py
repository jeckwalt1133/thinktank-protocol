"""测试 API 配置模块 — 验证 R186 双模型路由修复

验证目标:
1. call_openai_compatible() model 参数优先级正确
2. create_dual_api_critique() 两个回调使用不同模型
3. load_config() 环境变量覆盖正确
"""

import os
import sys
import json
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from thinktank_protocol.config import (
    call_openai_compatible,
    create_dual_api_critique,
    load_config,
    CONFIG_TEMPLATE,
)


class TestModelParameterPriority(unittest.TestCase):
    """验证 call_openai_compatible 的 model 参数优先级"""

    def setUp(self):
        self.config = {
            "api_key": "test-key",
            "base_url": "https://test-api.example.com/v1",
            "model_engineering": "qwen-plus",
            "temperature": 0.7,
            "max_tokens": 2048,
            "timeout": 10,
        }

    @patch("urllib.request.urlopen")
    def test_explicit_model_overrides_all(self, mock_urlopen):
        """显式 model 参数优先于 config 中所有 model 键"""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "choices": [{"message": {"content": "test"}}]
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        # 显式传入 model="glm-4-plus"
        call_openai_compatible(
            "system", "user", self.config, model="glm-4-plus"
        )

        # 验证请求体中的 model 字段
        call_args = mock_urlopen.call_args[0][0]
        body = json.loads(call_args.data.decode("utf-8"))
        self.assertEqual(body["model"], "glm-4-plus",
                         "显式 model 参数应优先于 config 中所有 model 键")

    @patch("urllib.request.urlopen")
    def test_config_model_key_takes_second_priority(self, mock_urlopen):
        """config['model'] 优先于 config['model_engineering']"""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "choices": [{"message": {"content": "test"}}]
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        config_with_model = {**self.config, "model": "custom-model-v2"}
        call_openai_compatible("system", "user", config_with_model)

        call_args = mock_urlopen.call_args[0][0]
        body = json.loads(call_args.data.decode("utf-8"))
        self.assertEqual(body["model"], "custom-model-v2",
                         "config['model'] 应优先于 config['model_engineering']")

    @patch("urllib.request.urlopen")
    def test_fallback_to_model_engineering(self, mock_urlopen):
        """无显式 model 且无 config['model'] 时回退到 config['model_engineering']"""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "choices": [{"message": {"content": "test"}}]
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        call_openai_compatible("system", "user", self.config)

        call_args = mock_urlopen.call_args[0][0]
        body = json.loads(call_args.data.decode("utf-8"))
        self.assertEqual(body["model"], "qwen-plus",
                         "应回退到 config['model_engineering']")


class TestDualApiCritiqueRouting(unittest.TestCase):
    """验证 create_dual_api_critique 两个回调使用不同模型"""

    def setUp(self):
        self.config = {
            "api_key": "test-key",
            "base_url": "https://test-api.example.com/v1",
            "model_engineering": "qwen-plus",
            "model_ontological": "glm-4-plus",
            "temperature": 0.7,
            "max_tokens": 2048,
            "timeout": 10,
        }

    @patch("urllib.request.urlopen")
    def test_engine_callback_uses_engineering_model(self, mock_urlopen):
        """工程回调实际使用 model_engineering"""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "choices": [{"message": {"content": "engineering critique"}}]
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        eng_cb, onto_cb = create_dual_api_critique(self.config)
        result = eng_cb("system", "test claim", "")

        body = json.loads(mock_urlopen.call_args[0][0].data.decode("utf-8"))
        self.assertEqual(body["model"], "qwen-plus",
                         "工程回调应使用 model_engineering=qwen-plus")
        self.assertEqual(result, "engineering critique")

    @patch("urllib.request.urlopen")
    def test_onto_callback_uses_ontological_model(self, mock_urlopen):
        """本体回调实际使用 model_ontological"""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "choices": [{"message": {"content": "ontological critique"}}]
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        eng_cb, onto_cb = create_dual_api_critique(self.config)
        result = onto_cb("system", "test claim", "")

        body = json.loads(mock_urlopen.call_args[0][0].data.decode("utf-8"))
        self.assertEqual(body["model"], "glm-4-plus",
                         "本体回调应使用 model_ontological=glm-4-plus")
        self.assertEqual(result, "ontological critique")

    @patch("urllib.request.urlopen")
    def test_two_callbacks_use_different_models(self, mock_urlopen):
        """两个回调实际使用不同模型 — R186核心修复验证"""
        models_used = []

        # urlopen 以 with urlopen(req) as resp: 形式被调用
        # 每次调用需要独立的 MagicMock 处理上下文管理器
        call_count = [0]

        def side_effect(req, *args, **kwargs):
            body = json.loads(req.data.decode("utf-8"))
            models_used.append(body["model"])
            call_count[0] += 1
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps({
                "choices": [{"message": {"content": f"critique_{call_count[0]}"}}]
            }).encode("utf-8")
            mock_ctx = MagicMock()
            mock_ctx.__enter__.return_value = mock_resp
            return mock_ctx

        mock_urlopen.side_effect = side_effect

        eng_cb, onto_cb = create_dual_api_critique(self.config)

        # 分别调用两个回调
        eng_cb("system prompt", "test claim", "")
        onto_cb("system prompt", "test claim", "")

        self.assertEqual(len(models_used), 2, "应该有两次API调用")
        self.assertEqual(models_used[0], "qwen-plus",
                         f"工程回调应使用 qwen-plus, 实际: {models_used[0]}")
        self.assertEqual(models_used[1], "glm-4-plus",
                         f"本体回调应使用 glm-4-plus, 实际: {models_used[1]}")
        self.assertNotEqual(models_used[0], models_used[1],
                            "两个回调必须使用不同的模型 — R186修复验证")


class TestLoadConfig(unittest.TestCase):
    """验证配置加载和环境变量覆盖"""

    def setUp(self):
        # 保存原始环境变量
        self.orig_env = {
            k: os.environ.get(k)
            for k in ["THINKTANK_API_KEY", "THINKTANK_BASE_URL",
                       "THINKTANK_MODEL_ENG", "THINKTANK_MODEL_ONT"]
            if k in os.environ
        }
        for k in self.orig_env:
            del os.environ[k]

    def tearDown(self):
        for k in list(os.environ.keys()):
            if k.startswith("THINKTANK_"):
                del os.environ[k]
        for k, v in self.orig_env.items():
            if v is not None:
                os.environ[k] = v

    def test_default_config_uses_template(self):
        """默认配置等于模板"""
        config = load_config()
        self.assertEqual(config["backend"], "openai")
        self.assertEqual(config["model_engineering"], "qwen-plus")
        self.assertEqual(config["model_ontological"], "glm-4-plus")

    def test_env_var_override_api_key(self):
        """环境变量覆盖 api_key"""
        os.environ["THINKTANK_API_KEY"] = "env-test-key"
        config = load_config()
        self.assertEqual(config["api_key"], "env-test-key")

    def test_env_var_override_model_engineering(self):
        """环境变量覆盖 model_engineering"""
        os.environ["THINKTANK_MODEL_ENG"] = "qwen-max"
        config = load_config()
        self.assertEqual(config["model_engineering"], "qwen-max")

    def test_env_var_override_model_ontological(self):
        """环境变量覆盖 model_ontological"""
        os.environ["THINKTANK_MODEL_ONT"] = "glm-4-flash"
        config = load_config()
        self.assertEqual(config["model_ontological"], "glm-4-flash")


if __name__ == "__main__":
    unittest.main()
