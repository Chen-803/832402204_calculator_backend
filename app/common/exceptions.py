"""业务异常。

与 :class:`app.calculator.errors.CalculatorError` 的区别：

- ``CalculatorError`` 描述"用户表达式有问题"，由计算器内核抛出；
- :class:`BusinessError` 描述"业务规则不满足"，例如"要删的历史记录不存在"。

两者都由 ``app.common.exception_handlers`` 统一转成标准信封响应，
Controller 里因此没有任何 ``try/except`` 样板代码。
"""

from __future__ import annotations

from ..calculator.errors import ErrorCode


class BusinessError(Exception):
    """业务规则异常。

    :param message: 面向用户的中文提示
    :param code: 业务错误码
    """

    def __init__(self, message: str, code: ErrorCode = ErrorCode.INVALID_REQUEST) -> None:
        super().__init__(message)
        self.message = message
        self.code = code


class NotFoundError(BusinessError):
    """请求的资源不存在（HTTP 404）。"""

    def __init__(self, message: str) -> None:
        super().__init__(message, ErrorCode.HISTORY_NOT_FOUND)


class InvalidConversionError(BusinessError):
    """进制 / 单位转换参数不合法（HTTP 400）。"""

    def __init__(self, message: str, code: ErrorCode = ErrorCode.INVALID_BASE) -> None:
        super().__init__(message, code)
