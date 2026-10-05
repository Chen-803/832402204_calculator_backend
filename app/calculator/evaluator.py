"""AST 求值器。

在 :mod:`app.calculator.parser` 产出的 AST 上做后序遍历求值。

精度策略
--------
整个求值过程包裹在 ``decimal.localcontext()`` 中，精度固定为 34 位有效数字
（IEEE 754-2008 decimal128 的精度）：

- **加减乘**：在该精度下对常见十进制小数是精确的，因此 ``0.1 + 0.2`` 得到
  ``0.3`` 而不是二进制浮点的 ``0.30000000000000004``；
- **除法**：无限小数在该精度下截断，最终展示时再统一四舍五入到 12 位小数
  （见 :mod:`app.calculator.formatter`），所以 ``1/3`` 显示为 ``0.333333333333``；
- **幂/开方**：``Decimal.pow`` / ``Decimal.sqrt`` 按精度正确舍入；
- **超越函数**：转 ``float`` 交给标准库 ``math``，回写时做"整平"处理。

这样做的好处是"内部高精度、展示低精度"分离：中间步骤不会因为反复取整
而累积误差。
"""

from __future__ import annotations

from decimal import Decimal, localcontext

from .ast_nodes import (
    BinaryOpNode,
    ConstantNode,
    FactorialNode,
    FunctionNode,
    Node,
    NumberNode,
    UnaryOpNode,
)
from .errors import DivisionByZeroError, DomainError
from .functions import call_function, factorial_of, get_constant, modulo_of, power_of

#: 内部计算精度（有效数字位数）
CALCULATION_PRECISION = 34

#: 允许的角度制取值
VALID_ANGLE_MODES = ("rad", "deg")


def _divide(left: Decimal, right: Decimal) -> Decimal:
    """除法，显式拦截除零。

    不依赖 ``decimal`` 自己抛的 ``DivisionByZero``，因为那样拿不到统一的
    错误码；这里主动判断，保证 ``1/0``、``-5/0``、``0/0`` 都返回 40003。
    """
    if right == 0:
        raise DivisionByZeroError()
    return left / right


def _evaluate_node(node: Node, angle_mode: str) -> Decimal:
    """递归求值单个节点。"""
    if isinstance(node, NumberNode):
        return Decimal(node.text)

    if isinstance(node, ConstantNode):
        return get_constant(node.name)

    if isinstance(node, UnaryOpNode):
        operand = _evaluate_node(node.operand, angle_mode)
        if node.op == "-":
            return -operand
        if node.op == "+":
            return operand
        if node.op == "%":  # 后缀百分号：x% == x/100
            return _divide(operand, Decimal(100))
        raise DomainError(f"未知的一元运算符 {node.op}")  # pragma: no cover

    if isinstance(node, FactorialNode):
        return factorial_of(_evaluate_node(node.operand, angle_mode))

    if isinstance(node, BinaryOpNode):
        left = _evaluate_node(node.left, angle_mode)
        right = _evaluate_node(node.right, angle_mode)
        if node.op == "+":
            return left + right
        if node.op == "-":
            return left - right
        if node.op == "*":
            return left * right
        if node.op == "/":
            return _divide(left, right)
        if node.op == "^":
            return power_of(left, right)
        if node.op == "mod":
            return modulo_of(left, right)
        raise DomainError(f"未知的二元运算符 {node.op}")  # pragma: no cover

    if isinstance(node, FunctionNode):
        args = [_evaluate_node(arg, angle_mode) for arg in node.args]
        return call_function(node.name, args, angle_mode)

    raise DomainError(f"未知的语法树节点 {type(node).__name__}")  # pragma: no cover


def evaluate(node: Node, angle_mode: str = "rad") -> Decimal:
    """对 AST 求值。

    :param node: AST 根节点
    :param angle_mode: ``'rad'``（弧度）或 ``'deg'``（角度）
    :returns: 高精度计算结果
    :raises CalculatorError: 除零、定义域错误等
    """
    if angle_mode not in VALID_ANGLE_MODES:
        angle_mode = "rad"
    with localcontext() as ctx:
        ctx.prec = CALCULATION_PRECISION
        return _evaluate_node(node, angle_mode)
