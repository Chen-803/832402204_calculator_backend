"""统一 API 响应构造。

设计动机
--------
作业要求后端"返回标准化的 API 响应"。标准化的价值在于：**前端只需要写一套
解析逻辑**，就能处理所有接口的成功与失败。

本项目采用**扁平信封**：

.. code-block:: json

    { "success": true, "code": 0, "message": "OK", "...业务字段": "..." }

为什么业务字段平铺在顶层，而不是塞进 ``data`` 子对象？

1. 作业示例给的报文就是平铺的（``{"success": true, "expression": "...", "result": 9}``），
   保持一致可以少一次"示例与实现不符"的解释成本；
2. 前端拿字段更直接：``res.resultText`` 而不是 ``res.data.resultText``；
3. ``data=null`` 这类"信封套信封"的写法在调试时噪音更大。

代价是响应体的字段命名空间是扁平的，因此规定：**业务字段不得使用
``success`` / ``code`` / ``message`` 这三个保留名**。
"""

from __future__ import annotations

from typing import Any

from fastapi.responses import JSONResponse

from ..calculator.errors import ErrorCode

#: 保留字段名，业务字段不得占用
RESERVED_FIELDS = frozenset({"success", "code", "message"})

#: 业务错误码 → HTTP 状态码
CODE_TO_HTTP_STATUS: dict[ErrorCode, int] = {
    ErrorCode.OK: 200,
    ErrorCode.EMPTY_EXPRESSION: 400,
    ErrorCode.SYNTAX_ERROR: 400,
    ErrorCode.DIVISION_BY_ZERO: 400,
    ErrorCode.EXPRESSION_TOO_LONG: 400,
    ErrorCode.UNKNOWN_FUNCTION: 400,
    ErrorCode.DOMAIN_ERROR: 400,
    ErrorCode.INVALID_BASE: 400,
    ErrorCode.INVALID_UNIT: 400,
    ErrorCode.ILLEGAL_CHARACTER: 400,
    ErrorCode.HISTORY_NOT_FOUND: 404,
    ErrorCode.INVALID_REQUEST: 422,
    ErrorCode.INTERNAL_ERROR: 500,
}


def http_status_for(code: ErrorCode | int, default: int = 400) -> int:
    """把业务错误码映射成 HTTP 状态码。"""
    try:
        error_code = ErrorCode(code)
    except ValueError:
        return default
    return CODE_TO_HTTP_STATUS.get(error_code, default)


def api_response(
    *,
    success: bool,
    code: int = int(ErrorCode.OK),
    message: str = "OK",
    http_status: int | None = None,
    **payload: Any,
) -> JSONResponse:
    """构造统一信封响应。

    :param success: 业务是否成功
    :param code: 业务错误码，成功为 0
    :param message: 人类可读信息
    :param http_status: 显式指定 HTTP 状态码；不传则按错误码推断
    :param payload: 业务字段，平铺到响应顶层
    """
    body: dict[str, Any] = {"success": success, "code": int(code), "message": message}
    for key, value in payload.items():
        if key in RESERVED_FIELDS:
            raise ValueError(f"业务字段名 {key!r} 与响应信封保留字段冲突")
        body[key] = value

    if http_status is None:
        http_status = http_status_for(ErrorCode(code), default=200 if success else 400)

    return JSONResponse(status_code=http_status, content=body)


def ok_response(message: str = "OK", http_status: int = 200, **payload: Any) -> JSONResponse:
    """成功响应。"""
    return api_response(
        success=True,
        code=int(ErrorCode.OK),
        message=message,
        http_status=http_status,
        **payload,
    )


def error_response(
    message: str,
    code: ErrorCode,
    http_status: int | None = None,
    **payload: Any,
) -> JSONResponse:
    """失败响应。"""
    return api_response(
        success=False,
        code=int(code),
        message=message,
        http_status=http_status if http_status is not None else http_status_for(code),
        **payload,
    )
