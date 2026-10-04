"""计算历史接口控制器。

接口一览（全部挂在 ``/api`` 前缀下）::

    GET    /api/history?page=1&page_size=10&keyword=&start_date=&end_date=
                       &favorite_only=false&sort=desc   分页查询（含检索与筛选）
    GET    /api/history/statistics                      计算统计（扩展功能）
    GET    /api/history/{id}                            查询单条
    DELETE /api/history/{id}                            删除指定记录
    DELETE /api/history                                 清空全部记录（扩展功能）
    PATCH  /api/history/{id}/favorite                   收藏 / 取消收藏（扩展功能）
"""

import logging

from flask import Blueprint, current_app, request

from ..common.api_response import error_response, success_response
from ..service.history_service import (
    clear_history,
    delete_record,
    get_record,
    list_history,
    set_favorite,
    statistics,
)

__all__ = ["history_blueprint"]

_LOGGER = logging.getLogger(__name__)

history_blueprint = Blueprint("history", __name__)

RECORD_NOT_FOUND_MESSAGE = "记录不存在：该历史记录可能已被删除"


def _app_config():
    """取当前应用的配置对象。"""
    return current_app.config["APP_CONFIG"]


@history_blueprint.route("/history", methods=["GET"])
def list_history_endpoint():
    """分页查询计算历史（支持关键字检索、日期筛选、收藏筛选与排序）。"""
    config = _app_config()
    arguments = request.args
    data = list_history(
        page=arguments.get("page", 1),
        page_size=arguments.get("page_size"),
        keyword=arguments.get("keyword"),
        start_date=arguments.get("start_date"),
        end_date=arguments.get("end_date"),
        favorite_only=arguments.get("favorite_only"),
        sort=arguments.get("sort", "desc"),
        default_page_size=config.default_page_size,
        max_page_size=config.max_page_size,
    )
    return success_response(data=data, message=f"查询成功，共 {data['total']} 条历史记录")


@history_blueprint.route("/history/statistics", methods=["GET"])
def statistics_endpoint():
    """返回计算统计信息（扩展功能）。"""
    data = statistics()
    return success_response(data=data, message="统计成功")


@history_blueprint.route("/history/<int:record_id>", methods=["GET"])
def get_history_endpoint(record_id: int):
    """按 ID 查询单条历史记录。"""
    record = get_record(record_id)
    if record is None:
        return error_response(RECORD_NOT_FOUND_MESSAGE, "RECORD_NOT_FOUND", 404)
    return success_response(data=record.to_dict(), message="查询成功")


@history_blueprint.route("/history/<int:record_id>", methods=["DELETE"])
def delete_history_endpoint(record_id: int):
    """删除指定历史记录（真正从数据库中删除）。"""
    if not delete_record(record_id):
        return error_response(RECORD_NOT_FOUND_MESSAGE, "RECORD_NOT_FOUND", 404)
    return success_response(data={"deleted_id": record_id}, message="删除成功")


@history_blueprint.route("/history", methods=["DELETE"])
def clear_history_endpoint():
    """清空全部历史记录（扩展功能）。"""
    deleted = clear_history()
    return success_response(data={"deleted": deleted}, message=f"已清空 {deleted} 条历史记录")


@history_blueprint.route("/history/<int:record_id>/favorite", methods=["PATCH"])
def favorite_history_endpoint(record_id: int):
    """收藏 / 取消收藏某条历史记录（扩展功能）。

    Request:
        ``{"is_favorite": true}``，省略该字段时在现有状态上取反。
    """
    payload = request.get_json(silent=True) or {}
    raw_value = payload.get("is_favorite") if isinstance(payload, dict) else None
    target = None if raw_value is None else bool(raw_value)

    record = set_favorite(record_id, target)
    if record is None:
        return error_response(RECORD_NOT_FOUND_MESSAGE, "RECORD_NOT_FOUND", 404)
    message = "已收藏" if record.is_favorite else "已取消收藏"
    return success_response(data=record.to_dict(), message=message)
