"""抽象语法树（AST）节点定义。

表达式被解析成由这些节点组成的树，再交给 :mod:`app.calculator.evaluator` 求值。
把"解析"和"求值"分成两个阶段是经典做法，好处是：

1. 语法是否正确可以在求值前一次性判定，错误信息更准确；
2. 求值器只需要处理"已经确定的合法结构"，代码简单且不易出错；
3. AST 可以复用（例如未来做表达式化简、求导、绘图）。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Node:
    """所有 AST 节点的基类。"""


@dataclass(frozen=True)
class NumberNode(Node):
    """数字字面量。``text`` 保留原始文本，交给 Decimal 解析以保证精度。"""

    text: str


@dataclass(frozen=True)
class ConstantNode(Node):
    """数学常量，如 ``pi``、``e``。"""

    name: str


@dataclass(frozen=True)
class UnaryOpNode(Node):
    """一元运算。

    :param op: ``'+'``、``'-'`` 或 ``'%'``（后缀百分号）
    :param operand: 操作数
    :param postfix: True 表示后缀形式（``x%``），False 表示前缀形式（``-x``）
    """

    op: str
    operand: Node
    postfix: bool = False


@dataclass(frozen=True)
class BinaryOpNode(Node):
    """二元运算：``+ - * / ^ mod``。"""

    op: str
    left: Node
    right: Node


@dataclass(frozen=True)
class FactorialNode(Node):
    """后缀阶乘 ``x!``。"""

    operand: Node


@dataclass(frozen=True)
class FunctionNode(Node):
    """函数调用，例如 ``sin(1)``、``log(8, 2)``、``max(1, 5, 3)``。"""

    name: str
    args: tuple[Node, ...]
