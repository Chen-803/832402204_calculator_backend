"""计算历史的数据访问层（Repository）。

**整个项目里唯一出现 SQL 的地方。** Service 层只调用这里的方法，
不直接接触 ``sqlite3``，因此将来把 SQLite 换成 MySQL 时，
只需要重写本文件，业务代码零改动。

SQL 注入防护
------------
所有涉及用户输入的语句一律使用**参数化占位符** ``?``，绝不拼接字符串。
例如搜索用 ``LIKE ?`` 配合 ``f"%{keyword}%"`` 作为参数传入，
即使用户输入 ``' OR 1=1 --`` 也只会被当成普通搜索词。
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta

from ..config import settings
from ..model.entities import HistoryRecord
from .database import get_connection

#: 允许的排序方向，白名单校验，防止把 ORDER BY 变成注入点
_ALLOWED_ORDERS = {"asc": "ASC", "desc": "DESC"}


class HistoryRepository:
    """``calculation_history`` 表的读写封装。"""

    def __init__(self, db_path: str | None = None) -> None:
        self._db_path = db_path

    # ------------------------------------------------------------------ #
    # 写入
    # ------------------------------------------------------------------ #
    def insert(
        self,
        *,
        expression: str,
        normalized_expression: str,
        result: str,
        angle_mode: str,
        elapsed_ms: float,
        created_at: str,
    ) -> int:
        """插入一条计算历史，返回新记录的 ID。

        使用 ``cursor.lastrowid`` 拿到自增主键，避免再查一次数据库。
        """
        sql = (
            "INSERT INTO calculation_history "
            "(expression, normalized_expression, result, angle_mode, elapsed_ms, favorite, created_at) "
            "VALUES (?, ?, ?, ?, ?, 0, ?)"
        )
        with get_connection(self._db_path) as conn:
            cursor = conn.execute(
                sql,
                (expression, normalized_expression, result, angle_mode, elapsed_ms, created_at),
            )
            return int(cursor.lastrowid or 0)

    # ------------------------------------------------------------------ #
    # 查询
    # ------------------------------------------------------------------ #
    def find_by_id(self, record_id: int) -> HistoryRecord | None:
        """按主键查询单条记录。"""
        sql = "SELECT * FROM calculation_history WHERE id = ?"
        with get_connection(self._db_path) as conn:
            row = conn.execute(sql, (record_id,)).fetchone()
        return HistoryRecord.from_row(row) if row else None

    def find_page(
        self,
        *,
        keyword: str = "",
        page: int = 1,
        page_size: int = 10,
        only_favorite: bool = False,
        order: str = "desc",
    ) -> list[HistoryRecord]:
        """分页查询历史。

        :param keyword: 表达式 / 结果的模糊搜索词，空串表示不过滤
        :param page: 页码，从 1 开始
        :param page_size: 每页条数
        :param only_favorite: 是否只看收藏
        :param order: ``asc`` 或 ``desc``
        """
        where_sql, params = self._build_where(keyword, only_favorite)
        direction = _ALLOWED_ORDERS.get(order.lower(), "DESC")
        offset = max(page - 1, 0) * page_size

        # 排序时用 created_at 优先、id 兜底，避免同一秒内写入的多条记录顺序抖动
        sql = (
            f"SELECT * FROM calculation_history {where_sql} "
            f"ORDER BY created_at {direction}, id {direction} "
            "LIMIT ? OFFSET ?"
        )
        with get_connection(self._db_path) as conn:
            rows = conn.execute(sql, (*params, page_size, offset)).fetchall()
        return [HistoryRecord.from_row(row) for row in rows]

    def count(self, *, keyword: str = "", only_favorite: bool = False) -> int:
        """统计满足条件的记录总数（用于算总页数）。"""
        where_sql, params = self._build_where(keyword, only_favorite)
        sql = f"SELECT COUNT(*) AS total FROM calculation_history {where_sql}"
        with get_connection(self._db_path) as conn:
            row = conn.execute(sql, params).fetchone()
        return int(row["total"]) if row else 0

    @staticmethod
    def _build_where(keyword: str, only_favorite: bool) -> tuple[str, tuple[object, ...]]:
        """构造 WHERE 子句与参数列表。

        ``LIKE`` 的转义：把用户输入里的 ``%`` 和 ``_`` 用 ``ESCAPE`` 转义掉，
        否则用户搜 ``%`` 会匹配到所有记录，语义上不直观。
        """
        conditions: list[str] = []
        params: list[object] = []

        if keyword:
            escaped = keyword.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            pattern = f"%{escaped}%"
            conditions.append(
                "(expression LIKE ? ESCAPE '\\' OR result LIKE ? ESCAPE '\\')"
            )
            params.extend([pattern, pattern])

        if only_favorite:
            conditions.append("favorite = 1")

        if not conditions:
            return "", ()
        return "WHERE " + " AND ".join(conditions), tuple(params)

    # ------------------------------------------------------------------ #
    # 删除 / 更新
    # ------------------------------------------------------------------ #
    def delete_by_id(self, record_id: int) -> int:
        """删除指定记录。

        :returns: 实际删除的行数（0 表示记录不存在）
        """
        sql = "DELETE FROM calculation_history WHERE id = ?"
        with get_connection(self._db_path) as conn:
            cursor = conn.execute(sql, (record_id,))
            return int(cursor.rowcount)

    def delete_all(self) -> int:
        """清空全部历史。

        :returns: 实际删除的行数
        """
        with get_connection(self._db_path) as conn:
            cursor = conn.execute("DELETE FROM calculation_history")
            return int(cursor.rowcount)

    def set_favorite(self, record_id: int, favorite: bool | None) -> HistoryRecord | None:
        """设置 / 切换收藏状态。

        :param favorite: ``True`` / ``False`` 表示设为指定值，``None`` 表示取反
        :returns: 更新后的记录；记录不存在时返回 ``None``
        """
        with get_connection(self._db_path) as conn:
            row = conn.execute(
                "SELECT * FROM calculation_history WHERE id = ?", (record_id,)
            ).fetchone()
            if row is None:
                return None

            current = bool(row["favorite"])
            target = (not current) if favorite is None else bool(favorite)
            conn.execute(
                "UPDATE calculation_history SET favorite = ? WHERE id = ?",
                (1 if target else 0, record_id),
            )
            updated = conn.execute(
                "SELECT * FROM calculation_history WHERE id = ?", (record_id,)
            ).fetchone()
        return HistoryRecord.from_row(updated) if updated else None

    # ------------------------------------------------------------------ #
    # 统计（扩展功能）
    # ------------------------------------------------------------------ #
    def count_total(self) -> int:
        """历史总条数。"""
        with get_connection(self._db_path) as conn:
            row = conn.execute("SELECT COUNT(*) AS c FROM calculation_history").fetchone()
        return int(row["c"]) if row else 0

    def count_favorite(self) -> int:
        """收藏条数。"""
        with get_connection(self._db_path) as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS c FROM calculation_history WHERE favorite = 1"
            ).fetchone()
        return int(row["c"]) if row else 0

    def count_since(self, since: str) -> int:
        """统计某个时间点之后（含）的记录数，用于"今日计算次数"。"""
        with get_connection(self._db_path) as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS c FROM calculation_history WHERE created_at >= ?",
                (since,),
            ).fetchone()
        return int(row["c"]) if row else 0

    def count_by_day(self, days: int = 7) -> list[tuple[str, int]]:
        """近 N 天的每日计算次数。

        :returns: ``[( '2026-10-05', 7 ), ...]``，按日期升序，缺失的日期补 0
        """
        today = datetime.now().date()
        start = today - timedelta(days=days - 1)
        sql = (
            "SELECT substr(created_at, 1, 10) AS day, COUNT(*) AS c "
            "FROM calculation_history WHERE created_at >= ? "
            "GROUP BY day ORDER BY day ASC"
        )
        with get_connection(self._db_path) as conn:
            rows = conn.execute(sql, (f"{start.isoformat()} 00:00:00",)).fetchall()

        counts = {row["day"]: int(row["c"]) for row in rows}
        return [
            ((start + timedelta(days=offset)).isoformat(),
             counts.get((start + timedelta(days=offset)).isoformat(), 0))
            for offset in range(days)
        ]

    def all_normalized_expressions(self, limit: int = 5000) -> list[str]:
        """取出近期若干条归一化表达式，供上层做运算符使用统计。

        这里把 SQL 限制在"只取一列 + 有上限"，避免历史表很大时把内存打满。
        """
        sql = (
            "SELECT normalized_expression FROM calculation_history "
            "ORDER BY id DESC LIMIT ?"
        )
        with get_connection(self._db_path) as conn:
            rows = conn.execute(sql, (limit,)).fetchall()
        return [row["normalized_expression"] or "" for row in rows]

    def recent_expressions(self, limit: int = 500) -> list[str]:
        """取出近期若干条原始表达式，供"最常用表达式"统计使用。"""
        sql = "SELECT expression FROM calculation_history ORDER BY id DESC LIMIT ?"
        with get_connection(self._db_path) as conn:
            rows = conn.execute(sql, (limit,)).fetchall()
        return [row["expression"] for row in rows]


def is_database_available(db_path: str | None = None) -> bool:
    """探测数据库是否可用（健康检查用）。"""
    try:
        with get_connection(db_path or settings.db_path) as conn:
            conn.execute("SELECT 1").fetchone()
        return True
    except sqlite3.Error:
        return False
