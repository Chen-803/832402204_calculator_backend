"""计算接口控制器。

只做三件事：**解析 HTTP 请求 -> 调用业务服务 -> 返回标准响应**。
不包含任何表达式解析或数据库代码，保证控制器足够薄。
"""

import logging

from flask import Blueprint, request

from ..calculator.exceptions import ValidationError
from ..common.api_response import success_response
from ..service.calculator_service import calculate

__all__ = ["calculate_blueprint"]

_LOGGER = logging.getLogger(__name__)

calculate_blueprint = Blueprint("calculate", __name__)


def _parse_persist_flag(raw_value) -> bool:
    """解析 ``persist`` 参数，缺省为 True。"""
    if raw_value is None:
        return True
    if isinstance(raw_value, bool):
        return raw_value
    if isinstance(raw_value, (int, float)):
        return bool(raw_value)
    return str(raw_value).strip().lower() not in ("false", "0", "no", "off", "")


@calculate_blueprint.route("/calculate", methods=["POST"])
def calculate_endpoint():
    """计算接口。

    Request:
        ``POST /api/calculate``

        .. code-block:: json

            {"expression": "(1+2)*3", "persist": true}

    Response (200):

        .. code-block:: json

            {"success": true, "expression": "(1+2)*3", "result": 9,
             "display_result": "9",
             "record": {"id": 1, "expression": "(1+2)*3", "result": "9",
                        "created_at": "2026-10-01 10:20:00", "is_favorite": 0}}

    Response (400):

        .. code-block:: json

            {"success": false, "message": "除数不能为零（division by zero）",
             "error_code": "DIVISION_BY_ZERO", "expression": "1/0"}
    """
    payload = request.get_json(silent=True)
    if payload is None:
        raise ValidationError(
            "请求体必须是合法的 JSON，例如 {\"expression\": \"1+2\"}"
        )
    if not isinstance(payload, dict):
        raise ValidationError("请求体必须是 JSON 对象")

    expression = payload.get("expression")
    if expression is None:
        raise ValidationError("缺少必要参数 expression")
    if not isinstance(expression, str):
        raise ValidationError("参数 expression 必须是字符串")

    persist = _parse_persist_flag(payload.get("persist"))

    result = calculate(expression, persist=persist)
    message = "计算成功" if persist else "试算成功（未写入历史）"
    return success_response(data=None, message=message, status=200, flat=result.to_dict())
