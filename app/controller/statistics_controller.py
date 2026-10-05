"""统计与健康检查接口控制器。

``GET /api/health`` 有两个实际用途：

1. 前端顶部的"后端连接状态"指示灯靠轮询它来判断后端是否在线；
2. 演示"停掉后端服务后，前端无法独立算出结果"时，助教可以先访问它确认服务状态。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ..common.responses import ok_response
from ..config import settings
from ..repository.history_repository import is_database_available
from ..service.calculation_service import now_text
from ..service.statistics_service import StatisticsService

router = APIRouter(tags=["统计与健康检查"])


def get_statistics_service() -> StatisticsService:
    """依赖注入：统计服务。"""
    return StatisticsService()


@router.get(
    "/stats",
    summary="计算统计",
    description=(
        "返回历史总数、今日计算次数、收藏数、运算符使用分布、"
        "最常用表达式和近七日趋势（扩展功能）。"
    ),
)
def statistics(service: StatisticsService = Depends(get_statistics_service)):
    """计算统计。"""
    return ok_response(**service.overview())


@router.get(
    "/health",
    summary="健康检查",
    description="返回服务版本、数据库连通状态与服务器时间。",
)
def health():
    """健康检查。"""
    return ok_response(
        service=settings.app_name,
        version=settings.version,
        database="ok" if is_database_available() else "error",
        time=now_text(),
    )
