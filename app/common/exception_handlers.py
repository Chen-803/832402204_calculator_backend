"""全局异常处理器。

**为什么要把异常处理集中到一处**

如果没有这一层，每个路由函数里都会出现这样的样板：::

    try:
        ...
    except ValueError as e:
        return JSONResponse(status_code=400, content={...})
    except Exception as e:
        return JSONResponse(status_code=500, content={...})

结果是：不同接口的错误报文长得不一样，前端要写好几套解析逻辑；
而且一旦漏掉某个分支，就会把 Python 的堆栈信息直接暴露给用户。

注册全局处理器后：

- **任何**异常路径（包括路由不存在、请求体格式错误这些框架自己抛的异常）
  都会经过 :func:`api_response`，响应结构 100% 一致；
- 业务代码里可以放心地 ``raise``，不需要关心 HTTP 状态码；
- 500 的堆栈只写日志，不回传给客户端，避免泄露内部实现。
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from ..calculator.errors import CalculatorError, ErrorCode
from .exceptions import BusinessError
from .responses import error_response

logger = logging.getLogger("calculator.exception")


def _first_validation_message(exc: RequestValidationError) -> str:
    """把 Pydantic 的校验错误整理成一句中文提示。"""
    errors = exc.errors()
    if not errors:
        return "请求参数不合法"
    first = errors[0]
    location = ".".join(str(part) for part in first.get("loc", ()) if part != "body")
    reason = first.get("msg", "格式不正确")
    if location:
        return f"请求参数不合法：{location} {reason}"
    return f"请求参数不合法：{reason}"


def register_exception_handlers(app: FastAPI) -> None:
    """把全部异常处理器注册到 FastAPI 应用上。"""

    @app.exception_handler(CalculatorError)
    async def _handle_calculator_error(_: Request, exc: CalculatorError):
        """表达式类错误 → 400，message 可直接展示给用户。"""
        payload: dict[str, object] = {}
        if exc.position is not None:
            payload["position"] = exc.position
        return error_response(exc.message, exc.code, **payload)

    @app.exception_handler(BusinessError)
    async def _handle_business_error(_: Request, exc: BusinessError):
        """业务类错误 → 404 / 400 等。"""
        return error_response(exc.message, exc.code)

    @app.exception_handler(RequestValidationError)
    async def _handle_validation_error(_: Request, exc: RequestValidationError):
        """请求体结构错误 → 422。"""
        return error_response(
            _first_validation_message(exc),
            ErrorCode.INVALID_REQUEST,
            http_status=422,
            details=[
                {"field": ".".join(str(p) for p in err.get("loc", ())), "reason": err.get("msg", "")}
                for err in exc.errors()[:5]
            ],
        )

    @app.exception_handler(StarletteHTTPException)
    async def _handle_http_exception(_: Request, exc: StarletteHTTPException):
        """框架抛出的 HTTPException（例如 404 路由不存在）也走统一信封。"""
        code = ErrorCode.INVALID_REQUEST
        if exc.status_code == 404:
            code = ErrorCode.HISTORY_NOT_FOUND
        elif exc.status_code >= 500:
            code = ErrorCode.INTERNAL_ERROR
        message = exc.detail if isinstance(exc.detail, str) else "请求失败"
        return error_response(message, code, http_status=exc.status_code)

    @app.exception_handler(Exception)
    async def _handle_unexpected(request: Request, exc: Exception):
        """兜底：未预期异常 → 500，堆栈只写日志。"""
        logger.exception("未处理异常 %s %s: %s", request.method, request.url.path, exc)
        return error_response(
            "服务器内部错误，请稍后重试",
            ErrorCode.INTERNAL_ERROR,
            http_status=500,
        )
