"""抽象语法树（AST）节点定义。

采用递归下降解析器，把表达式解析成由这些节点构成的树，
再由 :mod:`src.calculator.evaluator` 自底向上求值。

之所以不直接在解析过程中计算，是因为"解析"和"求值"分离之后：
    * 解析结果可以被缓存、被打印、被单元测试单独验证；
    * 求值过程可以统一处理精度与异常；
    * 未来要支持"变量"或"方程求解"时，只需扩展求值器。
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import List, Tuple

__all__ = [
    "Node",
    "NumberNode",
    "ConstantNode",
    "UnaryNode",
    "BinaryNode",
    "FunctionNode",
]


class Node:
    """AST 节点基类。"""

    def describe(self) -> str:
        """返回该节点对应表达式的规范化文本（用于日志与测试）。"""
        raise NotImplementedError

    def operators(self) -> Tuple[str, ...]:
        """返回该子树中出现过的二元运算符集合（用于历史统计）。"""
        return ()


@dataclass(frozen=True)
class NumberNode(Node):
    """数字字面量，例如 ``3.14``。"""

    value: Decimal
    literal: str = ""

    def describe(self) -> str:
        return self.literal or str(self.value)


@dataclass(frozen=True)
class ConstantNode(Node):
    """数学常量，例如 ``pi``、``e``。"""

    name: str
    value: Decimal

    def describe(self) -> str:
        return self.name


@dataclass(frozen=True)
class UnaryNode(Node):
    """一元运算，例如 ``-5``、``+8``。"""

    operator: str
    operand: Node

    def describe(self) -> str:
        return f"({self.operator}{self.operand.describe()})"

    def operators(self) -> Tuple[str, ...]:
        return self.operand.operators()


@dataclass(frozen=True)
class BinaryNode(Node):
    """二元运算，例如 ``1 + 2 * 3``。"""

    operator: str
    left: Node
    right: Node

    def describe(self) -> str:
        return f"({self.left.describe()} {self.operator} {self.right.describe()})"

    def operators(self) -> Tuple[str, ...]:
        return tuple({self.operator} | set(self.left.operators()) | set(self.right.operators()))


@dataclass(frozen=True)
class FunctionNode(Node):
    """函数调用，例如 ``sqrt(9)``、``log(2, 8)``，以及后缀阶乘 ``5!``。

    ``operator`` 为 ``"!"`` 时表示阶乘，此时 ``arguments`` 只有一个元素。
    """

    name: str
    arguments: List[Node] = field(default_factory=list)

    def describe(self) -> str:
        args = ", ".join(argument.describe() for argument in self.arguments)
        return f"{self.name}({args})"

    def operators(self) -> Tuple[str, ...]:
        collected: set = set()
        for argument in self.arguments:
            collected.update(argument.operators())
        return tuple(collected)
