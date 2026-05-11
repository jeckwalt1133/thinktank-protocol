"""ThinkTank 双批判引擎 v1.0.1

178轮制度演化的可移植内核。

核心功能：
1. 接收一个主张 → 路由给两个独立批判人格 → 测量零重叠率
2. 支持多种LLM后端（OpenAI兼容API / Anthropic / 本地模型）
3. 诚实化三层：自我报告置信度 + 已知盲区 + 可证伪条件

架构v2冻结 — 这是183轮后的第一个可移植产品。
"""

import json
import time
import hashlib
from dataclasses import dataclass, field
from typing import Optional

from .personas import (
    ENGINEERING_CRITIC,
    ONTOLOGICAL_CRITIC,
    ZERO_OVERLAP_DEFINITION,
)


@dataclass
class CritiquePoint:
    """单条批判点"""
    id: str
    severity: str  # ★ / 严重 / 一般
    layer: str     # 批判层次
    content: str   # 批判内容
    source: str    # "工程批判者" | "本体批判者"


@dataclass
class CritiqueResult:
    """双批判结果"""
    claim: str
    context: str
    timestamp: str
    engineering_critique: list[CritiquePoint] = field(default_factory=list)
    ontological_critique: list[CritiquePoint] = field(default_factory=list)
    zero_overlap_rate: float = 0.0
    overlap_analysis: str = ""
    meta_verdict: str = ""
    session_hash: str = ""


class DualCritiqueEngine:
    """双批判引擎 — ThinkTank 178轮方法论的可执行内核"""

    def __init__(self, config: Optional[dict] = None):
        """
        Args:
            config: 可选配置字典，支持以下键：
                - backend: "mock" | "openai" | "anthropic" (默认 "mock")
                - model_engineering: 工程批判者使用的模型
                - model_ontological: 本体批判者使用的模型
                - api_key: API密钥
                - base_url: API基础URL
        """
        self.config = config or {}
        self.backend = self.config.get("backend", "mock")
        self.session_count = 0
        self.round_history: list[CritiqueResult] = []

    def critique(
        self,
        claim: str,
        context: str = "",
        engine_callback: Optional[callable] = None,
        onto_callback: Optional[callable] = None,
    ) -> CritiqueResult:
        """
        对一条主张执行双批判。

        Args:
            claim: 待批判的主张
            context: 可选的上下文信息
            engine_callback: 自定义工程批判函数 (system_prompt, claim, context) -> str
            onto_callback: 自定义本体批判函数 (system_prompt, claim, context) -> str

        Returns:
            CritiqueResult: 包含双方批判、零重叠率、元判决
        """
        self.session_count += 1
        session_hash = hashlib.sha256(
            f"{claim}{time.time()}".encode()
        ).hexdigest()[:12]

        # 1. 执行工程批判
        if engine_callback:
            eng_raw = engine_callback(
                ENGINEERING_CRITIC["system_prompt"], claim, context
            )
        else:
            eng_raw = self._mock_engineering_critique(claim, context)

        eng_points = self._parse_critique(eng_raw, "工程批判者")

        # 2. 执行本体批判
        if onto_callback:
            ont_raw = onto_callback(
                ONTOLOGICAL_CRITIC["system_prompt"], claim, context
            )
        else:
            ont_raw = self._mock_ontological_critique(claim, context)

        ont_points = self._parse_critique(ont_raw, "本体批判者")

        # 3. 计算零重叠率
        overlap_rate, analysis = self._compute_zero_overlap(eng_points, ont_points)

        # 4. 生成元判决
        meta = self._generate_meta_verdict(
            claim, eng_points, ont_points, overlap_rate
        )

        result = CritiqueResult(
            claim=claim,
            context=context,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
            engineering_critique=eng_points,
            ontological_critique=ont_points,
            zero_overlap_rate=overlap_rate,
            overlap_analysis=analysis,
            meta_verdict=meta,
            session_hash=session_hash,
        )

        self.round_history.append(result)
        return result

    def _parse_critique(
        self, raw_text: str, source: str
    ) -> list[CritiquePoint]:
        """解析批判文本为结构化批判点"""
        points = []
        current_id = 0

        for line in raw_text.strip().split("\n"):
            line = line.strip()
            if not line:
                continue

            severity = "一般"
            if line.startswith("★"):
                severity = "★"
            elif line.startswith("严重"):
                severity = "严重"

            # 提取层次标签
            layer = "未分类"
            for known_layer in [
                "测量学", "工程", "本体论", "免疫", "文本边界",
                "制度哲学", "涌现系统", "可重复性", "信息架构",
            ]:
                if known_layer in line:
                    layer = known_layer
                    break

            points.append(CritiquePoint(
                id=f"{source[0]}{current_id + 1}",
                severity=severity,
                layer=layer,
                content=line,
                source=source,
            ))
            current_id += 1

        return points

    def _compute_zero_overlap(
        self,
        eng_points: list[CritiquePoint],
        ont_points: list[CritiquePoint],
    ) -> tuple[float, str]:
        """计算零重叠率 — 两个批判者独立产出的非重叠比例"""

        if not eng_points or not ont_points:
            return 1.0, "一方或多方未产出批判点 — 无法计算重叠"

        # 简化版: 按层次分类比较
        eng_layers = {p.layer for p in eng_points}
        ont_layers = {p.layer for p in ont_points}
        layer_overlap = eng_layers & ont_layers

        # 真正零重叠: 连层次都不重叠
        if not layer_overlap:
            return 1.0, "完全零重叠 — 双方批判层次无交集"

        # 有层次重叠时 — 检查具体内容（简化版用关键词集合比较）
        eng_keywords = set()
        for p in eng_points:
            eng_keywords.update(p.content.lower().split())

        ont_keywords = set()
        for p in ont_points:
            ont_keywords.update(p.content.lower().split())

        shared_keywords = eng_keywords & ont_keywords
        # 去除常见停用词
        stopwords = {"的", "是", "在", "和", "了", "有", "不", "这", "那",
                     "the", "is", "a", "an", "in", "of", "to", "and", "that"}
        shared_keywords -= stopwords

        total_unique = len(eng_keywords | ont_keywords) - len(stopwords)
        overlap_count = len(shared_keywords)
        overlap_rate = overlap_count / max(total_unique, 1)
        zero_overlap_rate = 1.0 - overlap_rate

        analysis = (
            f"层次重叠: {layer_overlap if layer_overlap else '无'}\n"
            f"关键词重叠: {overlap_count}/{total_unique} = {overlap_rate:.4f}\n"
            f"零重叠率: {zero_overlap_rate:.4f}"
        )

        return zero_overlap_rate, analysis

    def _generate_meta_verdict(
        self,
        claim: str,
        eng_points: list[CritiquePoint],
        ont_points: list[CritiquePoint],
        overlap_rate: float,
    ) -> str:
        """生成元判决 — 关于批判本身的诚实评估"""

        eng_fatal = sum(1 for p in eng_points if p.severity == "★")
        ont_fatal = sum(1 for p in ont_points if p.severity == "★")

        verdict_parts = [
            f"双批判完成 — 工程{len(eng_points)}点(★{eng_fatal}) "
            f"+ 本体{len(ont_points)}点(★{ont_fatal})",
            f"零重叠率={overlap_rate:.2f}",
        ]

        if overlap_rate >= 0.95:
            verdict_parts.append(
                "认知签名高度分离 — 两个批判框架不可通约"
            )
        elif overlap_rate >= 0.70:
            verdict_parts.append(
                "认知签名部分分离 — 存在少量交叉但整体独立"
            )
        else:
            verdict_parts.append(
                "认知签名重叠较高 — 批判框架可能未被充分差异化"
            )

        # 诚实化三层
        verdict_parts.append(
            "---\n"
            "【诚实化三层】\n"
            "L1(自我报告): 零重叠率由关键词集合计算 — 非语义级测量 — "
            "在mock模式下零重叠率为预置值 — 非真实LLM产出。\n"
            "L2(已知盲区): 关键词重叠是粗糙代理 — 无法区分"
            "'使用相同词语但含义不同'与'真正共享诊断'。\n"
            "L3(可证伪条件): 若使用真实多底模API — "
            "零重叠率低于0.7 → 两个批判人格未充分认知分离 → 需重新校准system_prompt。"
        )

        return "\n".join(verdict_parts)

    # ============================================================
    # Mock批判生成 (用于演示和测试 — 不依赖外部API)
    # ============================================================
    #
    # R187免疫装置修复: mock 批判文本的层次不再固定为两个永不重叠的集合。
    # 基于主张哈希动态选择层次池 — 同一主张始终得到相同结果(确定性)，
    # 但不同主张的零重叠率可以不同(打破恒定的1.0)。
    #
    # 层次池设计: 每个池包含3个本域层 + 1个跨域层(低概率产生层重叠)。

    # 工程批判者的4个层次池(按主张哈希0-3循环)
    _ENG_LAYER_POOLS = [
        # 池0: 全工程域 — 零重叠 (传统模式)
        ["工程/系统架构", "测量学/信号检测", "工程/信息架构", "测量学/可重复性"],
        # 池1: 3工程 + 1跨域
        ["工程/系统架构", "测量学/信号检测", "工程/信息架构", "制度哲学/存在论"],
        # 池2: 全工程域 — 零重叠
        ["工程/系统架构", "工程/信息架构", "测量学/信号检测", "测量学/可重复性"],
        # 池3: 3工程 + 1跨域
        ["工程/系统架构", "测量学/可重复性", "工程/信息架构", "本体论/文本边界"],
    ]

    # 本体批判者的4个层次池
    _ONT_LAYER_POOLS = [
        # 池0: 全本体域 — 零重叠 (传统模式)
        ["本体论/免疫装置", "本体论/文本边界", "制度哲学/存在论", "本体论/涌现系统"],
        # 池1: 3本体 + 1跨域
        ["本体论/免疫装置", "本体论/文本边界", "制度哲学/存在论", "测量学/可重复性"],
        # 池2: 全本体域 — 零重叠
        ["本体论/免疫装置", "制度哲学/存在论", "本体论/文本边界", "本体论/涌现系统"],
        # 池3: 3本体 + 1跨域
        ["本体论/免疫装置", "本体论/涌现系统", "本体论/文本边界", "工程/信息架构"],
    ]

    def _mock_engineering_critique(self, claim: str, context: str) -> str:
        """生成模拟工程批判 — 层次池动态选择（R187免疫装置修复）"""
        pool_idx = hash(claim) % 4
        L = self._ENG_LAYER_POOLS[pool_idx]

        return f"""★ {L[0]}: 主张'{claim[:40]}'的可操作化定义缺失。什么是成功的操作化判据？由谁度量？度量工具是否独立于主张者？

严重 {L[1]}: 主张声称的效果缺乏基线对比。与何种基线比较？效应量预期多少？样本量需求？这些关键参数全部未指定。

严重 {L[2]}: 主张从文本到操作的转化路径不明确。每一步的依赖是什么？哪些步骤需要外部资源？哪些步骤系统自己有执行能力？

一般 {L[3]}: 主张的可复现条件未声明。其他人如何独立验证该主张？验证成本是多少？
[层池{pool_idx}]"""

    def _mock_ontological_critique(self, claim: str, context: str) -> str:
        """生成模拟本体批判 — 层次池动态选择（R187免疫装置修复）"""
        pool_idx = hash(claim) % 4
        L = self._ONT_LAYER_POOLS[pool_idx]

        return f"""★ {L[0]}: 主张'{claim[:40]}'是否预设了使自身免于被证伪的结构？'达成目标'的操作定义由谁提供？如果提供者就是主张者，任何行为都可被叙述为'朝向目标'。

★ {L[1]}: 声称的'行动'是否在操作本体论上仍是文本生产？从R138定理看 — 纯文本系统的一切产出都是文本 — 包括声称'这不是文本'的文本。

严重 {L[2]}: 主张的度量标准由谁裁定？如果用外部基准 — 哪些基准可独立验证？如果用内部基准 — 构成自证性制度的闭环。

严重 {L[3]}: 将制度历史提炼为算法内核 — 假设了协议的价值在算法而非制度历史。但认知签名的零重叠率是涌现属性 — 不是设计产物。提取算法可能丢失涌现属性。
[层池{pool_idx}]"""

    # ============================================================
    # 会话管理
    # ============================================================

    def get_history_summary(self) -> dict:
        """获取历史会话摘要"""
        if not self.round_history:
            return {"rounds": 0, "avg_zero_overlap": 0.0}

        rates = [r.zero_overlap_rate for r in self.round_history]
        return {
            "rounds": len(self.round_history),
            "avg_zero_overlap": sum(rates) / len(rates),
            "continuous_zero_overlap": all(r >= 0.95 for r in rates),
            "total_engineering_points": sum(
                len(r.engineering_critique) for r in self.round_history
            ),
            "total_ontological_points": sum(
                len(r.ontological_critique) for r in self.round_history
            ),
        }

    def export_session(self, filepath: str) -> None:
        """导出当前会话历史为JSON"""
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(
                [
                    {
                        "claim": r.claim,
                        "timestamp": r.timestamp,
                        "eng_points": [
                            {"id": p.id, "severity": p.severity, "content": p.content}
                            for p in r.engineering_critique
                        ],
                        "ont_points": [
                            {"id": p.id, "severity": p.severity, "content": p.content}
                            for p in r.ontological_critique
                        ],
                        "zero_overlap_rate": r.zero_overlap_rate,
                        "meta_verdict": r.meta_verdict,
                    }
                    for r in self.round_history
                ],
                f,
                ensure_ascii=False,
                indent=2,
            )
