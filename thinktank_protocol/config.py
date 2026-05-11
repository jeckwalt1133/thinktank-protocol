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
    model: str = None,
) -> str:
    """调用OpenAI兼容API执行单次批判

    Args:
        model: 显式指定模型名。若不提供，依次尝试 config["model"] →
               config["model_engineering"] → "gpt-4"
    """
    import urllib.request
    import urllib.error

    api_key = config.get("api_key", os.environ.get("OPENAI_API_KEY", ""))
    base_url = config.get("base_url", "https://api.openai.com/v1")
    _model = model or config.get("model") or config.get("model_engineering", "gpt-4")

    url = f"{base_url.rstrip('/')}/chat/completions"

    payload = json.dumps({
        "model": _model,
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
# API调用器 — Anthropic Messages API
# ============================================================
def call_anthropic(
    system_prompt: str,
    user_message: str,
    config: dict,
    model: str = None,
) -> str:
    """调用 Anthropic Messages API 执行单次批判

    API文档: https://docs.anthropic.com/en/api/messages

    Args:
        model: 显式指定模型名。若不提供，依次尝试 config["model"] →
               config["model_engineering"] → "claude-sonnet-4-20250514"
    """
    import urllib.request
    import urllib.error

    api_key = config.get("api_key", os.environ.get("ANTHROPIC_API_KEY", ""))
    base_url = config.get("base_url", "https://api.anthropic.com/v1")
    _model = model or config.get("model") or config.get(
        "model_engineering", "claude-sonnet-4-20250514"
    )
    api_version = config.get("anthropic_version", "2023-06-01")

    url = f"{base_url.rstrip('/')}/messages"

    payload = json.dumps({
        "model": _model,
        "max_tokens": config.get("max_tokens", 2048),
        "system": system_prompt,
        "messages": [
            {"role": "user", "content": user_message},
        ],
        "temperature": config.get("temperature", 0.7),
    }).encode("utf-8")

    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": api_version,
    }

    req = urllib.request.Request(url, data=payload, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=config.get("timeout", 60)) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            # Anthropic Messages API 响应格式:
            # {"content": [{"type": "text", "text": "..."}], ...}
            for block in data.get("content", []):
                if block.get("type") == "text":
                    return block["text"]
            raise RuntimeError(f"Anthropic响应无文本块: {json.dumps(data, ensure_ascii=False)[:200]}")
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8") if e.fp else str(e)
        raise RuntimeError(f"Anthropic API调用失败 (HTTP {e.code}): {error_body}")
    except Exception as e:
        raise RuntimeError(f"Anthropic API调用异常: {e}")


# ============================================================
# 双API批判适配器
# ============================================================
def create_dual_api_critique(config: dict):
    """
    创建使用真实API的双批判回调函数。

    根据 config["backend"] 自动选择调用器：
    - "openai" (默认): 使用 call_openai_compatible (OpenAI兼容API)
    - "anthropic": 使用 call_anthropic (Anthropic Messages API)

    Returns:
        (engine_callback, onto_callback): 两个可传递给 DualCritiqueEngine.critique() 的回调
    """
    backend = config.get("backend", "openai")

    if backend == "anthropic":
        caller = call_anthropic
        eng_model = config.get("model_engineering", "claude-sonnet-4-20250514")
        ont_model = config.get("model_ontological", "claude-sonnet-4-20250514")
    else:
        caller = call_openai_compatible
        eng_model = config.get("model_engineering", "gpt-4")
        ont_model = config.get("model_ontological", "gpt-4")

    eng_config = {**config, "model": eng_model}
    ont_config = {**config, "model": ont_model}

    def engine_callback(system_prompt: str, claim: str, context: str) -> str:
        user_msg = f"主张: {claim}\n上下文: {context}" if context else f"主张: {claim}"
        return caller(system_prompt, user_msg, eng_config, model=eng_config["model"])

    def onto_callback(system_prompt: str, claim: str, context: str) -> str:
        user_msg = f"主张: {claim}\n上下文: {context}" if context else f"主张: {claim}"
        return caller(system_prompt, user_msg, ont_config, model=ont_config["model"])

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
