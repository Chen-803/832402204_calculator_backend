"""AST 求值器。

自底向上遍历 :mod:`src.calculator.ast_nodes` 定义的语法树并计算结果。

设计要点：
    * 全程使用 :class:`decimal.Decimal`，四则运算精确到 50 位有效数字，
      最后再按 15 位有效数字展示，避免浮点误差；
    * 每一种可能导致"非法结果"的运算都显式检查定义域，
      并抛出携带 ``error_code`` 的业务异常，而不是让底层异常穿透到接口层；
    * 每一步运算后都检查结果数量级，防止 ``9^99999`` 之类的表达式拖垮服务。
"""

from decimal import Decimal, DecimalException
from typing import Tuple

from .ast_nodes import (
    BinaryNode,
    ConstantNode,
    FunctionNode,
    Node,
    NumberNode,
    UnaryNode,
)
from .exceptions import MathDomainError, NumericOverflowError
from .functions import factorial_value, lookup_function, safe_divide, safe_modulo, safe_power
from .number_utils import MAX_ADJUSTED_EXPONENT, calculation_context

__all__ = ["Evaluator", "evaluate", "collect_operators"]


class Evaluator:
    """表达式求值器。

    Example:
        >>> from src.calculator.parser import parse_expression
        >>> Evaluator().evaluate(parse_expression("(1+2)*3"))
        Decimal('9')
    """

    def evaluate(self, node: Node) -> Decimal:
        """计算 AST 的值。

        Args:
            node: 语法树根节点。

        Returns:
            精确的 Decimal 结果。

        Raises:
            DivisionByZeroError: 除数为零。
            MathDomainError: 违反数学定义域。
            NumericOverflowError: 结果超出可表示范围。
        """
        with calculation_context():
            result = self._evaluate(node)
            if not result.is_finite():
                raise NumericOverflowError("计算结果超出可表示范围")
            self._guard_magnitude(result)
            return result

    # ------------------------------------------------------------------
    # 内部实现
    # ------------------------------------------------------------------
    def _evaluate(self, node: Node) -> Decimal:
        """按节点类型分派求值。"""
        if isinstance(node, NumberNode):
            return node.value

        if isinstance(node, ConstantNode):
            return node.value

        if isinstance(node, UnaryNode):
            operand = self._evaluate(node.operand)
            if node.operator == "-":
                return -operand
            return operand

        if isinstance(node, BinaryNode):
            left = self._evaluate(node.left)
            right = self._evaluate(node.right)
            result = self._apply_binary(node.operator, left, right)
            self._guard_magnitude(result)
            return result

        if isinstance(node, FunctionNode):
            if node.name == "!":
                return factorial_value(self._evaluate(node.arguments[0]))
            spec = lookup_function(node.name)
            if spec is None:  # pragma: no cover - 解析阶段已拦截
                raise MathDomainError(f"未知函数 '{node.name}'")
            arguments = tuple(self._evaluate(argument) for argument in node.arguments)
            return spec.call(arguments)

        raise MathDomainError("表达式包含无法识别的节点")  # pragma: no cover - 防御性分支

    def _apply_binary(self, operator: str, left: Decimal, right: Decimal) -> Decimal:
        """执行一次二元运算，并把底层异常翻译为业务异常。"""
        try:
            if operator == "+":
                return left + right
            if operator == "-":
                return left - right
            if operator == "*":
                return left * right
            if operator == "/":
                return safe_divide(left, right)
            if operator == "%":
                return safe_modulo(left, right)
            if operator == "^":
                return safe_power(left, right)
        except (MathDomainError, NumericOverflowError):
            raise
        except DecimalException as exc:
            raise NumericOverflowError("计算结果超出可计算范围") from exc
        raise MathDomainError(f"不支持的运算符 '{operator}'")  # pragma: no cover

    def _guard_magnitude(self, value: Decimal) -> None:
        """检查结果数量级，避免产生天文数字导致内存与响应体爆炸。"""
        if value == 0:
            return
        if abs(value.adjusted()) > MAX_ADJUSTED_EXPONENT:
            raise NumericOverflowError(
                f"计算结果数量级过大（超过 10^{MAX_ADJUSTED_EXPONENT}），已拒绝计算"
            )


def evaluate(node: Node) -> Decimal:
    """便捷函数：求值一个 AST。"""
    return Evaluator().evaluate(node)


def collect_operators(node: Node) -> Tuple[str, ...]:
    """收集表达式中出现过的二元运算符（供历史统计模块使用）。"""
    return node.operators()
