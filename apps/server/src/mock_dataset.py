from fastapi import HTTPException

from .config import settings


def is_mock_dataset_enabled() -> bool:
    return bool(settings.enable_mock_dataset)


def ensure_mock_dataset_enabled(detail: str) -> None:
    if not is_mock_dataset_enabled():
        raise HTTPException(status_code=503, detail=detail)
