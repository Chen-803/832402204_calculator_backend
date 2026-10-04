"""数值精度与展示格式化工具。

计算器使用 :class:`decimal.Decimal` 而不是二进制浮点数做核心运算，
这样可以避免 ``0.1 + 0.2 = 0.30000000000000004`` 这类经典问题，
让计算器的表现与用户手算结果一致。

本模块提供三个能力：
1. 统一的十进制运算上下文（精度、指数范围）；
2. 把高精度 Decimal 格式化为人类可读字符串（``display_result``）；
3. 把 Decimal 转成 JSON 数字（``result`` 字段），保持与作业示例的兼容性。
"""

from contextlib import contextmanager
from decimal import Decimal, InvalidOperation, localcontext

from .exceptions import NumericOverflowError

__all__ = [
    "CALCULATION_PRECISION",
    "DISPLAY_PRECISION",
    "MAX_ADJUSTED_EXPONENT",
    "calculation_context",
    "format_decimal",
    "to_json_number",
    "parse_decimal",
]

#: 中间计算精度。取 50 位有效数字，远高于展示精度，避免累积误差。
CALCULATION_PRECISION = 50

#: 展示精度。15 位有效数字约等于双精度浮点的可靠位数，足够日常使用。
DISPLAY_PRECISION = 15

#: 结果数量级上限：10^5000 已经远超任何合理计算场景。
MAX_ADJUSTED_EXPONENT = 5000


@contextmanager
def calculation_context():
    """上下文管理器：在 ``with`` 块内启用高精度、大指数范围的 Decimal 环境。

    ``decimal.localcontext()`` 会把当前线程的上下文临时替换成副本，
    退出 ``with`` 时自动还原，因此不会污染其它请求的计算环境（线程安全的关键）。

    用法::

        with calculation_context():
            value = left / right
    """
    with localcontext() as ctx:
        ctx.prec = CALCULATION_PRECISION
        ctx.Emax = 999_999
        ctx.Emin = -999_999
        yield ctx


def parse_decimal(text: str) -> Decimal:
    """把字面量字符串安全地转换为 Decimal。

    Args:
        text: 已经过词法分析的数字字面量，例如 ``"3.14"``、``"1e-3"``。

    Returns:
        对应的 Decimal 对象。

    Raises:
        NumericOverflowError: 字面量本身无法解析或数值非法（NaN/Infinity）。
    """
    try:
        value = Decimal(text)
    except (InvalidOperation, ValueError) as exc:  # pragma: no cover - 词法层已保证
        raise NumericOverflowError(f"无法解析数字：{text}") from exc
    if not value.is_finite():
        raise NumericOverflowError(f"数字超出可表示范围：{text}")
    return value


def _round_for_display(value: Decimal) -> Decimal:
    """按展示精度对结果做一次四舍五入（DECIMAL128 风格的四舍五入）。"""
    with localcontext() as ctx:
        ctx.prec = DISPLAY_PRECISION
        try:
            return +value
        except InvalidOperation as exc:  # pragma: no cover - 防御性分支
            raise NumericOverflowError("计算结果无法格式化") from exc


def format_decimal(value: Decimal) -> str:
    """把 Decimal 格式化为人类可读字符串。

    规则：
        * 整数结果不带小数点（``20`` 而不是 ``20.0``）；
        * 去掉小数末尾多余的 0（``1.500`` -> ``1.5``）；
        * 数量级过大或过小时使用 ``1.23e20`` 形式的科学计数法；
        * ``-0`` 统一显示为 ``0``。

    Args:
        value: 待格式化的数值。

    Returns:
        可直接展示给用户的字符串。
    """
    if not value.is_finite():
        raise NumericOverflowError("计算结果超出可表示范围")

    rounded = _round_for_display(value)
    if rounded == 0:
        return "0"

    adjusted = rounded.adjusted()
    if -7 <= adjusted < 16:
        text = format(rounded, "f")
        if "." in text:
            text = text.rstrip("0").rstrip(".")
        return text or "0"

    # 数量级过大/过小时改用科学计数法，避免出现几百位数字。
    mantissa, _, exponent = format(rounded, "E").partition("E")
    if "." in mantissa:
        mantissa = mantissa.rstrip("0").rstrip(".")
    return f"{mantissa}e{int(exponent)}"


def to_json_number(value: Decimal):
    """把 Decimal 转成 JSON 数字，供 ``result`` 字段使用。

    作业示例中 ``result`` 是一个 JSON 数字（``20``），因此这里优先返回 ``int``，
    其次返回 ``float``。当数值大到 float 溢出时退化为字符串，
    保证接口始终返回合法 JSON（真实精度以 ``display_result`` 为准）。
    """
    rounded = _round_for_display(value)
    if rounded == rounded.to_integral_value():
        try:
            as_int = int(rounded)
        except (ValueError, OverflowError):  # pragma: no cover - 防御性分支
            return format_decimal(rounded)
        if abs(as_int) < 10 ** 15:
            return as_int

    try:
        as_float = float(rounded)
    except (ValueError, OverflowError):  # pragma: no cover - 防御性分支
        return format_decimal(rounded)
    if as_float in (float("inf"), float("-inf")):
        return format_decimal(rounded)
    return as_float
