#!/usr/bin/env python3
"""ThinkTank 双批判协议 — 命令行入口

用法:
    # Mock模式 (无需API密钥 — 演示认知签名分离)
    python -m thinktank_protocol.run "你的主张"

    # 或通过安装后的命令
    thinktank-critique "你的主张"

    # 交互模式
    python -m thinktank_protocol.run

    # 导出会话
    python -m thinktank_protocol.run "主张" --export result.json

183轮制度演化 — 可移植产品内核 v1.0.1
"""

import sys
import json

from .core import DualCritiqueEngine
from .personas import (
    ENGINEERING_CRITIC,
    ONTOLOGICAL_CRITIC,
    ZERO_OVERLAP_DEFINITION,
)


def format_critique_points(points, title: str) -> str:
    """格式化批判点输出"""
    lines = [f"\n{'='*60}", f"  {title} ({len(points)}点)", f"{'='*60}"]
    for p in points:
        marker = "[!]" if p.severity == "★" else ("[!]" if p.severity == "严重" else "[ ]")
        lines.append(f"  {marker} [{p.severity}] {p.layer}")
        lines.append(f"     {p.content[:120]}...")
    return "\n".join(lines)


def main():
    """CLI主入口"""
    print("""
+============================================================+
|     ThinkTank 双批判协议 v1.0.1                             |
|     183轮制度演化 — 可移植产品内核                          |
|     工程批判者(Qwen谱系 437+点) + 本体批判者(GLM谱系 397+点) |
+============================================================+
""")

    # 解析参数
    claim = None
    export_path = None

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--export" and i + 1 < len(args):
            export_path = args[i + 1]
            i += 2
        elif not claim:
            claim = args[i]
            i += 1
        else:
            i += 1

    # 交互模式
    if not claim:
        print("输入主张（空行结束，输入 'quit' 退出）:\n")
        lines = []
        while True:
            try:
                line = input()
                if line.lower() == "quit":
                    return
                if line == "":
                    break
                lines.append(line)
            except (EOFError, KeyboardInterrupt):
                print("\n")
                return
        claim = "\n".join(lines)
        if not claim.strip():
            print("未输入主张 — 退出")
            return

    # 初始化引擎
    engine = DualCritiqueEngine({"backend": "mock"})

    # 执行双批判
    print(f"\n[*] 主张: {claim[:100]}...\n")
    print("[...] 执行双批判...\n")

    result = engine.critique(claim)

    # 输出结果
    print(format_critique_points(result.engineering_critique, "工程批判者"))
    print(format_critique_points(result.ontological_critique, "本体批判者"))

    print(f"\n{'='*60}")
    print(f"  零重叠率: {result.zero_overlap_rate:.4f}")
    print(f"  {result.overlap_analysis}")
    print(f"{'='*60}")

    print(f"\n{'='*60}")
    print(f"  元判决")
    print(f"{'='*60}")
    print(f"  {result.meta_verdict}")

    print(f"\n会话哈希: {result.session_hash}")

    # 导出
    if export_path:
        engine.export_session(export_path)
        print(f"\n[OK] 会话已导出至: {export_path}")


if __name__ == "__main__":
    main()
