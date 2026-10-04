"""表达式词法分析器（Tokenizer）。

把用户输入的表达式字符串切分成 Token 序列，作为语法分析（Parser）的输入。

安全设计：
    * 只识别白名单字符，遇到任何其它字符立即报错，天然阻断了代码注入；
    * 不做任何"执行"动作，纯字符串扫描；
    * 先把中文/全角/Unicode 数学符号归一化成 ASCII 形式，
      这样前端展示的 ``×``、``÷``、``π``、``√`` 也能被正确接受。

支持的语法元素：
    * 数字：``12``、``3.14``、``.5``、``1e-3``
    * 运算符：``+ - * / % ^``（``%`` 为取模，``^`` 为幂）
    * 括号：``( )``
    * 函数与常量：``sqrt(9)``、``pi``、``e``（见 :mod:`src.calculator.functions`）
    * 阶乘后缀：``5!``
    * 函数多参数分隔符：``log(2, 8)``
"""

from dataclasses import dataclass
from enum import Enum
from typing import List

from .exceptions import ExpressionTooLongError, InvalidCharacterError, InvalidExpressionError

__all__ = ["TokenType", "Token", "normalize_expression", "Tokenizer", "MAX_EXPRESSION_LENGTH"]

#: 表达式最大长度。前端输入框同样有 maxlength 限制，这里是服务端最后一道防线。
MAX_EXPRESSION_LENGTH = 200

#: Unicode / 全角符号 -> ASCII 归一化表。
_NORMALIZE_MAP = {
    "×": "*", "✕": "*", "✖": "*", "·": "*", "⋅": "*", "＊": "*", "∗": "*",
    "÷": "/", "／": "/", "∕": "/",
    "−": "-", "–": "-", "—": "-", "－": "-",
    "＋": "+", "（": "(", "）": ")", "，": ",", "％": "%", "＾": "^",
    "。": ".", "．": ".",
    "π": "pi", "√": "sqrt", "∛": "cbrt", "²": "^2", "³": "^3",
}
for _index, _full_width in enumerate("０１２３４５６７８９"):
    _NORMALIZE_MAP[_full_width] = str(_index)


class TokenType(Enum):
    """Token 类型枚举。"""

    NUMBER = "NUMBER"
    OPERATOR = "OPERATOR"
    IDENTIFIER = "IDENTIFIER"
    LEFT_PAREN = "LEFT_PAREN"
    RIGHT_PAREN = "RIGHT_PAREN"
    COMMA = "COMMA"
    FACTORIAL = "FACTORIAL"
    END = "END"


@dataclass(frozen=True)
class Token:
    """一个词法单元。

    Attributes:
        type: Token 类型。
        value: 归一化之后的文本内容（数字字面量或运算符/标识符原文）。
        position: 在原始表达式中的下标，用于精确报错。
    """

    type: TokenType
    value: str
    position: int


def normalize_expression(raw: str) -> str:
    """把用户输入归一化成后端内部统一的 ASCII 表达式。

    Args:
        raw: 用户原始输入。

    Returns:
        归一化后的表达式（保留空格，便于按位置报错）。
    """
    text = raw
    for source, target in _NORMALIZE_MAP.items():
        text = text.replace(source, target)
    # ``**`` 是很多语言里的幂运算符，这里统一成 ``^``。
    while "**" in text:
        text = text.replace("**", "^")
    return text


def describe_position(text: str, position: int) -> str:
    """生成"第 N 个字符附近"的可读提示，帮助用户定位错误。"""
    if position < 0 or position > len(text):
        return ""
    start = max(0, position - 6)
    end = min(len(text), position + 7)
    fragment = text[start:end]
    return f"（第 {position + 1} 个字符附近：…{fragment}…）"


class Tokenizer:
    """把表达式字符串切成 Token 列表。

    Example:
        >>> [t.value for t in Tokenizer("1+2*3").tokenize()]
        ['1', '+', '2', '*', '3', '']
    """

    def __init__(self, expression: str) -> None:
        self._raw = expression
        self._text = normalize_expression(expression)

    @property
    def normalized(self) -> str:
        """归一化之后的表达式文本。"""
        return self._text

    def tokenize(self) -> List[Token]:
        """执行词法分析。

        Returns:
            Token 列表，最后一项固定是 :attr:`TokenType.END`。

        Raises:
            ExpressionTooLongError: 表达式长度超限。
            InvalidCharacterError: 出现白名单之外的字符。
            InvalidExpressionError: 数字字面量格式非法。
        """
        if len(self._text) > MAX_EXPRESSION_LENGTH:
            raise ExpressionTooLongError(
                f"表达式过长，最多支持 {MAX_EXPRESSION_LENGTH} 个字符（当前 {len(self._text)} 个）"
            )

        tokens: List[Token] = []
        index = 0
        length = len(self._text)

        while index < length:
            char = self._text[index]

            if char.isspace():
                index += 1
                continue

            if char.isdigit() or (char == "." and self._is_digit_at(index + 1)):
                token, index = self._scan_number(index)
                tokens.append(token)
                continue

            if char.isalpha() or char == "_":
                token, index = self._scan_identifier(index)
                tokens.append(token)
                continue

            if char in "+-*/%^":
                tokens.append(Token(TokenType.OPERATOR, char, index))
                index += 1
                continue

            if char == "(":
                tokens.append(Token(TokenType.LEFT_PAREN, char, index))
                index += 1
                continue

            if char == ")":
                tokens.append(Token(TokenType.RIGHT_PAREN, char, index))
                index += 1
                continue

            if char == ",":
                tokens.append(Token(TokenType.COMMA, char, index))
                index += 1
                continue

            if char == "!":
                tokens.append(Token(TokenType.FACTORIAL, char, index))
                index += 1
                continue

            if char == ".":
                raise InvalidExpressionError(
                    f"小数点位置不合法{describe_position(self._text, index)}", position=index
                )

            raise InvalidCharacterError(
                f"表达式包含非法字符 '{char}'{describe_position(self._text, index)}", position=index
            )

        tokens.append(Token(TokenType.END, "", length))
        return tokens

    def _is_digit_at(self, index: int) -> bool:
        """判断指定下标处是否为数字字符。"""
        return index < len(self._text) and self._text[index].isdigit()

    def _scan_number(self, start: int):
        """扫描一个数字字面量（支持小数与科学计数法）。"""
        index = start
        length = len(self._text)
        dots = 0

        while index < length and (self._text[index].isdigit() or self._text[index] == "."):
            if self._text[index] == ".":
                dots += 1
                if dots > 1:
                    raise InvalidExpressionError(
                        f"数字中出现了多个小数点{describe_position(self._text, index)}",
                        position=index,
                    )
            index += 1

        # 科学计数法：1e3 / 1.5E-2（只有紧跟数字时才视为指数部分）
        if index < length and self._text[index] in "eE":
            cursor = index + 1
            if cursor < length and self._text[cursor] in "+-":
                cursor += 1
            if cursor < length and self._text[cursor].isdigit():
                while cursor < length and self._text[cursor].isdigit():
                    cursor += 1
                index = cursor

        literal = self._text[start:index]
        if literal in (".", ""):
            raise InvalidExpressionError(
                f"数字格式不合法{describe_position(self._text, start)}", position=start
            )
        return Token(TokenType.NUMBER, literal, start), index

    def _scan_identifier(self, start: int):
        """扫描一个标识符（函数名或常量名）。"""
        index = start
        length = len(self._text)
        while index < length and (self._text[index].isalnum() or self._text[index] == "_"):
            index += 1
        return Token(TokenType.IDENTIFIER, self._text[start:index].lower(), start), index
