"""数学常量与函数注册表。

设计说明
--------
把所有函数集中注册在一张表里，而不是写成 ``if name == 'sin': ... elif ...``：

1. 语法分析阶段就能校验函数名是否存在、参数个数对不对（错误提前暴露）；
2. 新增函数只需在 :data:`FUNCTIONS` 加一行，符合开闭原则；
3. 表本身就是一份"支持哪些函数"的文档。

精度说明
--------
- 加减乘除、幂、开方使用 :class:`decimal.Decimal`，避免二进制浮点误差；
- 三角函数、指数、对数等超越函数内部转 ``float`` 计算（标准库 ``math``），
  结果按 12 位小数做一次"整平"（见 :func:`clean_real`），
  这样 ``sin(180°)``、``log(1000, 10)`` 这类数学上应为整数/零的结果不会显示成
  ``1.2246467991473532e-16``、``2.9999999999999996``。
"""

from __future__ import annotations

import math
from decimal import Decimal, InvalidOperation
from typing import Callable

from .errors import DomainError, DivisionByZeroError, UnknownFunctionError

#: 常量表
CONSTANTS: dict[str, Decimal] = {
    "pi": Decimal("3.141592653589793238462643383279503"),
    "π": Decimal("3.141592653589793238462643383279503"),
    "e": Decimal("2.718281828459045235360287471352662"),
    "tau": Decimal("6.283185307179586476925286766559006"),
}

#: 阶乘参数上限：1000! 约 2568 位，计算耗时仍在毫秒级，再大就没有实际意义。
MAX_FACTORIAL_ARGUMENT = 1000

#: 幂运算指数上限，防止 ``2^999999999`` 之类的输入造成长时间占用。
MAX_EXPONENT = 100_000

#: 浮点结果"整平"到的小数位数
REAL_CLEAN_PLACES = 12


# ---------------------------------------------------------------------- #
# 内部工具
# ---------------------------------------------------------------------- #
def clean_real(value: float) -> Decimal:
    """把浮点计算结果整平后转回 :class:`Decimal`。

    做两件事：
    1. 四舍五入到 :data:`REAL_CLEAN_PLACES` 位小数，消除浮点尾数噪声；
    2. 把绝对值小于 ``1e-12`` 的值吸附为 0，避免 ``sin(180°)`` 输出 ``1.2e-16``。

    :param value: 浮点结果
    :raises DomainError: 结果为 NaN 或无穷大
    """
    if math.isnan(value):
        raise DomainError("计算结果不是实数")
    if math.isinf(value):
        raise DomainError("数值溢出，结果超出可表示范围")
    cleaned = round(value, REAL_CLEAN_PLACES)
    if cleaned == 0:
        return Decimal(0)
    return Decimal(repr(cleaned))


def to_float(value: Decimal) -> float:
    """Decimal → float，溢出时抛 :class:`DomainError`。"""
    try:
        return float(value)
    except (OverflowError, ValueError) as exc:  # pragma: no cover - 极端情况
        raise DomainError("数值超出可表示范围") from exc


def _require_args(name: str, args: list[Decimal], counts: tuple[int, ...]) -> None:
    """校验函数实参个数，个数不符时抛出语法错误。"""
    if len(args) not in counts:
        expected = " 或 ".join(str(c) for c in counts)
        from .errors import SyntaxError_

        raise SyntaxError_(f"函数 {name} 需要 {expected} 个参数，实际收到 {len(args)} 个")


def _to_degrees(rad: float) -> float:
    return math.degrees(rad)


def _to_radians(deg: float) -> float:
    return math.radians(deg)


# ---------------------------------------------------------------------- #
# 一元函数
# ---------------------------------------------------------------------- #
def _make_trig(name: str, fn: Callable[[float], float]) -> Callable:
    """构造三角函数实现，自动处理角度制（DEG/RAD）换算。"""

    def impl(args: list[Decimal], angle_mode: str) -> Decimal:
        _require_args(name, args, (1,))
        x = to_float(args[0])
        try:
            result = fn(_to_radians(x)) if angle_mode == "deg" else fn(x)
        except ValueError as exc:
            raise DomainError(f"{name} 的参数超出定义域") from exc
        return clean_real(result)

    return impl


def _make_inverse_trig(name: str, fn: Callable[[float], float]) -> Callable:
    """构造反三角函数实现，输出自动按角度制换算。"""

    def impl(args: list[Decimal], angle_mode: str) -> Decimal:
        _require_args(name, args, (1,))
        x = to_float(args[0])
        try:
            result = fn(x)
        except ValueError as exc:
            raise DomainError(f"{name} 的参数必须在 [-1, 1] 之间") from exc
        if angle_mode == "deg":
            result = _to_degrees(result)
        return clean_real(result)

    return impl


def _make_math1(name: str, fn: Callable[[float], float], domain_hint: str) -> Callable:
    """构造"实数一元函数"，把 ``math`` 的 ``ValueError`` 转成定义域错误。"""

    def impl(args: list[Decimal], angle_mode: str) -> Decimal:  # noqa: ARG001
        _require_args(name, args, (1,))
        x = to_float(args[0])
        try:
            result = fn(x)
        except ValueError as exc:
            raise DomainError(f"{name}：{domain_hint}") from exc
        except OverflowError as exc:
            raise DomainError("数值溢出，结果超出可表示范围") from exc
        return clean_real(result)

    return impl


def _sqrt_impl(args: list[Decimal], angle_mode: str) -> Decimal:  # noqa: ARG001
    """平方根。用 Decimal.sqrt() 保证 sqrt(4) 精确等于 2（而不是 2.0000000000000004）。"""
    _require_args("sqrt", args, (1,))
    x = args[0]
    if x < 0:
        raise DomainError("sqrt 的参数不能为负数")
    try:
        return +x.sqrt()
    except InvalidOperation as exc:  # pragma: no cover - 已由上面的判断覆盖
        raise DomainError("sqrt 的参数不能为负数") from exc


def _cbrt_impl(args: list[Decimal], angle_mode: str) -> Decimal:  # noqa: ARG001
    """立方根。负数也支持，因为实数域上负数有立方根。"""
    _require_args("cbrt", args, (1,))
    x = args[0]
    if x == 0:
        return Decimal(0)
    negative = x < 0
    magnitude = to_float(abs(x)) ** (1.0 / 3.0)
    result = clean_real(magnitude)
    return -result if negative else result


def _abs_impl(args: list[Decimal], angle_mode: str) -> Decimal:  # noqa: ARG001
    _require_args("abs", args, (1,))
    return abs(args[0])


def _floor_impl(args: list[Decimal], angle_mode: str) -> Decimal:  # noqa: ARG001
    _require_args("floor", args, (1,))
    return args[0].to_integral_value(rounding="ROUND_FLOOR")


def _ceil_impl(args: list[Decimal], angle_mode: str) -> Decimal:  # noqa: ARG001
    _require_args("ceil", args, (1,))
    return args[0].to_integral_value(rounding="ROUND_CEILING")


def _round_impl(args: list[Decimal], angle_mode: str) -> Decimal:  # noqa: ARG001
    """四舍五入。``round(x)`` 取整；``round(x, n)`` 保留 n 位小数。"""
    _require_args("round", args, (1, 2))
    if len(args) == 1:
        return args[0].to_integral_value(rounding="ROUND_HALF_UP")
    digits = int(args[1])
    if not -30 <= digits <= 30:
        raise DomainError("round 的位数必须在 -30 到 30 之间")
    exponent = Decimal(1).scaleb(-digits)
    return args[0].quantize(exponent, rounding="ROUND_HALF_UP")


def _sign_impl(args: list[Decimal], angle_mode: str) -> Decimal:  # noqa: ARG001
    _require_args("sign", args, (1,))
    x = args[0]
    return Decimal(0) if x == 0 else (Decimal(1) if x > 0 else Decimal(-1))


def _fact_impl(args: list[Decimal], angle_mode: str) -> Decimal:  # noqa: ARG001
    """阶乘。用 Python 原生大整数计算，保证结果完全精确。"""
    _require_args("fact", args, (1,))
    return factorial_of(args[0])


def factorial_of(value: Decimal) -> Decimal:
    """计算非负整数 ``value`` 的阶乘。

    :param value: 必须是非负整数
    :raises DomainError: 不是非负整数，或超过 :data:`MAX_FACTORIAL_ARGUMENT`
    """
    if value != value.to_integral_value():
        raise DomainError("阶乘只能作用于非负整数")
    if value < 0:
        raise DomainError("阶乘只能作用于非负整数")
    n = int(value)
    if n > MAX_FACTORIAL_ARGUMENT:
        raise DomainError(f"阶乘参数不能超过 {MAX_FACTORIAL_ARGUMENT}")
    return Decimal(math.factorial(n))


# ---------------------------------------------------------------------- #
# 二元 / 多元函数
# ---------------------------------------------------------------------- #
def _pow_impl(args: list[Decimal], angle_mode: str) -> Decimal:  # noqa: ARG001
    _require_args("pow", args, (2,))
    return power_of(args[0], args[1])


def power_of(base: Decimal, exponent: Decimal) -> Decimal:
    """幂运算 ``base ^ exponent``，统一处理溢出、定义域与除零。

    由 :data:`FUNCTIONS` 与求值器共用，保证 ``2^3`` 和 ``pow(2,3)`` 行为一致。
    """
    if exponent > MAX_EXPONENT or exponent < -MAX_EXPONENT:
        raise DomainError(f"指数绝对值不能超过 {MAX_EXPONENT}")
    if base == 0 and exponent < 0:
        raise DivisionByZeroError("0 不能作为负数次幂的底数")
    if base == 0 and exponent == 0:
        # 0^0 在数学上是未定式，但所有计算器与编程语言（含 Python 的 int 幂）
        # 都约定为 1；Decimal 默认会抛 InvalidOperation，这里显式给出约定值。
        return Decimal(1)
    try:
        return +((base) ** exponent)
    except InvalidOperation as exc:
        # 典型场景：(-8) ^ 0.5 —— 负数开偶次方，实数域无解
        raise DomainError("负数的非整数次幂不是实数（结果为复数，暂不支持）") from exc
    except ZeroDivisionError as exc:
        raise DivisionByZeroError() from exc
    except OverflowError as exc:
        raise DomainError("数值溢出，结果超出可表示范围") from exc


def _mod_impl(args: list[Decimal], angle_mode: str) -> Decimal:  # noqa: ARG001
    _require_args("mod", args, (2,))
    return modulo_of(args[0], args[1])


def modulo_of(left: Decimal, right: Decimal) -> Decimal:
    """取模。符号跟随被除数（与 C 语言 ``fmod``、Python ``math.fmod`` 一致）。"""
    if right == 0:
        raise DivisionByZeroError("取模的除数不能为 0")
    try:
        return +(left % right)
    except (InvalidOperation, ZeroDivisionError) as exc:  # pragma: no cover
        raise DivisionByZeroError("取模的除数不能为 0") from exc


def _log_impl(args: list[Decimal], angle_mode: str) -> Decimal:  # noqa: ARG001
    """对数。``log(x)`` 默认以 10 为底；``log(x, b)`` 以 b 为底。"""
    _require_args("log", args, (1, 2))
    x = args[0]
    if x <= 0:
        raise DomainError("对数的真数必须大于 0")
    if len(args) == 1:
        return clean_real(math.log10(to_float(x)))
    base = args[1]
    if base <= 0 or base == 1:
        raise DomainError("对数的底数必须大于 0 且不等于 1")
    return clean_real(math.log(to_float(x)) / math.log(to_float(base)))


def _ln_impl(args: list[Decimal], angle_mode: str) -> Decimal:  # noqa: ARG001
    _require_args("ln", args, (1,))
    if args[0] <= 0:
        raise DomainError("ln 的真数必须大于 0")
    return clean_real(math.log(to_float(args[0])))


def _log2_impl(args: list[Decimal], angle_mode: str) -> Decimal:  # noqa: ARG001
    _require_args("log2", args, (1,))
    if args[0] <= 0:
        raise DomainError("log2 的真数必须大于 0")
    return clean_real(math.log2(to_float(args[0])))


def _exp_impl(args: list[Decimal], angle_mode: str) -> Decimal:  # noqa: ARG001
    _require_args("exp", args, (1,))
    try:
        return clean_real(math.exp(to_float(args[0])))
    except OverflowError as exc:
        raise DomainError("exp 结果溢出") from exc


def _max_impl(args: list[Decimal], angle_mode: str) -> Decimal:  # noqa: ARG001
    if not args:
        from .errors import SyntaxError_

        raise SyntaxError_("max 至少需要 1 个参数")
    return max(args)


def _min_impl(args: list[Decimal], angle_mode: str) -> Decimal:  # noqa: ARG001
    if not args:
        from .errors import SyntaxError_

        raise SyntaxError_("min 至少需要 1 个参数")
    return min(args)


# ---------------------------------------------------------------------- #
# 函数注册表
# ---------------------------------------------------------------------- #
#: 函数名 -> 实现。实现签名统一为 ``(args: list[Decimal], angle_mode: str) -> Decimal``
FUNCTIONS: dict[str, Callable[[list[Decimal], str], Decimal]] = {
    # 三角 / 反三角（受角度制影响）
    "sin": _make_trig("sin", math.sin),
    "cos": _make_trig("cos", math.cos),
    "tan": _make_trig("tan", math.tan),
    "asin": _make_inverse_trig("asin", math.asin),
    "acos": _make_inverse_trig("acos", math.acos),
    "atan": _make_inverse_trig("atan", math.atan),
    # 双曲函数（不受角度制影响）
    "sinh": _make_math1("sinh", math.sinh, "参数超出定义域"),
    "cosh": _make_math1("cosh", math.cosh, "参数超出定义域"),
    "tanh": _make_math1("tanh", math.tanh, "参数超出定义域"),
    # 幂与根
    "sqrt": _sqrt_impl,
    "cbrt": _cbrt_impl,
    "pow": _pow_impl,
    # 指数与对数
    "ln": _ln_impl,
    "log": _log_impl,
    "lg": _log_impl,
    "log2": _log2_impl,
    "exp": _exp_impl,
    # 取整与符号
    "abs": _abs_impl,
    "floor": _floor_impl,
    "ceil": _ceil_impl,
    "round": _round_impl,
    "sign": _sign_impl,
    # 其它
    "fact": _fact_impl,
    "mod": _mod_impl,
    "max": _max_impl,
    "min": _min_impl,
}

#: 允许的实参个数（用于语法分析阶段的预校验）
FUNCTION_ARITY: dict[str, tuple[int, ...]] = {
    "sin": (1,), "cos": (1,), "tan": (1,),
    "asin": (1,), "acos": (1,), "atan": (1,),
    "sinh": (1,), "cosh": (1,), "tanh": (1,),
    "sqrt": (1,), "cbrt": (1,), "pow": (2,),
    "ln": (1,), "log": (1, 2), "lg": (1, 2), "log2": (1,), "exp": (1,),
    "abs": (1,), "floor": (1,), "ceil": (1,), "round": (1, 2), "sign": (1,),
    "fact": (1,), "mod": (2,),
    "max": (1, 2, 3, 4, 5, 6, 7, 8, 9, 10),
    "min": (1, 2, 3, 4, 5, 6, 7, 8, 9, 10),
}


def is_function(name: str) -> bool:
    """判断名字是否是已注册函数。"""
    return name.lower() in FUNCTIONS


def is_constant(name: str) -> bool:
    """判断名字是否是已注册常量。"""
    return name.lower() in CONSTANTS or name in CONSTANTS


def call_function(name: str, args: list[Decimal], angle_mode: str) -> Decimal:
    """调用函数。

    :param name: 函数名（大小写不敏感）
    :param args: 实参列表
    :param angle_mode: ``'deg'`` 或 ``'rad'``
    :raises UnknownFunctionError: 函数未注册
    """
    key = name.lower()
    impl = FUNCTIONS.get(key)
    if impl is None:
        raise UnknownFunctionError(name)
    return impl(args, angle_mode)


def get_constant(name: str) -> Decimal:
    """取常量值。

    :raises UnknownFunctionError: 常量不存在（复用函数未找到的错误码语义）
    """
    if name in CONSTANTS:
        return CONSTANTS[name]
    key = name.lower()
    if key in CONSTANTS:
        return CONSTANTS[key]
    raise UnknownFunctionError(name)
