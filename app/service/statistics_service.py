"""统计服务（扩展功能）。

作业允许扩展"计算统计"。这里的统计**不是拍脑袋数数**，而是复用计算器内核
真正的解析能力：把历史里的表达式重新解析成 AST，再遍历 AST 统计
"每个二元运算符被用了多少次"。这样 ``3*-2`` 里的 ``-`` 会被正确识别为
一元负号而不计入减法，统计结果比"数一下字符串里有多少个减号"准确得多。
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Any

from ..calculator.ast_nodes import BinaryOpNode, Node, UnaryOpNode
from ..calculator.parser import parse
from ..repository.history_repository import HistoryRepository

#: 运算符展示名，用于把内部符号转成界面上好看的写法
OPERATOR_DISPLAY = {
    "+": "+（加）",
    "-": "-（减）",
    "*": "×（乘）",
    "/": "÷（除）",
    "mod": "mod（取模）",
    "^": "^（幂）",
    "%": "%（百分号）",
    "!": "!（阶乘）",
}

#: 参与统计的最大历史条数，避免历史很大时统计接口变慢
MAX_SCAN_ROWS = 5000


def _walk(node: Node) -> list[str]:
    """遍历 AST，收集所有运算符的使用记录。

    :returns: 每个元素是一次运算符使用，例如 ``['+', '*', '+']``
    """
    found: list[str] = []

    if isinstance(node, BinaryOpNode):
        found.append(node.op)
        found.extend(_walk(node.left))
        found.extend(_walk(node.right))
    elif isinstance(node, UnaryOpNode):
        # 一元正号不算"运算"，否则 3+2 会被统计成一次加法 + 一次一元正号
        if node.op in ("%",):
            found.append(node.op)
        found.extend(_walk(node.operand))
    else:
        # FactorialNode / FunctionNode / NumberNode / ConstantNode
        for attr in ("operand",):
            child = getattr(node, attr, None)
            if isinstance(child, Node):
                found.extend(_walk(child))
        for child in getattr(node, "args", ()) or ():
            if isinstance(child, Node):
                found.extend(_walk(child))

    return found


class StatisticsService:
    """计算统计服务。"""

    def __init__(self, repository: HistoryRepository | None = None) -> None:
        self._repository = repository or HistoryRepository()

    def overview(self) -> dict[str, Any]:
        """汇总统计数据。

        :returns: 与 ``GET /api/stats`` 契约一致的字典
        """
        today_prefix = datetime.now().strftime("%Y-%m-%d")
        total = self._repository.count_total()

        expressions = self._repository.all_normalized_expressions(MAX_SCAN_ROWS)
        raw_expressions = self._repository.recent_expressions(500)

        operator_counter: Counter[str] = Counter()
        for expression in expressions:
            operator_counter.update(self._count_operators(expression))

        return {
            "totalCount": total,
            "todayCount": self._repository.count_since(f"{today_prefix} 00:00:00"),
            "favoriteCount": self._repository.count_favorite(),
            "scannedCount": len(expressions),
            "operatorUsage": [
                {"operator": op, "label": OPERATOR_DISPLAY.get(op, op), "count": count}
                for op, count in operator_counter.most_common()
            ],
            "topExpressions": [
                {"expression": expression, "count": count}
                for expression, count in Counter(raw_expressions).most_common(5)
            ],
            "recentSevenDays": [
                {"date": day, "count": count}
                for day, count in self._repository.count_by_day(7)
            ],
        }

    @staticmethod
    def _count_operators(expression: str) -> list[str]:
        """解析单个表达式并统计其中的运算符。

        解析失败时返回空列表——历史理论上是能解析成功的表达式，
        这里做防御性处理，保证统计接口不会因为一条脏数据整体 500。
        """
        if not expression:
            return []
        try:
            tree = parse(expression)
        except Exception:  # noqa: BLE001 - 统计是只读的旁路功能，不应影响主流程
            return []
        return _walk(tree)
