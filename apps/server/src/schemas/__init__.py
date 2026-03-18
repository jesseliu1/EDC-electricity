"""数据模式模块

导出所有 Pydantic 模式供其他模块使用。
"""

from .baseline import (
    BaselineCreate,
    BaselineListResponse,
    BaselinePreviewResponse,
    BaselineResponse,
    BaselineSummary,
    BaselineUpdate,
    BaselineWithCurve,
    CurveData,
)
from .common import (
    CurvePoint,
    DateRangeParams,
    ErrorResponse,
    MessageResponse,
    PaginatedResponse,
    PaginationParams,
)
from .dashboard import (
    DashboardStats,
    RealtimeCurveData,
    RecentHeat,
    RecentHeatsResponse,
)
from .heat import (
    BaselineCompareItem,
    CuttingTimelineEvent,
    CuttingTimelineResponse,
    DeviationRange,
    HeatAnalyzeRequest,
    HeatAnalyzeResponse,
    HeatCompareResponse,
    HeatListResponse,
    HeatResponse,
    HeatResumeCuttingRequest,
    HeatUpdate,
    HeatWithCurve,
    MetricCompareSeries,
)
from .setting import (
    BaselineLengthScopeSettingRequest,
    CuttingSettingRequest,
    EDCConnectionRequest,
    HostChannelCollectionResponse,
    HostChannelCollectionUpdateRequest,
    HostChannelItem,
    ReportSettingRequest,
    SettingItem,
    SettingsResponse,
    SettingsUpdateRequest,
    ToleranceSettingRequest,
)
from .task import (
    TaskCompleteRequest,
    TaskCreate,
    TaskDetailResponse,
    TaskListResponse,
    TaskResponse,
    TaskUpdate,
    TaskWithHeat,
)

__all__ = [
    # Common
    "CurvePoint",
    "PaginationParams",
    "PaginatedResponse",
    "DateRangeParams",
    "MessageResponse",
    "ErrorResponse",
    # Baseline
    "BaselineCreate",
    "BaselineUpdate",
    "BaselineResponse",
    "BaselineWithCurve",
    "BaselineListResponse",
    "BaselinePreviewResponse",
    "BaselineSummary",
    "CurveData",
    # Heat
    "DeviationRange",
    "MetricCompareSeries",
    "BaselineCompareItem",
    "CuttingTimelineEvent",
    "CuttingTimelineResponse",
    "HeatResponse",
    "HeatWithCurve",
    "HeatCompareResponse",
    "HeatListResponse",
    "HeatResumeCuttingRequest",
    "HeatAnalyzeRequest",
    "HeatAnalyzeResponse",
    "HeatUpdate",
    # Task
    "TaskCreate",
    "TaskUpdate",
    "TaskResponse",
    "TaskWithHeat",
    "TaskListResponse",
    "TaskDetailResponse",
    "TaskCompleteRequest",
    # Setting
    "SettingItem",
    "SettingsResponse",
    "HostChannelItem",
    "HostChannelCollectionResponse",
    "HostChannelCollectionUpdateRequest",
    "SettingsUpdateRequest",
    "ToleranceSettingRequest",
    "BaselineLengthScopeSettingRequest",
    "CuttingSettingRequest",
    "EDCConnectionRequest",
    "ReportSettingRequest",
    # Dashboard
    "DashboardStats",
    "RealtimeCurveData",
    "RecentHeat",
    "RecentHeatsResponse",
]
