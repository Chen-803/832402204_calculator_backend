"""表达式语法分析器（Parser）。

采用经典的**递归下降分析法**，把 Token 序列解析成 AST。

文法（EBNF）::

    expression     := additive
    additive       := multiplicative (('+' | '-') multiplicative)*
    multiplicative := unary (('*' | '/' | '%') unary)*
    unary          := ('+' | '-') unary | power
    power          := postfix ('^' unary)?          # 右结合
    postfix        := primary '!'*
    primary        := NUMBER
                    | IDENTIFIER '(' arguments ')'
                    | IDENTIFIER                     # 常量 pi / e
                    | '(' expression ')'
    arguments      := expression (',' expression)*

运算符优先级与结合性说明：
    * ``^`` 优先级最高且**右结合**，``2^3^2`` 解析为 ``2^(3^2) = 512``；
    * 一元正负号位于 ``^`` 之下，``-2^2`` 解析为 ``-(2^2) = -4``，符合数学惯例；
    * ``*`` ``/`` ``%`` 同级左结合，``+`` ``-`` 同级左结合。

这一步只负责"结构是否正确"，不做任何计算，也不执行任何用户输入。
"""

from typing import List

from .ast_nodes import (
    BinaryNode,
    ConstantNode,
    FunctionNode,
    Node,
    NumberNode,
    UnaryNode,
)
from .exceptions import InvalidExpressionError
from .functions import CONSTANTS, lookup_function
from .number_utils import parse_decimal
from .tokenizer import Token, TokenType, Tokenizer, describe_position

__all__ = ["Parser", "parse_expression", "MAX_NESTING_DEPTH"]

#: 括号最大嵌套深度，防止超长括号串触发解释器递归上限。
MAX_NESTING_DEPTH = 32

_ADDITIVE_OPERATORS = ("+", "-")
_MULTIPLICATIVE_OPERATORS = ("*", "/", "%")


class Parser:
    """把 Token 序列解析为 AST。

    Example:
        >>> from src.calculator.tokenizer import Tokenizer
        >>> parse_expression("1+2*3").describe()
        '(1 + (2 * 3))'
    """

    def __init__(self, tokens: List[Token], source: str = "") -> None:
        self._tokens = tokens
        self._source = source
        self._position = 0
        self._depth = 0

    # ------------------------------------------------------------------
    # 基础设施
    # ------------------------------------------------------------------
    def _current(self) -> Token:
        """返回当前 Token。"""
        return self._tokens[self._position]

    def _advance(self) -> Token:
        """消费当前 Token 并返回它。"""
        token = self._tokens[self._position]
        if token.type is not TokenType.END:
            self._position += 1
        return token

    def _error(self, message: str, token: Token) -> InvalidExpressionError:
        """构造带位置信息的语法错误。"""
        return InvalidExpressionError(
            f"{message}{describe_position(self._source, token.position)}", position=token.position
        )

    def _match_operator(self, operators) -> bool:
        """若当前 Token 是指定运算符之一，则消费并返回 True。"""
        token = self._current()
        if token.type is TokenType.OPERATOR and token.value in operators:
            self._advance()
            return True
        return False

    # ------------------------------------------------------------------
    # 文法规则
    # ------------------------------------------------------------------
    def parse(self) -> Node:
        """解析整个表达式。

        Returns:
            根节点。

        Raises:
            InvalidExpressionError: 语法错误，或表达式结束但仍有剩余内容。
        """
        node = self._parse_expression()
        token = self._current()
        if token.type is not TokenType.END:
            if token.type is TokenType.RIGHT_PAREN:
                raise self._error("括号不匹配：出现了多余的右括号", token)
            raise self._error(f"表达式中存在无法解析的内容 '{token.value}'", token)
        return node

    def _parse_expression(self) -> Node:
        """expression := additive"""
        return self._parse_additive()

    def _parse_additive(self) -> Node:
        """加减法：左结合，优先级低于乘除。"""
        node = self._parse_multiplicative()
        while True:
            token = self._current()
            if token.type is TokenType.OPERATOR and token.value in _ADDITIVE_OPERATORS:
                self._advance()
                right = self._parse_multiplicative()
                node = BinaryNode(token.value, node, right)
                continue
            return node

    def _parse_multiplicative(self) -> Node:
        """乘除法与取模：左结合。"""
        node = self._parse_unary()
        while True:
            token = self._current()
            if token.type is TokenType.OPERATOR and token.value in _MULTIPLICATIVE_OPERATORS:
                self._advance()
                right = self._parse_unary()
                node = BinaryNode(token.value, node, right)
                continue
            return node

    def _parse_unary(self) -> Node:
        """一元正负号。``--5`` 是合法的，等价于 ``+5``。"""
        token = self._current()
        if token.type is TokenType.OPERATOR and token.value in _ADDITIVE_OPERATORS:
            self._advance()
            operand = self._parse_unary()
            return UnaryNode(token.value, operand)
        return self._parse_power()

    def _parse_power(self) -> Node:
        """幂运算：右结合，指数部分允许再出现一元符号（``2^-3``）。"""
        base = self._parse_postfix()
        token = self._current()
        if token.type is TokenType.OPERATOR and token.value == "^":
            self._advance()
            # 指数部分复用 _parse_unary，因此 `2^-3`、`2^+3`、`2^3^2` 都能正确解析。
            exponent = self._parse_unary()
            return BinaryNode("^", base, exponent)
        return base

    def _parse_postfix(self) -> Node:
        """后缀阶乘：``5!``、``(2+3)!``。"""
        node = self._parse_primary()
        while self._current().type is TokenType.FACTORIAL:
            self._advance()
            node = FunctionNode("!", [node])
        return node

    def _parse_primary(self) -> Node:
        """最基本的语法单元：数字、常量、函数调用、括号表达式。"""
        token = self._current()

        if token.type is TokenType.NUMBER:
            self._advance()
            return NumberNode(parse_decimal(token.value), token.value)

        if token.type is TokenType.IDENTIFIER:
            return self._parse_identifier()

        if token.type is TokenType.LEFT_PAREN:
            self._advance()
            self._depth += 1
            if self._depth > MAX_NESTING_DEPTH:
                raise self._error(
                    f"括号嵌套层数过深（最多 {MAX_NESTING_DEPTH} 层）", token
                )
            inner = self._parse_expression()
            self._depth -= 1
            closing = self._current()
            if closing.type is not TokenType.RIGHT_PAREN:
                raise self._error("括号不匹配：缺少右括号 ')'", closing)
            self._advance()
            return inner

        if token.type is TokenType.RIGHT_PAREN:
            raise self._error("括号不匹配：出现了多余的右括号", token)

        if token.type is TokenType.END:
            raise self._error("表达式不完整：缺少操作数", token)

        if token.type is TokenType.COMMA:
            raise self._error("逗号 ',' 只能用于分隔函数参数", token)

        if token.type is TokenType.FACTORIAL:
            raise self._error("阶乘符号 '!' 之前缺少操作数", token)

        raise self._error(f"无法解析的符号 '{token.value}'", token)

    def _parse_identifier(self) -> Node:
        """解析标识符：函数调用或数学常量。"""
        token = self._advance()
        name = token.value
        spec = lookup_function(name)

        if self._current().type is TokenType.LEFT_PAREN:
            if spec is None:
                raise self._error(f"未知函数 '{name}'", token)
            self._advance()
            self._depth += 1
            if self._depth > MAX_NESTING_DEPTH:
                raise self._error(f"括号嵌套层数过深（最多 {MAX_NESTING_DEPTH} 层）", token)
            arguments = [self._parse_expression()]
            while self._current().type is TokenType.COMMA:
                self._advance()
                arguments.append(self._parse_expression())
            self._depth -= 1
            closing = self._current()
            if closing.type is not TokenType.RIGHT_PAREN:
                raise self._error(f"函数 '{name}' 缺少右括号 ')'", closing)
            self._advance()
            return FunctionNode(name, arguments)

        if spec is not None:
            raise self._error(
                f"函数 '{name}' 需要括号与参数，例如 {spec.usage}0)", token
            )

        if name in CONSTANTS:
            return ConstantNode(name, CONSTANTS[name])

        raise self._error(f"未知的函数或常量 '{name}'", token)


def parse_expression(expression: str) -> Node:
    """一步完成"词法分析 + 语法分析"的便捷入口。

    Args:
        expression: 用户输入的表达式（可包含 ``×`` ``÷`` ``π`` 等符号）。

    Returns:
        表达式对应的 AST 根节点。
    """
    tokenizer = Tokenizer(expression)
    tokens = tokenizer.tokenize()
    return Parser(tokens, tokenizer.normalized).parse()
