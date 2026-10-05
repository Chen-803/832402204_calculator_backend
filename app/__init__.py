"""前后端分离计算器系统 —— 后端应用包。

分层结构::

    app/
    ├── controller/   接口层：路由、请求模型、状态码
    ├── service/      业务层：编排计算、历史、统计、转换
    ├── calculator/   内核层：词法分析 → 语法分析 → 求值（纯函数，不依赖框架）
    ├── repository/   数据层：SQLite 连接与全部 SQL
    ├── model/        模型层：领域实体 + 请求校验模型
    └── common/       公共层：统一响应、异常处理器

依赖方向严格单向：controller → service → {calculator, repository} → model。
下层不允许反向 import 上层，因此计算内核可以脱离 FastAPI 单独做单元测试。
"""

__version__ = "1.0.0"