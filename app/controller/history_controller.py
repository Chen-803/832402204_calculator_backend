"""计算历史接口控制器。

提供作业要求的两个核心接口，以及两个扩展接口：

============================ ==========================================
接口                          说明
============================ ==========================================
``GET /api/history``          查询历史（支持关键字搜索、分页、只看收藏）
``DELETE /api/history/{id}``  删除指定历史（作业必做）
``DELETE /api/history``       清空全部历史（扩展）
``PATCH /api/history/{id}/favorite`` 切换收藏（扩展）
============================ ==========================================

删除接口的语义约定：**只返回真正被删掉的行数**。
如果 ID 不存在，返回 404 而不是"假装成功"，这样前端的提示才不会骗人。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query

from ..common.responses import ok_response
from ..model.schemas import FavoriteRequest
from ..service.history_service import HistoryService

router = APIRouter(prefix="/history", tags=["计算历史"])


def get_history_service() -> HistoryService:
    """依赖注入：历史服务。"""
    return HistoryService()


@router.get(
    "",
    summary="查询计算历史",
    description="从**后端数据库**读取计算历史，支持关键字模糊搜索、分页和只看收藏。",
)
def list_history(
    keyword: str = Query(default="", max_length=100, description="按表达式或结果模糊搜索"),
    page: int = Query(default=1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(default=10, ge=1, le=100, alias="pageSize", description="每页条数"),
    only_favorite: bool = Query(default=False, alias="onlyFavorite", description="只看收藏"),
    order: str = Query(default="desc", pattern="^(asc|desc)$", description="时间排序方向"),
    service: HistoryService = Depends(get_history_service),
):
    """分页查询计算历史。"""
    data = service.list_history(
        keyword=keyword,
        page=page,
        page_size=page_size,
        only_favorite=only_favorite,
        order=order,
    )
    return ok_response(**data)


@router.delete(
    "",
    summary="清空全部计算历史",
    description="删除数据库中的全部计算历史记录（扩展功能）。",
)
def clear_history(service: HistoryService = Depends(get_history_service)):
    """清空全部历史。"""
    return ok_response(**service.clear_history())


@router.delete(
    "/{record_id}",
    summary="删除指定计算历史",
    description=(
        "按 ID 删除一条计算历史。\n\n"
        "记录不存在时返回 **404**，记录存在时返回实际删除的行数。"
    ),
)
def delete_history(
    record_id: int = Path(..., ge=1, description="历史记录 ID"),
    service: HistoryService = Depends(get_history_service),
):
    """删除指定历史记录。"""
    return ok_response(**service.delete_history(record_id))


@router.patch(
    "/{record_id}/favorite",
    summary="设置或切换收藏",
    description="请求体省略 ``favorite`` 字段时表示取反（扩展功能）。",
)
def toggle_favorite(
    record_id: int = Path(..., ge=1, description="历史记录 ID"),
    payload: FavoriteRequest | None = None,
    service: HistoryService = Depends(get_history_service),
):
    """切换历史记录的收藏状态。"""
    favorite = payload.favorite if payload is not None else None
    return ok_response(**service.set_favorite(record_id, favorite))
