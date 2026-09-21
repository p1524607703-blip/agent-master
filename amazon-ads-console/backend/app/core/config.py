from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    app_name: str = "Amazon Ads Console API"
    api_prefix: str = "/api"

    # 应用库：iam 身份与角色、会话、CPO 应用层表
    database_url: str = "postgresql+asyncpg://ads:ads@localhost:5432/amazon_ads"

    # 数据仓库：广告活动事实表（core.report_*_daily）。
    # PostgreSQL 不支持跨库 JOIN，所以业务读走独立连接；为空时回落到 database_url（本地开发）。
    # 注：venv 为 Python 3.9，这里用 Optional 而非 `str | None`（PEP 604 需 3.10+）。
    rds_database_url: Optional[str] = None

    auth_session_hours: int = 12
    operator_warmup_enabled: bool = True
    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")

    @property
    def data_database_url(self) -> str:
        """业务查询（数据仓库）用的 DSN。"""
        return self.rds_database_url or self.database_url


settings = Settings()
