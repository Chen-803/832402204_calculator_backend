# 后端代码规范（codestyle.md）

> 学号：**832402204** ｜ 姓名：**陈俊洁** ｜ 项目：前后端分离计算器系统 · 后端

## 0. 规范来源

本项目的代码规范**不是自创的**，而是在以下主流官方规范的基础上，
结合本项目的技术栈（Python 3.10+ / FastAPI / SQLite）裁剪而成：

| 序号 | 规范 | 制定方 | 链接 |
| --- | --- | --- | --- |
| 1 | **PEP 8 – Style Guide for Python Code** | Python 官方（Python Software Foundation） | <https://peps.python.org/pep-0008/> |
| 2 | **PEP 257 – Docstring Conventions** | Python 官方 | <https://peps.python.org/pep-0257/> |
| 3 | **PEP 484 – Type Hints** | Python 官方 | <https://peps.python.org/pep-0484/> |
| 4 | **Google Python Style Guide** | Google | <https://google.github.io/styleguide/pyguide.html> |
| 5 | **The Zen of Python (PEP 20)** | Python 官方 | <https://peps.python.org/pep-0020/> |
| 6 | **FastAPI 官方项目结构建议** | FastAPI / tiangolo | <https://fastapi.tiangolo.com/tutorial/bigger-applications/> |

**冲突时的取舍顺序**：PEP 8 > Google Python Style Guide > 本文件的自定义条款。
本文件只对上述规范未覆盖、或本项目有特殊约定的部分做出补充规定。

---

## 1. 格式化基线

### 1.1 行长度

- 代码行最长 **100** 个字符（PEP 8 允许 79，Google 允许 80；
  本项目放宽到 100，因为中文注释很多，79 会让注释频繁换行反而更难读）。
- 文档字符串与注释同样遵守 100 字符上限。
- 禁止用反斜杠续行，一律使用括号隐式续行。

```python
# ✅ 正确：括号内隐式续行，对齐到开括号后
result = calculator.calculate(
    expression=expression,
    angle_mode=angle_mode,
)

# ❌ 错误：反斜杠续行
result = calculator.calculate(expression=expression, \
                              angle_mode=angle_mode)
```

### 1.2 缩进

- **4 个空格**，禁止 Tab。
- 续行使用**悬挂缩进**（hanging indent）或与开分隔符对齐，二选一但同一文件内保持一致。

### 1.3 空行

- 顶层函数与类之间：**2 个空行**。
- 类内部方法之间：**1 个空行**。
- 函数内部用空行分隔逻辑段落，但不要超过 1 个连续空行。

### 1.4 导入

按下面的**三段式**排列，段间空一行，段内按字母序：

```python
# 1) 标准库
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from decimal import Decimal

# 2) 第三方库
from fastapi import APIRouter, Depends

# 3) 本项目模块（一律使用相对导入）
from ..calculator.errors import ErrorCode
from ..common.responses import ok_response
```

- 所有模块首行统一写 `from __future__ import annotations`，
  让类型标注延迟求值，既避免循环导入又能使用 `X | None` 写法。
- **禁止** `from module import *`。
- 未使用的导入必须删除（本项目用 `ruff` 的 `F401` 规则自查）。

---

## 2. 命名规范

| 对象 | 规则 | 示例 |
| --- | --- | --- |
| 模块 / 包 | 全小写 + 下划线 | `history_repository.py` |
| 类 | 大驼峰 `CapWords` | `CalculationService`、`HistoryRecord` |
| 异常类 | 大驼峰 + `Error` 后缀 | `DivisionByZeroError`、`NotFoundError` |
| 函数 / 方法 | 全小写 + 下划线 | `find_page`、`set_favorite` |
| 变量 | 全小写 + 下划线 | `page_size`、`angle_mode` |
| 常量 | 全大写 + 下划线 | `MAX_EXPRESSION_LENGTH` |
| 私有成员 | 单下划线前缀 | `self._repository` |
| 类型别名 | 大驼峰 | `JsonPayload` |

### 2.1 命名的语义要求

- **布尔值**用 `is_` / `has_` / `can_` / `should_` 开头：
  `is_finite`、`has_children`、`should_retry`。
- **集合类变量用复数**：`records`、`tokens`、`categories`（不要写 `record_list`）。
- **避免无意义缩写**：写 `expression` 不写 `expr`（局部高频变量与 API 字段对齐时除外，
  此时以 `docs/API_CONTRACT.md` 的字段名为准）。
- **禁止单字符变量名**，除了：循环下标 `i` / `j`、
  推导式里的 `x`、lambda 参数、`_`（表示不使用的值）。

```python
# ✅ 正确
for index, record in enumerate(records):
    ...

# ❌ 错误：含义不明
for a in d:
    ...
```

---

## 3. 类型标注

**所有函数（含测试辅助函数）必须有完整的参数与返回值标注。**

```python
# ✅ 正确
def find_page(
    self,
    *,
    keyword: str = "",
    page: int = 1,
    page_size: int = 10,
) -> list[HistoryRecord]:
    ...

# ❌ 错误：缺少标注
def find_page(self, keyword="", page=1, page_size=10):
    ...
```

约定：

- 可选类型统一写作 `X | None`（配合 `from __future__ import annotations`），
  不使用 `Optional[X]`。
- 容器类型使用内置泛型 `list[str]`、`dict[str, Any]`，不使用 `typing.List`。
- 函数参数超过 3 个时，调用点使用**关键字参数**，并且函数定义里加 `*` 强制关键字传参，
  避免调用方把 `page` 和 `page_size` 传反。

---

## 4. 文档字符串（Docstring）

采用 **PEP 257** 风格，中文书写。所有**公开**的模块、类、函数都要有 docstring。

### 4.1 模块级

第一个语句即 docstring，说明"这个模块负责什么、为什么这样设计"：

```python
"""计算历史的数据访问层（Repository）。

**整个项目里唯一出现 SQL 的地方。** Service 层只调用这里的方法，
不直接接触 ``sqlite3``，因此将来把 SQLite 换成 MySQL 时，
只需要重写本文件，业务代码零改动。
"""
```

### 4.2 函数级

采用 Sphinx 风格的字段标记，顺序固定为：摘要 → 补充说明 → `:param:` → `:returns:` → `:raises:`。

```python
def delete_by_id(self, record_id: int) -> int:
    """删除指定记录。

    :param record_id: 历史记录主键
    :returns: 实际删除的行数（0 表示记录不存在）
    """
```

### 4.3 强调设计意图

本项目的 docstring 不只是复述函数名，必须回答**"为什么这么做"**：

```python
# ✅ 好的 docstring：解释了设计动机
def _divide(left: Decimal, right: Decimal) -> Decimal:
    """除法，显式拦截除零。

    不依赖 ``decimal`` 自己抛的 ``DivisionByZero``，因为那样拿不到统一的
    错误码；这里主动判断，保证 ``1/0``、``-5/0``、``0/0`` 都返回 40003。
    """
```

---

## 5. 注释

- 注释解释**为什么**，不解释**是什么**。代码本身已经说明了"是什么"。
- 行内注释与代码至少隔 **2 个空格**，并以 `# ` 开头。
- **禁止**保留被注释掉的死代码，需要的话交给 Git。
- 涉及"反直觉但正确"的地方必须写注释，例如：

```python
# 语法分析每层括号约消耗 6 个 Python 栈帧，取 64 可保证远低于默认递归上限（1000）。
MAX_NESTING_DEPTH = 64

# 0^0 在数学上是未定式，但所有计算器与编程语言（含 Python 的 int 幂）
# 都约定为 1；Decimal 默认会抛 InvalidOperation，这里显式给出约定值。
if base == 0 and exponent == 0:
    return Decimal(1)
```

---

## 6. 字符串

- 统一使用**双引号** `"..."`（PEP 8 不强制，但 Google 风格与前端保持一致）。
- 需要插值时优先用 **f-string**：

```python
# ✅ 正确
message = f"历史记录不存在：id={record_id}"

# ❌ 错误
message = "历史记录不存在：id=" + str(record_id)
message = "历史记录不存在：id=%s" % record_id
```

- 面向用户的提示语用**中文**；日志、异常类型名保留英文。

---

## 7. 分层与依赖规则

这是本项目**最重要的架构约束**：

```text
controller  →  service  →  calculator      （纯计算，不碰数据库）
                       ↘  repository       （纯数据，不做计算）
                             ↓
                           model
```

强制规则：

1. **依赖只能向下**：`calculator` 不允许 import `service` / `controller`；
   `repository` 不允许 import `service`。
2. **SQL 只能出现在 `repository/`**。其它层出现 `SELECT` / `INSERT` 视为违规。
3. **`calculator/` 不允许依赖 FastAPI**。它必须能脱离 Web 框架单独测试。
4. **Controller 里不允许写业务判断**，也不允许出现 `try/except`——
   异常统一由 `app/common/exception_handlers.py` 处理。
5. **业务字段命名不得与响应信封保留字冲突**：`success` / `code` / `message`。
   `api_response()` 会在运行时报错拦截。

---

## 8. 异常处理

### 8.1 分层异常体系

| 异常基类 | 所在层 | 含义 | 由谁抛出 |
| --- | --- | --- | --- |
| `CalculatorError` | `calculator` | 用户表达式有问题 | 计算内核 |
| `BusinessError` | `common` | 业务规则不满足 | Service |

两者都携带 `code`（`ErrorCode` 枚举），由全局异常处理器映射成 HTTP 状态码。

### 8.2 规则

- **禁止**裸 `except:` 和 `except Exception: pass`。
- 捕获后要么处理、要么**带上原始异常**重新抛出（`raise X from exc`），
  保留调用链：

```python
# ✅ 正确
try:
    return +((base) ** exponent)
except InvalidOperation as exc:
    raise DomainError("负数的非整数次幂不是实数（结果为复数，暂不支持）") from exc

# ❌ 错误：丢失了原始堆栈
except InvalidOperation:
    raise DomainError("...")
```

- 面向用户的 `message` 必须是**中文、无技术术语、可直接展示**；
  技术细节（堆栈、SQL 语句）只写日志，不回传给客户端。
- 500 错误绝不返回堆栈信息，避免泄露内部实现。

---

## 9. 数据库与 SQL

- **强制参数化查询**，禁止字符串拼接 SQL：

```python
# ✅ 正确
sql = "SELECT * FROM calculation_history WHERE id = ?"
conn.execute(sql, (record_id,))

# ❌ 错误：SQL 注入
conn.execute(f"SELECT * FROM calculation_history WHERE id = {record_id}")
```

- `LIKE` 查询必须转义 `%` 和 `_`，并显式写明 `ESCAPE` 子句。
- `ORDER BY` 的列名与方向**必须来自白名单**，不能直接拼用户输入。
- 查询类接口必须有 `LIMIT` 上限，防止一次性把整张表读进内存。
- 事务边界由 `get_connection()` 上下文管理器统一管理，业务代码不手写 `commit()`。

---

## 10. API 设计与响应

- 所有响应走 `api_response()` / `ok_response()` / `error_response()`，
  **不允许**手写 `JSONResponse` 或直接 `return dict`。
- HTTP 状态码语义：

| 状态码 | 使用场景 |
| --- | --- |
| 200 | 查询、删除、转换成功 |
| 201 | 创建了资源（`POST /api/calculate` 会落库一条历史） |
| 400 | 表达式非法、除零、参数语义错误 |
| 404 | 资源不存在 |
| 422 | 请求体结构不合法（字段缺失 / 类型错误） |
| 500 | 未捕获异常 |

- API 字段名统一使用 **camelCase**（`resultText`、`historyId`、`pageSize`），
  与前端 JavaScript 习惯一致；Python 内部保持 snake_case，
  通过 Pydantic 的 `alias` 做转换。

---

## 11. 测试规范

- 测试文件命名 `test_*.py`，测试类 `Test*`，测试函数 `test_*`。
- 测试函数名必须是**完整句子**，说明被测行为：
  `test_failed_calculation_is_not_saved`、`test_page_out_of_range_is_clamped`。
- 大量同类用例使用 `@pytest.mark.parametrize`，一个业务规则一条用例。
- 断言必须具体：断言状态码、业务码、字段值，
  不要只写 `assert response`。
- **关键业务规则要有"数据库层面"的二次验证**，例如删除历史后
  直接查 SQLite 确认记录真的没了。
- 测试必须独立：每个用例前清空数据，不依赖执行顺序。
- 安全约束（禁止 `eval`）用 `ast` 静态分析写成自动化测试，而不是口头约定。

---

## 12. 提交信息规范（Conventional Commits）

格式：`<type>(<scope>): <subject>`

| type | 含义 |
| --- | --- |
| `feat` | 新功能 |
| `fix` | 修复缺陷 |
| `refactor` | 重构（不改变外部行为） |
| `test` | 增加 / 修改测试 |
| `docs` | 文档 |
| `style` | 格式化（不影响逻辑） |
| `chore` | 构建 / 依赖 / 配置 |

示例：

```text
feat(calculator): 支持一元正负号与幂运算
fix(api): 修正 page 越界时返回空列表的问题
test(api): 补充删除历史后直接查库的验证用例
docs(readme): 补充数据库初始化说明
```

---

## 13. 自查清单

提交前逐条核对：

- [ ] 所有函数都有完整的类型标注
- [ ] 所有公开模块 / 类 / 函数都有 docstring，且说明了"为什么"
- [ ] 没有超过 100 字符的行
- [ ] 导入分三段且无未使用项
- [ ] 没有 `eval` / `exec` / `compile`
- [ ] 没有裸 `except:`
- [ ] 没有字符串拼接的 SQL
- [ ] 新增功能都有对应测试，且 `python -m pytest` 全绿
- [ ] Controller 里没有 `try/except`
- [ ] 面向用户的报错信息是中文
