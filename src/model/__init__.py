"""数据模型层：数据库连接、表结构与历史记录的增删改查。"""

from .calculation_record import (
    CalculationRecord,
    count_all,
    count_favorites,
    count_since,
    delete_all,
    delete_by_id,
    fetch_all_expressions,
    fetch_time_range,
    find_by_id,
    find_page,
    insert_record,
    now_text,
    update_favorite,
)
from .database import get_connection, init_database, register_teardown

__all__ = [
    "CalculationRecord",
    "get_connection",
    "init_database",
    "register_teardown",
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
    "count_favorites",
    "now_text",
]
