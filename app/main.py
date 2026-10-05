"""FastAPI 应用装配。

这里是整个后端唯一"把各层拼起来"的地方：

.. code-block:: text

    main.py
      ├── 创建 FastAPI 实例（含 lifespan：启动时建库）
      ├── 挂载 CORS 中间件（让前端开发服务器能跨域访问）
      ├── 注册全局异常处理器（统一错误信封）
      └── 挂载 controller 层的路由（统一 /api 前缀）

应用工厂
--------
用 :func:`create_app` 而不是在模块顶层直接建 ``app``，是为了让测试可以
针对每个测试用例创建独立实例（配独立的数据库文件），互不干扰。
"""

from __future__ import annotations

import logging
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .common.exception_handlers import register_exception_handlers
from .config import settings
from .controller import ROUTERS
from .repository.database import init_database

#: API 统一前缀
API_PREFIX = "/api"


def configure_logging() -> None:
    """配置日志。开发时输出到 stdout，方便直接看 uvicorn 控制台。"""
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        stream=sys.stdout,
    )


def create_app(*, init_db: bool = True) -> FastAPI:
    """创建并配置 FastAPI 应用。

    :param init_db: 是否在创建时初始化数据库（创建目录、建表、建索引）。
        测试里会传入独立的 DB 路径，因此保留这个开关。
    """
    configure_logging()
    logger = logging.getLogger("calculator.app")

    application = FastAPI(
        title="前后端分离计算器系统 · 后端 API",
        description=(
            "软件工程课程作业：前后端分离计算器系统的后端服务。\n\n"
            "**职责**：接收表达式 → 校验 → 解析 → 计算 → 存储历史 → 返回结果。\n\n"
            "所有接口返回统一信封：`{success, code, message, ...业务字段}`。"
        ),
        version=settings.version,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # ------------------------------------------------------------------ #
    # 1) CORS：前后端分离部署时，前端与后端不同源，必须显式放行
    # ------------------------------------------------------------------ #
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["*"],
    )

    # ------------------------------------------------------------------ #
    # 2) 全局异常处理器
    # ------------------------------------------------------------------ #
    register_exception_handlers(application)

    # ------------------------------------------------------------------ #
    # 3) 路由
    # ------------------------------------------------------------------ #
    for router in ROUTERS:
        application.include_router(router, prefix=API_PREFIX)

    # ------------------------------------------------------------------ #
    # 4) 根路径：给直接访问后端的人一个指引，而不是 404
    # ------------------------------------------------------------------ #
    @application.get("/", include_in_schema=False)
    async def root():
        return {
            "success": True,
            "code": 0,
            "message": "OK",
            "service": settings.app_name,
            "version": settings.version,
            "docs": "/docs",
            "apiPrefix": API_PREFIX,
        }

    # ------------------------------------------------------------------ #
    # 5) 数据库初始化
    # ------------------------------------------------------------------ #
    if init_db:
        path = init_database()
        logger.info("数据库已就绪：%s", path)

    logger.info("CORS 允许来源：%s", ", ".join(settings.cors_origins))
    return application


#: ASGI 入口，供 ``uvicorn app.main:app`` 使用
app = create_app()
