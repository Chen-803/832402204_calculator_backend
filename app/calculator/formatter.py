"""计算结果的展示格式化。

为什么需要单独一层
------------------
内部计算用 34 位有效数字的 :class:`decimal.Decimal`，但没人想看
``0.3333333333333333333333333333333333``。展示层负责把高精度值转成
"人能读、且不丢关键信息"的字符串，并且**保证同一个值永远格式化成同一个字符串**
（历史记录里存的、接口返回的、界面显示的三者一致）。

规则
----
============ ==================================================
数值范围      输出形式
============ ==================================================
整数         精确整数，不做位数截断（``1000!`` 也能完整输出）
``|x| < 1e-12`` 科学计数法，12 位有效数字
其它小数      四舍五入到最多 12 位小数，去掉尾随 0
``|x| >= 1e16`` 且非整数  科学计数法
============ ==================================================

JSON 里另有一个 ``result`` 数值字段，由 :func:`to_json_number` 生成；
它可能是 ``None``（数值超出 double 范围），所以**前端应优先使用 ``resultText``**。
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

#: 常规小数最多展示的小数位数
MAX_DISPLAY_DECIMALS = 12

#: 小于该绝对值改用科学计数法
SMALL_THRESHOLD = Decimal("1e-12")

#: 大于该绝对值且非整数时改用科学计数法
LARGE_THRESHOLD = Decimal("1e16")

#: float（JSON number）能安全表示的上界
_JSON_SAFE_LIMIT = Decimal("1e308")


def _to_scientific(value: Decimal, significant_digits: int = 12) -> str:
    """转成 ``1.234e-15`` 形式的科学计数法字符串，尾数去掉多余的 0。"""
    text = format(value, f".{significant_digits - 1}e")
    mantissa, _, exponent = text.partition("e")
    mantissa = mantissa.rstrip("0").rstrip(".")
    if mantissa in ("", "-", "+"):
        mantissa = "0"
    return f"{mantissa}e{int(exponent)}"


def format_decimal(value: Decimal) -> str:
    """把 :class:`Decimal` 格式化成展示字符串。

    :param value: 计算结果
    :raises ArithmeticError: 传入非有限值（理论上求值阶段已拦截）
    """
    if not value.is_finite():
        raise ArithmeticError("无法格式化非有限数值")

    if value == 0:
        return "0"

    magnitude = abs(value)

    # 1) 精确整数：完整输出，不截断位数
    #    注意必须先 to_integral_value() 再格式化：
    #    Decimal('1.0') 与 Decimal('1') 数值相等，但 format(Decimal('1.0'), 'f')
    #    会输出 '1.0'。三角函数等经由 float 回来的结果常常带尾随 .0，
    #    不归一化就会出现 "tan(45) = 1.0" 这种不整洁的展示。
    if value == value.to_integral_value():
        return format(value.to_integral_value(), "f")

    # 2) 极小值：科学计数法
    if magnitude < SMALL_THRESHOLD:
        return _to_scientific(value)

    # 3) 巨大且非整数：科学计数法
    if magnitude >= LARGE_THRESHOLD:
        return _to_scientific(value)

    # 4) 常规小数：保留最多 12 位小数，去掉尾随 0
    quantum = Decimal(1).scaleb(-MAX_DISPLAY_DECIMALS)
    try:
        rounded = value.quantize(quantum, rounding="ROUND_HALF_UP")
    except InvalidOperation:  # pragma: no cover - 已被上面的范围判断覆盖
        return _to_scientific(value)

    if rounded == rounded.to_integral_value():
        return format(rounded.to_integral_value(), "f")
    return format(rounded.normalize(), "f")


def to_json_number(value: Decimal) -> float | None:
    """把 :class:`Decimal` 转成 JSON 里可安全序列化的 ``float``。

    :returns: 有限 double 时返回值；超出 double 范围时返回 ``None``，
              此时调用方应依赖 ``resultText`` 字段。
    """
    if abs(value) > _JSON_SAFE_LIMIT:
        return None
    try:
        result = float(value)
    except (OverflowError, ValueError):  # pragma: no cover
        return None
    if result != result or result in (float("inf"), float("-inf")):  # NaN / Inf
        return None
    return result
