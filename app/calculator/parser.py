"""表达式语法分析器（Parser）。

采用 **Pratt 解析 / 优先级爬升（precedence climbing）** 算法，把 Token 序列
转换成 AST。相比递归下降的"每个优先级写一个函数"的写法，优先级爬升用一张
优先级表统一驱动，新增运算符只需要改表，不需要改控制流。

文法（EBNF）
-----------
.. code-block:: text

    expression := add_sub
    add_sub    := mul_div   ( ('+' | '-') mul_div )*
    mul_div    := unary     ( ('*' | '/' | 'mod') unary
                            | <紧邻的隐式乘法> unary )*
    unary      := ('+' | '-') unary | power
    power      := postfix   ( '^' unary )?          # 右结合
    postfix    := primary   ( '!' | '%' )*
    primary    := NUMBER
                | IDENT '(' arg_list ')'
                | IDENT                             # 常量
                | '(' expression ')'

关键设计决策
------------
1. **一元负号优先级低于幂**：``-2^2`` 解析为 ``-(2^2) = -4``，符合数学惯例；
   同时 ``3*-2``、``2^-3`` 都能正常解析。
2. **``^`` 右结合**：``2^3^2`` 解析为 ``2^(3^2) = 512``。
3. **隐式乘法只在 Token 紧邻时生效**：``2pi``、``2(3+4)`` 合法，
   但 ``1 2`` 报语法错误，避免把用户的手误当成合法输入。
4. **函数名与参数个数在解析期校验**：错误尽早暴露，且能给出精确位置。

安全声明
--------
本解析器**不调用** ``eval`` / ``exec`` / ``compile`` / ``ast.literal_eval``，
也不使用任何"把字符串当代码执行"的第三方库。用户输入的字符只有两条出路：
被识别成合法 Token 进入 AST，或者被拒绝并报错。
"""

from __future__ import annotations

from .ast_nodes import (
    BinaryOpNode,
    ConstantNode,
    FactorialNode,
    FunctionNode,
    Node,
    NumberNode,
    UnaryOpNode,
)
from .errors import CalculatorError, ErrorCode, SyntaxError_, UnknownFunctionError
from .functions import FUNCTION_ARITY, is_constant, is_function
from .tokenizer import Token, TokenType, tokenize

#: 二元运算符优先级表（数值越大结合越紧）
BINARY_PRECEDENCE: dict[str, int] = {
    "+": 1,
    "-": 1,
    "*": 2,
    "/": 2,
    "mod": 2,
}


class Parser:
    """把 Token 序列解析成 AST。"""

    def __init__(self, tokens: list[Token]) -> None:
        self._tokens = tokens
        self._index = 0
        # 记录上一个被消费的 Token，用于判断"紧邻"从而实现隐式乘法
        self._prev: Token | None = None

    # ------------------------------------------------------------------ #
    # Token 游标管理
    # ------------------------------------------------------------------ #
    @property
    def _current(self) -> Token:
        return self._tokens[self._index]

    def _advance(self) -> Token:
        token = self._tokens[self._index]
        if token.type is not TokenType.EOF:
            self._prev = token
            self._index += 1
        return token

    def _expect(self, token_type: TokenType, what: str) -> Token:
        if self._current.type is not token_type:
            raise SyntaxError_(f"期望 {what}，实际遇到 {self._describe(self._current)}",
                               self._current.position)
        return self._advance()

    @staticmethod
    def _describe(token: Token) -> str:
        if token.type is TokenType.EOF:
            return "表达式结束"
        return f"“{token.value}”"

    def _is_adjacent_to_prev(self) -> bool:
        """当前 Token 是否与上一个被消费的 Token 直接相邻（中间没有空白）。"""
        if self._prev is None:
            return False
        return self._current.position == self._prev.position + len(self._prev.value)

    # ------------------------------------------------------------------ #
    # 文法规则
    # ------------------------------------------------------------------ #
    def parse(self) -> Node:
        """解析整个表达式，返回根节点。"""
        if self._current.type is TokenType.EOF:
            raise SyntaxError_("表达式不完整", 0)
        node = self._parse_add_sub()
        if self._current.type is not TokenType.EOF:
            raise SyntaxError_(
                f"表达式存在多余内容 {self._describe(self._current)}",
                self._current.position,
            )
        return node

    def _parse_add_sub(self) -> Node:
        node = self._parse_mul_div()
        while self._current.type is TokenType.OPERATOR and self._current.value in "+-":
            op = self._advance().value
            right = self._parse_mul_div()
            node = BinaryOpNode(op, node, right)
        return node

    def _parse_mul_div(self) -> Node:
        node = self._parse_unary()
        while True:
            token = self._current

            # 显式乘除：* / mod
            if token.type is TokenType.OPERATOR and token.value in "*/":
                op = self._advance().value
                node = BinaryOpNode(op, node, self._parse_unary())
                continue
            if token.type is TokenType.IDENTIFIER and token.value.lower() == "mod":
                self._advance()
                node = BinaryOpNode("mod", node, self._parse_unary())
                continue

            # 隐式乘法：2pi、2(3+4)、(1+2)(3+4)；要求 Token 紧邻，避免吞掉手误
            #
            # 额外排除"数字紧跟数字"的情形：否则 "1..2" 会被理解成
            # "1." 乘 ".2" 得到 0.2，把明显的输入错误变成一个看似合理的结果。
            # 让词法分析器把 "1..2" 切成了两个数字 Token 是合理的（"1." 是合法数字），
            # 但语法层必须拒绝这种连写。
            if token.type in (TokenType.NUMBER, TokenType.IDENTIFIER,
                              TokenType.LPAREN) and self._is_adjacent_to_prev():
                previous_is_number = (
                    self._prev is not None and self._prev.type is TokenType.NUMBER
                )
                if not (previous_is_number and token.type is TokenType.NUMBER):
                    node = BinaryOpNode("*", node, self._parse_unary())
                    continue

            return node

    def _parse_unary(self) -> Node:
        token = self._current
        if token.type is TokenType.OPERATOR and token.value in "+-":
            self._advance()
            operand = self._parse_unary()
            return UnaryOpNode(token.value, operand, postfix=False)
        return self._parse_power()

    def _parse_power(self) -> Node:
        base = self._parse_postfix()
        if self._current.type is TokenType.OPERATOR and self._current.value == "^":
            self._advance()
            # 右结合且允许指数带一元符号：2^-3、2^3^2
            exponent = self._parse_unary()
            return BinaryOpNode("^", base, exponent)
        return base

    def _parse_postfix(self) -> Node:
        node = self._parse_primary()
        while True:
            token = self._current
            if token.type is TokenType.FACTORIAL:
                self._advance()
                node = FactorialNode(node)
                continue
            if token.type is TokenType.PERCENT:
                self._advance()
                node = UnaryOpNode("%", node, postfix=True)
                continue
            return node

    def _parse_primary(self) -> Node:
        token = self._current

        if token.type is TokenType.NUMBER:
            self._advance()
            return NumberNode(token.value)

        if token.type is TokenType.LPAREN:
            self._advance()
            if self._current.type is TokenType.RPAREN:
                raise SyntaxError_("括号内缺少表达式", self._current.position)
            inner = self._parse_add_sub()
            self._expect(TokenType.RPAREN, "右括号 )")
            return inner

        if token.type is TokenType.IDENTIFIER:
            return self._parse_identifier()

        if token.type is TokenType.RPAREN:
            raise SyntaxError_("多余的右括号", token.position)
        if token.type is TokenType.COMMA:
            raise SyntaxError_("逗号位置不正确", token.position)
        if token.type is TokenType.EOF:
            raise SyntaxError_("表达式意外结束，缺少操作数", token.position)
        raise SyntaxError_(f"此处不应出现 {self._describe(token)}", token.position)

    def _parse_identifier(self) -> Node:
        token = self._advance()
        name = token.value

        # 情况一：函数调用，形如 sin(x) / log(x, 2)
        if self._current.type is TokenType.LPAREN:
            self._advance()
            args: list[Node] = []
            if self._current.type is not TokenType.RPAREN:
                args.append(self._parse_add_sub())
                while self._current.type is TokenType.COMMA:
                    self._advance()
                    args.append(self._parse_add_sub())
            self._expect(TokenType.RPAREN, "右括号 )")
            return self._build_function_node(name, args, token.position)

        # 情况二：常量，形如 pi / e
        if is_constant(name):
            return ConstantNode(name)

        # 情况三：既不是函数也不是常量
        raise CalculatorError(
            f"不支持的函数或常量：{name}",
            ErrorCode.UNKNOWN_FUNCTION,
            token.position,
        )

    @staticmethod
    def _build_function_node(name: str, args: list[Node], position: int) -> Node:
        """构造函数节点，同时在解析期完成"函数是否存在 + 参数个数是否正确"的校验。"""
        if not is_function(name):
            raise UnknownFunctionError(name, position)

        allowed = FUNCTION_ARITY.get(name.lower())
        if allowed is not None and len(args) not in allowed:
            expected = " 或 ".join(str(c) for c in allowed)
            raise SyntaxError_(
                f"函数 {name} 需要 {expected} 个参数，实际收到 {len(args)} 个",
                position,
            )

        # 语法糖：单参数调用 pow(x, y) 与 mod(x, y) 保持原样，
        # 由求值器统一处理，这里只做结构封装。
        return FunctionNode(name.lower(), tuple(args))


def parse(expression: str) -> Node:
    """便捷函数：词法分析 + 语法分析。

    :param expression: 用户输入的表达式
    :returns: AST 根节点
    :raises CalculatorError: 任何表达式错误
    """
    return Parser(tokenize(expression)).parse()
