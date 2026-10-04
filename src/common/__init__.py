"""通用工具包：统一响应格式与全局异常处理。"""

from .api_response import error_response, success_response
from .errors import register_error_handlers

__all__ = ["success_response", "error_response", "register_error_handlers"]
