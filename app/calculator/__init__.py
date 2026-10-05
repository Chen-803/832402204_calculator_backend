"""计算器核心包 —— 后端"计算能力"的唯一出口。

对外只暴露 :func:`calculate`，Service 层不需要知道内部有词法分析、语法分析、
求值三个阶段。

流水线
------
.. code-block:: text

    用户表达式
        │
        ├─ 1. normalize_expression  归一化（× → *，全角 → 半角，长度校验）
        ├─ 2. Tokenizer             词法分析 → Token 序列
        ├─ 3. Parser                语法分析（优先级爬升）→ AST
        ├─ 4. Evaluator             后序遍历求值 → Decimal（34 位精度）
        └─ 5. format_decimal        展示格式化 → resultText

安全说明：全流程 **不出现** ``eval`` / ``exec`` / ``compile``，
也不引入任何会把字符串当代码执行的库。
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .errors import CalculatorError, ErrorCode
from .evaluator import CALCULATION_PRECISION, VALID_ANGLE_MODES, evaluate
from .formatter import format_decimal, to_json_number
from .parser import Parser, parse
from .tokenizer import (
    MAX_EXPRESSION_LENGTH,
    MAX_NESTING_DEPTH,
    Tokenizer,
    normalize_expression,
    tokenize,
)

__all__ = [
    "CalculatorError",
    "CalculationOutcome",
    "ErrorCode",
    "calculate",
    "CALCULATION_PRECISION",
    "MAX_EXPRESSION_LENGTH",
    "MAX_NESTING_DEPTH",
    "VALID_ANGLE_MODES",
    "format_decimal",
    "normalize_expression",
    "parse",
    "to_json_number",
    "tokenize",
]


@dataclass(frozen=True)
class CalculationOutcome:
    """一次成功计算的完整结果。

    :param expression: 前端提交的原始表达式
    :param normalized_expression: 归一化后的表达式（入库与调试用）
    :param value: 高精度数值结果
    :param result_text: 展示用字符串结果（前端应优先展示它）
    """

    expression: str
    normalized_expression: str
    value: Decimal
    result_text: str

    @property
    def json_number(self) -> float | None:
        """结果的 JSON number 形式；超出 double 范围时为 ``None``。"""
        return to_json_number(self.value)


def calculate(expression: str, angle_mode: str = "rad") -> CalculationOutcome:
    """计算表达式。这是整个后端最核心的函数。

    :param expression: 用户输入的表达式，例如 ``"(1+2)*3"``、``"sin(30)"``
    :param angle_mode: ``'deg'`` 或 ``'rad'``，仅影响三角函数
    :returns: :class:`CalculationOutcome`
    :raises CalculatorError: 表达式为空 / 过长 / 非法字符 / 语法错误 /
        除零 / 定义域错误 / 未知函数
    """
    if angle_mode not in VALID_ANGLE_MODES:
        angle_mode = "rad"

    # 1) 归一化：这一步就会拒绝空表达式与超长表达式
    normalized = normalize_expression(expression)

    # 2) 词法分析 → 3) 语法分析 → 4) 求值
    #    这里直接复用 Tokenizer/Parser，避免 parse() 内部重复做一次词法分析。
    tokens = Tokenizer(normalized).tokenize()
    tree = Parser(tokens).parse()
    value = evaluate(tree, angle_mode)

    # 5) 展示格式化
    result_text = format_decimal(value)

    return CalculationOutcome(
        expression=expression,
        normalized_expression=normalized,
        value=value,
        result_text=result_text,
    )
