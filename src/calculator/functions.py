"""函数与常量注册表，以及带异常保护的算术原语。

本模块是"计算能力"的唯一来源：
    * :data:`CONSTANTS` 定义数学常量（``pi``、``e``）；
    * :data:`FUNCTIONS` 定义可调用的数学函数及其参数个数，供
      ``GET /api/meta/functions`` 直接下发给前端动态渲染按钮；
    * :func:`safe_divide` / :func:`safe_modulo` / :func:`safe_power` 等
      算术原语把 Python 的底层异常翻译成业务异常，供求值器统一使用。

精度策略：
    * 四则运算、``sqrt``、``ln``、``exp``、``log10`` 等使用 Decimal 原生实现，
      保持高精度；
    * 三角函数 Decimal 没有原生实现，退化为 ``math`` 的双精度浮点，
      并对结果做"近零吸附"处理（如 ``sin(pi)`` 显示为 0 而不是 1.2e-16）。
"""

import math
from decimal import Decimal, DecimalException, InvalidOperation, localcontext
from typing import Callable, Dict, Optional, Tuple

from .exceptions import DivisionByZeroError, MathDomainError, NumericOverflowError

__all__ = [
    "CONSTANTS",
    "FUNCTIONS",
    "FunctionSpec",
    "safe_divide",
    "safe_modulo",
    "safe_power",
    "factorial_value",
    "describe_functions",
    "describe_constants",
]

#: 常量表。使用高精度字面量，避免 source 层面就丢失精度。
CONSTANTS: Dict[str, Decimal] = {
    "pi": Decimal("3.14159265358979323846264338327950288419716939937511"),
    "e": Decimal("2.71828182845904523536028747135266249775724709369996"),
}

#: 阶乘上限，防止 ``999999!`` 之类的输入耗尽 CPU。
MAX_FACTORIAL_ARGUMENT = 1000

#: 幂运算的指数绝对值上限。
MAX_POWER_EXPONENT = 10_000

#: 三角函数近零吸附阈值（双精度浮点的有效位数约为 1e-16）。
_TRIG_ZERO_TOLERANCE = 1e-15


def _to_float(value: Decimal) -> float:
    """Decimal -> float，转换失败时抛出溢出异常。"""
    try:
        result = float(value)
    except (ValueError, OverflowError, DecimalException) as exc:
        raise NumericOverflowError("数值超出可计算范围") from exc
    if math.isinf(result) or math.isnan(result):
        raise NumericOverflowError("数值超出可计算范围")
    return result


def _from_float(value: float, *, snap_zero: bool = False) -> Decimal:
    """float -> Decimal，可选地把极小值吸附为 0。"""
    if math.isnan(value):
        raise MathDomainError("该函数在此处没有实数结果")
    if math.isinf(value):
        raise NumericOverflowError("函数结果超出可计算范围")
    if snap_zero and abs(value) < _TRIG_ZERO_TOLERANCE:
        return Decimal(0)
    return Decimal(repr(value))


def safe_divide(left: Decimal, right: Decimal) -> Decimal:
    """除法，除数为 0 时抛出 :class:`DivisionByZeroError`。"""
    if right == 0:
        raise DivisionByZeroError("除数不能为零（division by zero）")
    try:
        with localcontext() as ctx:
            ctx.prec = 50
            return left / right
    except DecimalException as exc:
        raise NumericOverflowError("除法结果超出可计算范围") from exc


def safe_modulo(left: Decimal, right: Decimal) -> Decimal:
    """取模，除数为 0 时抛出 :class:`DivisionByZeroError`。"""
    if right == 0:
        raise DivisionByZeroError("取模运算的除数不能为零（modulo by zero）")
    try:
        return left % right
    except DecimalException as exc:
        raise NumericOverflowError("取模结果超出可计算范围") from exc


def safe_power(base: Decimal, exponent: Decimal) -> Decimal:
    """幂运算 ``base ^ exponent``，含定义域与规模保护。

    规则：
        * ``0`` 的负数次幂 -> 除零错误；
        * 负数的非整数次幂 -> 定义域错误（实数范围内无解）；
        * ``0 ^ 0`` 约定为 1（与主流计算器一致）；
        * 指数绝对值超过 :data:`MAX_POWER_EXPONENT` 时判定为溢出。
    """
    if abs(exponent) > MAX_POWER_EXPONENT:
        raise NumericOverflowError(
            f"指数过大（|exponent| ≤ {MAX_POWER_EXPONENT}），结果超出可计算范围"
        )
    if base == 0 and exponent < 0:
        raise DivisionByZeroError("0 不能作为负指数幂的底数（等价于除以零）")
    if base == 0 and exponent == 0:
        return Decimal(1)
    if base < 0 and exponent != exponent.to_integral_value():
        raise MathDomainError("负数不能开非整数次方（实数范围内无解）")

    try:
        with localcontext() as ctx:
            ctx.prec = 50
            ctx.Emax = 999_999
            ctx.Emin = -999_999
            return base ** exponent
    except InvalidOperation as exc:
        raise MathDomainError("幂运算的底数与指数组合无实数结果") from exc
    except DecimalException as exc:
        raise NumericOverflowError("幂运算结果超出可计算范围") from exc


def factorial_value(value: Decimal) -> Decimal:
    """阶乘，仅接受 0 ~ :data:`MAX_FACTORIAL_ARGUMENT` 之间的整数。"""
    if value != value.to_integral_value():
        raise MathDomainError("阶乘只支持非负整数")
    if value < 0:
        raise MathDomainError("阶乘只支持非负整数")
    if value > MAX_FACTORIAL_ARGUMENT:
        raise NumericOverflowError(f"阶乘参数过大（n ≤ {MAX_FACTORIAL_ARGUMENT}）")
    limit = int(value)
    result = Decimal(1)
    for factor in range(2, limit + 1):
        result *= factor
    return result


class FunctionSpec:
    """一个数学函数的元数据与实现。

    Attributes:
        name: 内部名称（小写），也是表达式中书写的名称。
        label: 前端按钮上显示的短标签。
        usage: 前端点击按钮时插入的表达式片段。
        arity: ``(最少参数个数, 最多参数个数)``。
        description: 中文说明，用于接口文档与界面提示。
        implementation: 具体实现，入参为 Decimal 元组。
    """

    def __init__(
        self,
        name: str,
        label: str,
        usage: str,
        arity: Tuple[int, int],
        description: str,
        implementation: Callable[[Tuple[Decimal, ...]], Decimal],
    ) -> None:
        self.name = name
        self.label = label
        self.usage = usage
        self.arity = arity
        self.description = description
        self.implementation = implementation

    def to_dict(self) -> dict:
        """转换为接口返回的字典结构。"""
        return {
            "name": self.name,
            "label": self.label,
            "usage": self.usage,
            "arity": list(self.arity),
            "description": self.description,
        }

    def call(self, arguments: Tuple[Decimal, ...]) -> Decimal:
        """校验参数个数后调用实现。"""
        minimum, maximum = self.arity
        if not minimum <= len(arguments) <= maximum:
            if minimum == maximum:
                expected = f"{minimum} 个"
            else:
                expected = f"{minimum} ~ {maximum} 个"
            raise MathDomainError(
                f"函数 {self.name} 需要 {expected}参数，实际收到 {len(arguments)} 个"
            )
        return self.implementation(arguments)


# ---------------------------------------------------------------------------
# 各函数的实现
# ---------------------------------------------------------------------------


def _unary(func: Callable[[Decimal], Decimal]) -> Callable[[Tuple[Decimal, ...]], Decimal]:
    """把一元函数适配成注册表需要的签名。"""

    def wrapper(arguments: Tuple[Decimal, ...]) -> Decimal:
        return func(arguments[0])

    return wrapper


def _sqrt(value: Decimal) -> Decimal:
    if value < 0:
        raise MathDomainError("负数不能开平方（sqrt 的定义域为 x ≥ 0）")
    with localcontext() as ctx:
        ctx.prec = 50
        return value.sqrt()


def _cbrt(value: Decimal) -> Decimal:
    if value == 0:
        return Decimal(0)
    negative = value < 0
    with localcontext() as ctx:
        ctx.prec = 50
        magnitude = abs(value) ** (Decimal(1) / Decimal(3))
    return -magnitude if negative else magnitude


def _ln(value: Decimal) -> Decimal:
    if value <= 0:
        raise MathDomainError("对数函数的真数必须大于 0")
    with localcontext() as ctx:
        ctx.prec = 50
        return value.ln()


def _log(args: Tuple[Decimal, ...]) -> Decimal:
    """``log(x)`` 为常用对数；``log(base, x)`` 为指定底数的对数。"""
    if len(args) == 1:
        value = args[0]
        if value <= 0:
            raise MathDomainError("对数函数的真数必须大于 0")
        with localcontext() as ctx:
            ctx.prec = 50
            return value.log10()
    base, value = args[0], args[1]
    if base <= 0 or base == 1:
        raise MathDomainError("对数的底数必须大于 0 且不等于 1")
    if value <= 0:
        raise MathDomainError("对数函数的真数必须大于 0")
    with localcontext() as ctx:
        ctx.prec = 50
        return value.ln() / base.ln()


def _log2(value: Decimal) -> Decimal:
    if value <= 0:
        raise MathDomainError("对数函数的真数必须大于 0")
    with localcontext() as ctx:
        ctx.prec = 50
        return value.ln() / Decimal(2).ln()


def _exp(value: Decimal) -> Decimal:
    with localcontext() as ctx:
        ctx.prec = 50
        ctx.Emax = 999_999
        return value.exp()


def _abs(value: Decimal) -> Decimal:
    return abs(value)


def _floor(value: Decimal) -> Decimal:
    return value.to_integral_value(rounding="ROUND_FLOOR")


def _ceil(value: Decimal) -> Decimal:
    return value.to_integral_value(rounding="ROUND_CEILING")


def _round(args: Tuple[Decimal, ...]) -> Decimal:
    value = args[0]
    digits = int(args[1]) if len(args) > 1 else 0
    if not -15 <= digits <= 15:
        raise MathDomainError("round 的小数位数需要在 -15 ~ 15 之间")
    exponent = Decimal(1).scaleb(-digits)
    return value.quantize(exponent, rounding="ROUND_HALF_UP")


def _max(args: Tuple[Decimal, ...]) -> Decimal:
    return max(args)


def _min(args: Tuple[Decimal, ...]) -> Decimal:
    return min(args)


def _pow(args: Tuple[Decimal, ...]) -> Decimal:
    return safe_power(args[0], args[1])


def _mod(args: Tuple[Decimal, ...]) -> Decimal:
    return safe_modulo(args[0], args[1])


def _factorial(args: Tuple[Decimal, ...]) -> Decimal:
    return factorial_value(args[0])


# 三角函数：Decimal 无原生实现，退化为双精度浮点并做近零吸附。
def _sin(value: Decimal) -> Decimal:
    return _from_float(math.sin(_to_float(value)), snap_zero=True)


def _cos(value: Decimal) -> Decimal:
    return _from_float(math.cos(_to_float(value)), snap_zero=True)


def _tan(value: Decimal) -> Decimal:
    radians = _to_float(value)
    cosine = math.cos(radians)
    if abs(cosine) < _TRIG_ZERO_TOLERANCE:
        raise MathDomainError("tan 在 90° + kπ 处没有定义")
    return _from_float(math.tan(radians), snap_zero=True)


def _asin(value: Decimal) -> Decimal:
    number = _to_float(value)
    if number < -1 or number > 1:
        raise MathDomainError("asin 的定义域为 -1 ≤ x ≤ 1")
    return _from_float(math.asin(number), snap_zero=True)


def _acos(value: Decimal) -> Decimal:
    number = _to_float(value)
    if number < -1 or number > 1:
        raise MathDomainError("acos 的定义域为 -1 ≤ x ≤ 1")
    return _from_float(math.acos(number))


def _atan(value: Decimal) -> Decimal:
    return _from_float(math.atan(_to_float(value)), snap_zero=True)


def _sinh(value: Decimal) -> Decimal:
    return _from_float(math.sinh(_to_float(value)), snap_zero=True)


def _cosh(value: Decimal) -> Decimal:
    return _from_float(math.cosh(_to_float(value)))


def _tanh(value: Decimal) -> Decimal:
    return _from_float(math.tanh(_to_float(value)), snap_zero=True)


#: 函数注册表。新增函数只需在这里登记一条即可被解析器、求值器和接口同时感知。
FUNCTIONS: Dict[str, FunctionSpec] = {
    spec.name: spec
    for spec in (
        FunctionSpec("sqrt", "√", "sqrt(", (1, 1), "平方根", _unary(_sqrt)),
        FunctionSpec("cbrt", "∛", "cbrt(", (1, 1), "立方根", _unary(_cbrt)),
        FunctionSpec("abs", "|x|", "abs(", (1, 1), "绝对值", _unary(_abs)),
        FunctionSpec("exp", "eˣ", "exp(", (1, 1), "自然指数 e 的 x 次幂", _unary(_exp)),
        FunctionSpec("ln", "ln", "ln(", (1, 1), "自然对数（底数 e）", _unary(_ln)),
        FunctionSpec("log", "log", "log(", (1, 2), "常用对数 log(x)，或 log(底数, x)", _log),
        FunctionSpec("log2", "log₂", "log2(", (1, 1), "以 2 为底的对数", _unary(_log2)),
        FunctionSpec("sin", "sin", "sin(", (1, 1), "正弦（弧度）", _unary(_sin)),
        FunctionSpec("cos", "cos", "cos(", (1, 1), "余弦（弧度）", _unary(_cos)),
        FunctionSpec("tan", "tan", "tan(", (1, 1), "正切（弧度）", _unary(_tan)),
        FunctionSpec("asin", "asin", "asin(", (1, 1), "反正弦（返回弧度）", _unary(_asin)),
        FunctionSpec("acos", "acos", "acos(", (1, 1), "反余弦（返回弧度）", _unary(_acos)),
        FunctionSpec("atan", "atan", "atan(", (1, 1), "反正切（返回弧度）", _unary(_atan)),
        FunctionSpec("sinh", "sinh", "sinh(", (1, 1), "双曲正弦", _unary(_sinh)),
        FunctionSpec("cosh", "cosh", "cosh(", (1, 1), "双曲余弦", _unary(_cosh)),
        FunctionSpec("tanh", "tanh", "tanh(", (1, 1), "双曲正切", _unary(_tanh)),
        FunctionSpec("pow", "pow", "pow(", (2, 2), "幂运算 pow(底数, 指数)", _pow),
        FunctionSpec("mod", "mod", "mod(", (2, 2), "取模 mod(被除数, 除数)", _mod),
        FunctionSpec("factorial", "n!", "factorial(", (1, 1), "阶乘（非负整数）", _factorial),
        FunctionSpec("floor", "⌊x⌋", "floor(", (1, 1), "向下取整", _unary(_floor)),
        FunctionSpec("ceil", "⌈x⌉", "ceil(", (1, 1), "向上取整", _unary(_ceil)),
        FunctionSpec("round", "round", "round(", (1, 2), "四舍五入，可指定小数位数", _round),
        FunctionSpec("max", "max", "max(", (1, 8), "取最大值", _max),
        FunctionSpec("min", "min", "min(", (1, 8), "取最小值", _min),
    )
}


def describe_functions() -> list:
    """返回可下发给前端的函数元数据列表。"""
    return [spec.to_dict() for spec in FUNCTIONS.values()]


def describe_constants() -> list:
    """返回可下发给前端的常量元数据列表。"""
    labels = {"pi": "π", "e": "e"}
    return [
        {"name": name, "label": labels.get(name, name), "value": str(value)}
        for name, value in CONSTANTS.items()
    ]


def lookup_function(name: str) -> Optional[FunctionSpec]:
    """按名称查找函数定义，不存在时返回 None。"""
    return FUNCTIONS.get(name)
