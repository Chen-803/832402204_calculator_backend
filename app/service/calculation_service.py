"""计算服务：把"算"和"存"编排在一起。

职责边界
--------
- 纯计算逻辑在 :mod:`app.calculator`（不碰数据库）；
- 纯数据访问在 :class:`app.repository.history_repository.HistoryRepository`（不做计算）；
- 本层负责**编排**：计时 → 调用计算内核 → 落库 → 组装返回数据。

这是典型的"Service 层薄编排"：它自己不实现任何算法，
但决定了"一次计算请求要做哪些事、按什么顺序做"。
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from ..calculator import CalculatorError, calculate
from ..repository.history_repository import HistoryRepository

#: 时间格式：作业示例使用 ``YYYY-MM-DD HH:mm:ss``
DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"


def now_text() -> str:
    """当前时间的标准字符串形式。"""
    return datetime.now().strftime(DATETIME_FORMAT)


@dataclass(frozen=True)
class CalculationResult:
    """一次计算请求的完整结果（含落库后的历史 ID）。"""

    expression: str
    normalized_expression: str
    result: float | None
    result_text: str
    history_id: int
    created_at: str
    elapsed_ms: float


class CalculationService:
    """计算业务服务。"""

    def __init__(self, repository: HistoryRepository | None = None) -> None:
        self._repository = repository or HistoryRepository()

    def calculate(self, expression: str, angle_mode: str = "rad") -> CalculationResult:
        """执行一次计算并持久化历史。

        流程（严格对应作业要求的前后端交互顺序）::

            前端发表达式
              → 后端校验（归一化 + 长度 + 字符）
              → 后端解析（词法 + 语法）
              → 后端计算（求值）
              → 后端入库（计算成功才写）
              → 后端返回结果 + 历史 ID

        注意：**只有计算成功才会写历史**。失败的计算（除零、语法错误）
        不入库，避免历史列表被错误记录污染。

        :param expression: 用户表达式
        :param angle_mode: ``rad`` 或 ``deg``
        :raises CalculatorError: 表达式相关的任何错误
        """
        started = time.perf_counter()
        outcome = calculate(expression, angle_mode)
        elapsed_ms = round((time.perf_counter() - started) * 1000, 3)

        created_at = now_text()
        history_id = self._repository.insert(
            expression=outcome.expression.strip(),
            normalized_expression=outcome.normalized_expression,
            result=outcome.result_text,
            angle_mode=angle_mode,
            elapsed_ms=elapsed_ms,
            created_at=created_at,
        )

        return CalculationResult(
            expression=outcome.expression.strip(),
            normalized_expression=outcome.normalized_expression,
            result=outcome.json_number,
            result_text=outcome.result_text,
            history_id=history_id,
            created_at=created_at,
            elapsed_ms=elapsed_ms,
        )

    def to_payload(self, result: CalculationResult) -> dict[str, Any]:
        """把计算结果转成 API 响应字段。"""
        return {
            "expression": result.expression,
            "normalizedExpression": result.normalized_expression,
            "result": result.result,
            "resultText": result.result_text,
            "historyId": result.history_id,
            "createdAt": result.created_at,
            "elapsedMs": result.elapsed_ms,
        }


__all__ = [
    "CalculationResult",
    "CalculationService",
    "CalculatorError",
    "DATETIME_FORMAT",
    "now_text",
]
