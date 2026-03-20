from fastapi import HTTPException

from .request_mode import is_showtime_mode


def is_mock_dataset_enabled() -> bool:
    """仅在显式 showtime 请求中开放 mock 数据集。"""
    return is_showtime_mode()


def ensure_mock_dataset_enabled(detail: str) -> None:
    if not is_mock_dataset_enabled():
        raise HTTPException(status_code=503, detail=detail)
