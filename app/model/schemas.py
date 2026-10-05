"""API 请求模型（Pydantic Schema）。

这一层只负责**请求体结构校验**：字段缺失、类型不对、长度越界、枚举值非法
都会在这里被拦下，并转换成统一的 422 响应（见 ``app.common.exception_handlers``）。

注意区分两类错误：

- **结构错误**（缺字段、类型错）→ 422，错误码 42201，由本层负责；
- **语义错误**（表达式非法、除零）→ 400，由计算器核心负责。

把两者分开，前端就能区分"我请求发错了"和"用户表达式写错了"。
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from ..calculator.tokenizer import MAX_EXPRESSION_LENGTH


class CalculateRequest(BaseModel):
    """``POST /api/calculate`` 请求体。"""

    expression: str = Field(
        ...,
        description="待计算的表达式原文，例如 (1+2)*3",
        max_length=MAX_EXPRESSION_LENGTH,
        examples=["(1+2)*3"],
    )
    angle_mode: str = Field(
        default="rad",
        alias="angleMode",
        description="角度制：rad（弧度）或 deg（角度），仅影响三角函数",
    )

    model_config = {
        "populate_by_name": True,
        "json_schema_extra": {"example": {"expression": "(1+2)*3", "angleMode": "deg"}},
    }

    @field_validator("angle_mode")
    @classmethod
    def _check_angle_mode(cls, value: str) -> str:
        normalized = (value or "rad").strip().lower()
        if normalized not in ("rad", "deg"):
            raise ValueError("angleMode 只能是 rad 或 deg")
        return normalized


class FavoriteRequest(BaseModel):
    """``PATCH /api/history/{id}/favorite`` 请求体。"""

    favorite: bool | None = Field(
        default=None,
        description="目标收藏状态；省略表示取反",
    )


class BaseConvertRequest(BaseModel):
    """``POST /api/convert/base`` 请求体。"""

    value: str = Field(..., description="待转换的数值文本，例如 255 或 -1F.8", max_length=64)
    from_base: int = Field(..., alias="fromBase", ge=2, le=36, description="源进制 2..36")
    to_base: int = Field(..., alias="toBase", ge=2, le=36, description="目标进制 2..36")

    model_config = {"populate_by_name": True}

    @field_validator("value")
    @classmethod
    def _check_value(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("value 不能为空")
        return value.strip()


class UnitConvertRequest(BaseModel):
    """``POST /api/convert/unit`` 请求体。"""

    category: str = Field(..., description="单位类别 key，例如 length", min_length=1, max_length=32)
    from_unit: str = Field(..., alias="from", description="源单位 key，例如 m")
    to_unit: str = Field(..., alias="to", description="目标单位 key，例如 km")
    value: float = Field(..., description="待换算的数值")

    model_config = {"populate_by_name": True}

    @field_validator("value")
    @classmethod
    def _check_finite(cls, value: float) -> float:
        if value != value or value in (float("inf"), float("-inf")):
            raise ValueError("value 必须是有限数值")
        return value


class ApiEnvelope(BaseModel):
    """统一响应信封的文档模型（仅用于生成 OpenAPI 文档，实际由 ``api_response`` 构造）。"""

    success: bool
    code: int
    message: str
    data: dict[str, Any] | None = None

    @model_validator(mode="after")
    def _noop(self) -> "ApiEnvelope":  # pragma: no cover - 占位校验器
        return self
