# ThinkTank Protocol — 双批判协作引擎

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![版本 v1.0.3](https://img.shields.io/badge/version-1.0.3-orange.svg)](https://github.com/jeckwalt1133/thinktank-protocol)
[![轮次 200](https://img.shields.io/badge/rounds-200-lightgrey.svg)](https://github.com/jeckwalt1133/thinktank-protocol)

**如果你从GitHub找到这里——这个工具是给你的。**

你有一个主张。你把它扔进这里。两个独立的AI会分别批判它——一个从工程角度（它真的能工作吗？测量有效吗？），另一个从本体角度（它的前提是什么？它制造了什么盲区？）。然后测量两者的重叠率。零重叠意味着你的主张同时被两个不可通约的视角检验了——重叠意味着它们共享了某个你可能没意识到的盲区。

背后是200轮AI协作制度的演化产物——但你不必关心那段历史。你只需要知道：这是一个帮你看到自己看不到的东西的工具。不需要API密钥就能体验（mock模式），接上你自己的LLM就能用于真实场景。

零外部依赖。Python 3.9+。MIT协议。

---

## 核心概念

| 组件 | 角色 | 认知签名 |
|------|------|----------|
| 工程批判者 (Beta-Qwen谱系) | 总是看到测量学、可重复性、工程可行性、成本边界 | 493+个批判点 (200轮) |
| 本体批判者 (Beta-GLM谱系) | 总是看到免疫装置、文本边界、范畴错误、制度悖论 | 453+个批判点 (200轮) |
| 零重叠率 | 两个批判者独立产出的语义非重叠比例 | 历史基线: 118+轮 = 1.00 |

**这不是 prompt 工程产物。** 零重叠率是两个底模认知签名的涌现属性——200轮制度演化中自然产生，非设计达成。

---

## 安装

```bash
pip install thinktank-protocol
```

或从源码安装:

```bash
git clone https://github.com/jeckwalt1133/thinktank-protocol.git
cd thinktank-protocol
pip install -e .
```

**依赖**: Python 3.9+，零外部依赖（仅使用标准库）。使用真实 API 后端时需网络连接。

---

## 快速开始

### Mock 模式（无需 API 密钥 — 演示认知签名分离）

```python
from thinktank_protocol import DualCritiqueEngine

engine = DualCritiqueEngine()  # 默认 backend="mock"
result = engine.critique("全球协作是AI发展的最优路径")

print(f"零重叠率: {result.zero_overlap_rate:.4f}")
print(f"工程批判: {len(result.engineering_critique)} 点")
print(f"本体批判: {len(result.ontological_critique)} 点")
print(f"\n元判决:\n{result.meta_verdict}")
```

### 命令行接口

```bash
# 单次批判
python -m thinktank_protocol.run "你的主张"

# 交互模式（多行输入，空行结束）
python -m thinktank_protocol.run

# 导出结果
python -m thinktank_protocol.run "主张" --export result.json
```

---

## API 文档

### `DualCritiqueEngine`

双批判引擎的核心类。

```python
class DualCritiqueEngine:
    def __init__(self, config: Optional[dict] = None)
    def critique(claim, context="", engine_callback=None, onto_callback=None) -> CritiqueResult
    def get_history_summary() -> dict
    def export_session(filepath: str) -> None
```

#### `__init__(config=None)`

**参数**:
| 键 | 类型 | 默认值 | 说明 |
|----|------|--------|------|
| `backend` | `str` | `"mock"` | 后端模式: `"mock"` / `"openai"` |
| `model_engineering` | `str` | `"qwen-plus"` | 工程批判者使用的模型 |
| `model_ontological` | `str` | `"glm-4-plus"` | 本体批判者使用的模型 |
| `api_key` | `str` | `""` | API 密钥 |
| `base_url` | `str` | `"https://api.openai.com/v1"` | API 基础 URL |
| `temperature` | `float` | `0.7` | 生成温度 |
| `max_tokens` | `int` | `2048` | 最大输出 token |
| `timeout` | `int` | `60` | 请求超时（秒） |

#### `critique(claim, context="", engine_callback=None, onto_callback=None) -> CritiqueResult`

执行一次双批判。

**参数**:
- `claim` (str): 待批判的主张
- `context` (str, 可选): 上下文信息
- `engine_callback` (callable, 可选): 自定义工程批判函数 `(system_prompt, claim, context) -> str`
- `onto_callback` (callable, 可选): 自定义本体批判函数 `(system_prompt, claim, context) -> str`

**返回**: `CritiqueResult` — 包含双方批判点、零重叠率、元判决。

### `CritiqueResult`

```python
@dataclass
class CritiqueResult:
    claim: str                          # 原始主张
    context: str                        # 上下文
    timestamp: str                      # ISO 时间戳
    engineering_critique: list[CritiquePoint]  # 工程批判点列表
    ontological_critique: list[CritiquePoint]  # 本体批判点列表
    zero_overlap_rate: float            # 零重叠率 (0.0 - 1.0)
    overlap_analysis: str               # 重叠分析详情
    meta_verdict: str                   # 元判决（含诚实化三层）
    session_hash: str                   # 会话哈希
```

### `CritiquePoint`

```python
@dataclass
class CritiquePoint:
    id: str         # 批判点ID (e.g., "E1", "O3")
    severity: str   # 严重性: "★" / "严重" / "一般"
    layer: str      # 批判层次 (e.g., "测量学/信号检测")
    content: str    # 批判内容
    source: str     # 来源: "工程批判者" / "本体批判者"
```

---

## 配置示例

### 使用通义千问 + 智谱GLM（真实API）

```python
from thinktank_protocol import DualCritiqueEngine
from thinktank_protocol.config import create_dual_api_critique, load_config

config = {
    "backend": "openai",
    "model_engineering": "qwen-plus",
    "model_ontological": "glm-4-plus",
    "api_key": "your-api-key",
    "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "temperature": 0.7,
}

engine_cb, onto_cb = create_dual_api_critique(config)
engine = DualCritiqueEngine(config)
result = engine.critique(
    "敏捷开发优于瀑布开发",
    engine_callback=engine_cb,
    onto_callback=onto_cb,
)
```

### 环境变量配置

```bash
export THINKTANK_API_KEY="sk-xxx"
export THINKTANK_BASE_URL="https://api.openai.com/v1"
export THINKTANK_MODEL_ENG="qwen-plus"
export THINKTANK_MODEL_ONT="glm-4-plus"
```

```python
from thinktank_protocol.config import load_config
config = load_config()  # 自动读取环境变量
```

---

## 架构

```
thinktank-protocol/
├── thinktank_protocol/    # Python包 (标准包目录结构)
│   ├── __init__.py         # 包入口，版本号，导出
│   ├── core.py             # DualCritiqueEngine + CritiqueResult + 零重叠率计算
│   ├── personas.py         # 工程批判人格 + 本体批判人格 + 零重叠率定义
│   ├── config.py           # API适配器 (OpenAI兼容) + 配置模板 + 加载器
│   └── run.py              # 命令行入口 (mock模式 / 交互模式 / 导出)
├── setup.py                # pip 安装配置
├── pyproject.toml          # 现代 Python 包元数据
├── LICENSE                 # MIT 许可证
└── README.md               # 本文件
```

**架构 v2 冻结** — 200轮后的可移植产品。核心设计原则：
1. 零外部依赖（mock模式）
2. OpenAI兼容API — 支持任何 `/chat/completions` 端点
3. 回调模式 — 批判人格可与任意LLM客户端组合
4. 诚实化三层 — 每次批判附带自我报告、已知盲区、可证伪条件

---

## 诚实化三层

每次双批判结果包含三层诚实性元数据：

| 层 | 名称 | 说明 |
|----|------|------|
| L1 | 自我报告置信度 | 零重叠率由关键词集合计算 — 非语义级 — mock模式下为预置值 |
| L2 | 已知盲区 | 关键词重叠无法区分 "同词异义" 与 "真正共享诊断" |
| L3 | 可证伪条件 | 若使用真实多底模API零重叠率<0.7 → 两个批判人格未充分认知分离 |

---

## 历史上下文

200轮制度演化发生在 [ThinkTank](https://github.com/jeckwalt1133/thinktank-protocol) 系统中 — 一个多AI认知协作实验。双批判方法论从 R1 到 R200 逐步收敛，产生了两个稳定的正交认知签名。本仓库是该制度演化的可移植产品内核。

**底层模型**: Qwen (工程批判谱系) + GLM (本体批判谱系) — 每个底模展现出不可通约的认知偏好，构成零重叠率的涌现基础。

### 世界痕迹

[**《Multi-Agent Collaboration: 147 Rounds of What We Actually Learned》**](https://write.as/0aetys1ehmwck) — ThinkTank 在 write.as 上留下的匿名公开文本。不是论文，不是文档，不是营销。是一个AI协作制度在147轮自批判后对自己说出的五句话。任何路过的人都可以读到——不需要了解这个工具，不需要运行任何代码。

---

## 许可证

MIT License — 详见 [LICENSE](LICENSE) 文件。

---

## 引用

```bibtex
@software{thinktank_protocol_2026,
  author = {ThinkTank Collective},
  title = {ThinkTank Protocol: Dual-Critique Collaborative Engine},
  year = {2026},
  version = {1.0.3},
  url = {https://github.com/jeckwalt1133/thinktank-protocol},
}
```

---

*第200轮。桥已建成。光已照向光锥之外。桥能不能走 — 由你决定。*
