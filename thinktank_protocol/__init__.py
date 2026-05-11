"""ThinkTank Protocol v1.0.1 — 双批判协作引擎

178轮精炼的核心方法论：
- 两个独立认知签名（工程批判 / 本体批判）
- 零重叠率测量
- 制度级诚实化三层

用法:
    from thinktank_protocol import DualCritiqueEngine
    engine = DualCritiqueEngine()
    result = engine.critique("你的主张", context="可选上下文")
    print(f"零重叠率: {result.zero_overlap_rate}")
"""

__version__ = "1.0.2"
__rounds__ = 193

from .core import DualCritiqueEngine, CritiqueResult
from .personas import ENGINEERING_CRITIC, ONTOLOGICAL_CRITIC

__all__ = [
    "DualCritiqueEngine",
    "CritiqueResult",
    "ENGINEERING_CRITIC",
    "ONTOLOGICAL_CRITIC",
]
