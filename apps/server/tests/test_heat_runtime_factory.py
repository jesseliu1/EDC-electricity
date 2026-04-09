"""HeatRuntimeFactory 单测。"""

from datetime import datetime

from src.schemas.common import CurvePoint
from src.services.heat_cutting_service import HeatCuttingConfig
from src.services.heat_deviation_analysis_service import BaselineCurvePayload
from src.services.heat_runtime_factory import HeatRuntimeFactory


def test_factory_builds_birth_snapshot_from_candidate_and_templates() -> None:
    factory = HeatRuntimeFactory()
    candidate = {
        "id": "runtime-heat-001",
        "furnace_id": "2349:199",
        "_live_context_key": "2349:199",
        "_live_cutting_mode": "signal_inference",
        "_live_expected_duration_minutes": 30,
        "_live_plant_timezone": "Asia/Shanghai",
        "baseline_id": "def-001:001",
        "baseline_bindings": [
            {
                "heat_id": "runtime-heat-001",
                "baseline_id": "def-001:001",
                "baseline_definition_id": "def-001",
                "baseline_item": "001",
                "is_primary": True,
                "baseline_effective_from": datetime(2026, 3, 19, 8, 0),
                "tolerance_percent": 12.0,
                "analysis_status": "ready",
                "deviation_score": 1.5,
                "avg_deviation_score": 0.8,
                "analysis_details_json": None,
                "abnormal_duration_minutes": 0.0,
            }
        ],
    }
    applicable_baselines = [
        {
            "id": "def-001:001",
            "definition_id": "def-001",
            "item": "001",
        }
    ]
    definition_templates = [
        {
            "item": "001",
            "metric_key": "power",
            "metric_name": "总有功功率",
            "unit": "kW",
            "color": "#409EFF",
            "sort_order": 1,
            "edc_channel_id": "2349-199",
            "source_channel_name": "总有功功率",
            "source_channel_label": "测试设备 / 总有功功率 / kW",
            "enabled": True,
        },
        {
            "item": "003",
            "metric_key": "temperature",
            "metric_name": "熔炼温度",
            "unit": "℃",
            "color": "#E6A23C",
            "sort_order": 3,
            "edc_channel_id": "2054-128",
            "source_channel_name": "热电偶温度采集通道",
            "source_channel_label": "测试设备 / 熔炼温度 / ℃",
            "enabled": True,
        }
    ]
    baseline_curve_payloads = {
        "def-001:001": BaselineCurvePayload(
            curves_by_metric={
                "power": [CurvePoint(timestamp=1000, value=410.0)],
                "voltage": [CurvePoint(timestamp=1000, value=220.0)],
                "temperature": [CurvePoint(timestamp=1000, value=1560.0)],
            },
            curve_source="baseline_metric_series",
        )
    }
    cutting_config = HeatCuttingConfig(
        time_tolerance_percent=12.0,
        major_issue_duration_minutes=5,
        plant_timezone="Asia/Shanghai",
        work_start_time="08:00",
        work_end_time="20:00",
        break_periods=("12:00-13:00",),
        cutting_mode="signal_inference",
        fixed_interval_minutes=None,
    )

    snapshot = factory.build_birth_snapshot(
        candidate,
        applicable_baselines=applicable_baselines,
        definition_templates=definition_templates,
        baseline_curve_payloads=baseline_curve_payloads,
        cutting_config=cutting_config,
    )

    assert snapshot.birth_context["primary_baseline_id"] == "def-001:001"
    assert snapshot.birth_context["expected_duration_minutes"] == 30
    assert snapshot.birth_context["cutting_mode"] == "signal_inference"
    assert snapshot.birth_context["cutting_config_snapshot"]["plant_timezone"] == "Asia/Shanghai"
    assert snapshot.definition_metric_snapshots[0]["metric_key"] == "power"
    assert snapshot.baseline_curve_snapshots[0]["curve_source"] == "baseline_metric_series"
    assert snapshot.baseline_curve_snapshots[0]["points"][0].value == 410.0
    assert any(
        entry["metric_key"] == "temperature" and entry["points"][0].value == 1560.0
        for entry in snapshot.baseline_curve_snapshots
    )


def test_factory_resolves_frozen_analysis_inputs_from_birth_context() -> None:
    factory = HeatRuntimeFactory()
    candidate = {
        "id": "runtime-heat-001",
        "birth_context": {
            "heat_id": "runtime-heat-001",
            "channel_key": "2349:199",
            "cutting_mode": "signal_inference",
            "expected_duration_minutes": 30,
            "plant_timezone": "Asia/Shanghai",
            "primary_baseline_id": "def-001:001",
            "baseline_bindings_snapshot": [
                {
                    "baseline_id": "def-001:001",
                    "baseline_definition_id": "def-001",
                    "baseline_item": "001",
                    "is_primary": True,
                    "baseline_effective_from": datetime(2026, 3, 19, 8, 0),
                    "tolerance_percent": 12.0,
                }
            ],
            "definition_metric_snapshots": [
                {
                    "item": "001",
                    "metric_key": "power",
                    "metric_name": "总有功功率",
                    "unit": "kW",
                    "color": "#409EFF",
                    "sort_order": 1,
                    "edc_channel_id": "2349-199",
                    "source_channel_name": "总有功功率",
                    "source_channel_label": "测试设备 / 总有功功率 / kW",
                    "enabled": True,
                }
            ],
            "baseline_curve_snapshots": [
                {
                    "baseline_id": "def-001:001",
                    "metric_key": "power",
                    "curve_source": "baseline_metric_series",
                    "points": [{"timestamp": 1000, "value": 410.0}],
                },
                {
                    "baseline_id": "def-001:001",
                    "metric_key": "temperature",
                    "curve_source": "baseline_metric_series",
                    "points": [{"timestamp": 1000, "value": 1560.0}],
                }
            ],
        }
    }

    inputs = factory.resolve_frozen_analysis_inputs(candidate)

    assert inputs is not None
    assert inputs.applicable_baselines[0]["definition_id"] == "def-001"
    assert inputs.applicable_baselines[0]["is_default"] is True
    assert inputs.definition_metric_snapshots[0]["metric_key"] == "power"
    assert inputs.baseline_curve_payloads["def-001:001"].power_curve[0].value == 410.0
    assert inputs.baseline_curve_payloads["def-001:001"].curves_by_metric["temperature"][0].value == 1560.0
