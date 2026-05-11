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
# 模块级常量 — 单一真相源（R198 合并）
# ============================================================
ANTHROPIC_VERSION = "2023-06-01"  # Anthropic Messages API 版本头，全模块唯一声明

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
    "anthropic_version": ANTHROPIC_VERSION,  # 引用模块常量，非字面量
}

# ============================================================
# 共享API调用基础设施 — R195提取，消除call_openai_compatible与
# call_anthropic之间约70%的重复代码。
#
# 设计原则：
# - _call_api 处理所有通用逻辑（URL构建、JSON编码、HTTP请求、错误处理）
# - 各后端通过回调函数提供差异化行为（payload结构、headers、响应解析）
# - 新增后端只需实现三个回调函数，无需重复网络/错误处理代码
# ============================================================

def _call_api(
    system_prompt: str,
    user_message: str,
    config: dict,
    model: str = None,
    *,
    endpoint: str,
    env_key_name: str,
    default_base_url: str,
    default_model: str,
    build_payload,
    build_headers,
    parse_response,
) -> str:
    """共享API调用基础设施 — 所有后端的单一调用路径

    Args:
        endpoint: API端点路径。必须以"/"开头，例如"/chat/completions"或"/messages"。
                  拼接规则: URL = base_url.rstrip("/") + endpoint。
                  依赖endpoint自带前导斜杠，调用方不应省略。
        env_key_name: 环境变量名用于回退API密钥，例如 "OPENAI_API_KEY"
        default_base_url: 默认API基础URL（当config无base_url时使用）
        default_model: 默认模型名（当config和显式参数均未提供时使用）
        build_payload(model, system_prompt, user_message, config) -> dict
        build_headers(api_key, config) -> dict
        parse_response(data: dict) -> str
    """
    import urllib.request
    import urllib.error

    api_key = config.get("api_key", os.environ.get(env_key_name, ""))
    base_url = config.get("base_url", default_base_url)
    _model = model or config.get("model") or config.get("model_engineering", default_model)

    url = f"{base_url.rstrip('/')}{endpoint}"
    payload = json.dumps(
        build_payload(_model, system_prompt, user_message, config)
    ).encode("utf-8")
    headers = build_headers(api_key, config)

    req = urllib.request.Request(url, data=payload, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=config.get("timeout", 60)) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return parse_response(data)
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8") if e.fp else str(e)
        raise RuntimeError(f"API调用失败 (HTTP {e.code}): {error_body}")
    except Exception as e:
        raise RuntimeError(f"API调用异常: {e}")


# ------------------------------------------------------------
# OpenAI兼容后端 — payload/headers/response回调
# ------------------------------------------------------------
def _build_openai_payload(model, system_prompt, user_message, config):
    return {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "temperature": config.get("temperature", 0.7),
        "max_tokens": config.get("max_tokens", 2048),
    }

def _build_openai_headers(api_key, config):
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

def _parse_openai_response(data):
    return data["choices"][0]["message"]["content"]


# ------------------------------------------------------------
# Anthropic Messages API 后端 — payload/headers/response回调
# ------------------------------------------------------------
def _build_anthropic_payload(model, system_prompt, user_message, config):
    return {
        "model": model,
        "max_tokens": config.get("max_tokens", 2048),
        "system": system_prompt,
        "messages": [
            {"role": "user", "content": user_message},
        ],
        "temperature": config.get("temperature", 0.7),
    }

def _build_anthropic_headers(api_key, config):
    return {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        # R199修复: 恢复 or 语义 — .get(key, default) 在 key 存在但值为 "" 时不回退
        # or ANTHROPIC_VERSION 确保空字符串也回退到模块常量 — 保留R198的单一真相源
        "anthropic-version": config.get("anthropic_version") or ANTHROPIC_VERSION,
    }

def _parse_anthropic_response(data):
    for block in data.get("content", []):
        if block.get("type") == "text":
            return block["text"]
    raise RuntimeError(
        f"Anthropic响应无文本块: {json.dumps(data, ensure_ascii=False)[:200]}"
    )


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
    return _call_api(
        system_prompt, user_message, config, model,
        endpoint="/chat/completions",
        env_key_name="OPENAI_API_KEY",
        default_base_url="https://api.openai.com/v1",
        default_model="gpt-4",
        build_payload=_build_openai_payload,
        build_headers=_build_openai_headers,
        parse_response=_parse_openai_response,
    )


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
    return _call_api(
        system_prompt, user_message, config, model,
        endpoint="/messages",
        env_key_name="ANTHROPIC_API_KEY",
        default_base_url="https://api.anthropic.com/v1",
        default_model="claude-sonnet-4-20250514",
        build_payload=_build_anthropic_payload,
        build_headers=_build_anthropic_headers,
        parse_response=_parse_anthropic_response,
    )


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
    if os.environ.get("THINKTANK_ANTHROPIC_VERSION"):
        config["anthropic_version"] = os.environ["THINKTANK_ANTHROPIC_VERSION"]

    return config
