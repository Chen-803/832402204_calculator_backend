"""进制转换与单位换算接口控制器（扩展功能）。

这两个接口把"换算"这件事也放在后端：前端只提交参数，
换算规则（进制解析、单位系数、温度零点偏移）全部由后端维护，
因此将来增删单位只需要改后端，前端不需要发版。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ..common.responses import ok_response
from ..model.schemas import BaseConvertRequest, UnitConvertRequest
from ..service.conversion_service import (
    convert_base,
    convert_unit,
    list_unit_categories,
)

router = APIRouter(prefix="/convert", tags=["转换"])


@router.post(
    "/base",
    summary="进制转换",
    description="把数值从 ``fromBase`` 进制转换到 ``toBase`` 进制，支持 2..36 进制与小数。",
)
def base_convert(payload: BaseConvertRequest):
    """进制转换。"""
    return ok_response(
        **convert_base(payload.value, payload.from_base, payload.to_base)
    )


@router.get(
    "/units",
    summary="获取单位类别定义",
    description="返回所有单位类别及其单位列表，供前端渲染下拉框。",
)
def units_definition():
    """列出单位类别。"""
    return ok_response(categories=list_unit_categories())


@router.post(
    "/unit",
    summary="单位换算",
    description="在同一个类别内做单位换算，支持长度、质量、面积、体积、时间、速度、温度、数据存储。",
)
def unit_convert(payload: UnitConvertRequest):
    """单位换算。"""
    return ok_response(
        **convert_unit(
            payload.category,
            payload.from_unit,
            payload.to_unit,
            payload.value,
        )
    )
