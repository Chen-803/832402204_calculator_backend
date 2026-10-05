"""领域实体（Domain Entity）。

实体是"业务概念"在代码里的表示，与数据库表结构、API 报文结构解耦：

- **数据库表结构**（``calculation_history``）关心列类型、索引；
- **API 报文**（``docs/API_CONTRACT.md``）关心字段名与 JSON 类型；
- **实体**关心"一条计算历史到底是什么"。

三者分开之后，改数据库列名不会影响接口，改接口字段也不会影响数据库。
实体自身的 :meth:`HistoryRecord.from_row` / :meth:`to_dict` 负责两层之间的翻译。
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any


@dataclass(frozen=True)
class HistoryRecord:
    """一条计算历史记录。"""

    id: int
    expression: str
    normalized_expression: str
    result: str
    angle_mode: str
    elapsed_ms: float
    favorite: bool
    created_at: str

    # ------------------------------------------------------------------ #
    # 与数据库行之间的转换
    # ------------------------------------------------------------------ #
    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "HistoryRecord":
        """由数据库行构造实体。"""
        return cls(
            id=int(row["id"]),
            expression=row["expression"],
            normalized_expression=row["normalized_expression"],
            result=row["result"],
            angle_mode=row["angle_mode"],
            elapsed_ms=float(row["elapsed_ms"]),
            favorite=bool(row["favorite"]),
            created_at=row["created_at"],
        )

    # ------------------------------------------------------------------ #
    # 与 API 报文之间的转换
    # ------------------------------------------------------------------ #
    def to_dict(self) -> dict[str, Any]:
        """转成 API 响应里的字典。

        ``result`` 字段在数据库中存的是**字符串**（见设计说明），
        这里额外提供一个 JSON number 形式的 ``result``，
        转换失败（超出 double 范围）时回退为字符串，保证前端永远拿得到值。
        """
        return {
            "id": self.id,
            "expression": self.expression,
            "result": self._json_result(),
            "resultText": self.result,
            "favorite": self.favorite,
            "createdAt": self.created_at,
        }

    def _json_result(self) -> float | str:
        """把字符串结果转成 JSON number，超范围时原样返回字符串。"""
        try:
            number = float(self.result)
        except (TypeError, ValueError, InvalidOperation):
            return self.result
        if number != number or number in (float("inf"), float("-inf")):
            return self.result
        return number

    @property
    def decimal_result(self) -> Decimal | None:
        """结果的高精度形式；无法解析时为 ``None``。"""
        try:
            return Decimal(self.result)
        except (InvalidOperation, TypeError, ValueError):
            return None
