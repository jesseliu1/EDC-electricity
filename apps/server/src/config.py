"""配置管理模块"""

from pydantic_settings import BaseSettings

DEFAULT_EDC_BASE_URL = ""
DEFAULT_CORS_ORIGINS = ",".join(
    [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ]
)


class Settings(BaseSettings):
    """应用配置"""

    # 应用配置
    app_name: str = "ASNS AI老师傅系统"
    debug: bool = False

    # 数据库
    database_url: str = "sqlite+aiosqlite:///./data/asns.db"

    # EDC API
    edc_base_url: str = DEFAULT_EDC_BASE_URL
    edc_username: str | None = None
    edc_password: str | None = None
    edc_api_key: str | None = None

    # CORS
    cors_allowed_origins: str = DEFAULT_CORS_ORIGINS

    # 默认参数
    default_tolerance_percent: float = 15.0
    enable_mock_dataset: bool = False
    bootstrap_mode: str = "demo"

    # 报表
    report_generation_hour: int = 2  # 凌晨 2 点生成日报

    model_config = {"env_file": ".env", "env_prefix": "ASNS_"}

    @property
    def cors_allowed_origin_list(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.cors_allowed_origins.split(",")
            if origin.strip()
        ]


settings = Settings()
