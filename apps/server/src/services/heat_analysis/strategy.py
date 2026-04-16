"""炉次统一分析策略接口与数据结构。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from ...schemas.common import CurvePoint


@dataclass(slots=True)
class HeatAnalysisMetricDefinition:
    """定义指标快照。"""

    item: str
    metric_key: str
    metric_name: str
    unit: str | None
    color: str
    sort_order: int


@dataclass(slots=True)
class HeatAnalysisMetricInput:
    """单指标分析输入。"""

    definition: HeatAnalysisMetricDefinition
    baseline_points: list[CurvePoint]
    current_points: list[CurvePoint]


@dataclass(slots=True)
class HeatAnalysisMetricResult:
    """单指标分析结果。"""

    metric_item: str
    metric_key: str
    metric_name: str
    unit: str | None
    point_count: int
    scale_method: str
    scale_value: float
    mean_abs_residual: float
    max_abs_residual: float
    contribution_mean: float
    contribution_p95: float
    peak_residual_at: int | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric_item": self.metric_item,
            "metric_key": self.metric_key,
            "metric_name": self.metric_name,
            "unit": self.unit,
            "point_count": self.point_count,
            "scale_method": self.scale_method,
            "scale_value": self.scale_value,
            "mean_abs_residual": self.mean_abs_residual,
            "max_abs_residual": self.max_abs_residual,
            "contribution_mean": self.contribution_mean,
            "contribution_p95": self.contribution_p95,
            "peak_residual_at": self.peak_residual_at,
        }


@dataclass(slots=True)
class HeatAnalysisPointRange:
    """连续异常区间。"""

    start: int
    end: int
    score: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "start": self.start,
            "end": self.end,
            "score": self.score,
        }


@dataclass(slots=True)
class HeatAnalysisRequest:
    """统一分析请求。"""

    baseline_id: str
    metric_inputs: list[HeatAnalysisMetricInput]


@dataclass(slots=True)
class HeatAnalysisResult:
    """统一分析结果。"""

    analysis_status: str
    analysis_reason: str | None
    analysis_message: str | None
    deviation_score: float | None
    avg_deviation_score: float | None
    abnormal_duration_minutes: float | None
    derived_status: str | None
    analysis_details: dict[str, Any] = field(default_factory=dict)


class HeatAnalysisStrategy(Protocol):
    """统一分析策略协议。"""

    strategy_key: str

    def analyze(self, request: HeatAnalysisRequest) -> HeatAnalysisResult:
        """返回一套 baseline 级统一分析结果。"""
