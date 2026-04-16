"""统一分析策略测试。"""

from datetime import datetime, timedelta

from src.schemas.common import CurvePoint
from src.services.heat_analysis import (
    HeatAnalysisMetricDefinition,
    HeatAnalysisMetricInput,
    HeatAnalysisRequest,
    NormalizedMultiMetricStrategy,
)


def _curve_points(
    start_time: datetime,
    values: list[float],
) -> list[CurvePoint]:
    return [
        CurvePoint(
            timestamp=int((start_time + timedelta(minutes=index * 10)).timestamp() * 1000),
            value=value,
        )
        for index, value in enumerate(values)
    ]


def _metric_definition(
    *,
    item: str,
    metric_key: str,
    metric_name: str,
    unit: str,
    color: str,
    sort_order: int,
) -> HeatAnalysisMetricDefinition:
    return HeatAnalysisMetricDefinition(
        item=item,
        metric_key=metric_key,
        metric_name=metric_name,
        unit=unit,
        color=color,
        sort_order=sort_order,
    )


def test_normalized_multi_metric_strategy_returns_ready_summary() -> None:
    strategy = NormalizedMultiMetricStrategy(point_score_threshold=2.0, heat_score_percentile=95.0)
    start_time = datetime(2026, 4, 9, 8, 0, 0)
    request = HeatAnalysisRequest(
        baseline_id="def-001:001",
        metric_inputs=[
            HeatAnalysisMetricInput(
                definition=_metric_definition(
                    item="001",
                    metric_key="power",
                    metric_name="总有功功率",
                    unit="kW",
                    color="#409EFF",
                    sort_order=1,
                ),
                baseline_points=_curve_points(start_time, [410.0, 420.0, 432.0, 445.0]),
                current_points=_curve_points(start_time, [455.0, 468.0, 486.0, 501.0]),
            ),
            HeatAnalysisMetricInput(
                definition=_metric_definition(
                    item="002",
                    metric_key="voltage",
                    metric_name="A相电压",
                    unit="V",
                    color="#67C23A",
                    sort_order=2,
                ),
                baseline_points=_curve_points(start_time, [220.0, 222.0, 225.0, 227.0]),
                current_points=_curve_points(start_time, [229.0, 232.0, 236.0, 239.0]),
            ),
        ],
    )

    result = strategy.analyze(request)

    assert result.analysis_status == "ready"
    assert result.deviation_score is not None
    assert result.avg_deviation_score is not None
    assert result.abnormal_duration_minutes is not None
    assert result.derived_status == "abnormal"
    assert result.analysis_details["summary_method"] == "normalized_multi_metric_v1"
    assert result.analysis_details["summary"]["deviation_score"] == result.deviation_score
    assert len(result.analysis_details["metric_results"]) == 2
    assert result.analysis_details["metric_results"][0]["metric_key"] == "power"
    assert result.analysis_details["abnormal_ranges"]


def test_normalized_multi_metric_strategy_returns_waiting_when_metric_inputs_missing() -> None:
    strategy = NormalizedMultiMetricStrategy()

    result = strategy.analyze(
        HeatAnalysisRequest(
            baseline_id="def-001:001",
            metric_inputs=[],
        )
    )

    assert result.analysis_status == "waiting"
    assert result.analysis_reason == "metric_inputs_missing"
    assert result.analysis_message == "当前数据尚未准备完成，暂无法计算偏离度"
    assert result.deviation_score is None
    assert result.avg_deviation_score is None
    assert result.abnormal_duration_minutes is None
    assert result.analysis_details["reason"] == "metric_inputs_missing"


def test_normalized_multi_metric_strategy_returns_unsupported_when_scale_invalid() -> None:
    strategy = NormalizedMultiMetricStrategy()
    start_time = datetime(2026, 4, 9, 8, 0, 0)

    result = strategy.analyze(
        HeatAnalysisRequest(
            baseline_id="def-001:001",
            metric_inputs=[
                HeatAnalysisMetricInput(
                    definition=_metric_definition(
                        item="001",
                        metric_key="power",
                        metric_name="总有功功率",
                        unit="kW",
                        color="#409EFF",
                        sort_order=1,
                    ),
                    baseline_points=_curve_points(start_time, [410.0, 410.0, 410.0, 410.0]),
                    current_points=_curve_points(start_time, [420.0, 421.0, 422.0, 423.0]),
                )
            ],
        )
    )

    assert result.analysis_status == "unsupported"
    assert result.analysis_reason == "metric_scale_invalid"
    assert result.analysis_message == "该黄金基线包含当前模型不适用的低波动或离散台阶型指标，未计算偏离度"
    assert result.analysis_details["reason"] == "metric_scale_invalid"
    assert result.analysis_details["metric_key"] == "power"
