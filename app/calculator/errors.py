"""计算器模块的异常体系。

设计说明
--------
所有由"用户表达式"引起的问题都收敛到 :class:`CalculatorError` 这一个基类，
并携带一个稳定的业务错误码 ``code``。上层（Service / Controller）只需要捕获
``CalculatorError`` 就能把任意表达式错误转换成统一的 API 响应，不需要了解
词法、语法、求值三个阶段的差异。

这样做的好处：
1. 异常 → 错误码 → HTTP 状态码 的映射表只有一份，位于 ``app/common/errors.py``；
2. 单元测试可以直接断言 ``code``，不受 message 文案调整的影响；
3. 新增错误类型时不必修改 Controller。
"""

from __future__ import annotations

from enum import IntEnum


class ErrorCode(IntEnum):
    """业务错误码。

    与 ``docs/API_CONTRACT.md`` 中的错误码表一一对应，禁止随意改动数值。
    """

    OK = 0

    # --- 表达式相关（HTTP 400） ---
    EMPTY_EXPRESSION = 40001
    SYNTAX_ERROR = 40002
    DIVISION_BY_ZERO = 40003
    EXPRESSION_TOO_LONG = 40004
    UNKNOWN_FUNCTION = 40005
    DOMAIN_ERROR = 40006

    # --- 转换相关（HTTP 400） ---
    INVALID_BASE = 40007
    INVALID_UNIT = 40008
    ILLEGAL_CHARACTER = 40009

    # --- 资源相关（HTTP 404） ---
    HISTORY_NOT_FOUND = 40401

    # --- 请求相关（HTTP 422） ---
    INVALID_REQUEST = 42201

    # --- 服务端（HTTP 500） ---
    INTERNAL_ERROR = 50000


class CalculatorError(Exception):
    """所有表达式计算类异常的基类。

    :param message: 直接面向用户的中文提示，会被原样放进 API 响应的 ``message`` 字段。
    :param code: 业务错误码，默认 ``SYNTAX_ERROR``。
    :param position: 出错字符在表达式中的下标（从 0 开始），用于给用户精确定位。
    """

    def __init__(
        self,
        message: str,
        code: ErrorCode = ErrorCode.SYNTAX_ERROR,
        position: int | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.position = position

    def __str__(self) -> str:  # pragma: no cover - 仅调试用
        if self.position is None:
            return self.message
        return f"{self.message}（位置 {self.position}）"


class EmptyExpressionError(CalculatorError):
    """表达式为空或只有空白字符。"""

    def __init__(self, message: str = "表达式为空") -> None:
        super().__init__(message, ErrorCode.EMPTY_EXPRESSION)


class ExpressionTooLongError(CalculatorError):
    """表达式长度超过安全上限。

    限制长度既是为了防误输入，也是拒绝服务（DoS）防护措施：表达式越长，
    语法分析递归越深，必须提前拒绝。
    """

    def __init__(self, limit: int) -> None:
        super().__init__(
            f"表达式过长，最多支持 {limit} 个字符",
            ErrorCode.EXPRESSION_TOO_LONG,
        )


class IllegalCharacterError(CalculatorError):
    """出现了词法分析无法识别的字符。"""

    def __init__(self, char: str, position: int) -> None:
        super().__init__(
            f"字符无法识别：{char}",
            ErrorCode.ILLEGAL_CHARACTER,
            position,
        )


class SyntaxError_(CalculatorError):
    """语法错误：括号不匹配、缺少操作数、函数参数个数不对等。"""

    def __init__(self, message: str, position: int | None = None) -> None:
        super().__init__(f"表达式语法错误：{message}", ErrorCode.SYNTAX_ERROR, position)


class DivisionByZeroError(CalculatorError):
    """除数为 0（含对 0 取模、0 的负数次幂）。"""

    def __init__(self, message: str = "除数不能为 0") -> None:
        super().__init__(message, ErrorCode.DIVISION_BY_ZERO)


class UnknownFunctionError(CalculatorError):
    """调用了未注册的函数名。"""

    def __init__(self, name: str, position: int | None = None) -> None:
        super().__init__(f"不支持的函数：{name}", ErrorCode.UNKNOWN_FUNCTION, position)


class DomainError(CalculatorError):
    """数学定义域错误，例如 sqrt(-1)、ln(0)、asin(2)、(-8)^0.5。"""

    def __init__(self, message: str) -> None:
        super().__init__(f"函数定义域错误：{message}", ErrorCode.DOMAIN_ERROR)
