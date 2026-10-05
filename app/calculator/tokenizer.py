"""表达式词法分析器（Tokenizer）。

职责
----
把用户输入的表达式字符串切分成有类型的 Token 序列，供语法分析器消费。

为什么不用正则一把梭
--------------------
``re.split`` 之类的做法无法区分"一元负号"和"二元减号"，也无法给出精确的出错位置。
这里用**手写状态机**逐字符扫描，好处是：

1. 每个 Token 都记录了它在原串中的起始下标，报错时能精确定位；
2. 可以顺手处理全角字符、空白符等输入噪声；
3. 完全不依赖任何第三方库，避免"用错库就等于任意代码执行"的风险。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

from .errors import EmptyExpressionError, ExpressionTooLongError, IllegalCharacterError, SyntaxError_

#: 表达式长度上限。既是易用性约束，也是拒绝服务（DoS）防护。
MAX_EXPRESSION_LENGTH = 500

#: 括号最大嵌套深度，防止构造超深递归拖垮语法分析器。
#: 语法分析每层括号约消耗 6 个 Python 栈帧，取 64 可保证远低于默认递归上限（1000）。
MAX_NESTING_DEPTH = 64


class TokenType(Enum):
    """Token 类型。"""

    NUMBER = auto()      # 数字字面量，如 12、3.14、1.5e-3
    IDENTIFIER = auto()  # 标识符：函数名或常量名，如 sin、pi
    OPERATOR = auto()    # 运算符：+ - * / ^ mod
    LPAREN = auto()      # (
    RPAREN = auto()      # )
    COMMA = auto()       # ,
    FACTORIAL = auto()   # ! 后缀阶乘
    PERCENT = auto()     # % 后缀百分号
    EOF = auto()         # 结束标记，简化语法分析器的边界判断


@dataclass(frozen=True)
class Token:
    """一个词法单元。

    :param type: Token 类型
    :param value: Token 的原始文本
    :param position: 在（归一化后的）表达式中的起始下标
    """

    type: TokenType
    value: str
    position: int

    def __repr__(self) -> str:  # pragma: no cover - 仅调试用
        return f"Token({self.type.name}, {self.value!r}, pos={self.position})"


#: 输入归一化映射表：把常见全角字符与数学符号统一成 ASCII 形式。
#: 这样用户从 Word / 微信里复制来的 "１２＋３" 或 "(1+2)×3" 也能正常计算。
_NORMALIZE_MAP = {
    # 运算符号
    "×": "*", "✕": "*", "✖": "*", "＊": "*", "·": "*",
    "÷": "/", "／": "/",
    "−": "-", "–": "-", "—": "-", "－": "-",
    "＋": "+",
    "＾": "^", "︿": "^",
    "！": "!", "％": "%",
    "＊": "*",
    # 括号与逗号
    "（": "(", "）": ")", "［": "[", "］": "]",
    "，": ",", "、": ",",
    # 空格类
    "\u3000": " ", "\u00a0": " ",
}

#: 全角数字 → 半角数字
_FULLWIDTH_DIGITS = {chr(ord("０") + i): str(i) for i in range(10)}


def normalize_expression(raw: str) -> str:
    """把用户输入归一化成标准 ASCII 表达式。

    :param raw: 用户原始输入
    :returns: 归一化后的表达式（未做去空白处理，词法分析器会跳过空白）
    :raises EmptyExpressionError: 输入为空或只有空白
    :raises ExpressionTooLongError: 归一化后长度超过 :data:`MAX_EXPRESSION_LENGTH`
    """
    if raw is None:
        raise EmptyExpressionError()

    text = raw.strip()
    if not text:
        raise EmptyExpressionError()

    result_chars: list[str] = []
    for ch in text:
        if ch in _FULLWIDTH_DIGITS:
            result_chars.append(_FULLWIDTH_DIGITS[ch])
        elif ch in _NORMALIZE_MAP:
            result_chars.append(_NORMALIZE_MAP[ch])
        else:
            result_chars.append(ch)
    normalized = "".join(result_chars)

    if len(normalized) > MAX_EXPRESSION_LENGTH:
        raise ExpressionTooLongError(MAX_EXPRESSION_LENGTH)
    if not normalized.strip():
        raise EmptyExpressionError()
    return normalized


def _is_identifier_start(ch: str) -> bool:
    return ch.isalpha() or ch == "_"


def _is_identifier_part(ch: str) -> bool:
    return ch.isalnum() or ch == "_"


class Tokenizer:
    """手写状态机词法分析器。"""

    def __init__(self, text: str) -> None:
        self._text = text
        self._pos = 0
        self._length = len(text)

    def tokenize(self) -> list[Token]:
        """扫描整个表达式，返回 Token 列表，末尾一定是一个 ``EOF`` Token。"""
        tokens: list[Token] = []
        depth = 0

        while self._pos < self._length:
            ch = self._text[self._pos]

            # 1) 跳过空白
            if ch.isspace():
                self._pos += 1
                continue

            # 2) 数字字面量
            if ch.isdigit() or (ch == "." and self._peek_is_digit(1)):
                tokens.append(self._read_number())
                continue

            # 3) 标识符（函数名 / 常量名）
            if _is_identifier_start(ch):
                tokens.append(self._read_identifier())
                continue

            # 4) 单字符 Token
            start = self._pos
            if ch == "(":
                depth += 1
                if depth > MAX_NESTING_DEPTH:
                    raise SyntaxError_(
                        f"括号嵌套层数过多，最多 {MAX_NESTING_DEPTH} 层", start
                    )
                self._pos += 1
                tokens.append(Token(TokenType.LPAREN, ch, start))
                continue
            if ch == ")":
                depth -= 1
                if depth < 0:
                    raise SyntaxError_("多余的右括号", start)
                self._pos += 1
                tokens.append(Token(TokenType.RPAREN, ch, start))
                continue
            if ch == ",":
                self._pos += 1
                tokens.append(Token(TokenType.COMMA, ch, start))
                continue
            if ch == "!":
                self._pos += 1
                tokens.append(Token(TokenType.FACTORIAL, ch, start))
                continue
            if ch == "%":
                self._pos += 1
                tokens.append(Token(TokenType.PERCENT, ch, start))
                continue
            if ch in "+-*/^":
                self._pos += 1
                tokens.append(Token(TokenType.OPERATOR, ch, start))
                continue

            # 5) 走到这里说明是非法字符
            raise IllegalCharacterError(ch, start)

        if depth != 0:
            raise SyntaxError_("缺少右括号", self._length)

        tokens.append(Token(TokenType.EOF, "", self._length))
        return tokens

    # ------------------------------------------------------------------ #
    # 内部辅助方法
    # ------------------------------------------------------------------ #
    def _peek_is_digit(self, offset: int) -> bool:
        idx = self._pos + offset
        return idx < self._length and self._text[idx].isdigit()

    def _read_number(self) -> Token:
        """读取数字字面量，支持 ``12``、``3.14``、``.5``、``1.5e-3`` 四种形态。"""
        start = self._pos
        seen_dot = False

        while self._pos < self._length:
            ch = self._text[self._pos]
            if ch.isdigit():
                self._pos += 1
            elif ch == "." and not seen_dot:
                seen_dot = True
                self._pos += 1
            else:
                break

        # 科学计数法：数字后紧跟 e/E，且后面确实跟着指数
        if self._pos < self._length and self._text[self._pos] in "eE":
            save = self._pos
            idx = self._pos + 1
            if idx < self._length and self._text[idx] in "+-":
                idx += 1
            if idx < self._length and self._text[idx].isdigit():
                self._pos = idx
                while self._pos < self._length and self._text[self._pos].isdigit():
                    self._pos += 1
            else:
                # 不是科学计数法（例如 "2e" 后面没有数字），回退，
                # 让 e 作为常量被后续逻辑处理，从而支持 "2e" = 2*e 这种写法。
                self._pos = save

        value = self._text[start:self._pos]
        if value == ".":
            raise SyntaxError_("孤立的小数点", start)
        return Token(TokenType.NUMBER, value, start)

    def _read_identifier(self) -> Token:
        start = self._pos
        while self._pos < self._length and _is_identifier_part(self._text[self._pos]):
            self._pos += 1
        return Token(TokenType.IDENTIFIER, self._text[start:self._pos], start)


def tokenize(expression: str) -> list[Token]:
    """便捷函数：归一化 + 词法分析。"""
    return Tokenizer(normalize_expression(expression)).tokenize()
