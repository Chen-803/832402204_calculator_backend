"""SQLite 数据库连接与建表。

技术选型说明
------------
作业没有限制数据库类型。这里选择 **SQLite**，原因：

1. **零安装**：数据库就是项目目录下的一个 ``.db`` 文件，助教 ``git clone``
   之后不需要装 MySQL、建用户、配密码，``python run.py`` 直接跑起来；
2. **依赖标准库**：Python 自带 ``sqlite3``，不需要 ORM、不需要驱动，
   项目依赖只有 FastAPI 一个家族，符合"不应不必要地依赖特定本地环境"的要求；
3. **确实是"后端数据库"**：数据存在服务器进程的文件系统上，
   关浏览器、刷新页面、重启前端都不会丢，满足作业"不得只依赖前端缓存"的要求。

为了将来能平滑迁移到 MySQL / PostgreSQL，所有 SQL 都收敛在
:mod:`app.repository.history_repository` 里，业务层不写 SQL。
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from ..config import settings

#: 当前数据库结构版本，写入 ``schema_meta`` 表，便于将来做迁移。
SCHEMA_VERSION = 1

#: 建表语句。使用 ``IF NOT EXISTS``，保证初次运行与重复运行都安全。
SCHEMA_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS schema_meta (
        key   TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS calculation_history (
        id                    INTEGER PRIMARY KEY AUTOINCREMENT,
        expression            TEXT    NOT NULL,
        normalized_expression TEXT    NOT NULL DEFAULT '',
        result                TEXT    NOT NULL,
        angle_mode            TEXT    NOT NULL DEFAULT 'rad',
        elapsed_ms            REAL    NOT NULL DEFAULT 0,
        favorite              INTEGER NOT NULL DEFAULT 0,
        created_at            TEXT    NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_history_created_at ON calculation_history (created_at DESC, id DESC)",
    "CREATE INDEX IF NOT EXISTS idx_history_favorite ON calculation_history (favorite)",
)


def _ensure_parent_dir(path: Path) -> None:
    """确保数据库文件所在目录存在（首次运行时 ``data/`` 目录可能还不存在）。"""
    path.parent.mkdir(parents=True, exist_ok=True)


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    """创建一个新的数据库连接。

    每次调用都新建连接，是因为 FastAPI 会把同步的路由函数丢到线程池里执行，
    而 ``sqlite3.Connection`` 默认不允许跨线程复用。SQLite 打开文件的开销极小，
    这种"每请求一连接"的做法在这个规模下完全够用，也彻底避开了并发问题。
    """
    path = db_path or settings.db_path
    _ensure_parent_dir(path)
    connection = sqlite3.connect(str(path), timeout=10.0)
    connection.row_factory = sqlite3.Row
    # 打开外键约束（当前表暂时没有外键，属于防御性设置）
    connection.execute("PRAGMA foreign_keys = ON")
    # WAL 模式：读写可以并发，避免查询历史时阻塞写入
    connection.execute("PRAGMA journal_mode = WAL")
    return connection


@contextmanager
def get_connection(db_path: Path | None = None) -> Iterator[sqlite3.Connection]:
    """上下文管理器：自动提交 / 回滚 / 关闭连接。

    用法::

        with get_connection() as conn:
            conn.execute("INSERT ...")

    正常退出时提交事务；抛异常时回滚，保证不会写入半截数据。
    """
    connection = connect(db_path)
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def init_database(db_path: Path | None = None) -> Path:
    """初始化数据库：创建目录、建表、建索引、写入结构版本。

    :returns: 实际使用的数据库文件绝对路径
    """
    path = db_path or settings.db_path
    with get_connection(path) as conn:
        for statement in SCHEMA_STATEMENTS:
            conn.execute(statement)
        conn.execute(
            "INSERT INTO schema_meta (key, value) VALUES ('schema_version', ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (str(SCHEMA_VERSION),),
        )
    return path


def check_database(db_path: Path | None = None) -> bool:
    """健康检查：能否连上数据库并查到历史表。"""
    try:
        with get_connection(db_path) as conn:
            conn.execute("SELECT COUNT(*) FROM calculation_history").fetchone()
        return True
    except sqlite3.Error:
        return False
