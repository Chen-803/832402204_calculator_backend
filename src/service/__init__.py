"""业务服务层：计算用例与历史管理用例。"""

from .calculator_service import CalculationResult, calculate
from .history_service import (
    clear_history,
    delete_record,
    get_record,
    list_history,
    set_favorite,
    statistics,
)

__all__ = [
    "calculate",
    "CalculationResult",
    "list_history",
    "get_record",
    "delete_record",
    "clear_history",
    "set_favorite",
    "statistics",
]
