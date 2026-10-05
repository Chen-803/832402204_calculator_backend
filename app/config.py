"""应用配置。

所有可变配置都集中在这里，并且都可以通过**环境变量**覆盖，
这样同一份代码在本地、测试、部署三种环境下都能用，不需要改代码。

环境变量一览
------------
=========================== ========================================== ==========================
变量名                       含义                                        默认值
=========================== ========================================== ==========================
``CALCULATOR_DB_PATH``       SQLite 数据库文件路径                        ``data/calculator.db``
``CALCULATOR_HOST``          监听地址                                     ``127.0.0.1``
``CALCULATOR_PORT``          监听端口                                     ``8000``
``CALCULATOR_CORS_ORIGINS``  允许跨域的来源，逗号分隔；``*`` 表示全部      见下
``CALCULATOR_LOG_LEVEL``     日志级别                                     ``INFO``
=========================== ========================================== ==========================
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

#: 后端项目根目录（``app/`` 的上一级）
BASE_DIR = Path(__file__).resolve().parent.parent

#: 默认允许跨域的前端来源。
#: 开发时 Vite 默认跑在 5173；同时放行 4173（``vite preview`` 默认端口）
#: 和 127.0.0.1 变体，避免因为主机名写法不同导致 CORS 失败。
DEFAULT_CORS_ORIGINS = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:4173",
    "http://127.0.0.1:4173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
)


def _env_str(name: str, default: str) -> str:
    value = os.environ.get(name)
    return value if value not in (None, "") else default


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw in (None, ""):
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _parse_origins(raw: str) -> tuple[str, ...]:
    """解析 CORS 来源配置。``*`` 表示允许任意来源。"""
    raw = raw.strip()
    if raw == "*":
        return ("*",)
    items = tuple(item.strip() for item in raw.split(",") if item.strip())
    return items or DEFAULT_CORS_ORIGINS


@dataclass(frozen=True)
class Settings:
    """运行时配置对象。"""

    app_name: str = "calculator-backend"
    version: str = "1.0.0"
    description: str = "前后端分离计算器系统 —— 后端服务"

    host: str = field(default_factory=lambda: _env_str("CALCULATOR_HOST", "127.0.0.1"))
    port: int = field(default_factory=lambda: _env_int("CALCULATOR_PORT", 8000))
    log_level: str = field(default_factory=lambda: _env_str("CALCULATOR_LOG_LEVEL", "INFO"))

    #: SQLite 数据库文件绝对路径
    db_path: Path = field(
        default_factory=lambda: Path(
            _env_str("CALCULATOR_DB_PATH", str(BASE_DIR / "data" / "calculator.db"))
        ).resolve()
    )

    cors_origins: tuple[str, ...] = field(
        default_factory=lambda: _parse_origins(
            _env_str("CALCULATOR_CORS_ORIGINS", ",".join(DEFAULT_CORS_ORIGINS))
        )
    )

    #: 历史记录每页最大条数，防止前端传入超大 pageSize 拖垮数据库
    max_page_size: int = 100


#: 全局唯一配置实例
settings = Settings()
