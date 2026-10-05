"""计算接口控制器。

Controller 的职责被刻意压到最薄：

1. 声明路由、请求模型、状态码（这些是 API 契约的一部分）；
2. 调用 Service；
3. 把 Service 的返回值包装成统一信封。

**没有** ``try/except``：所有 ``CalculatorError`` / ``BusinessError``
都由 ``app.common.exception_handlers`` 注册的全局异常处理器接管，
保证"任何路径返回的报文结构都一致"这件事只需要在一个地方维护。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from ..common.responses import ok_response
from ..model.schemas import CalculateRequest
from ..service.calculation_service import CalculationService

router = APIRouter(tags=["计算"])


def get_calculation_service() -> CalculationService:
    """依赖注入：为每个请求创建 Service。

    Service 本身是无状态的（状态在数据库里），所以这里创建的是轻量对象。
    之所以不注册成全局单例，是为了将来要换成"带请求级缓存/事务"的实现时
    不需要改 Controller 的代码。
    """
    return CalculationService()


@router.post(
    "/calculate",
    status_code=status.HTTP_201_CREATED,
    summary="计算表达式",
    description=(
        "接收前端提交的表达式原文，在后端完成校验、解析、求值，"
        "把结果写入数据库后返回。\n\n"
        "**返回 201 Created**：本次请求在数据库中新建了一条计算历史记录。\n\n"
        "失败时返回 400，并在 ``message`` 中给出可直接展示给用户的中文原因。"
    ),
)
def calculate(payload: CalculateRequest,
              service: CalculationService = Depends(get_calculation_service)):
    """计算表达式并保存历史。"""
    result = service.calculate(payload.expression, payload.angle_mode)
    return ok_response(
        http_status=status.HTTP_201_CREATED,
        **service.to_payload(result),
    )
