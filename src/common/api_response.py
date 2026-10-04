"""统一的 API 响应构造器。

前后端分离项目最重要的约定之一就是"响应格式稳定"。
本模块把成功/失败两种响应的外壳收敛到一处，避免每个控制器各写一套：

成功响应::

    {"success": true, "data": {...}, "message": "操作成功"}

失败响应::

    {"success": false, "message": "除数不能为零", "error_code": "DIVISION_BY_ZERO",
     "expression": "1/0"}

其中 ``error_code`` 是稳定的机器可读错误码，前端据此决定提示样式，
而不是去匹配中文文案（文案改动不会破坏前端逻辑）。
"""

from typing import Any, Dict, Optional, Tuple

from flask import jsonify

__all__ = ["success_response", "error_response", "ResponsePayload"]

#: 控制器返回值类型别名：(可 JSON 序列化的字典, HTTP 状态码)
ResponsePayload = Tuple[Any, int]

DEFAULT_SUCCESS_MESSAGE = "操作成功"
DEFAULT_ERROR_CODE = "UNKNOWN_ERROR"


def success_response(
    data: Any = None,
    message: str = DEFAULT_SUCCESS_MESSAGE,
    status: int = 200,
    flat: Optional[Dict[str, Any]] = None,
) -> Any:
    """构造成功响应。

    Args:
        data: 业务数据，放在 ``data`` 字段下。
        message: 面向用户的提示信息。
        status: HTTP 状态码，默认 200。
        flat: 需要提升到响应体顶层字段的键值对。
            ``/api/calculate`` 按作业示例返回扁平的
            ``{"success":true,"expression":"...","result":20}``，
            此时不再额外输出 ``data`` 字段，保持响应体干净。

    Returns:
        Flask 响应对象与状态码组成的元组。
    """
    payload: Dict[str, Any] = {"success": True}
    if flat:
        payload.update(flat)
        payload["message"] = message
        return jsonify(payload), status

    payload["data"] = data
    payload["message"] = message
    return jsonify(payload), status


def error_response(
    message: str,
    error_code: str = DEFAULT_ERROR_CODE,
    status: int = 400,
    **extra: Any,
) -> Any:
    """构造失败响应。

    Args:
        message: 面向用户的错误描述（中文）。
        error_code: 稳定的错误码。
        status: HTTP 状态码，默认 400。
        **extra: 需要附加的字段，例如 ``expression`` 或 ``position``。

    Returns:
        Flask 响应对象与状态码组成的元组。
    """
    payload: Dict[str, Any] = {"success": False, "message": message, "error_code": error_code}
    payload.update(extra)
    return jsonify(payload), status
