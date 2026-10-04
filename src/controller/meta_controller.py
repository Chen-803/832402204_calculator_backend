"""服务元信息接口控制器：健康检查与计算能力元数据。"""

from datetime import datetime

from flask import Blueprint, current_app

from ..calculator import define_metadata
from ..common.api_response import success_response

__all__ = ["meta_blueprint"]

meta_blueprint = Blueprint("meta", __name__)


@meta_blueprint.route("/health", methods=["GET"])
def health_endpoint():
    """健康检查接口，供前端判断后端是否可用、供部署平台做存活探测。

    响应里额外带上 ``database`` 字段，方便部署后确认实际连的是哪种数据库
    （本地/SQLite 还是云端/PostgreSQL）。
    """
    config = current_app.config["APP_CONFIG"]
    return success_response(
        data={
            "status": "ok",
            "service": config.service_name,
            "version": config.service_version,
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "database": config.dialect,
        },
        message="服务运行正常",
    )


@meta_blueprint.route("/meta/functions", methods=["GET"])
def functions_endpoint():
    """返回后端支持的运算符、常量与函数，前端据此动态渲染科学计算面板。

    这样一个好处是：后端新增一个函数，前端不需要改一行代码就能用上。
    """
    return success_response(data=define_metadata(), message="查询成功")
