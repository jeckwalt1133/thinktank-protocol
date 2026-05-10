"""ThinkTank Protocol 安装配置

最小兼容安装 — 零外部依赖。
包结构: thinktank_protocol/ 子目录为标准 Python 包。
"""

from setuptools import setup, find_packages

# 读取 README
with open("README.md", encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="thinktank-protocol",
    version="1.0.1",
    description="ThinkTank 双批判协作引擎 — 183轮制度演化的可移植内核",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="ThinkTank Collective",
    url="https://github.com/jeckwalt1133/thinktank-protocol",
    packages=find_packages(include=["thinktank_protocol", "thinktank_protocol.*"]),
    python_requires=">=3.9",
    install_requires=[],  # 零外部依赖
    entry_points={
        "console_scripts": [
            "thinktank-critique=thinktank_protocol.run:main",
        ],
    },
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Science/Research",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    keywords="ai-collaboration, critique-engine, multi-agent, zero-overlap, 双批判, 认知签名",
)
