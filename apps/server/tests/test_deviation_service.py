"""偏差分析服务单元测试。"""

from src.services import DeviationService


def test_calculate_deviation_returns_normal_for_identical_curves() -> None:
    service = DeviationService()
    baseline = [(0.0, 100.0), (1.0, 120.0), (2.0, 110.0)]
    current = [(0.0, 100.0), (1.0, 120.0), (2.0, 110.0)]

    result = service.calculate_deviation(baseline, current, tolerance=5.0)

    assert result["status"] == "normal"
    assert result["max_deviation"] == 0.0
    assert result["avg_deviation"] == 0.0
    assert result["abnormal_ranges"] == []


def test_calculate_deviation_detects_abnormal_ranges() -> None:
    service = DeviationService()
    baseline = [(0.0, 100.0), (1.0, 100.0), (2.0, 100.0), (3.0, 100.0), (4.0, 100.0)]
    current = [(0.0, 100.0), (1.0, 118.0), (2.0, 125.0), (3.0, 100.0), (4.0, 130.0)]

    result = service.calculate_deviation(baseline, current, tolerance=15.0)

    assert result["status"] == "abnormal"
    assert result["max_deviation"] >= 25.0
    assert len(result["abnormal_ranges"]) == 2
    assert result["abnormal_ranges"][0]["start"] == 1.0
    assert result["abnormal_ranges"][0]["end"] == 2.0


def test_align_curves_with_different_lengths() -> None:
    service = DeviationService()
    baseline = [(0.0, 100.0), (1.0, 110.0), (2.0, 120.0), (3.0, 130.0)]
    current = [(0.0, 100.0), (3.0, 130.0)]

    aligned_baseline, aligned_current = service._align_curves(baseline, current)

    assert len(aligned_baseline) == 2
    assert len(aligned_current) == 2
    assert aligned_baseline[0][1] == 100.0
    assert aligned_baseline[1][1] == 130.0
