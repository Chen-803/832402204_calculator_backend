# 前后端分离计算器系统 · 后端（832402204_calculator_backend）

> 软件工程课程第一次作业 —— 前后端分离计算器系统
> 学号：832402204　姓名：陈俊洁（Chen Junjie）
> 本仓库为**后端**部分，前端仓库见文末"相关仓库"。

## 一、项目简介

本项目是一个**前后端分离**的计算器系统的后端服务，使用 Python + Flask 实现，
对外提供一组 JSON over HTTP 的 RESTful 接口。

后端承担本项目的全部"重活"：

| 职责 | 说明 |
| --- | --- |
| 接收计算请求 | `POST /api/calculate` |
| 输入校验 | 空表达式、超长、非法字符、类型检查 |
| 表达式处理 | 自研词法分析器 + 语法分析器（递归下降），**不使用 `eval`/`exec`** |
| 执行计算 | 基于 `decimal.Decimal` 的高精度求值，支持优先级、括号、一元正负号、函数 |
| 异常处理 | 除零、定义域错误、溢出、语法错误，全部返回结构化错误码 |
| 存储历史 | SQLite 持久化每一次成功的计算 |
| 查询历史 | 分页、关键字检索、日期筛选、收藏筛选、排序 |
| 删除历史 | 删除指定记录 / 清空全部记录（真正落库删除） |
| 标准化响应 | 统一 `{"success": ...}` 响应外壳与稳定错误码 |

**核心计算 100% 在后端完成**，前端只负责输入表达式与展示后端返回的结果。
停掉本服务后，前端界面仍可正常交互，但**无法得到任何新的计算结果**。

## 二、技术栈

| 层次 | 选型 | 说明 |
| --- | --- | --- |
| 语言 | Python 3.10+（开发环境 3.14.5） | 只需标准库 + Flask |
| Web 框架 | Flask 3.1.3 | 轻量、零配置、易于讲解分层 |
| 数据库 | SQLite 3（标准库 `sqlite3`） | 单文件、免安装、随项目分发 |
| 数值类型 | `decimal.Decimal` | 避免二进制浮点误差（`0.1+0.2 = 0.3`） |
| 表达式解析 | **自研**词法/语法分析器 | 满足"禁止 `eval`/`exec`"的安全要求 |
| 测试 | `unittest`（标准库） | 78 个用例，覆盖引擎与接口 |

**第三方依赖只有一个 Flask**（见 `requirements.txt`），其余全部使用 Python 标准库，
不依赖任何本地特定环境。

## 三、运行环境

* Python ≥ 3.10（推荐 3.11 ~ 3.14）
* 操作系统：Windows / macOS / Linux 均可（SQLite 已随 Python 内置）
* 无需安装额外的数据库服务

检查环境：

```bash
python --version
```

## 四、目录结构

```
832402204_calculator_backend/
├── app.py                          # 服务启动入口（WSGI 入口 app）
├── requirements.txt                # 依赖清单（仅 Flask）
├── README.md                       # 本文件
├── codestyle.md                    # 代码规范（源自 PEP 8 / Google Python Style Guide）
├── .gitignore
├── sql/
│   └── schema.sql                  # 建表脚本（表结构 + 索引）
├── scripts/
│   └── init_db.py                  # 数据库初始化命令行工具
├── data/                           # SQLite 数据库文件目录（运行时生成）
├── src/
│   ├── __init__.py                 # create_app()：应用工厂与装配
│   ├── config.py                   # 配置（支持环境变量覆盖）
│   ├── common/                     # 通用基础设施
│   │   ├── api_response.py         # 统一成功/失败响应构造
│   │   └── errors.py               # 全局异常处理器
│   ├── controller/                 # 控制器层：解析 HTTP 请求
│   │   ├── calculate_controller.py #   POST /api/calculate
│   │   ├── history_controller.py   #   历史相关接口
│   │   └── meta_controller.py      #   健康检查与能力元数据
│   ├── service/                    # 业务服务层：编排用例
│   │   ├── calculator_service.py   #   校验 -> 计算 -> 落库
│   │   └── history_service.py      #   历史查询/删除/统计 + 参数校验
│   ├── model/                      # 数据模型层：数据库访问
│   │   ├── database.py             #   连接管理与建表
│   │   └── calculation_record.py   #   记录实体 + DAO
│   └── calculator/                 # 计算核心（不依赖 Flask 与数据库）
│       ├── tokenizer.py            #   词法分析
│       ├── parser.py               #   语法分析（递归下降）
│       ├── ast_nodes.py            #   AST 节点定义
│       ├── evaluator.py            #   求值器
│       ├── functions.py            #   函数/常量注册表与算术原语
│       ├── number_utils.py         #   精度控制与结果格式化
│       └── exceptions.py           #   业务异常与错误码
└── tests/
    ├── test_calculator.py          # 计算引擎单元测试（48 项）
    └── test_api.py                 # HTTP 接口集成测试（30 项）
```

分层依赖方向是单向的：

```
controller  →  service  →  model  →  database(SQLite)
     ↘            ↓
      common   calculator（纯业务，可独立测试）
```

## 五、安装方法

```bash
# 1. 克隆仓库
git clone <backend-repository-url>
cd 832402204_calculator_backend

# 2. （推荐）创建虚拟环境
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

# 3. 安装依赖（只有 Flask）
pip install -r requirements.txt
```

## 六、数据库初始化方法

数据库表结构定义在 `sql/schema.sql`。有三种初始化方式，任选其一：

**方式一（推荐）：运行初始化脚本**

```bash
python scripts/init_db.py
```

输出示例：

```
============================================================
数据库初始化完成
  数据库文件：D:\...\832402204_calculator_backend\data\calculator.db
  建表脚本  ：D:\...\sql\schema.sql
  数据表    ：calculation_history(id, expression, result, created_at, is_favorite)
============================================================
```

**方式二：启动服务时自动初始化**

`create_app()` 启动阶段会自动执行 `schema.sql`（`CREATE TABLE IF NOT EXISTS`，幂等），
所以直接启动服务也会自动建库建表，无需手动执行任何 SQL。

**方式三：手工执行 SQL**

```bash
sqlite3 data/calculator.db < sql/schema.sql
```

表结构：

```sql
CREATE TABLE IF NOT EXISTS calculation_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,   -- 记录 ID
    expression  TEXT    NOT NULL,                    -- 计算表达式
    result      TEXT    NOT NULL,                    -- 计算结果（高精度文本）
    created_at  TEXT    NOT NULL,                    -- 计算时间 YYYY-MM-DD HH:MM:SS
    is_favorite INTEGER NOT NULL DEFAULT 0           -- 收藏标记（扩展功能）
);
```

> `result` 使用 `TEXT` 而不是 `REAL`：计算在业务层用高精度 `Decimal` 完成，
> 存成文本可以原样保留精度，避免浮点入库丢精度。

## 七、启动方法

```bash
python app.py
```

启动后控制台会打印：

```
====================================================================
 前后端分离计算器 · 后端服务
 监听地址 : http://127.0.0.1:8000
 数据库   : .../data/calculator.db
 健康检查 : http://127.0.0.1:8000/api/health
 按 Ctrl+C 停止服务
====================================================================
```

用浏览器访问 <http://127.0.0.1:8000/> 可以看到接口索引，
访问 <http://127.0.0.1:8000/api/health> 可以看到健康检查结果。

生产环境可用 WSGI 服务器（示例）：

```bash
pip install waitress
waitress-serve --listen=0.0.0.0:8000 app:app
```

## 八、配置说明

所有配置都可以用**环境变量**覆盖，无需修改代码：

| 环境变量 | 含义 | 默认值 |
| --- | --- | --- |
| `CALC_HOST` | 监听地址 | `127.0.0.1` |
| `CALC_PORT` | 监听端口 | `8000` |
| `CALC_DEBUG` | 调试模式 | `false` |
| `CALC_DB_PATH` | SQLite 文件路径 | `<项目根>/data/calculator.db` |
| `CALC_ALLOWED_ORIGIN` | 允许跨域的前端来源 | `*` |
| `CALC_MAX_PAGE_SIZE` | 历史分页最大条数 | `100` |

示例（Windows PowerShell）：

```powershell
$env:CALC_PORT = "9000"
$env:CALC_ALLOWED_ORIGIN = "http://127.0.0.1:5173"
python app.py
```

示例（Linux / macOS）：

```bash
CALC_PORT=9000 CALC_ALLOWED_ORIGIN=http://127.0.0.1:5173 python app.py
```

## 九、API 接口说明

所有接口统一前缀 `/api`，请求与响应均为 UTF-8 JSON。

统一响应外壳：

```json
{ "success": true,  "data": { }, "message": "操作成功" }
{ "success": false, "message": "除数不能为零（division by zero）", "error_code": "DIVISION_BY_ZERO" }
```

### 9.1 接口总览

| 方法 | 路径 | 说明 | 成功状态码 |
| --- | --- | --- | --- |
| POST | `/api/calculate` | 计算表达式并（可选）写入历史 | 200 |
| GET | `/api/history` | 分页查询历史（含检索/筛选/排序） | 200 |
| GET | `/api/history/statistics` | 计算统计（扩展） | 200 |
| GET | `/api/history/{id}` | 查询单条历史 | 200 |
| DELETE | `/api/history/{id}` | 删除指定历史 | 200 |
| DELETE | `/api/history` | 清空全部历史（扩展） | 200 |
| PATCH | `/api/history/{id}/favorite` | 收藏/取消收藏（扩展） | 200 |
| GET | `/api/meta/functions` | 支持的常量与函数（扩展） | 200 |
| GET | `/api/health` | 健康检查 | 200 |

### 9.2 计算接口

**请求**

```http
POST /api/calculate
Content-Type: application/json

{ "expression": "(1+2)*3", "persist": true }
```

`persist` 可选，默认 `true`；传 `false` 表示**只试算不写入历史**（前端输入时的实时预览使用）。

**成功响应（200）**

```json
{
  "success": true,
  "expression": "(1+2)*3",
  "raw_expression": "(1+2)*3",
  "result": 9,
  "display_result": "9",
  "record": {
    "id": 3,
    "expression": "(1+2)*3",
    "result": "9",
    "created_at": "2026-10-01 10:22:00",
    "is_favorite": 0
  },
  "message": "计算成功"
}
```

* `result`：JSON 数值，便于程序消费（与作业示例一致）；
* `display_result`：后端格式化后的展示文本，精度更高，前端直接显示即可；
* `record`：落库后的历史记录，`persist=false` 时为 `null`。

> 说明：该接口为了贴合作业示例采用**扁平结构**（不用 `data` 包裹），
> 其余查询类接口统一使用 `{"success":true,"data":{...},"message":"..."}` 外壳。

**错误响应（400）**

```json
{
  "success": false,
  "message": "除数不能为零（division by zero）",
  "error_code": "DIVISION_BY_ZERO",
  "expression": "1/0"
}
```

错误响应会回带 `expression`（原始输入）以及可能的 `position`（出错字符位置），
方便前端直接回显与定位。

**错误码一览**

| `error_code` | HTTP | 触发场景 | 示例输入 |
| --- | --- | --- | --- |
| `EMPTY_EXPRESSION` | 400 | 表达式为空 | `""` |
| `EXPRESSION_TOO_LONG` | 400 | 超过 200 个字符 | 超长表达式 |
| `INVALID_CHARACTER` | 400 | 出现非法字符 | `1+2$` |
| `INVALID_EXPRESSION` | 400 | 语法错误 | `1+`、`(1+2`、`1 2` |
| `DIVISION_BY_ZERO` | 400 | 除数为零 / 取模为零 | `1/0`、`5%0` |
| `MATH_DOMAIN_ERROR` | 400 | 违反数学定义域 | `sqrt(-1)`、`ln(0)` |
| `OVERFLOW_ERROR` | 400 | 结果过大或计算量过大 | `2^99999` |
| `VALIDATION_ERROR` | 400 | 请求参数非法 | 缺少 `expression` |
| `RECORD_NOT_FOUND` | 404 | 记录不存在 | `DELETE /api/history/999` |
| `UNKNOWN_ERROR` | 500 | 未预期异常 | — |

### 9.3 历史查询接口

```http
GET /api/history?page=1&page_size=10&keyword=1%2B2&start_date=2026-10-01&end_date=2026-10-07&favorite_only=false&sort=desc
```

| 参数 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `page` | int ≥ 1 | 1 | 页码 |
| `page_size` | int 1~100 | 10 | 每页条数 |
| `keyword` | string ≤ 50 | 空 | 同时匹配表达式与结果 |
| `start_date` | `YYYY-MM-DD` | 空 | 起始日期（含当天） |
| `end_date` | `YYYY-MM-DD` | 空 | 结束日期（含当天） |
| `favorite_only` | bool | false | 只看收藏 |
| `sort` | `asc` / `desc` | desc | 时间排序方向 |

响应：

```json
{
  "success": true,
  "data": {
    "items": [
      { "id": 3, "expression": "(1+2)*3", "result": "9",
        "created_at": "2026-10-01 10:22:00", "is_favorite": 0 }
    ],
    "total": 3, "page": 1, "page_size": 10, "total_pages": 1
  },
  "message": "查询成功，共 3 条历史记录"
}
```

### 9.4 删除接口

```http
DELETE /api/history/2      →  200 {"success":true,"data":{"deleted_id":2},"message":"删除成功"}
DELETE /api/history/999    →  404 {"success":false,"message":"记录不存在：该历史记录可能已被删除","error_code":"RECORD_NOT_FOUND"}
DELETE /api/history        →  200 {"success":true,"data":{"deleted":5},"message":"已清空 5 条历史记录"}
```

### 9.5 支持的计算语法

| 类别 | 支持内容 |
| --- | --- |
| 运算符 | `+` `-` `*` `/` `%`（取模） `^`（幂，右结合） `!`（后缀阶乘） |
| 兼容符号 | `×` `÷` `−` `**` `π` `√` 以及全角数字/括号 |
| 括号 | `(` `)`，最多 32 层嵌套 |
| 一元运算 | `-5`、`+8`、`3*-2`、`--5` |
| 数字 | 整数、小数、科学计数法（`1e-3`） |
| 常量 | `pi`（或 `π`）、`e` |
| 函数 | `sqrt` `cbrt` `abs` `exp` `ln` `log` `log2` `sin` `cos` `tan` `asin` `acos` `atan` `sinh` `cosh` `tanh` `pow` `mod` `factorial` `floor` `ceil` `round` `max` `min` |

优先级（由高到低）：后缀 `!` → 幂 `^` → 一元 `+`/`-` → `*` `/` `%` → `+` `-`。
完整清单可通过 `GET /api/meta/functions` 动态获取。

## 十、前端连接方法

后端默认监听 `127.0.0.1:8000`，并且已经开启 CORS（`Access-Control-Allow-Origin: *`）。
前端只需把请求指向本服务即可：

```javascript
fetch("http://127.0.0.1:8000/api/calculate", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ expression: "(1+2)*3", persist: true }),
})
  .then((response) => response.json())
  .then((body) => console.log(body.display_result));  // "9"
```

前端仓库的 `src/js/config.js` 中的 `API_BASE` 就是该地址，
也可以在打开前端页面时用查询参数覆盖：`http://127.0.0.1:5173/?api=http://192.168.1.10:8000/api`。

**联调验证步骤**

1. 启动后端：`python app.py`；
2. 浏览器访问 `http://127.0.0.1:8000/api/health`，看到 `"status": "ok"` 即后端正常；
3. 启动前端：`python -m http.server 5173 --directory src`（在前端仓库根目录执行）；
4. 浏览器打开 `http://127.0.0.1:5173/`，输入 `1+2*3` 点 `=`，界面显示 `7`；
5. 刷新页面，历史记录依然存在（数据来自后端数据库）；
6. 停掉后端服务，前端点击 `=` 会提示"无法连接后端服务"，且**不会**显示任何计算结果。

## 十一、测试

```bash
# 在项目根目录执行
python -m unittest discover -s tests -v
```

测试覆盖：

* `tests/test_calculator.py`（48 项）：四则运算、优先级、括号、一元正负号、幂结合性、
  小数精度、函数、阶乘、除零、定义域、非法字符、超长、溢出、**"源码中不得出现 eval"的静态检查**；
* `tests/test_api.py`（30 项）：全部接口的成功与失败路径、分页、检索、日期校验、
  删除、清空、收藏、统计、**"重启应用后历史仍在"的持久化验证**、统一错误格式。

## 十二、常见问题（FAQ）

**Q1：端口 8000 被占用怎么办？**

```powershell
$env:CALC_PORT = "9000"; python app.py
```

**Q2：前端请求报跨域错误？**

确认后端已启动，并检查 `CALC_ALLOWED_ORIGIN`。生产环境建议把它设置为前端的实际来源，
而不是 `*`。

**Q3：数据库文件在哪里？如何重置？**

默认在 `data/calculator.db`。重置：

```bash
python scripts/init_db.py --reset
```

**Q4：为什么 `result` 和 `display_result` 两个字段？**

`result` 是 JSON 数值，方便程序使用；`display_result` 是后端按 15 位有效数字格式化好的
文本，前端直接展示以避免前端做任何数值处理。

**Q5：为什么不用 `eval`？**

`eval` 会把用户输入当作程序代码执行，存在任意代码执行漏洞。
本项目自行实现了词法分析、语法分析与求值三个步骤，
只识别白名单字符与函数，从根本上杜绝代码注入。

## 十三、相关仓库

| 内容 | 地址 |
| --- | --- |
| 前端仓库 | <https://github.com/Chen-803/832402204_calculator_frontend> |
| 后端仓库 | <https://github.com/Chen-803/832402204_calculator_backend> |
| 前端代码规范 | <https://github.com/Chen-803/832402204_calculator_frontend/blob/main/codestyle.md> |
| 后端代码规范 | <https://github.com/Chen-803/832402204_calculator_backend/blob/main/codestyle.md> |
| 作业博客 | <https://blog.csdn.net/>（发布后填写） |
