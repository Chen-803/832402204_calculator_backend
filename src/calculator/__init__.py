"""计算器核心模块（纯业务，不依赖 Flask 或数据库）。

对外只暴露一个高层入口 :func:`calculate_expression`，以及异常类型与元数据接口。

分层意图：
    * ``tokenizer`` / ``parser`` / ``evaluator`` 负责"算得对"；
    * ``functions`` / ``number_utils`` 负责"算得准、算得安全"；
    * ``exceptions`` 负责"算错了也要讲清楚"。

该模块完全可以脱离 Web 框架单独使用或单独测试::

    from src.calculator import calculate_expression
    calculate_expression("(1+2)*3").display      # '9'
"""

from dataclasses import dataclass
from decimal import Decimal

from .exceptions import (
    CalculatorError,
    DivisionByZeroError,
    EmptyExpressionError,
    ExpressionTooLongError,
    InvalidCharacterError,
    InvalidExpressionError,
    MathDomainError,
    NumericOverflowError,
    ValidationError,
)
from .evaluator import Evaluator
from .functions import (
    CONSTANTS,
    FUNCTIONS,
    describe_constants,
    describe_functions,
    lookup_function,
)
from .number_utils import format_decimal, to_json_number
from .parser import parse_expression
from .tokenizer import MAX_EXPRESSION_LENGTH, Tokenizer, normalize_expression

__all__ = [
    "CalculationOutcome",
    "calculate_expression",
    "CalculatorError",
    "DivisionByZeroError",
    "EmptyExpressionError",
    "ExpressionTooLongError",
    "InvalidCharacterError",
    "InvalidExpressionError",
    "MathDomainError",
    "NumericOverflowError",
    "ValidationError",
    "CONSTANTS",
    "FUNCTIONS",
    "define_metadata",
    "lookup_function",
]


@dataclass(frozen=True)
class CalculationOutcome:
    """一次计算的完整结果。

    Attributes:
        expression: 归一化之后、真正参与计算的表达式，会被写入数据库。
        raw_expression: 用户原始输入，用于回显。
        value: 高精度 Decimal 结果。
        display: 面向用户的格式化结果字符串。
        json_number: 可直接放进 JSON 的数值（``int`` 或 ``float``）。
    """

    expression: str
    raw_expression: str
    value: Decimal
    display: str
    json_number: object


def calculate_expression(raw_expression: str) -> CalculationOutcome:
    """计算一个数学表达式的值（本项目的核心业务入口）。

    Args:
        raw_expression: 用户输入，可能包含 ``×`` ``÷`` ``π`` 等符号。

    Returns:
        :class:`CalculationOutcome`。

    Raises:
        EmptyExpressionError: 输入为空。
        ExpressionTooLongError: 输入过长。
        InvalidCharacterError: 出现非法字符。
        InvalidExpressionError: 语法错误。
        DivisionByZeroError: 除数为零。
        MathDomainError: 定义域错误。
        NumericOverflowError: 结果溢出。
    """
    if raw_expression is None or not raw_expression.strip():
        raise EmptyExpressionError("表达式不能为空，请输入例如 1+2*3 的算式")

    tokenizer = Tokenizer(raw_expression)
    normalized = tokenizer.normalized

    ast = parse_expression(raw_expression)
    value = Evaluator().evaluate(ast)

    return CalculationOutcome(
        expression=normalized,
        raw_expression=raw_expression,
        value=value,
        display=format_decimal(value),
        json_number=to_json_number(value),
    )


def define_metadata() -> dict:
    """返回计算器能力元数据（常量 + 函数），供前端动态渲染。"""
    return {
        "constants": describe_constants(),
        "functions": describe_functions(),
        "max_expression_length": MAX_EXPRESSION_LENGTH,
        "operators": [
            {"symbol": "+", "label": "+", "description": "加法"},
            {"symbol": "-", "label": "−", "description": "减法"},
            {"symbol": "*", "label": "×", "description": "乘法"},
            {"symbol": "/", "label": "÷", "description": "除法"},
            {"symbol": "%", "label": "mod", "description": "取模"},
            {"symbol": "^", "label": "xʸ", "description": "幂运算（右结合）"},
            {"symbol": "!", "label": "n!", "description": "阶乘（后缀）"},
        ],
    }
