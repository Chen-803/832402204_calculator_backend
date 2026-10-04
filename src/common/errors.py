"""全局异常处理。

把三类异常统一转换成前端的标准错误响应：

1. :class:`src.calculator.exceptions.CalculatorError`：业务异常，
   使用异常自带的 ``error_code`` 与 ``http_status``；
2. ``HTTPException``：Flask/Werkzeug 内置异常（404、405 等），
   转成 JSON 而不是默认的 HTML 页面，保证前端拿到的一律是 JSON；
3. 其它未预期异常：记录完整堆栈，对外只暴露 "服务器内部错误"，
   避免把实现细节泄漏给调用方。
"""

import logging
import traceback

from flask import Flask, Response
from werkzeug.exceptions import HTTPException

from ..calculator.exceptions import CalculatorError
from .api_response import error_response

__all__ = ["register_error_handlers"]

_LOGGER = logging.getLogger(__name__)

#: Werkzeug 内置异常到中文文案的映射。
_HTTP_MESSAGES = {
    400: "请求格式错误：请确认请求体是合法的 JSON",
    401: "未授权访问",
    403: "没有权限访问该资源",
    404: "请求的接口或资源不存在",
    405: "请求方法不被允许",
    413: "请求体过大",
    415: "不支持的请求内容类型，请使用 application/json",
    500: "服务器内部错误",
}


def register_error_handlers(app: Flask) -> None:
    """把所有异常处理器注册到应用上。"""

    @app.errorhandler(CalculatorError)
    def handle_calculator_error(exc: CalculatorError) -> Response:
        """业务异常 -> 标准错误响应。"""
        _LOGGER.info("业务异常：%s (%s)", exc.message, exc.error_code)
        extra = dict(exc.to_dict())
        # message / error_code 已经作为位置参数传入，这里只补充其余字段
        extra.pop("message", None)
        extra.pop("error_code", None)
        return error_response(exc.message, exc.error_code, exc.http_status, **extra)

    @app.errorhandler(HTTPException)
    def handle_http_exception(exc: HTTPException) -> Response:
        """HTTP 异常 -> JSON 错误响应。"""
        message = _HTTP_MESSAGES.get(exc.code, exc.description or "请求失败")
        code_map = {
            400: "BAD_REQUEST",
            404: "NOT_FOUND",
            405: "METHOD_NOT_ALLOWED",
            415: "UNSUPPORTED_MEDIA_TYPE",
        }
        error_code = code_map.get(exc.code, "HTTP_ERROR")
        return error_response(message, error_code, exc.code or 500)

    @app.errorhandler(Exception)
    def handle_unexpected_error(exc: Exception) -> Response:
        """兜底异常处理：记录堆栈，对外返回 500。"""
        _LOGGER.error("未预期异常：%s\n%s", exc, traceback.format_exc())
        return error_response(
            "服务器内部错误，请稍后重试或联系开发者", "UNKNOWN_ERROR", 500
        )
