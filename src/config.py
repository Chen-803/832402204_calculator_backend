"""后端运行配置。

所有可变参数都支持通过环境变量覆盖，做到"同一份代码，多种环境可跑"：

======================= ========================= ============================
环境变量                含义                      默认值
======================= ========================= ============================
``CALC_HOST``           监听地址                   ``127.0.0.1``
``CALC_PORT``           监听端口                   ``8000``
``CALC_DEBUG``          是否开启调试模式           ``false``
``CALC_DB_PATH``        SQLite 数据库文件路径       ``<项目根>/data/calculator.db``
``DATABASE_URL``        PostgreSQL 连接串          未设置（即使用 SQLite）
``CALC_ALLOWED_ORIGIN`` 允许跨域的前端来源         ``*``
``CALC_MAX_PAGE_SIZE``  历史分页最大条数           ``100``
======================= ========================= ============================

**数据库是怎么选的**：
    设置了 ``DATABASE_URL`` -> 使用 PostgreSQL；
    没有设置 -> 使用内置的 SQLite 单文件数据库。
这样本地开发和"永久部署到云平台"用的是同一套代码，业务逻辑一行都不用改。
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

#: 后端项目根目录（本文件位于 ``<root>/src/config.py``）。
PROJECT_ROOT = Path(__file__).resolve().parent.parent

#: 数据库类型标识。
DIALECT_SQLITE = "sqlite"
DIALECT_POSTGRESQL = "postgresql"

__all__ = [
    "Config",
    "load_config",
    "PROJECT_ROOT",
    "DIALECT_SQLITE",
    "DIALECT_POSTGRESQL",
]


def _as_bool(value: Optional[str], default: bool = False) -> bool:
    """把环境变量字符串解析成布尔值。"""
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def _as_int(value: Optional[str], default: int) -> int:
    """把环境变量字符串解析成整数，非法时回退默认值。"""
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


@dataclass
class Config:
    """应用配置对象。"""

    host: str = "127.0.0.1"
    port: int = 8000
    debug: bool = False
    database_path: str = field(default_factory=lambda: str(PROJECT_ROOT / "data" / "calculator.db"))
    database_url: Optional[str] = None
    allowed_origin: str = "*"
    max_page_size: int = 100
    default_page_size: int = 10
    service_name: str = "calculator-backend"
    service_version: str = "1.0.0"

    @property
    def normalized_database_url(self) -> Optional[str]:
        """规范化 PostgreSQL 连接串。

        Render / Heroku 等平台习惯给出 ``postgres://`` 前缀，
        而 psycopg 只认 ``postgresql://``，这里统一转换。
        """
        if not self.database_url:
            return None
        url = self.database_url.strip()
        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://"):]
        return url or None

    @property
    def dialect(self) -> str:
        """当前生效的数据库类型：``sqlite`` 或 ``postgresql``。"""
        return DIALECT_POSTGRESQL if self.normalized_database_url else DIALECT_SQLITE

    @property
    def database_uri(self) -> str:
        """用于日志展示的数据库标识（会隐去连接串里的密码）。"""
        url = self.normalized_database_url
        if not url:
            return self.database_path
        if "@" in url:
            scheme, _, remainder = url.partition("://")
            return f"{scheme}://***@{remainder.split('@', 1)[-1]}"
        return url

    def ensure_database_directory(self) -> None:
        """确保 SQLite 数据库文件所在目录存在（PostgreSQL 模式无需处理）。"""
        if self.dialect == DIALECT_SQLITE:
            Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)


def load_config() -> Config:
    """从环境变量加载配置。"""
    return Config(
        host=os.environ.get("CALC_HOST", "127.0.0.1"),
        port=_as_int(os.environ.get("CALC_PORT"), 8000),
        debug=_as_bool(os.environ.get("CALC_DEBUG"), False),
        database_path=os.environ.get(
            "CALC_DB_PATH", str(PROJECT_ROOT / "data" / "calculator.db")
        ),
        database_url=os.environ.get("DATABASE_URL") or None,
        allowed_origin=os.environ.get("CALC_ALLOWED_ORIGIN", "*"),
        max_page_size=_as_int(os.environ.get("CALC_MAX_PAGE_SIZE"), 100),
    )
