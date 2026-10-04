# 后端代码规范（832402204_calculator_backend）

## 规范来源

本项目的代码规范以**主流官方/社区标准**为依据，并结合本项目实际情况做少量补充约定。
规范的来源如下（按重要性排序）：

1. **PEP 8 – Style Guide for Python Code**（Python 官方，<https://peps.python.org/pep-0008/>）
   —— 命名、缩进、空行、导入、注释等基础风格；
2. **PEP 257 – Docstring Conventions**（Python 官方，<https://peps.python.org/pep-0257/>）
   —— 文档字符串的书写规范；
3. **Google Python Style Guide**（Google，<https://google.github.io/styleguide/pyguide.html>）
   —— 模块/类/函数文档字符串格式、导入分组、异常使用；
4. **The Twelve-Factor App**（<https://12factor.net/config>）
   —— 配置外置（本项目所有配置通过环境变量注入，见 `src/config.py`）；
5. **Flask 官方文档 – Patterns for scalable projects**
   （<https://flask.palletsprojects.com/en/stable/patterns/>）
   —— 应用工厂（application factory）与蓝图（Blueprint）的组织方式；
6. 本项目补充约定（第十二节），用于约束本作业特有的分层、响应格式与安全红线。

> 说明：选择 Python 技术栈是因为本课程作业允许自由选择语言，
> 而 Python 的标准库即可提供 SQLite 与 HTTP 能力，依赖最少、跨平台最好。
> 因此代码规范选择 Python 官方 PEP 与 Google Python Style Guide 作为基准。

---

## 一、工具与格式基线

| 项目 | 规定 |
| --- | --- |
| Python 版本 | ≥ 3.10（使用了 `dataclass`、`X | None` 类型注解风格） |
| 缩进 | 4 个空格，禁止使用 Tab |
| 行宽 | 最长 100 个字符（Google 风格建议 80，本项目取 100 以减少无意义换行） |
| 换行符 | LF（`\n`），文件统一 UTF-8 编码 |
| 文件结尾 | 保留一个空行，去掉行尾空白 |
| 编码声明 | 使用 UTF-8 且文件无 BOM；Python 3 无需写 `# -*- coding: utf-8 -*-` |
| 自动检查（建议） | `ruff` / `flake8` + `black`（行宽 100）；本项目代码已按上述基线书写 |

推荐的自检命令：

```bash
python -m compileall src app.py         # 语法检查
python -m unittest discover -s tests -v # 运行全部测试
```

---

## 二、命名规范（PEP 8）

| 对象 | 规则 | 正例 | 反例 |
| --- | --- | --- | --- |
| 模块 / 包 | 全小写，单词用下划线分隔 | `calculation_record.py` | `CalculationRecord.py` |
| 类 | 大驼峰（CapWords） | `CalculationRecord` | `calculation_record` |
| 函数 / 方法 / 变量 | 小写下划线（snake_case） | `find_page`、`max_size` | `findPage`、`maxSize` |
| 常量 | 全大写下划线 | `MAX_PAGE_SIZE` | `maxPageSize` |
| 私有成员 | 单个前导下划线 | `_build_filters` | `build_filters_private` |
| 类型变量 | 大驼峰 | `ResponsePayload` | `response_payload` |
| 布尔变量 | 用 `is_` / `has_` / `can_` 前缀 | `is_favorite` | `favorite_flag` |

命名要求"见名知义"，禁止 `data1`、`tmp`、`aaa` 之类的无意义名称。
业务术语保持全项目一致：本项目统一使用 `expression`（表达式）、
`result`（结果）、`created_at`（计算时间）、`record`（历史记录）。

```python
# 正例
MAX_EXPRESSION_LENGTH = 200
def find_page(page: int, page_size: int) -> tuple[list[CalculationRecord], int]: ...

# 反例
MAXLEN = 200                      # 缩写不明
def findPage(p, n): ...           # 驼峰 + 无意义参数名
```

---

## 三、导入（PEP 8 / Google）

1. 一个导入一行，禁止 `import os, sys`；
2. 分组书写，组间空一行：**标准库 → 第三方库 → 本项目模块**；
3. 优先使用绝对导入（`from src.model import ...`），相对导入仅在包内部使用且必须显式（`from .database import get_connection`）；
4. 禁止 `from module import *`；
5. 只在类型注解中使用的名称，放在 `if TYPE_CHECKING:` 或使用字符串注解，避免循环导入。

```python
# 正例
import logging
import sqlite3
from dataclasses import dataclass
from typing import List, Optional

from flask import Blueprint, request

from ..common.api_response import success_response


# 反例
import sys, os
from src.model.database import *
```

---

## 四、类型注解

* 所有**公开函数/方法的参数与返回值**必须写类型注解；
* 可空类型使用 `Optional[X]`（或 `X | None`），不要用隐式的"可能为 None"；
* 容器类型写清元素类型：`List[CalculationRecord]`、`Dict[str, int]`；
* 复杂返回值用 `Tuple[A, B]` 说明顺序，并在 docstring 的 Returns 中再次说明。

```python
# 正例
def find_page(
    page: int = 1,
    page_size: int = 10,
    keyword: Optional[str] = None,
) -> Tuple[List[CalculationRecord], int]:
    """分页查询历史记录。Returns: (当前页记录列表, 总条数)。"""

# 反例
def find_page(page=1, page_size=10, keyword=None):
    ...
```

---

## 五、文档字符串（PEP 257 + Google 风格）

* 每个**模块**顶部必须有模块级 docstring，说明"这个文件负责什么、为什么这样设计"；
* 每个**公开类/函数**必须有 docstring；
* 采用 Google 风格的小节：`Args:` / Returns: / Raises: / Attributes:`；
* 第一行是一句话概述，以句号结尾，与后续内容空一行；
* 注释解释"**为什么**"，而不是复述"做了什么"。

```python
# 正例
def calculate(expression: str, persist: bool = True) -> CalculationResult:
    """执行一次计算。

    Args:
        expression: 用户输入的表达式（可以包含 ``×`` ``÷`` ``π`` 等符号）。
        persist: 是否把成功的结果写入历史表；实时预览传 False。

    Returns:
        :class:`CalculationResult`。

    Raises:
        CalculatorError: 输入非法、语法错误、除零、定义域错误或结果溢出。
    """

# 反例
def calculate(expression, persist=True):
    # 计算
    ...
```

---

## 六、代码结构与可读性

* 单个函数不超过 **60 行**，超过就拆分为语义明确的子函数；
* 单个模块不超过 **400 行**，超过就按职责拆分模块；
* 圈复杂度尽量低：优先"早返回（early return）"，减少深层 `if` 嵌套；
* 禁止魔法数字，必须提取为具名常量：

```python
# 正例（src/calculator/functions.py）
MAX_FACTORIAL_ARGUMENT = 1000

def factorial_value(value: Decimal) -> Decimal:
    if value > MAX_FACTORIAL_ARGUMENT:
        raise NumericOverflowError(f"阶乘参数过大（n ≤ {MAX_FACTORIAL_ARGUMENT}）")

# 反例
if value > 1000:
    raise NumericOverflowError("too big")
```

* 一行只做一件事，一行只写一条语句；
* 使用 f-string 进行字符串格式化，不使用 `%` 或 `str.format`（可读性更好）。

---

## 七、异常处理

* **禁止**裸 `except:` 和 `except Exception: pass`；
* 捕获异常时必须处理或转换成携带上下文的业务异常：

```python
# 正例
try:
    value = Decimal(text)
except (InvalidOperation, ValueError) as exc:
    raise NumericOverflowError(f"无法解析数字：{text}") from exc

# 反例
try:
    value = Decimal(text)
except:
    pass
```

* 使用 `raise ... from exc` 保留原始异常链，便于排查；
* 业务异常统一继承 `CalculatorError`（见 `src/calculator/exceptions.py`），
  且必须定义稳定的 `error_code`；
* 未预期异常由 `src/common/errors.py` 统一兜底，对外只暴露 `UNKNOWN_ERROR`，
  完整堆栈写入服务端日志。

---

## 八、安全规范（本项目强制红线）

1. **严禁**使用 `eval`、`exec`、`compile`、`__import__` 处理用户输入；
   `tests/test_calculator.py::SecurityTests::test_no_eval_in_source_code` 会做静态检查；
2. **严禁**字符串拼接 SQL，所有查询必须使用参数化占位符 `?`：

```python
# 正例（src/model/calculation_record.py）
connection.execute(
    "SELECT id FROM calculation_history WHERE expression LIKE ?", (pattern,)
)

# 反例（存在 SQL 注入漏洞）
connection.execute(f"SELECT id FROM calculation_history WHERE expression LIKE '%{keyword}%'")
```

3. **严禁**把用户输入直接拼进 `ORDER BY` / 表名，必须使用白名单映射：

```python
_SORT_DIRECTIONS = {"asc": "ASC", "desc": "DESC"}
direction = _SORT_DIRECTIONS.get(sort.lower(), "DESC")
```

4. 所有外部输入必须做**长度与类型校验**（`MAX_EXPRESSION_LENGTH = 200`、
   `page_size ≤ 100`、阶乘参数 ≤ 1000、指数 ≤ 10000），防止资源耗尽；
5. 错误信息可以给用户看，但**不得**暴露文件路径、SQL 语句、堆栈等实现细节。

---

## 九、分层与依赖规范（本项目约定）

| 层 | 目录 | 允许依赖 | 禁止事项 |
| --- | --- | --- | --- |
| 控制器 | `src/controller` | service、common | 禁止直接写 SQL、禁止写业务规则 |
| 服务 | `src/service` | model、calculator、common | 禁止触碰 `request`/`jsonify` |
| 模型 | `src/model` | `sqlite3`、config | 禁止写业务规则 |
| 计算核心 | `src/calculator` | 仅标准库 | **禁止**依赖 Flask 与数据库 |

依赖方向必须单向，不得出现反向依赖或循环导入。
这样 `src/calculator` 可以完全脱离 Web 框架被单元测试直接调用。

---

## 十、API 与响应规范（本项目约定）

1. 所有接口挂在 `/api` 前缀下，路径使用**复数名词**（`/api/history`）；
2. 请求与响应一律 `application/json; charset=utf-8`；
3. 响应外壳统一由 `src/common/api_response.py` 生成，禁止在控制器里手写字典：

```python
# 正例
return success_response(data=record.to_dict(), message="查询成功")

# 反例
return jsonify({"code": 0, "msg": "ok", "result": record})
```

4. 错误响应必须包含 `success`、`message`、`error_code` 三个字段；
5. 正确使用 HTTP 状态码：200 成功、400 参数/业务错误、404 资源不存在、
   405 方法不允许、500 服务器内部错误；
6. 中文错误信息直接使用 UTF-8，不转义为 `\uXXXX`（`app.json.ensure_ascii = False`）。

---

## 十一、测试规范

* 测试文件放在 `tests/`，命名为 `test_*.py`，使用标准库 `unittest`（零额外依赖）；
* 测试方法命名 `test_<行为>_<预期>`，例如 `test_division_by_zero_returns_400`；
* 每个测试必须**独立**：不得依赖其它测试的执行顺序或残留数据；
* 涉及数据库的测试使用独立的临时数据库文件，测试结束清理；
* 新增功能必须同时补充测试；提交前必须全部通过。

```bash
python -m unittest discover -s tests -v     # 78 个用例全部通过
```

---

## 十二、Git 提交规范

采用 Conventional Commits，提交信息格式：`<type>(<scope>): <描述>`

| type | 含义 |
| --- | --- |
| `feat` | 新功能 |
| `fix` | 缺陷修复 |
| `refactor` | 重构（不改变外部行为） |
| `docs` | 文档 |
| `test` | 测试 |
| `style` | 格式调整 |
| `chore` | 构建/依赖/杂项 |

示例：

```
feat(calculator): 支持一元正负号与右结合幂运算
fix(api): 修正未知 /api 路径返回 405 而非 404 的问题
docs(readme): 补充数据库初始化与前端联调步骤
test(api): 增加历史记录重启后仍然存在的持久化用例
```

一次提交只做一件事，提交信息用祈使句，不加句号。

---

## 十三、自查清单

提交代码前逐项确认：

- [ ] `python -m unittest discover -s tests -v` 全部通过
- [ ] 公开函数都有类型注解与 docstring
- [ ] 没有 `eval` / `exec` / SQL 字符串拼接 / 裸 `except`
- [ ] 没有魔法数字，常量已提取并命名
- [ ] 没有超过 100 字符的行，文件为 UTF-8 无 BOM
- [ ] 分层依赖方向正确，`src/calculator` 未引入 Flask 或数据库
- [ ] 新增接口已在 README 的 API 表格中登记
