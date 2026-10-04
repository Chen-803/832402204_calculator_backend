"""数据库连接管理与初始化：同一套代码同时支持 SQLite 与 PostgreSQL。

为什么要有两种数据库
--------------------
* **本地开发 / 课程演示**：使用 Python 标准库自带的 ``sqlite3``，
  单文件、零安装、随项目分发；
* **永久部署到云平台**：免费云平台的容器文件系统是临时的，每次重新部署都会清空，
  SQLite 文件会随之丢失。因此线上改用免费托管的 PostgreSQL（例如 Neon），
  把数据放在外部持久存储里。

两者的差异被收敛在本模块内部——上层（Repository / Service / Controller）
完全不感知用的是哪种数据库：

============================ ============================== ==========================
差异点                         SQLite                         PostgreSQL
============================ ============================== ==========================
驱动                          ``sqlite3``（标准库）            ``psycopg``（第三方）
占位符                        ``?``                          ``%s``
结果行                         ``sqlite3.Row``                ``dict_row``（字典）
自增主键回填                   ``cursor.lastrowid``           ``INSERT ... RETURNING id``
DDL 自增写法                   ``AUTOINCREMENT``              ``GENERATED ... AS IDENTITY``
大小写不敏感的模糊匹配          ``LIKE`` 天然不敏感             需要 ``ILIKE``
============================ ============================== ==========================

连接生命周期
------------
每个 HTTP 请求复用同一个连接（挂在 Flask 的 ``g`` 上），
请求结束由 ``teardown_appcontext`` 统一关闭，既避免频繁建连，也避免连接泄漏。
"""

import logging
import sqlite3
from pathlib import Path
from typing import Any, List, Optional, Sequence, Tuple

from flask import current_app, g

from ..config import Config, DIALECT_POSTGRESQL, DIALECT_SQLITE, load_config

__all__ = [
    "DatabaseConnection",
    "SCHEMA_FILE",
    "SCHEMA_FILE_POSTGRES",
    "translate_placeholders",
    "split_sql_statements",
    "schema_path_for",
    "resolve_database_target",
    "create_connection",
    "get_connection",
    "init_database",
    "close_connection",
    "register_teardown",
    "get_database_path",
]

_LOGGER = logging.getLogger(__name__)

_SQL_ROOT = Path(__file__).resolve().parent.parent.parent / "sql"

#: 建表脚本（SQLite）。
SCHEMA_FILE = _SQL_ROOT / "schema.sql"

#: 建表脚本（PostgreSQL）。
SCHEMA_FILE_POSTGRES = _SQL_ROOT / "schema_postgres.sql"


# ---------------------------------------------------------------------------
# SQL 方言适配
# ---------------------------------------------------------------------------
def translate_placeholders(sql: str) -> str:
    """把 ``?`` 占位符翻译成 psycopg 需要的 ``%s``。

    转换时会跳过字符串字面量与双引号标识符，并把字面量中的 ``%`` 转义为 ``%%``，
    因此 ``LIKE '%a?b%'`` 这类内容不会被误改。

    Args:
        sql: 使用 ``?`` 占位符的 SQL 语句。

    Returns:
        适用于 psycopg 的 SQL 语句。
    """
    output: List[str] = []
    index = 0
    length = len(sql)
    while index < length:
        char = sql[index]

        if char in ("'", '"'):
            quote = char
            output.append(char)
            index += 1
            while index < length:
                current = sql[index]
                output.append(current)
                if current == quote:
                    # 连续两个引号是转义，仍属于字面量内部
                    if index + 1 < length and sql[index + 1] == quote:
                        output.append(sql[index + 1])
                        index += 2
                        continue
                    index += 1
                    break
                index += 1
            continue

        if char == "?":
            output.append("%s")
            index += 1
            continue

        if char == "%":
            output.append("%%")
            index += 1
            continue

        output.append(char)
        index += 1
    return "".join(output)


def split_sql_statements(script: str) -> List[str]:
    """把建表脚本切分成一条条可单独执行的语句。

    psycopg 没有 ``executescript``，所以需要自己按分号切分；
    这里会先去掉 ``--`` 行注释，再忽略空语句。
    """
    without_comments = []
    for line in script.splitlines():
        if line.strip().startswith("--"):
            continue
        without_comments.append(line)
    text = "\n".join(without_comments)
    return [statement.strip() for statement in text.split(";") if statement.strip()]


def schema_path_for(dialect: str) -> Path:
    """按数据库类型返回对应的建表脚本路径。"""
    return SCHEMA_FILE_POSTGRES if dialect == DIALECT_POSTGRESQL else SCHEMA_FILE


# ---------------------------------------------------------------------------
# 连接封装
# ---------------------------------------------------------------------------
class DatabaseConnection:
    """对 ``sqlite3.Connection`` 与 ``psycopg.Connection`` 的统一封装。

    上层只需要 ``execute(sql, params)`` / ``commit()`` / ``close()`` 三个方法，
    占位符统一写 ``?``，其余方言差异由本类处理。
    """

    def __init__(self, raw: Any, dialect: str) -> None:
        self.raw = raw
        self.dialect = dialect

    @property
    def is_postgres(self) -> bool:
        """是否为 PostgreSQL 连接。"""
        return self.dialect == DIALECT_POSTGRESQL

    def execute(self, sql: str, parameters: Sequence = ()):
        """执行一条 SQL，返回游标。

        Args:
            sql: 使用 ``?`` 占位符的 SQL。
            parameters: 参数序列（用户输入只能出现在这里，绝不拼接进 SQL）。
        """
        arguments: Tuple = tuple(parameters or ())
        if self.is_postgres:
            cursor = self.raw.cursor()
            cursor.execute(translate_placeholders(sql), arguments)
            return cursor
        return self.raw.execute(sql, arguments)

    def commit(self) -> None:
        """提交事务（PostgreSQL 连接为 autocommit，此处是无害的空操作）。"""
        try:
            self.raw.commit()
        except Exception:  # noqa: BLE001 - autocommit 连接提交可能抛错，忽略即可
            pass

    def close(self) -> None:
        """关闭连接。"""
        self.raw.close()


def _connect_sqlite(database_path: str) -> sqlite3.Connection:
    """创建 SQLite 连接。"""
    Path(database_path).parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    # WAL 模式让读写并发更友好，多个请求同时读写时不易出现 "database is locked"
    connection.execute("PRAGMA journal_mode = WAL")
    return connection


def _connect_postgres(database_url: str):
    """创建 PostgreSQL 连接（需要安装 psycopg）。"""
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError as exc:  # pragma: no cover - 依赖缺失时的友好提示
        raise RuntimeError(
            "检测到 DATABASE_URL（PostgreSQL），但当前环境未安装 psycopg。"
            "请执行：pip install -r requirements-postgres.txt"
        ) from exc

    return psycopg.connect(
        database_url,
        row_factory=dict_row,   # 结果行是字典：row["id"] 可直接取字段
        autocommit=True,        # 与 SQLite 的显式 commit 语义等价，避免事务残留
        connect_timeout=10,
    )


# ---------------------------------------------------------------------------
# 目标解析与连接获取
# ---------------------------------------------------------------------------
def _app_config() -> Optional[Config]:
    """取当前应用的配置对象；不在应用上下文中时返回 None。"""
    try:
        return current_app.config.get("APP_CONFIG")
    except RuntimeError:
        return None


def resolve_database_target(
    database_path: Optional[str] = None,
    database_url: Optional[str] = None,
) -> Tuple[str, str]:
    """决定本次要连接哪个数据库。

    Args:
        database_path: 显式指定 SQLite 文件路径时，强制使用 SQLite。
        database_url: 显式指定 PostgreSQL 连接串时，强制使用 PostgreSQL。

    Returns:
        ``(dialect, target)``：SQLite 下 target 是文件路径，PostgreSQL 下是连接串。
    """
    if database_path:
        return DIALECT_SQLITE, database_path

    config = _app_config() or load_config()
    url = database_url if database_url is not None else config.normalized_database_url
    if url:
        return DIALECT_POSTGRESQL, url
    return DIALECT_SQLITE, config.database_path


def create_connection(
    database_path: Optional[str] = None,
    database_url: Optional[str] = None,
) -> DatabaseConnection:
    """按配置创建一个数据库连接。"""
    dialect, target = resolve_database_target(database_path, database_url)
    if dialect == DIALECT_POSTGRESQL:
        return DatabaseConnection(_connect_postgres(target), dialect)
    return DatabaseConnection(_connect_sqlite(target), dialect)


def get_database_path() -> str:
    """获取当前生效的数据库标识（SQLite 文件路径或隐去密码的连接串）。"""
    config = _app_config() or load_config()
    return config.database_uri


def get_connection() -> DatabaseConnection:
    """获取当前请求的数据库连接（不存在则创建并缓存到 ``g``）。"""
    if "db_connection" not in g:
        g.db_connection = create_connection()
    return g.db_connection


def close_connection(exception=None) -> None:
    """请求结束时关闭连接（由 Flask 调用）。"""
    connection = g.pop("db_connection", None)
    if connection is not None:
        connection.close()


def register_teardown(app) -> None:
    """把连接释放逻辑注册到应用上下文销毁钩子上。"""
    app.teardown_appcontext(close_connection)


def init_database(
    database_path: Optional[str] = None,
    database_url: Optional[str] = None,
) -> None:
    """执行建表脚本，确保表与索引存在（幂等操作）。

    Args:
        database_path: 可选的 SQLite 文件路径；给出时强制使用 SQLite。
        database_url: 可选的 PostgreSQL 连接串；给出时强制使用 PostgreSQL。
    """
    dialect, target = resolve_database_target(database_path, database_url)
    schema_sql = schema_path_for(dialect).read_text(encoding="utf-8")

    connection = create_connection(database_path, database_url)
    try:
        if connection.is_postgres:
            for statement in split_sql_statements(schema_sql):
                connection.execute(statement)
        else:
            connection.raw.executescript(schema_sql)
        connection.commit()
        _LOGGER.info("数据库初始化完成（%s）", dialect)
    finally:
        connection.close()
