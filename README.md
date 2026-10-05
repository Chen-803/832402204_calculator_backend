# 前后端分离计算器系统 · 后端

> 软件工程课程第一次作业 — **前后端分离计算器系统** 的后端仓库
>
> 学号：**832402204** ｜ 姓名：**陈俊洁**

本仓库是计算器系统的**后端服务**，负责表达式的校验、解析、求值与计算历史的持久化。
前端仓库（Vue 3）通过 HTTP/JSON 调用本服务，**所有计算结果均由本服务产生**。

---

## 🔗 在线演示地址

项目已部署到公网，无需安装环境即可测试：

| 项目 | 地址 |
| --- | --- |
| 后端接口文档（Swagger，可在线调试） | https://asset-mountains-roger-handbags.trycloudflare.com/docs |
| 后端 API 根地址 | https://asset-mountains-roger-handbags.trycloudflare.com/api |
| 前端页面 | https://london-click-extended-lewis.trycloudflare.com |

> 该地址通过 Cloudflare 快速隧道把本机服务映射到公网，**需要本机保持开机联网**；
> 隧道域名是临时的，重启后会变化。

---

## 目录

- [1. 项目介绍](#1-项目介绍)
- [2. 技术栈](#2-技术栈)
- [3. 运行环境](#3-运行环境)
- [4. 安装方法](#4-安装方法)
- [5. 启动方法](#5-启动方法)
- [6. 配置说明](#6-配置说明)
- [7. 数据库初始化](#7-数据库初始化)
- [8. 数据库设计](#8-数据库设计)
- [9. API 接口一览](#9-api-接口一览)
- [10. 前后端连接方式](#10-前后端连接方式)
- [11. 目录结构](#11-目录结构)
- [12. 表达式语法](#12-表达式语法)
- [13. 运行测试](#13-运行测试)
- [14. 常见问题](#14-常见问题)

---

## 1. 项目介绍

本项目实现了一个**前后端分离**的计算器系统。后端提供 RESTful API，职责包括：

| 职责 | 说明 |
| --- | --- |
| 接收计算请求 | `POST /api/calculate`，请求体只包含**表达式字符串** |
| 输入校验 | 长度上限、字符白名单、括号配对、函数名与参数个数校验 |
| 表达式解析 | 自研词法分析器 + 语法分析器（优先级爬升），**不使用 `eval`** |
| 执行计算 | `decimal.Decimal` 高精度求值，支持四则运算、括号、一元正负号、小数、幂、阶乘、百分号与科学函数 |
| 异常处理 | 除零、语法错误、定义域错误、未知函数等，统一错误码与中文提示 |
| 存储历史 | 计算成功后写入 SQLite 数据库 |
| 读取历史 | 支持关键字搜索、分页、只看收藏 |
| 删除历史 | 按 ID 删除指定记录；另提供清空全部 |
| 标准化响应 | 所有接口返回统一的 `{success, code, message, ...}` 信封 |

**本项目不允许**"前端算好结果发给后端存储"的实现方式。前端只发送表达式原文。

---

## 2. 技术栈

| 层次 | 选型 | 说明 |
| --- | --- | --- |
| Web 框架 | **FastAPI 0.115+** | 自带请求体校验与 OpenAPI 文档 |
| ASGI 服务器 | **Uvicorn 0.30+** | 轻量、启动快 |
| 数据校验 | **Pydantic v2** | 随 FastAPI 一起安装 |
| 数据库 | **SQLite 3** | Python 标准库自带，零安装 |
| 数据库访问 | **标准库 `sqlite3`** | 手写 SQL + Repository 分层，不引入 ORM |
| 数值计算 | **标准库 `decimal`** | 34 位有效数字，避免二进制浮点误差 |
| 表达式解析 | **自研** | 词法分析 → 优先级爬升 → AST → 求值 |
| 测试 | **pytest + httpx** | 217 个用例 |

**为什么依赖这么少？**
作业要求"技术选型不应不必要地依赖特定本地环境"。SQLite 是文件数据库、
不需要装数据库服务；表达式解析完全自研、不需要第三方数学库。
结果是：助教只要有 Python 3.10+，`pip install -r requirements.txt` 之后就能直接跑。

---

## 3. 运行环境

| 项目 | 要求 |
| --- | --- |
| 操作系统 | Windows / macOS / Linux 均可（开发环境为 Windows 11） |
| Python | **3.10 及以上**（开发环境为 3.14.5） |
| 依赖 | 见 `requirements.txt`（仅 FastAPI + Uvicorn 两条） |
| 数据库 | 无需额外安装（使用 SQLite 文件） |
| 端口 | 默认 `8000`，如被占用可通过参数修改 |

---

## 4. 安装方法

### 方式一：使用虚拟环境（推荐）

```bash
# 1. 进入后端项目目录
cd 832402204_calculator_backend

# 2. 创建虚拟环境
python -m venv .venv

# 3. 激活虚拟环境
#    Windows (PowerShell)
.venv\Scripts\Activate.ps1
#    Windows (CMD)
.venv\Scripts\activate.bat
#    macOS / Linux
source .venv/bin/activate

# 4. 安装依赖
pip install -r requirements.txt
```

> **Windows 提示**：如果 PowerShell 提示"禁止运行脚本"，可以先执行
> `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`，
> 或者直接使用 CMD 的 `activate.bat`。

### 方式二：直接安装到当前 Python 环境

```bash
cd 832402204_calculator_backend
pip install -r requirements.txt
```

安装完成后可以用下面的命令自检：

```bash
python -c "import fastapi, uvicorn; print('依赖安装成功', fastapi.__version__)"
```

---

## 5. 启动方法

### 推荐：使用 `run.py`

```bash
python run.py
```

启动后会打印：

```text
==================================================================
  前后端分离计算器系统 · 后端服务
==================================================================
  数据库文件 : .../832402204_calculator_backend/data/calculator.db
  服务地址   : http://127.0.0.1:8000
  接口文档   : http://127.0.0.1:8000/docs
  健康检查   : http://127.0.0.1:8000/api/health
==================================================================
```

### 其他启动方式

```bash
# 指定端口（默认端口被占用时使用）
python run.py --port 8010

# 允许局域网访问（部署到服务器时使用）
python run.py --host 0.0.0.0 --port 8000

# 开发模式：修改代码自动重启
python run.py --reload

# 直接用 uvicorn 启动（等价方式）
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### 验证服务是否正常

浏览器打开 `http://127.0.0.1:8000/api/health`，应当返回：

```json
{
  "success": true,
  "code": 0,
  "message": "OK",
  "service": "calculator-backend",
  "version": "1.0.0",
  "database": "ok",
  "time": "2026-10-05 12:26:29"
}
```

### 交互式接口文档

服务启动后访问 **`http://127.0.0.1:8000/docs`**，可以直接在页面上调试所有接口，
不需要写任何代码。这是 FastAPI 根据代码里的类型标注自动生成的。

---

## 6. 配置说明

所有配置都可以通过**环境变量**覆盖，不需要修改代码。

| 环境变量 | 含义 | 默认值 |
| --- | --- | --- |
| `CALCULATOR_DB_PATH` | SQLite 数据库文件路径 | `data/calculator.db`（相对于后端项目根目录） |
| `CALCULATOR_HOST` | 监听地址 | `127.0.0.1` |
| `CALCULATOR_PORT` | 监听端口 | `8000` |
| `CALCULATOR_CORS_ORIGINS` | 允许跨域的前端来源，逗号分隔；`*` 表示全部 | 见下 |
| `CALCULATOR_LOG_LEVEL` | 日志级别 | `INFO` |

默认允许的跨域来源：

```text
http://localhost:5173     ← Vite 开发服务器（默认端口）
http://127.0.0.1:5173
http://localhost:4173     ← vite preview 默认端口
http://127.0.0.1:4173
http://localhost:3000
http://127.0.0.1:3000
```

**配置示例**

```powershell
# Windows PowerShell
$env:CALCULATOR_PORT = "8010"
$env:CALCULATOR_DB_PATH = "D:\data\calc.db"
python run.py
```

```bash
# macOS / Linux
export CALCULATOR_PORT=8010
export CALCULATOR_CORS_ORIGINS="*"
python run.py
```

---

## 7. 数据库初始化

**不需要手动初始化。** 服务启动时会自动完成：

1. 检查数据库文件所在目录是否存在，不存在则创建（`data/`）；
2. 执行建表语句 `CREATE TABLE IF NOT EXISTS calculation_history (...)`；
3. 创建索引 `idx_history_created_at`、`idx_history_favorite`；
4. 在 `schema_meta` 表中写入结构版本号 `schema_version = 1`。

因为使用了 `IF NOT EXISTS`，**重复启动是安全的**，不会清空已有数据。

如果你想**手动初始化**（例如想换一个数据库路径），可以执行：

```bash
python -c "from app.repository.database import init_database; print(init_database())"
```

### 查看数据库内容

```bash
# 方式一：使用 sqlite3 命令行工具（如果已安装）
sqlite3 data/calculator.db "SELECT * FROM calculation_history LIMIT 10;"

# 方式二：使用 Python（无需额外安装任何东西）
python -c "
import sqlite3
conn = sqlite3.connect('data/calculator.db')
for row in conn.execute('SELECT id, expression, result, created_at FROM calculation_history ORDER BY id DESC LIMIT 10'):
    print(row)
"
```

### 重置数据库

直接删除数据库文件后重启服务即可（**会丢掉全部历史**）：

```bash
# Windows
del data\calculator.db

# macOS / Linux
rm data/calculator.db
```

---

## 8. 数据库设计

### 表：`calculation_history`

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | 主键，前端删除历史时使用 |
| `expression` | TEXT | NOT NULL | 用户输入的**原始表达式**（保留 `×` `÷` 等写法） |
| `normalized_expression` | TEXT | NOT NULL | 后端归一化后的表达式（`×`→`*`），用于调试与统计 |
| `result` | TEXT | NOT NULL | 计算结果，**以字符串存储**（见下方说明） |
| `angle_mode` | TEXT | NOT NULL DEFAULT `'rad'` | 本次计算使用的角度制 |
| `elapsed_ms` | REAL | NOT NULL DEFAULT 0 | 后端计算耗时（毫秒） |
| `favorite` | INTEGER | NOT NULL DEFAULT 0 | 是否收藏（0/1），扩展功能 |
| `created_at` | TEXT | NOT NULL | 计算时间，格式 `YYYY-MM-DD HH:mm:ss` |

### 索引

```sql
CREATE INDEX idx_history_created_at ON calculation_history (created_at DESC, id DESC);
CREATE INDEX idx_history_favorite     ON calculation_history (favorite);
```

- 第一个索引服务于"按时间倒序分页查询历史"这个最高频的操作；
  加上 `id` 是为了让**同一秒内写入的多条记录**也有稳定顺序。
- 第二个索引服务于"只看收藏"筛选。

### 辅助表：`schema_meta`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `key` | TEXT PRIMARY KEY | 配置项名 |
| `value` | TEXT NOT NULL | 配置项值 |

目前只存 `schema_version`，为将来的数据库结构迁移留出扩展点。

### 为什么 `result` 存字符串而不是 REAL？

SQLite 的 `REAL` 是 IEEE 754 双精度浮点，只有约 15~16 位有效数字。
而计算内核用 34 位精度的 `Decimal`，并且支持 `100!` 这类 158 位的大整数结果。

如果存成 `REAL`：

- `100!` 会被截断，精度永久丢失；
- 数据库里的值和界面上显示的值可能对不上。

存字符串可以**原样保留**计算结果，接口再额外提供一个 JSON number 形式的
`result` 字段（超出 double 范围时回退为字符串），兼顾精度与前端便利性。

---

## 9. API 接口一览

**基地址**：`http://127.0.0.1:8000`，所有业务接口统一前缀 `/api`。

完整接口契约见仓库内 [`docs/API_CONTRACT.md`](docs/API_CONTRACT.md)（前后端并行开发时冻结的接口版本，前端仓库中另有一份相同副本）。

### 统一响应信封

所有接口（含错误）都返回同一结构：

```json
{ "success": true, "code": 0, "message": "OK", "...业务字段": "..." }
```

### 接口列表

| 方法 | 路径 | 说明 | 成功状态码 |
| --- | --- | --- | --- |
| POST | `/api/calculate` | 计算表达式并保存历史 | **201 Created** |
| GET | `/api/history` | 查询历史（搜索 / 分页 / 只看收藏） | 200 |
| DELETE | `/api/history/{id}` | 删除指定历史记录 | 200 |
| DELETE | `/api/history` | 清空全部历史（扩展） | 200 |
| PATCH | `/api/history/{id}/favorite` | 切换收藏（扩展） | 200 |
| GET | `/api/stats` | 计算统计（扩展） | 200 |
| POST | `/api/convert/base` | 进制转换（扩展） | 200 |
| GET | `/api/convert/units` | 单位类别定义（扩展） | 200 |
| POST | `/api/convert/unit` | 单位换算（扩展） | 200 |
| GET | `/api/health` | 健康检查 | 200 |

### 调用示例（curl）

```bash
# 1) 计算：前端只发表达式，结果由后端算出
curl -X POST http://127.0.0.1:8000/api/calculate \
     -H "Content-Type: application/json" \
     -d "{\"expression\":\"(1+2)*3\"}"

# 返回 201：
# {"success":true,"code":0,"message":"OK","expression":"(1+2)*3",
#  "normalizedExpression":"(1+2)*3","result":9.0,"resultText":"9",
#  "historyId":1,"createdAt":"2026-10-05 12:26:29","elapsedMs":0.063}

# 2) 查询历史
curl "http://127.0.0.1:8000/api/history?page=1&pageSize=10&keyword=1%2B2"

# 3) 删除指定历史（记录不存在返回 404）
curl -X DELETE http://127.0.0.1:8000/api/history/1

# 4) 除零错误：返回 400
curl -X POST http://127.0.0.1:8000/api/calculate \
     -H "Content-Type: application/json" -d "{\"expression\":\"1/0\"}"
# {"success":false,"code":40003,"message":"除数不能为 0","expression":"1/0"}
```

### 错误码表

| code | HTTP | message 示例 | 触发条件 |
| --- | --- | --- | --- |
| `0` | 200/201 | `OK` | 成功 |
| `40001` | 400 | `表达式为空` | 空表达式 |
| `40002` | 400 | `表达式语法错误：缺少右括号` | 语法错误 |
| `40003` | 400 | `除数不能为 0` | 除以零 |
| `40004` | 400 | `表达式过长，最多支持 500 个字符` | 超过长度上限 |
| `40005` | 400 | `不支持的函数：foo` | 未知函数 |
| `40006` | 400 | `函数定义域错误：sqrt 的参数不能为负数` | 数学定义域错误 |
| `40007` | 400 | `进制转换参数不合法` | 进制越界 |
| `40008` | 400 | `不支持的单位类别` | 单位不存在 |
| `40009` | 400 | `字符无法识别：@` | 非法字符 |
| `40401` | 404 | `历史记录不存在：id=99` | 记录不存在 |
| `42201` | 422 | `请求参数不合法：expression 字段缺失` | 请求体结构错误 |
| `50000` | 500 | `服务器内部错误，请稍后重试` | 未捕获异常 |

---

## 10. 前后端连接方式

```text
┌─────────────────────┐        HTTP / JSON         ┌─────────────────────┐
│   前端 Vue 3 (5173)  │  ───────────────────────▶  │  后端 FastAPI (8000) │
│                     │                            │                     │
│  · 界面呈现          │  POST /api/calculate       │  · 校验表达式        │
│  · 按键交互          │  { "expression": "1+2" }   │  · 解析（词法+语法）  │
│  · 拼接表达式字符串   │                            │  · 计算（Decimal）   │
│  · 展示后端返回的结果 │  ◀───────────────────────  │  · 写入 SQLite       │
│  · 展示历史 / 发删除  │  201 { resultText: "3" }   │  · 返回统一信封       │
└─────────────────────┘                            └──────────┬──────────┘
                                                              │ SQL
                                                              ▼
                                                   ┌─────────────────────┐
                                                   │  SQLite 数据库文件    │
                                                   │  calculation_history │
                                                   └─────────────────────┘
```

**前端如何配置后端地址**

前端仓库中的 `src/api/http.js` 这样取基地址：

```js
const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'
```

因此有两种方式指向本后端：

1. **默认**：后端跑在 `127.0.0.1:8000`（`python run.py` 的默认值），前端无需任何配置。
2. **自定义**：在**前端仓库**根目录新建 `.env.local`：

   ```text
   VITE_API_BASE_URL=http://192.168.1.10:8000
   ```

   然后重启前端的 `npm run dev`。

**跨域（CORS）**

前后端分离时前端与后端不同源，浏览器会发起跨域请求。
后端已通过 `CORSMiddleware` 放行了常用的本地开发端口（见[配置说明](#6-配置说明)）。
如果前端跑在其他端口上，用 `CALCULATOR_CORS_ORIGINS` 环境变量补上即可。

---

## 11. 目录结构

```text
832402204_calculator_backend/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI 应用装配（CORS、异常处理器、路由挂载）
│   ├── config.py                  # 配置（全部支持环境变量覆盖）
│   ├── controller/                # ① 接口层：路由、请求模型、HTTP 状态码
│   │   ├── calculation_controller.py
│   │   ├── history_controller.py
│   │   ├── conversion_controller.py
│   │   └── statistics_controller.py
│   ├── service/                   # ② 业务层：编排"一次请求要做哪些事"
│   │   ├── calculation_service.py
│   │   ├── history_service.py
│   │   ├── conversion_service.py
│   │   └── statistics_service.py
│   ├── calculator/                # ③ 计算内核：纯函数，不依赖 FastAPI / 数据库
│   │   ├── __init__.py            #    对外唯一出口 calculate()
│   │   ├── errors.py              #    异常体系与错误码
│   │   ├── tokenizer.py           #    词法分析（手写状态机）+ 输入归一化
│   │   ├── ast_nodes.py           #    AST 节点定义
│   │   ├── parser.py              #    语法分析（优先级爬升）
│   │   ├── evaluator.py           #    AST 求值（Decimal 高精度）
│   │   ├── functions.py           #    数学函数与常量注册表
│   │   └── formatter.py           #    结果展示格式化
│   ├── repository/                # ④ 数据层：唯一出现 SQL 的地方
│   │   ├── database.py            #    连接管理、建表、健康检查
│   │   └── history_repository.py  #    历史表全部增删改查
│   ├── model/                     # ⑤ 模型层
│   │   ├── entities.py            #    领域实体 HistoryRecord
│   │   └── schemas.py             #    Pydantic 请求模型
│   └── common/                    # ⑥ 公共层
│       ├── responses.py           #    统一响应信封
│       ├── exceptions.py          #    业务异常
│       └── exception_handlers.py  #    全局异常处理器
├── tests/
│   ├── conftest.py                #    pytest 夹具（独立测试数据库）
│   ├── test_calculator_engine.py  #    计算内核单元测试（含静态安全审计）
│   └── test_api.py                #    接口集成测试
├── data/
│   └── calculator.db              # SQLite 数据库（首次启动自动创建）
├── docs/
│   └── API_CONTRACT.md            # 接口契约（冻结版）
├── run.py                         # 启动入口
├── requirements.txt               # 运行依赖
├── pytest.ini                     # 测试配置
├── codestyle.md                   # 代码规范
└── README.md
```

**依赖方向严格单向**：`controller → service → {calculator, repository} → model`。
下层不 import 上层，因此计算内核可以脱离 Web 框架独立做单元测试。

---

## 12. 表达式语法

### 支持的运算

| 运算 | 符号 | 优先级 | 结合性 |
| --- | --- | --- | --- |
| 加 | `+` | 1 | 左 |
| 减 | `-` | 1 | 左 |
| 乘 | `*` `×` | 2 | 左 |
| 除 | `/` `÷` | 2 | 左 |
| 取模 | `mod` | 2 | 左 |
| 一元正/负 | `+x` `-x` | 3 | 右 |
| 幂 | `^` | 4 | 右 |
| 阶乘 | `x!` | 5 | 后缀 |
| 百分号 | `x%` | 5 | 后缀（等价 `x/100`） |

### 函数与常量

| 类别 | 名称 |
| --- | --- |
| 常量 | `pi`、`e`、`tau` |
| 三角（受角度制影响） | `sin` `cos` `tan` `asin` `acos` `atan` |
| 双曲 | `sinh` `cosh` `tanh` |
| 幂与根 | `sqrt` `cbrt` `pow(a,b)` |
| 指数与对数 | `ln` `log(x)` `log(x,b)` `lg` `log2` `exp` |
| 取整与符号 | `abs` `floor` `ceil` `round(x)` `round(x,n)` `sign` |
| 其它 | `fact(n)` `mod(a,b)` `max(...)` `min(...)` |

### 精度策略

- 内部使用 `decimal.Decimal`（**34 位有效数字**）做加减乘除与幂；
  因此 `0.1 + 0.2` 得到 `0.3`，而不是二进制浮点的 `0.30000000000000004`。
- 三角函数等超越函数转 `float` 计算后回写，并做"整平"处理，
  所以 `sin(180°)` 显示 `0`、`log(1000)` 显示 `3`，而不是 `1.22e-16` / `2.9999999999999996`。
- 除法等无限小数在展示时统一四舍五入到 **12 位小数**：`1/3` → `0.333333333333`。
- 整数结果**完整输出不截断**：`100!` 会输出全部 158 位。

### 安全约束

- **禁止** `eval` / `exec` / `compile` / `ast.literal_eval` 等一切把用户输入当代码执行的手段；
- 表达式长度上限 **500** 字符，括号嵌套上限 **64** 层，阶乘参数上限 **1000**；
- 以上约束都有对应的**自动化测试**（`tests/test_calculator_engine.py::TestSecurity`），
  用 `ast` 静态分析计算内核的源码与调用，防止有人无意中引入 `eval`。

---

## 13. 运行测试

```bash
# 运行全部测试（217 个用例）
python -m pytest

# 显示每个用例名
python -m pytest -v

# 只测计算内核（不依赖 Web 框架）
python -m pytest tests/test_calculator_engine.py -v

# 只测接口
python -m pytest tests/test_api.py -v

# 查看覆盖率式的分组统计
python -m pytest -v --tb=short
```

测试覆盖范围：

| 测试类 | 覆盖内容 |
| --- | --- |
| `TestBasicArithmetic` | 加减乘除、全角符号归一化 |
| `TestCompoundExpressions` | 优先级、括号、小数、一元正负号、幂、阶乘、百分号、函数 |
| `TestAngleMode` | DEG/RAD 角度制切换、浮点噪声整平 |
| `TestErrorHandling` | 六类除零、空表达式、13 类语法错误、14 类具体错误码、长度与嵌套上限 |
| `TestSecurity` | 9 种代码注入尝试全部被拒 + `ast` 静态审计内核源码 |
| `TestTokenizer` | Token 序列、位置记录、全角归一化 |
| `TestParser` | AST 结构（优先级形状、幂的右结合） |
| `TestFormatter` | 整数归一化、12 位小数、科学计数法、大整数不截断 |
| `TestCalculateEndpoint` | 201 状态码、信封结构、角度制透传、错误分支、失败不入库 |
| `TestHistoryEndpoint` | 空历史、倒序、分页、越界夹取、搜索（含通配符转义）、排序、**持久化** |
| `TestDeleteEndpoint` | 删除指定记录（API + 数据库双重验证）、404、重复删除、清空 |
| `TestFavoriteEndpoint` | 设置 / 切换收藏、只看收藏筛选 |
| `TestStatsEndpoint` | 统计结构、一元负号不被误统计为减法 |
| `TestConversionEndpoints` | 8 组进制转换、11 组单位换算、非法参数 |
| `TestGeneralBehaviour` | 健康检查、根路径、未知路由信封、CORS 响应头、OpenAPI schema |

---

## 14. 常见问题

### Q1. 启动时报 `error while attempting to bind on address ... 只允许使用一次`

端口 8000 被其他程序占用了。换一个端口：

```bash
python run.py --port 8010
```

同时记得把前端 `.env.local` 里的 `VITE_API_BASE_URL` 改成对应的端口。

在 Windows 上查看端口占用：

```powershell
netstat -ano | findstr :8000
```

### Q2. 前端页面显示"无法连接后端服务"

按顺序排查：

1. 后端进程是否在运行？浏览器访问 `http://127.0.0.1:8000/api/health` 看一下；
2. 前端的 `VITE_API_BASE_URL` 是否指向了正确的地址和端口？
3. 浏览器控制台是否有 CORS 报错？如果有，把前端地址加到
   `CALCULATOR_CORS_ORIGINS` 环境变量里再重启后端；
4. 改过 `.env.local` 之后**必须重启** `npm run dev`，Vite 不会热更新环境变量。

### Q3. 数据库文件在哪？可以直接删掉重来吗？

默认在 `data/calculator.db`。可以直接删除，重启服务会自动重建空表。
如果想保留数据但换个位置，用 `CALCULATOR_DB_PATH` 环境变量指定。

### Q4. 为什么不用 MySQL / PostgreSQL？

作业对数据库类型没有限制，SQLite 完全满足"后端数据库持久化"的要求，
而且省掉了助教装数据库、建用户、配密码的步骤。
由于所有 SQL 都收敛在 `app/repository/history_repository.py` 里，
将来要迁移到 MySQL 只需要重写这一个文件。

### Q5. 为什么 `POST /api/calculate` 返回 201 而不是 200？

201 Created 表示"请求成功**并且创建了新资源**"。每次计算成功都会在
`calculation_history` 表里插入一条记录，确实创建了新资源，所以返回 201。
查询、删除等不创建资源的接口返回 200。

作业原文明确允许自定义状态码设计："The exact status code design may be
determined according to the actual API implementation."

### Q6. 前端能不能不启动后端就得到结果？

**不能，这是设计目标。** 所有计算逻辑都在后端，前端只拼接表达式字符串并发送 HTTP 请求。
把后端服务停掉之后，前端界面仍然可以点击、可以输入，但点 `=` 只会提示
"无法连接后端服务"，得不到任何计算结果。这正是作业要求的验证方式。

---

## 附：与作业要求的对应关系

| 作业要求 | 本仓库的实现 | 相关文件 |
| --- | --- | --- |
| Feature 1 基本计算（+ - × ÷） | 后端计算并返回 | `app/calculator/` |
| Feature 2 复合表达式（优先级/括号/小数/一元正负/非法表达式/除零） | 自研词法+语法+求值 | `app/calculator/parser.py`、`evaluator.py` |
| 禁止 `eval` / `exec` | 全流程无代码执行；有静态审计测试 | `tests/test_calculator_engine.py::TestSecurity` |
| Feature 3 计算历史入库 | SQLite 持久化，重启不丢 | `app/repository/history_repository.py` |
| Feature 4 删除指定历史 | `DELETE /api/history/{id}`，实际删除 | `app/controller/history_controller.py` |
| 前后端分离、HTTP/JSON | REST API + CORS | `app/main.py` |
| 标准化 API 响应 | 统一信封 + 错误码表 | `app/common/responses.py` |
| 扩展功能 | 科学计算、角度制、搜索分页、收藏、统计、进制转换、单位换算 | `app/service/` |
