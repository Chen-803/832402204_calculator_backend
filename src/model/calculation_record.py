"""历史记录数据模型与数据访问对象（DAO）。

本模块是"业务逻辑"与"数据库"之间唯一的桥梁：
    * :class:`CalculationRecord` 是记录的领域对象；
    * 其余函数是数据访问方法（增 / 查 / 改 / 删 / 统计）。

安全约定：**所有** SQL 都使用参数化查询（``?`` 占位符），
绝不通过字符串拼接把用户输入放进 SQL，从根本上杜绝 SQL 注入。
"""

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Tuple

from .database import get_connection

__all__ = [
    "CalculationRecord",
    "TIMESTAMP_FORMAT",
    "now_text",
    "insert_record",
    "find_by_id",
    "find_page",
    "delete_by_id",
    "delete_all",
    "update_favorite",
    "fetch_all_expressions",
    "fetch_time_range",
    "count_since",
    "count_all",
]

#: 数据库中的时间格式。
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"

#: 允许的排序方向（白名单，防止把用户输入直接拼进 ORDER BY）。
_SORT_DIRECTIONS = {"asc": "ASC", "desc": "DESC"}


@dataclass(frozen=True)
class CalculationRecord:
    """一条计算历史记录。

    Attributes:
        id: 主键。
        expression: 归一化后的表达式。
        result: 结果文本（保留完整精度）。
        created_at: 计算时间，形如 ``2026-10-01 10:20:00``。
        is_favorite: 是否被收藏。
    """

    id: int
    expression: str
    result: str
    created_at: str
    is_favorite: bool

    def to_dict(self) -> dict:
        """转换为接口返回结构。"""
        return {
            "id": self.id,
            "expression": self.expression,
            "result": self.result,
            "created_at": self.created_at,
            "is_favorite": int(self.is_favorite),
        }


def now_text() -> str:
    """返回当前本地时间的标准文本表示。"""
    return datetime.now().strftime(TIMESTAMP_FORMAT)


def _to_record(row: sqlite3.Row) -> CalculationRecord:
    """把数据库行映射为领域对象。"""
    return CalculationRecord(
        id=row["id"],
        expression=row["expression"],
        result=row["result"],
        created_at=row["created_at"],
        is_favorite=bool(row["is_favorite"]),
    )


def insert_record(expression: str, result: str, created_at: Optional[str] = None) -> CalculationRecord:
    """插入一条计算历史并返回落库后的完整记录。

    Args:
        expression: 归一化后的表达式。
        result: 结果文本。
        created_at: 计算时间，缺省取当前时间。

    Returns:
        带自增主键的记录对象。
    """
    connection = get_connection()
    timestamp = created_at or now_text()
    statement = (
        "INSERT INTO calculation_history (expression, result, created_at, is_favorite) "
        "VALUES (?, ?, ?, 0)"
    )
    if connection.is_postgres:
        # PostgreSQL 没有 lastrowid，用 RETURNING 直接拿回自增主键
        row = connection.execute(f"{statement} RETURNING id", (expression, result, timestamp)).fetchone()
        record_id = int(row["id"])
    else:
        cursor = connection.execute(statement, (expression, result, timestamp))
        record_id = int(cursor.lastrowid)
    connection.commit()
    created = find_by_id(record_id)
    if created is None:  # pragma: no cover - 理论上不可能
        raise sqlite3.DatabaseError("历史记录写入失败")
    return created


def find_by_id(record_id: int) -> Optional[CalculationRecord]:
    """按主键查询单条记录，不存在时返回 None。"""
    row = get_connection().execute(
        "SELECT id, expression, result, created_at, is_favorite "
        "FROM calculation_history WHERE id = ?",
        (record_id,),
    ).fetchone()
    return _to_record(row) if row else None


def _build_filters(
    keyword: Optional[str],
    start_date: Optional[str],
    end_date: Optional[str],
    favorite_only: bool,
    is_postgres: bool = False,
) -> Tuple[str, list]:
    """构造 WHERE 子句与参数列表。

    这里的每个条件都对应一个 ``?`` 占位符，用户输入只作为参数传入，
    不会成为 SQL 语法的一部分。

    Args:
        is_postgres: PostgreSQL 的 ``LIKE`` 区分大小写，而 SQLite 的 ``LIKE``
            对 ASCII 默认不区分大小写，因此这里为 PostgreSQL 改用 ``ILIKE``，
            保证两种数据库下的搜索体验一致。
    """
    clauses: List[str] = []
    parameters: List[object] = []
    like_operator = "ILIKE" if is_postgres else "LIKE"

    if keyword:
        clauses.append(f"(expression {like_operator} ? OR result {like_operator} ?)")
        pattern = f"%{keyword}%"
        parameters.extend([pattern, pattern])

    if start_date:
        clauses.append("created_at >= ?")
        parameters.append(f"{start_date} 00:00:00")

    if end_date:
        clauses.append("created_at <= ?")
        parameters.append(f"{end_date} 23:59:59")

    if favorite_only:
        clauses.append("is_favorite = 1")

    where_sql = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    return where_sql, parameters


def find_page(
    page: int = 1,
    page_size: int = 10,
    keyword: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    favorite_only: bool = False,
    sort: str = "desc",
) -> Tuple[List[CalculationRecord], int]:
    """分页查询历史记录。

    Args:
        page: 页码，从 1 开始。
        page_size: 每页条数。
        keyword: 关键字，同时匹配表达式与结果。
        start_date: 起始日期 ``YYYY-MM-DD``（含当天）。
        end_date: 结束日期 ``YYYY-MM-DD``（含当天）。
        favorite_only: 是否只看收藏。
        sort: 排序方向，``asc`` / ``desc``。

    Returns:
        ``(当前页记录列表, 满足条件的总条数)``。
    """
    direction = _SORT_DIRECTIONS.get((sort or "desc").lower(), "DESC")
    connection = get_connection()
    where_sql, parameters = _build_filters(
        keyword, start_date, end_date, favorite_only, connection.is_postgres
    )

    total = int(
        connection.execute(
            f"SELECT COUNT(*) AS total FROM calculation_history{where_sql}", parameters
        ).fetchone()["total"]
    )

    offset = (page - 1) * page_size
    rows = connection.execute(
        f"SELECT id, expression, result, created_at, is_favorite FROM calculation_history"
        f"{where_sql} ORDER BY created_at {direction}, id {direction} LIMIT ? OFFSET ?",
        parameters + [page_size, offset],
    ).fetchall()

    return [_to_record(row) for row in rows], total


def delete_by_id(record_id: int) -> bool:
    """按主键删除一条记录。

    Returns:
        True 表示确实删除了 1 行；False 表示该记录不存在。
    """
    connection = get_connection()
    cursor = connection.execute("DELETE FROM calculation_history WHERE id = ?", (record_id,))
    connection.commit()
    return cursor.rowcount > 0


def delete_all() -> int:
    """清空全部历史记录。

    Returns:
        被删除的行数。
    """
    connection = get_connection()
    cursor = connection.execute("DELETE FROM calculation_history")
    connection.commit()
    return cursor.rowcount


def update_favorite(record_id: int, is_favorite: bool) -> Optional[CalculationRecord]:
    """更新收藏状态。

    Returns:
        更新后的记录；记录不存在时返回 None。
    """
    connection = get_connection()
    cursor = connection.execute(
        "UPDATE calculation_history SET is_favorite = ? WHERE id = ?",
        (1 if is_favorite else 0, record_id),
    )
    connection.commit()
    if cursor.rowcount == 0:
        return None
    return find_by_id(record_id)


def fetch_all_expressions() -> List[str]:
    """取出全部表达式文本（供统计模块分析运算符使用）。"""
    rows = get_connection().execute("SELECT expression FROM calculation_history").fetchall()
    return [row["expression"] for row in rows]


def fetch_time_range() -> Tuple[Optional[str], Optional[str]]:
    """返回历史记录的首次与最近一次计算时间。"""
    row = get_connection().execute(
        "SELECT MIN(created_at) AS first_at, MAX(created_at) AS last_at FROM calculation_history"
    ).fetchone()
    if not row:
        return None, None
    return row["first_at"], row["last_at"]


def count_since(moment: str) -> int:
    """统计某个时间点之后的记录条数。"""
    row = get_connection().execute(
        "SELECT COUNT(*) AS total FROM calculation_history WHERE created_at >= ?", (moment,)
    ).fetchone()
    return int(row["total"])


def count_all() -> int:
    """统计历史记录总条数。"""
    row = get_connection().execute(
        "SELECT COUNT(*) AS total FROM calculation_history"
    ).fetchone()
    return int(row["total"])


def count_favorites() -> int:
    """统计收藏记录条数。"""
    row = get_connection().execute(
        "SELECT COUNT(*) AS total FROM calculation_history WHERE is_favorite = 1"
    ).fetchone()
    return int(row["total"])
