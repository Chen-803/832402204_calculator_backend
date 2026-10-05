"""后端启动入口。

用法::

    python run.py                  # 使用默认配置启动（127.0.0.1:8000）
    python run.py --port 9000      # 指定端口
    python run.py --host 0.0.0.0   # 允许局域网访问（部署时常用）
    python run.py --reload         # 开发模式，改代码自动重启

为什么不让助教直接敲 ``uvicorn app.main:app``？
------------------------------------------------
``uvicorn ...`` 依赖命令行参数拼写正确，而 ``python run.py`` 更不容易出错，
并且它可以在启动前先把数据库初始化好、打印出可点击的地址。

真正的 ASGI 应用仍然是标准的 ``app.main:app``，所以
``uvicorn app.main:app --reload`` 同样可用。
"""

from __future__ import annotations

import argparse
import sys

import uvicorn

from app.config import settings
from app.repository.database import init_database


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(
        description="前后端分离计算器系统 —— 后端服务",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--host", default=settings.host, help="监听地址")
    parser.add_argument("--port", type=int, default=settings.port, help="监听端口")
    parser.add_argument("--reload", action="store_true", help="开发模式：代码变更自动重启")
    parser.add_argument(
        "--log-level",
        default=settings.log_level.lower(),
        choices=["critical", "error", "warning", "info", "debug", "trace"],
        help="日志级别",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """启动服务。"""
    args = parse_args(argv)

    db_path = init_database()
    print("=" * 66)
    print("  前后端分离计算器系统 · 后端服务")
    print("=" * 66)
    print(f"  数据库文件 : {db_path}")
    print(f"  服务地址   : http://{args.host}:{args.port}")
    print(f"  接口文档   : http://{args.host}:{args.port}/docs")
    print(f"  健康检查   : http://{args.host}:{args.port}/api/health")
    print("=" * 66)

    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level=args.log_level,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
