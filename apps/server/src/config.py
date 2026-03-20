"""配置管理模块"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用配置"""

    # 应用配置
    app_name: str = "ASNS AI老师傅系统"
    debug: bool = False

    # 数据库
    database_url: str = "sqlite+aiosqlite:///./data/asns.db"

    # EDC API
    edc_base_url: str = "http://localhost:8080"
    edc_username: str | None = None
    edc_password: str | None = None
    edc_api_key: str | None = None

    # 默认参数
    default_tolerance_percent: float = 15.0
    enable_mock_dataset: bool = False

    # 报表
    report_generation_hour: int = 2  # 凌晨 2 点生成日报

    model_config = {"env_file": ".env", "env_prefix": "ASNS_"}


settings = Settings()
