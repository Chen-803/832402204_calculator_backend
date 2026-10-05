# 接口契约（API Contract）v1.0 — 冻结版本

> 本文件是前后端并行开发的**唯一接口依据**。前端只依赖本文件描述的 URL、请求体、响应体与错误码；
> 后端必须严格实现本文件。任何一方需要变更接口，必须先修改本文件再改代码。

- 后端基地址（本地）：`http://127.0.0.1:8000`
- 所有业务接口统一前缀：`/api`
- 请求与响应编码：`application/json; charset=utf-8`
- 跨域：后端开启 CORS，允许前端开发服务器（`http://localhost:5173`）访问

---

## 1. 统一响应信封（Envelope）

**所有**接口（含错误）都返回如下**扁平信封**，业务字段直接平铺在顶层：

```json
{
  "success": true,
  "code": 0,
  "message": "OK",
  "...业务字段": "..."
}
```

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `success` | boolean | 业务是否成功。`true` 仅在计算/查询真正成功时为真 |
| `code` | integer | 业务码。`0` 表示成功，非 0 见错误码表 |
| `message` | string | 人类可读信息；失败时是可直接展示给用户的中文提示 |
| 业务字段 | any | 由各接口定义 |

前端判定规则：**以 `success` 为准**，同时结合 HTTP 状态码。

---

## 2. HTTP 状态码约定

| 状态码 | 使用场景 |
| --- | --- |
| `200 OK` | 查询历史、删除历史、统计、进制/单位转换成功 |
| `201 Created` | `POST /api/calculate` 计算成功（同时在后端数据库中新建了一条历史记录） |
| `400 Bad Request` | 表达式非法、除零、函数定义域错误、转换参数非法 |
| `404 Not Found` | 要删除/操作的历史记录 ID 不存在 |
| `422 Unprocessable Entity` | 请求体 JSON 结构不合法（缺少 `expression` 等） |
| `500 Internal Server Error` | 后端未预期异常 |

---

## 3. 错误码表

| code | HTTP | message 示例 | 触发条件 |
| --- | --- | --- | --- |
| `0` | 200/201 | `OK` | 成功 |
| `40001` | 400 | `表达式为空` | 表达式为空串或只有空白 |
| `40002` | 400 | `表达式语法错误：缺少右括号` | 词法/语法错误 |
| `40003` | 400 | `除数不能为 0` | 除以零 / 对 0 取模 |
| `40004` | 400 | `表达式过长，最多支持 500 个字符` | 超过长度上限 |
| `40005` | 400 | `不支持的函数：foo` | 未知函数名 |
| `40006` | 400 | `函数定义域错误：sqrt 的参数不能为负数` | 数学定义域错误 |
| `40007` | 400 | `进制转换参数不合法` | 进制不在 2..36，或数字与进制不匹配 |
| `40008` | 400 | `不支持的单位类别` | 单位类别/单位符号不存在 |
| `40009` | 400 | `字符无法识别：@` | 出现非法字符 |
| `40401` | 404 | `历史记录不存在：id=99` | 指定 ID 不存在 |
| `42201` | 422 | `请求参数不合法：expression 字段缺失` | 请求体结构错误 |
| `50000` | 500 | `服务器内部错误` | 未捕获异常 |

---

## 4. 接口清单

### 4.1 `POST /api/calculate` — 计算表达式（核心）

前端**只发送表达式原文**，结果由后端计算并返回。

**请求体**

```json
{
  "expression": "(1+2)*3",
  "angleMode": "deg"
}
```

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `expression` | string | 是 | 表达式原文。可用 `×` `÷`，后端会自动归一化为 `*` `/` |
| `angleMode` | string | 否 | `"deg"` 或 `"rad"`，默认 `"rad"`；仅影响三角/反三角函数 |

**成功响应 `201 Created`**

```json
{
  "success": true,
  "code": 0,
  "message": "OK",
  "expression": "(1+2)*3",
  "normalizedExpression": "(1+2)*3",
  "result": 9,
  "resultText": "9",
  "historyId": 12,
  "createdAt": "2026-10-05 12:30:00",
  "elapsedMs": 0.42
}
```

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `expression` | string | 前端原始输入（回显） |
| `normalizedExpression` | string | 后端归一化后的表达式（`×`→`*` 等） |
| `result` | number | 数值结果（前端展示请优先用 `resultText`） |
| `resultText` | string | **推荐前端直接展示的字符串结果**，已做精度处理 |
| `historyId` | integer | 本次计算落库后的历史记录 ID |
| `createdAt` | string | 计算时间，格式 `YYYY-MM-DD HH:mm:ss` |
| `elapsedMs` | number | 后端计算耗时（毫秒，保留 3 位小数） |

**失败响应（示例：除零）`400 Bad Request`**

```json
{
  "success": false,
  "code": 40003,
  "message": "除数不能为 0",
  "expression": "1/0"
}
```

---

### 4.2 `GET /api/history` — 查询历史（支持搜索 / 分页 / 收藏筛选）

**Query 参数**

| 参数 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `keyword` | string | 空 | 按表达式或结果模糊搜索 |
| `page` | int | 1 | 页码，从 1 开始 |
| `pageSize` | int | 10 | 每页条数，1..100 |
| `onlyFavorite` | bool | false | 只看收藏 |
| `order` | string | `desc` | `desc` 按时间倒序，`asc` 正序 |

**成功响应 `200 OK`**

```json
{
  "success": true,
  "code": 0,
  "message": "OK",
  "total": 42,
  "page": 1,
  "pageSize": 10,
  "totalPages": 5,
  "items": [
    {
      "id": 12,
      "expression": "(1+2)*3",
      "result": 9,
      "resultText": "9",
      "favorite": false,
      "createdAt": "2026-10-05 12:30:00"
    }
  ]
}
```

`items` 按 `createdAt`（同秒时按 `id`）排序。

---

### 4.3 `DELETE /api/history/{id}` — 删除指定历史

**成功响应 `200 OK`**

```json
{ "success": true, "code": 0, "message": "OK", "deleted": 1, "id": 12 }
```

**失败响应 `404 Not Found`**

```json
{ "success": false, "code": 40401, "message": "历史记录不存在：id=99", "id": 99 }
```

---

### 4.4 `DELETE /api/history` — 清空全部历史（扩展）

```json
{ "success": true, "code": 0, "message": "OK", "deleted": 42 }
```

---

### 4.5 `PATCH /api/history/{id}/favorite` — 切换收藏（扩展）

**请求体**

```json
{ "favorite": true }
```

`favorite` 省略时表示取反。

**成功响应 `200 OK`**

```json
{
  "success": true, "code": 0, "message": "OK",
  "id": 12, "favorite": true
}
```

---

### 4.6 `GET /api/stats` — 计算统计（扩展）

```json
{
  "success": true,
  "code": 0,
  "message": "OK",
  "totalCount": 42,
  "todayCount": 7,
  "favoriteCount": 3,
  "operatorUsage": [{ "operator": "+", "count": 20 }, { "operator": "*", "count": 11 }],
  "topExpressions": [{ "expression": "1+2", "count": 5 }],
  "recentSevenDays": [{ "date": "2026-10-05", "count": 7 }]
}
```

---

### 4.7 `POST /api/convert/base` — 进制转换（扩展）

**请求体**

```json
{ "value": "255", "fromBase": 10, "toBase": 16 }
```

`fromBase` / `toBase` 取值 `2..36`；`value` 允许带符号与小数点。

**成功响应 `200 OK`**

```json
{
  "success": true, "code": 0, "message": "OK",
  "input": "255", "fromBase": 10, "toBase": 16,
  "output": "FF", "decimalValue": "255"
}
```

---

### 4.8 `GET /api/convert/units` — 单位类别与单位定义（扩展）

```json
{
  "success": true, "code": 0, "message": "OK",
  "categories": [
    {
      "key": "length", "name": "长度",
      "units": [{ "key": "m", "name": "米" }, { "key": "km", "name": "千米" }]
    }
  ]
}
```

### 4.9 `POST /api/convert/unit` — 单位换算（扩展）

**请求体**

```json
{ "category": "length", "from": "m", "to": "km", "value": 1000 }
```

**成功响应 `200 OK`**

```json
{
  "success": true, "code": 0, "message": "OK",
  "category": "length", "from": "m", "to": "km",
  "value": 1000, "output": 1, "outputText": "1"
}
```

---

### 4.10 `GET /api/health` — 健康检查

```json
{ "success": true, "code": 0, "message": "OK", "service": "calculator-backend", "version": "1.0.0", "database": "ok", "time": "2026-10-05 12:30:00" }
```

---

## 5. 表达式语法规范（后端实现依据）

### 5.1 支持的运算

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

### 5.2 函数与常量

- 常量：`pi`、`e`
- 一元函数：`sin cos tan asin acos atan sinh cosh tanh sqrt cbrt abs ln log log2 lg exp floor ceil round sign`
- 二元函数：`pow(a,b)` `max(a,b,...)` `min(a,b,...)` `mod(a,b)` `log(a,b)`（b 为底）
- `fact(n)` 阶乘，等价 `n!`
- `log(x)` 为常用对数（底 10），`ln(x)` 为自然对数，`log(x, b)` 为以 b 为底

### 5.3 输入归一化（后端做）

`×`→`*`，`÷`→`/`，`（`→`(`，`）`→`)`，`，`→`,`，全角数字→半角，`−`/`–`→`-`，
`＋`→`+`，`－`→`-`，`＊`→`*`，`／`→`/`，`＾`→`^`，`！`→`!`，`％`→`%`

### 5.4 精度策略

- 内部使用 `decimal.Decimal`（`prec=34`）做加减乘除与幂，避免 `0.1+0.2=0.30000000000000004`
- 三角函数等超越函数转 `float` 计算后回写 `Decimal`
- 输出：整数结果直接输出整数串；非整数结果保留**最多 12 位小数**并去掉尾随 0
- 超出常规范围（`|x| >= 1e16` 或 `0 < |x| < 1e-12`）时使用科学计数法

### 5.5 安全约束（作业硬性要求）

- **禁止** `eval` / `exec` / `compile` / `ast.literal_eval` 等一切把用户输入当程序代码执行的手段
- 自研 词法分析 → 语法分析（Pratt / 优先级爬升）→ AST → 求值 流水线
- 表达式长度上限 500 字符；括号嵌套深度上限 100；`fact` 参数上限 1000
