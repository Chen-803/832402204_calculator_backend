"""计算器后端应用包。

``create_app`` 采用工厂函数模式：
    * 便于单元测试时构造不同配置的应用实例；
    * 便于生产环境用 WSGI 服务器（gunicorn / waitress）加载；
    * 让"应用装配"与"进程启动参数"解耦（见项目根目录的 ``app.py``）。

装配顺序：错误处理 -> 路由 -> 跨域 -> 数据库。
"""

import logging

from flask import Flask, Response

from .common.api_response import success_response
from .common.errors import register_error_handlers
from .config import Config, load_config
from .controller.calculate_controller import calculate_blueprint
from .controller.history_controller import history_blueprint
from .controller.meta_controller import meta_blueprint
from .model.database import init_database, register_teardown

__all__ = ["create_app"]

_LOGGER = logging.getLogger(__name__)


def create_app(config: Config = None) -> Flask:
    """创建并配置 Flask 应用。

    Args:
        config: 可选的配置对象，缺省时从环境变量加载。

    Returns:
        已完成路由、CORS、数据库注册的 Flask 应用实例。
    """
    active_config = config or load_config()

    app = Flask(__name__)
    app.config["APP_CONFIG"] = active_config
    app.json.ensure_ascii = False  # 保证中文错误信息不被转义成 \\uXXXX

    register_error_handlers(app)
    register_blueprints(app)
    register_cors(app, active_config)
    register_database(app, active_config)

    _LOGGER.info("计算器后端初始化完成：数据库=%s", active_config.database_path)
    return app


def register_blueprints(app: Flask) -> None:
    """注册所有控制器（Blueprint），统一挂在 ``/api`` 前缀下。"""
    app.register_blueprint(calculate_blueprint, url_prefix="/api")
    app.register_blueprint(history_blueprint, url_prefix="/api")
    app.register_blueprint(meta_blueprint, url_prefix="/api")

    @app.route("/", methods=["GET"])
    def service_index():
        """根路径：返回接口索引，方便直接用浏览器确认后端已启动。"""
        config: Config = app.config["APP_CONFIG"]
        return success_response(
            data={
                "service": config.service_name,
                "version": config.service_version,
                "endpoints": [
                    "POST   /api/calculate",
                    "GET    /api/history",
                    "GET    /api/history/statistics",
                    "GET    /api/history/{id}",
                    "DELETE /api/history/{id}",
                    "DELETE /api/history",
                    "PATCH  /api/history/{id}/favorite",
                    "GET    /api/meta/functions",
                    "GET    /api/health",
                ],
            },
            message="前后端分离计算器后端服务运行中",
        )


def register_cors(app: Flask, config: Config) -> None:
    """注册跨域（CORS）响应头与预检请求处理。

    前后端分离部署时前端与后端不同源，必须由后端显式声明允许的跨域来源。
    这里手写而不引入 ``flask-cors``：少一个第三方依赖，
    同时让"跨域"这个关键知识点在代码中显式可见、可讲解。
    """

    @app.after_request
    def add_cors_headers(response: Response) -> Response:
        # 显式声明 UTF-8：部分客户端（如 Windows PowerShell 5.1）在
        # Content-Type 缺少 charset 时会按 Latin-1 解码，导致中文错误信息乱码。
        content_type = response.headers.get("Content-Type", "")
        if response.mimetype == "application/json" and "charset" not in content_type:
            response.headers["Content-Type"] = "application/json; charset=utf-8"

        response.headers["Access-Control-Allow-Origin"] = config.allowed_origin
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PATCH, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Accept"
        response.headers["Access-Control-Max-Age"] = "86400"
        response.headers["Vary"] = "Origin"
        return response

    # 预检请求（OPTIONS）由 Flask 针对每个已注册路由自动响应 200，
    # 上面的 after_request 已经为它补上了跨域响应头，
    # 因此这里不再注册通配的 OPTIONS 路由，避免把"未知接口"误判成 405。


def register_database(app: Flask, config: Config) -> None:
    """注册数据库连接的生命周期钩子，并确保表结构存在。"""
    register_teardown(app)
    with app.app_context():
        init_database()
