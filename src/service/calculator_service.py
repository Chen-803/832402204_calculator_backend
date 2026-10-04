"""计算业务服务层。

职责：把"计算"与"落库"编排在一起，对外提供一个原子化的用例：
**校验输入 -> 解析表达式 -> 计算 -> （可选）写入历史 -> 返回结果**。

控制器（controller）只负责解析 HTTP 请求并调用这里，
不直接接触表达式解析器，也不直接写 SQL，
从而保证"接口层 / 业务层 / 数据层"职责清晰、可分别测试。
"""

import logging
from typing import Optional

from ..calculator import CalculationOutcome, calculate_expression
from ..calculator.exceptions import CalculatorError
from ..model.calculation_record import CalculationRecord, insert_record

__all__ = ["calculate", "CalculationResult"]

_LOGGER = logging.getLogger(__name__)


class CalculationResult:
    """计算用例的返回对象。

    Attributes:
        outcome: 纯计算结果（表达式、Decimal 值、展示文本）。
        record: 落库后的历史记录；``persist=False`` 时为 None。
    """

    def __init__(self, outcome: CalculationOutcome, record: Optional[CalculationRecord]) -> None:
        self.outcome = outcome
        self.record = record

    def to_dict(self) -> dict:
        """转换为 ``/api/calculate`` 的响应数据。"""
        return {
            "expression": self.outcome.expression,
            "raw_expression": self.outcome.raw_expression,
            "result": self.outcome.json_number,
            "display_result": self.outcome.display,
            "record": self.record.to_dict() if self.record else None,
        }


def calculate(expression: str, persist: bool = True) -> CalculationResult:
    """执行一次计算。

    Args:
        expression: 用户输入的表达式（可以包含 ``×`` ``÷`` ``π`` 等符号）。
        persist: 是否把成功的结果写入历史表。
            前端输入过程中的"实时预览"会传 ``False``，避免污染历史记录。

    Returns:
        :class:`CalculationResult`。

    Raises:
        CalculatorError: 输入非法、语法错误、除零、定义域错误或结果溢出。
    """
    try:
        outcome = calculate_expression(expression)
    except CalculatorError as exc:
        # 把原始输入回填到错误响应里，前端无需自己拼装错误上下文。
        exc.attach_context(expression=expression)
        raise

    record = None
    if persist:
        # 只保存"计算成功"的记录；失败请求不写入历史，
        # 这样历史表始终是"可信的计算结果档案"。
        record = insert_record(outcome.expression, outcome.display)
        _LOGGER.info(
            "计算成功：%s = %s (记录 ID=%s)", outcome.expression, outcome.display, record.id
        )
    else:
        _LOGGER.info("试算（不落库）：%s = %s", outcome.expression, outcome.display)

    return CalculationResult(outcome, record)
