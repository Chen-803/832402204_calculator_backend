"""计算历史业务服务层。

职责：
    * 参数校验（页码、每页条数、日期格式、关键字长度）；
    * 把数据访问层返回的领域对象整理成接口所需的响应结构；
    * 统计信息的计算（总数、今日、收藏数、最常用运算符等）。

说明：统计中的"运算符分布"由后端对表达式文本做一遍安全扫描得到，
不使用 ``eval``，也不依赖任何前端数据。
"""

import logging
import re
from datetime import datetime
from typing import Dict, List, Optional

from ..calculator.exceptions import ValidationError
from ..model import calculation_record as repository

__all__ = [
    "list_history",
    "get_record",
    "delete_record",
    "clear_history",
    "set_favorite",
    "statistics",
]

_LOGGER = logging.getLogger(__name__)

#: 日期筛选参数的格式。
_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")

#: 参与统计的二元运算符。
_BINARY_OPERATORS = ("+", "-", "*", "/", "%", "^")

#: 运算符的展示名称。
_OPERATOR_LABELS = {
    "+": "加法 +",
    "-": "减法 -",
    "*": "乘法 ×",
    "/": "除法 ÷",
    "%": "取模 %",
    "^": "幂运算 ^",
}

#: 可以作为"左操作数结尾"的字符：数字、右括号、阶乘符号。
_OPERAND_END_CHARACTERS = frozenset("0123456789)!.")


def _validate_date(value: Optional[str], field_name: str) -> Optional[str]:
    """校验 ``YYYY-MM-DD`` 形式的日期。"""
    if value in (None, ""):
        return None
    if not _DATE_PATTERN.match(value):
        raise ValidationError(f"参数 {field_name} 必须是 YYYY-MM-DD 格式的日期，当前为 '{value}'")
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise ValidationError(f"参数 {field_name} 不是合法日期：'{value}'") from exc
    return value


def _normalize_paging(page, page_size, default_page_size: int, max_page_size: int):
    """把分页参数转换成整数并做范围校验。"""
    try:
        page_number = int(page) if page not in (None, "") else 1
    except (TypeError, ValueError) as exc:
        raise ValidationError("参数 page 必须是整数") from exc

    try:
        size = int(page_size) if page_size not in (None, "") else default_page_size
    except (TypeError, ValueError) as exc:
        raise ValidationError("参数 page_size 必须是整数") from exc

    if page_number < 1:
        raise ValidationError("参数 page 必须大于等于 1")
    if size < 1 or size > max_page_size:
        raise ValidationError(f"参数 page_size 的取值范围是 1 ~ {max_page_size}")
    return page_number, size


def count_operators(expression: str) -> Dict[str, int]:
    """统计表达式中二元运算符的出现次数。

    判断规则：当运算符前面的最近一个非空白字符是"数字 / 右括号 / 小数点 / 阶乘"
    时，它才是二元运算符；否则视为一元正负号（例如 ``-5+8`` 中的 ``-``）或
    科学计数法的指数符号（例如 ``1e-3`` 中的 ``-``）。

    Args:
        expression: 已经归一化的表达式。

    Returns:
        运算符到出现次数的映射，只包含出现过的运算符。
    """
    counts: Dict[str, int] = {}
    previous_meaningful = ""
    for character in expression:
        if character.isspace():
            continue
        if character in _BINARY_OPERATORS and previous_meaningful in _OPERAND_END_CHARACTERS:
            counts[character] = counts.get(character, 0) + 1
        previous_meaningful = character
    return counts


def list_history(
    page=1,
    page_size=None,
    keyword: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    favorite_only=False,
    sort: str = "desc",
    default_page_size: int = 10,
    max_page_size: int = 100,
) -> dict:
    """分页查询计算历史。

    Returns:
        ``{"items": [...], "total": n, "page": p, "page_size": s, "total_pages": t}``
    """
    page_number, size = _normalize_paging(page, page_size, default_page_size, max_page_size)
    start = _validate_date(start_date, "start_date")
    end = _validate_date(end_date, "end_date")
    if start and end and start > end:
        raise ValidationError("起始日期不能晚于结束日期")

    clean_keyword = (keyword or "").strip()
    if len(clean_keyword) > 50:
        raise ValidationError("搜索关键字最长 50 个字符")

    favorite = str(favorite_only).strip().lower() in ("1", "true", "yes", "on")
    records, total = repository.find_page(
        page=page_number,
        page_size=size,
        keyword=clean_keyword or None,
        start_date=start,
        end_date=end,
        favorite_only=favorite,
        sort=sort,
    )

    total_pages = (total + size - 1) // size if total else 0
    return {
        "items": [record.to_dict() for record in records],
        "total": total,
        "page": page_number,
        "page_size": size,
        "total_pages": total_pages,
    }


def get_record(record_id: int):
    """查询单条历史记录，不存在时返回 None。"""
    return repository.find_by_id(record_id)


def delete_record(record_id: int) -> bool:
    """删除指定历史记录。

    Returns:
        True 表示删除成功；False 表示记录不存在。
    """
    deleted = repository.delete_by_id(record_id)
    if deleted:
        _LOGGER.info("删除历史记录 ID=%s", record_id)
    return deleted


def clear_history() -> int:
    """清空全部历史记录，返回删除条数。"""
    deleted = repository.delete_all()
    _LOGGER.info("清空历史记录，共删除 %s 条", deleted)
    return deleted


def set_favorite(record_id: int, is_favorite: Optional[bool]):
    """设置或切换收藏状态。

    Args:
        record_id: 记录 ID。
        is_favorite: 目标状态；传 None 表示在现有状态上取反。

    Returns:
        更新后的记录；记录不存在时返回 None。
    """
    current = repository.find_by_id(record_id)
    if current is None:
        return None
    target = (not current.is_favorite) if is_favorite is None else bool(is_favorite)
    return repository.update_favorite(record_id, target)


def statistics() -> dict:
    """汇总计算统计信息（扩展功能）。"""
    distribution: Dict[str, int] = {}
    for expression in repository.fetch_all_expressions():
        for operator, count in count_operators(expression).items():
            distribution[operator] = distribution.get(operator, 0) + count

    ordered = dict(sorted(distribution.items(), key=lambda item: (-item[1], item[0])))
    most_used = next(iter(ordered), None)
    first_at, last_at = repository.fetch_time_range()
    today_prefix = datetime.now().strftime("%Y-%m-%d")

    return {
        "total": repository.count_all(),
        "today": repository.count_since(f"{today_prefix} 00:00:00"),
        "favorite_count": repository.count_favorites(),
        "most_used_operator": most_used,
        "most_used_operator_label": _OPERATOR_LABELS.get(most_used) if most_used else None,
        "operator_distribution": ordered,
        "operator_total": sum(ordered.values()),
        "first_calculation_at": first_at,
        "last_calculation_at": last_at,
    }
