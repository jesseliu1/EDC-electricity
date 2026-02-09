"""通用 Pydantic 模式"""

from datetime import datetime

from pydantic import BaseModel, Field


class CurvePoint(BaseModel):
    """曲线数据点"""

    timestamp: int = Field(..., description="时间戳(毫秒)")
    value: float = Field(..., description="数值")


class PaginationParams(BaseModel):
    """分页参数"""

    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页数量")


class PaginatedResponse(BaseModel):
    """分页响应基类"""

    total: int = Field(..., description="总数")
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页数量")
    pages: int = Field(..., description="总页数")


class DateRangeParams(BaseModel):
    """日期范围参数"""

    start_date: datetime | None = Field(default=None, description="开始日期")
    end_date: datetime | None = Field(default=None, description="结束日期")


class MessageResponse(BaseModel):
    """通用消息响应"""

    message: str = Field(..., description="消息内容")
    success: bool = Field(default=True, description="是否成功")


class ErrorResponse(BaseModel):
    """错误响应"""

    detail: str = Field(..., description="错误详情")
    code: str | None = Field(default=None, description="错误代码")
