"""计算器领域异常定义。

本模块集中定义表达式解析与求值过程中可能抛出的业务异常。
所有异常都携带 ``error_code``（稳定的机器可读错误码）与 ``http_status``
（建议返回给前端的 HTTP 状态码），便于上层统一转换成标准 API 响应。

设计说明：
    将"计算错误"与"参数校验错误"统一收敛到 :class:`CalculatorError` 之下，
    控制器层只需要一个异常处理器即可，避免在每一层写重复的 try/except。
"""

from typing import Optional

__all__ = [
    "CalculatorError",
    "EmptyExpressionError",
    "ExpressionTooLongError",
    "InvalidCharacterError",
    "InvalidExpressionError",
    "DivisionByZeroError",
    "MathDomainError",
    "NumericOverflowError",
    "ValidationError",
]


class CalculatorError(Exception):
    """计算器异常基类。

    Attributes:
        error_code: 机器可读的错误码，前端据此选择提示样式。
        http_status: 建议的 HTTP 状态码。
        message: 面向用户的错误描述。
        position: 出错字符在原始表达式中的下标（从 0 开始），未知时为 None。
    """

    error_code: str = "UNKNOWN_ERROR"
    http_status: int = 400

    def __init__(self, message: str, position: Optional[int] = None) -> None:
        super().__init__(message)
        self.message = message
        self.position = position
        #: 额外上下文，会一并放进错误响应，方便前端回显。
        self.context: dict = {}

    def attach_context(self, **context) -> "CalculatorError":
        """附加额外上下文并返回自身，便于在 ``except`` 中链式调用。"""
        self.context.update(context)
        return self

    def to_dict(self) -> dict:
        """转换为可 JSON 序列化的字典（供 API 层直接使用）。"""
        payload = {"message": self.message, "error_code": self.error_code}
        if self.position is not None:
            payload["position"] = self.position
        payload.update(self.context)
        return payload


class EmptyExpressionError(CalculatorError):
    """表达式为空或只有空白字符。"""

    error_code = "EMPTY_EXPRESSION"
    http_status = 400


class ExpressionTooLongError(CalculatorError):
    """表达式长度超出允许上限（防止恶意超长输入拖垮服务）。"""

    error_code = "EXPRESSION_TOO_LONG"
    http_status = 400


class InvalidCharacterError(CalculatorError):
    """表达式包含无法识别的字符。"""

    error_code = "INVALID_CHARACTER"
    http_status = 400


class InvalidExpressionError(CalculatorError):
    """表达式语法错误（括号不匹配、缺少操作数、未知函数等）。"""

    error_code = "INVALID_EXPRESSION"
    http_status = 400


class DivisionByZeroError(CalculatorError):
    """除数为零（包含取模运算的除数为零）。"""

    error_code = "DIVISION_BY_ZERO"
    http_status = 400


class MathDomainError(CalculatorError):
    """数学定义域错误，例如 sqrt(-1)、ln(0)、asin(2)。"""

    error_code = "MATH_DOMAIN_ERROR"
    http_status = 400


class NumericOverflowError(CalculatorError):
    """计算结果超出可表示范围或计算量过大。"""

    error_code = "OVERFLOW_ERROR"
    http_status = 400


class ValidationError(CalculatorError):
    """请求参数校验失败（分页参数非法、请求体格式错误等）。"""

    error_code = "VALIDATION_ERROR"
    http_status = 400
