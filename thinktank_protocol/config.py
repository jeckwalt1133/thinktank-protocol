"""ThinkTank 协议配置 — API适配器与配置模板

支持后端:
- mock: 内置模拟批判（演示用）
- openai: OpenAI兼容API（任何支持chat/completions的服务）
- anthropic: Anthropic Messages API
"""

import os
import json
from typing import Optional

# ============================================================
# 配置模板
# ============================================================
CONFIG_TEMPLATE = {
    "backend": "openai",
    "model_engineering": "qwen-plus",       # 工程批判者使用的模型
    "model_ontological": "glm-4-plus",       # 本体批判者使用的模型
    "api_key": "your-api-key-here",
    "base_url": "https://api.openai.com/v1",  # OpenAI兼容端点
    "temperature": 0.7,
    "max_tokens": 2048,
    "timeout": 60,
}

# ============================================================
# API调用器 — OpenAI兼容
# ============================================================
def call_openai_compatible(
    system_prompt: str,
    user_message: str,
    config: dict,
) -> str:
    """调用OpenAI兼容API执行单次批判"""
    import urllib.request
    import urllib.error

    api_key = config.get("api_key", os.environ.get("OPENAI_API_KEY", ""))
    base_url = config.get("base_url", "https://api.openai.com/v1")
    model = config.get("model_engineering", "gpt-4")

    url = f"{base_url.rstrip('/')}/chat/completions"

    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "temperature": config.get("temperature", 0.7),
        "max_tokens": config.get("max_tokens", 2048),
    }).encode("utf-8")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    req = urllib.request.Request(url, data=payload, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=config.get("timeout", 60)) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8") if e.fp else str(e)
        raise RuntimeError(f"API调用失败 (HTTP {e.code}): {error_body}")
    except Exception as e:
        raise RuntimeError(f"API调用异常: {e}")


# ============================================================
# 双API批判适配器
# ============================================================
def create_dual_api_critique(config: dict):
    """
    创建使用真实API的双批判回调函数。

    Returns:
        (engine_callback, onto_callback): 两个可传递给 DualCritiqueEngine.critique() 的回调
    """
    eng_config = {**config, "model": config.get("model_engineering", "gpt-4")}
    ont_config = {**config, "model": config.get("model_ontological", "gpt-4")}

    def engine_callback(system_prompt: str, claim: str, context: str) -> str:
        user_msg = f"主张: {claim}\n上下文: {context}" if context else f"主张: {claim}"
        return call_openai_compatible(system_prompt, user_msg, eng_config)

    def onto_callback(system_prompt: str, claim: str, context: str) -> str:
        user_msg = f"主张: {claim}\n上下文: {context}" if context else f"主张: {claim}"
        return call_openai_compatible(system_prompt, user_msg, ont_config)

    return engine_callback, onto_callback


# ============================================================
# 配置加载器
# ============================================================
def load_config(config_path: Optional[str] = None) -> dict:
    """从文件或环境变量加载配置"""
    config = CONFIG_TEMPLATE.copy()

    if config_path and os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            file_config = json.load(f)
            config.update(file_config)

    # 环境变量覆盖
    if os.environ.get("THINKTANK_API_KEY"):
        config["api_key"] = os.environ["THINKTANK_API_KEY"]
    if os.environ.get("THINKTANK_BASE_URL"):
        config["base_url"] = os.environ["THINKTANK_BASE_URL"]
    if os.environ.get("THINKTANK_MODEL_ENG"):
        config["model_engineering"] = os.environ["THINKTANK_MODEL_ENG"]
    if os.environ.get("THINKTANK_MODEL_ONT"):
        config["model_ontological"] = os.environ["THINKTANK_MODEL_ONT"]

    return config
