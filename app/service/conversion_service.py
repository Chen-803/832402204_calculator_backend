"""进制转换与单位换算服务（扩展功能）。

两个转换都在**后端**完成，前端只负责收集参数和展示结果，与作业
"核心逻辑在后端"的要求保持一致。

进制转换为什么不用 ``int(s, base)`` 就完事
------------------------------------------
因为要支持**小数**：``int("1F.8", 16)`` 直接报错。所以这里手写解析：

1. 按小数点拆成整数部分和小数部分；
2. 整数部分：按位权累加 ``Σ digit_i × base^(n-1-i)``；
3. 小数部分：按位权累加 ``Σ digit_i × base^-(i+1)``（用 ``Decimal`` 保证不丢精度）；
4. 反向转换：整数部分除基取余，小数部分乘基取整。

全程只对"白名单字符"做映射查表，**不做任何字符串到代码的求值**。
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from ..common.exceptions import InvalidConversionError
from ..calculator.errors import ErrorCode

#: 支持的数位字符（2..36 进制）
DIGITS = "0123456789abcdefghijklmnopqrstuvwxyz"

#: 小数部分最多转换的位数，防止无限循环（例如 0.1 在二进制下是无限小数）
MAX_FRACTION_DIGITS = 16

#: 单位类别定义。
#: ``factor`` 表示"1 个该单位等于多少个基准单位"，温度类别特殊处理。
UNIT_CATEGORIES: dict[str, dict[str, Any]] = {
    "length": {
        "name": "长度",
        "base": "m",
        "units": {
            "mm": ("毫米", 0.001), "cm": ("厘米", 0.01), "dm": ("分米", 0.1),
            "m": ("米", 1.0), "km": ("千米", 1000.0),
            "in": ("英寸", 0.0254), "ft": ("英尺", 0.3048), "yd": ("码", 0.9144),
            "mi": ("英里", 1609.344), "nmi": ("海里", 1852.0),
        },
    },
    "mass": {
        "name": "质量",
        "base": "kg",
        "units": {
            "mg": ("毫克", 1e-6), "g": ("克", 0.001), "kg": ("千克", 1.0),
            "t": ("吨", 1000.0), "oz": ("盎司", 0.028349523125),
            "lb": ("磅", 0.45359237), "jin": ("斤", 0.5), "liang": ("两", 0.05),
        },
    },
    "area": {
        "name": "面积",
        "base": "m2",
        "units": {
            "cm2": ("平方厘米", 1e-4), "m2": ("平方米", 1.0),
            "km2": ("平方千米", 1e6), "ha": ("公顷", 10000.0),
            "mu": ("亩", 666.6666666666666), "ft2": ("平方英尺", 0.09290304),
            "acre": ("英亩", 4046.8564224),
        },
    },
    "volume": {
        "name": "体积",
        "base": "l",
        "units": {
            "ml": ("毫升", 0.001), "l": ("升", 1.0), "m3": ("立方米", 1000.0),
            "cm3": ("立方厘米", 0.001), "gal": ("美制加仑", 3.785411784),
            "qt": ("美制夸脱", 0.946352946),
        },
    },
    "time": {
        "name": "时间",
        "base": "s",
        "units": {
            "ms": ("毫秒", 0.001), "s": ("秒", 1.0), "min": ("分钟", 60.0),
            "h": ("小时", 3600.0), "d": ("天", 86400.0),
            "wk": ("周", 604800.0), "yr": ("年(365天)", 31536000.0),
        },
    },
    "speed": {
        "name": "速度",
        "base": "m/s",
        "units": {
            "m/s": ("米/秒", 1.0), "km/h": ("千米/小时", 1 / 3.6),
            "mph": ("英里/小时", 0.44704), "kn": ("节", 0.5144444444444445),
            "ft/s": ("英尺/秒", 0.3048),
        },
    },
    "temperature": {
        "name": "温度",
        "base": "c",
        "units": {
            "c": ("摄氏度", 1.0), "f": ("华氏度", 1.0),
            "k": ("开尔文", 1.0),
        },
    },
    "data": {
        "name": "数据存储",
        "base": "B",
        "units": {
            "bit": ("比特", 0.125), "B": ("字节", 1.0),
            "KB": ("千字节", 1024.0), "MB": ("兆字节", 1024.0 ** 2),
            "GB": ("吉字节", 1024.0 ** 3), "TB": ("太字节", 1024.0 ** 4),
        },
    },
}


# ---------------------------------------------------------------------- #
# 进制转换
# ---------------------------------------------------------------------- #
def _digit_value(char: str) -> int:
    """把单个数位字符转成数值；非法字符返回 -1。"""
    lowered = char.lower()
    index = DIGITS.find(lowered)
    return index


def _parse_in_base(text: str, base: int) -> Decimal:
    """把 ``text`` 按 ``base`` 进制解析成 :class:`Decimal`。

    :raises InvalidConversionError: 出现非法字符或多个小数点时
    """
    raw = text.strip().replace(" ", "").replace("_", "")
    if not raw:
        raise InvalidConversionError("数值不能为空", ErrorCode.INVALID_BASE)

    negative = False
    if raw[0] in "+-":
        negative = raw[0] == "-"
        raw = raw[1:]
    if not raw:
        raise InvalidConversionError("数值不能只有符号", ErrorCode.INVALID_BASE)

    if raw.count(".") > 1:
        raise InvalidConversionError("数值中最多只能有一个小数点", ErrorCode.INVALID_BASE)

    integer_part, _, fraction_part = raw.partition(".")
    if not integer_part and not fraction_part:
        raise InvalidConversionError("数值格式不正确", ErrorCode.INVALID_BASE)

    # 整数部分：按位权累加
    total = Decimal(0)
    for char in integer_part:
        value = _digit_value(char)
        if value < 0 or value >= base:
            raise InvalidConversionError(
                f"字符 “{char}” 不是合法的 {base} 进制数位", ErrorCode.INVALID_BASE
            )
        total = total * base + value

    # 小数部分：按负位权累加，用 Decimal 保证精度
    if fraction_part:
        weight = Decimal(1)
        fraction = Decimal(0)
        for char in fraction_part:
            value = _digit_value(char)
            if value < 0 or value >= base:
                raise InvalidConversionError(
                    f"字符 “{char}” 不是合法的 {base} 进制数位", ErrorCode.INVALID_BASE
                )
            weight = weight / base
            fraction += weight * value
        total += fraction

    return -total if negative else total


def _format_in_base(value: Decimal, base: int) -> str:
    """把 :class:`Decimal` 按 ``base`` 进制格式化。

    整数部分用"除基取余"，小数部分用"乘基取整"，小数最多保留
    :data:`MAX_FRACTION_DIGITS` 位。
    """
    negative = value < 0
    value = abs(value)

    integer_part = int(value.to_integral_value(rounding="ROUND_FLOOR"))
    fraction_part = value - integer_part

    # 整数部分
    if integer_part == 0:
        integer_text = "0"
    else:
        digits: list[str] = []
        while integer_part > 0:
            integer_part, remainder = divmod(integer_part, base)
            digits.append(DIGITS[remainder].upper())
        integer_text = "".join(reversed(digits))

    # 小数部分
    fraction_text = ""
    if fraction_part > 0:
        chars: list[str] = []
        remainder = fraction_part
        for _ in range(MAX_FRACTION_DIGITS):
            if remainder == 0:
                break
            remainder *= base
            digit = int(remainder.to_integral_value(rounding="ROUND_FLOOR"))
            chars.append(DIGITS[digit].upper())
            remainder -= digit
        fraction_text = "".join(chars).rstrip("0")
        if fraction_text:
            fraction_text = "." + fraction_text

    text = f"{integer_text}{fraction_text}"
    return f"-{text}" if negative else text


def convert_base(value: str, from_base: int, to_base: int) -> dict[str, Any]:
    """进制转换。

    :param value: 数值文本，可带符号与小数点
    :param from_base: 源进制 2..36
    :param to_base: 目标进制 2..36
    :raises InvalidConversionError: 进制越界或数值与进制不匹配
    """
    if not 2 <= int(from_base) <= 36:
        raise InvalidConversionError("源进制必须在 2 到 36 之间", ErrorCode.INVALID_BASE)
    if not 2 <= int(to_base) <= 36:
        raise InvalidConversionError("目标进制必须在 2 到 36 之间", ErrorCode.INVALID_BASE)
    if len(value) > 64:
        raise InvalidConversionError("数值过长，最多 64 个字符", ErrorCode.INVALID_BASE)

    try:
        decimal_value = _parse_in_base(value, int(from_base))
    except InvalidOperation as exc:  # pragma: no cover - 防御性
        raise InvalidConversionError("数值解析失败", ErrorCode.INVALID_BASE) from exc

    output = _format_in_base(decimal_value, int(to_base))

    # 十进制形式用规范化字符串，去掉多余的尾随 0
    normalized = decimal_value.normalize()
    decimal_text = format(normalized, "f") if normalized != normalized.to_integral_value() \
        else str(normalized.to_integral_value())

    return {
        "input": value.strip(),
        "fromBase": int(from_base),
        "toBase": int(to_base),
        "output": output,
        "decimalValue": decimal_text,
    }


# ---------------------------------------------------------------------- #
# 单位换算
# ---------------------------------------------------------------------- #
def list_unit_categories() -> list[dict[str, Any]]:
    """列出所有单位类别与单位定义，供前端渲染下拉框。"""
    result: list[dict[str, Any]] = []
    for key, definition in UNIT_CATEGORIES.items():
        result.append({
            "key": key,
            "name": definition["name"],
            "base": definition["base"],
            "units": [
                {"key": unit_key, "name": unit_name}
                for unit_key, (unit_name, _) in definition["units"].items()
            ],
        })
    return result


def _convert_temperature(value: float, from_unit: str, to_unit: str) -> float:
    """温度换算。因为存在零点偏移，不能简单乘系数，必须走"先归一到摄氏度再展开"。"""
    # 先归一到摄氏度
    if from_unit == "c":
        celsius = value
    elif from_unit == "f":
        celsius = (value - 32.0) * 5.0 / 9.0
    elif from_unit == "k":
        celsius = value - 273.15
    else:  # pragma: no cover - 已由上层校验
        raise InvalidConversionError(f"不支持的温度单位：{from_unit}", ErrorCode.INVALID_UNIT)

    # 再从摄氏度展开到目标单位
    if to_unit == "c":
        return celsius
    if to_unit == "f":
        return celsius * 9.0 / 5.0 + 32.0
    if to_unit == "k":
        return celsius + 273.15
    raise InvalidConversionError(f"不支持的温度单位：{to_unit}", ErrorCode.INVALID_UNIT)  # pragma: no cover


def convert_unit(category: str, from_unit: str, to_unit: str, value: float) -> dict[str, Any]:
    """单位换算。

    :param category: 类别 key，例如 ``length``
    :param from_unit: 源单位 key
    :param to_unit: 目标单位 key
    :param value: 待换算数值
    :raises InvalidConversionError: 类别或单位不存在
    """
    definition = UNIT_CATEGORIES.get(category)
    if definition is None:
        raise InvalidConversionError(
            f"不支持的单位类别：{category}", ErrorCode.INVALID_UNIT
        )

    units: dict[str, tuple[str, float]] = definition["units"]
    if from_unit not in units:
        raise InvalidConversionError(
            f"类别「{definition['name']}」下不存在单位：{from_unit}", ErrorCode.INVALID_UNIT
        )
    if to_unit not in units:
        raise InvalidConversionError(
            f"类别「{definition['name']}」下不存在单位：{to_unit}", ErrorCode.INVALID_UNIT
        )

    if category == "temperature":
        output = _convert_temperature(value, from_unit, to_unit)
    else:
        # 先乘源单位系数归一到基准单位，再除以目标单位系数
        output = value * units[from_unit][1] / units[to_unit][1]

    return {
        "category": category,
        "from": from_unit,
        "to": to_unit,
        "value": value,
        "output": output,
        "outputText": _format_float(output),
    }


def _format_float(value: float) -> str:
    """把浮点结果转成"不刺眼"的字符串：去掉尾随 0，必要时用科学计数法。"""
    if value == 0:
        return "0"
    if abs(value) >= 1e16 or abs(value) < 1e-12:
        return f"{value:.12g}"
    text = f"{value:.12f}".rstrip("0").rstrip(".")
    return text or "0"
