"""炉次统一分析状态与原因映射。"""


ANALYSIS_REASON_TO_STATUS: dict[str, str] = {
    "metric_inputs_missing": "waiting",
    "metric_points_insufficient": "waiting",
    "baseline_curve_missing": "waiting",
    "runtime_metric_missing": "waiting",
    "published_baselines_missing": "waiting",
    "point_timestamps_missing": "waiting",
    "metric_scale_invalid": "unsupported",
    "unsupported_metric_kind": "unsupported",
    "analysis_exception": "failed",
    "internal_error": "failed",
}

ANALYSIS_REASON_TO_MESSAGE: dict[str, str] = {
    "metric_inputs_missing": "当前数据尚未准备完成，暂无法计算偏离度",
    "metric_points_insufficient": "当前数据点不足，暂无法计算偏离度",
    "baseline_curve_missing": "黄金基线曲线尚未准备完成，暂无法计算偏离度",
    "runtime_metric_missing": "当前炉次指标曲线尚未准备完成，暂无法计算偏离度",
    "published_baselines_missing": "当前时间点没有可用的已发布黄金基线，暂无法计算偏离度",
    "point_timestamps_missing": "当前曲线时间戳不完整，暂无法计算偏离度",
    "metric_scale_invalid": "该黄金基线包含当前模型不适用的低波动或离散台阶型指标，未计算偏离度",
    "unsupported_metric_kind": "该黄金基线包含当前模型不支持的指标类型，未计算偏离度",
    "analysis_exception": "偏离分析执行失败，请稍后重试",
    "internal_error": "偏离分析执行失败，请稍后重试",
}


def analysis_status_from_reason(reason: str | None) -> str:
    """根据原因码映射正式分析状态。"""

    normalized = str(reason or "").strip()
    if not normalized:
        return "failed"
    return ANALYSIS_REASON_TO_STATUS.get(normalized, "failed")


def analysis_message_from_reason(reason: str | None) -> str:
    """根据原因码生成用户可读消息。"""

    normalized = str(reason or "").strip()
    if not normalized:
        return ANALYSIS_REASON_TO_MESSAGE["internal_error"]
    return ANALYSIS_REASON_TO_MESSAGE.get(normalized, ANALYSIS_REASON_TO_MESSAGE["internal_error"])
