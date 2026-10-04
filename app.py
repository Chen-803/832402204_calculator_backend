"""后端服务启动入口。

本地开发::

    python app.py

生产部署（示例，使用 waitress 之类的 WSGI 服务器）::

    waitress-serve --listen=0.0.0.0:8000 app:app

等价的环境变量启动方式::

    $env:CALC_PORT = "8000"; python app.py
"""

import logging
import sys

from src import create_app
from src.config import load_config


def configure_logging(debug: bool = False) -> None:
    """配置日志格式。"""
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


config = load_config()
configure_logging(config.debug)

#: WSGI 入口。生产环境用 ``gunicorn app:app`` / ``waitress-serve app:app`` 加载。
app = create_app(config)


def main() -> int:
    """启动开发服务器。"""
    print("=" * 68)
    print(" 前后端分离计算器 · 后端服务")
    print(f" 监听地址 : http://{config.host}:{config.port}")
    print(f" 数据库   : {config.database_path}")
    print(f" 健康检查 : http://{config.host}:{config.port}/api/health")
    print(" 按 Ctrl+C 停止服务")
    print("=" * 68)
    app.run(host=config.host, port=config.port, debug=config.debug, threaded=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
