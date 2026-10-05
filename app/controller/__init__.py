"""接口层：把 HTTP 请求翻译成 Service 调用，并把结果包装成统一信封。"""

from . import (
    calculation_controller,
    conversion_controller,
    history_controller,
    statistics_controller,
)

#: 所有路由模块，由 ``app.main`` 统一挂载
ROUTERS = (
    calculation_controller.router,
    history_controller.router,
    conversion_controller.router,
    statistics_controller.router,
)

__all__ = ["ROUTERS"]