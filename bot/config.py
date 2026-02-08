import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    # Telegram
    bot_token: str = os.getenv("BOT_TOKEN", "")
    admin_ids: list[int] = field(default_factory=list)

    # OpenAI / ProxyAPI
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_base_url: str = os.getenv("OPENAI_BASE_URL", "https://api.proxyapi.ru/openai/v1")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-5-mini-2025-08-07")

    # Лимиты
    free_daily_limit: int = int(os.getenv("FREE_DAILY_LIMIT", "3"))
    standard_monthly_limit: int = int(os.getenv("STANDARD_MONTHLY_LIMIT", "50"))
    pro_monthly_limit: int = int(os.getenv("PRO_MONTHLY_LIMIT", "999999"))

    # Цены
    price_standard: int = int(os.getenv("PRICE_STANDARD", "490"))
    price_pro: int = int(os.getenv("PRICE_PRO", "990"))

    # Пути
    db_path: str = os.getenv("DB_PATH", "data/bot.db")

    def __post_init__(self):
        raw = os.getenv("ADMIN_IDS", "")
        self.admin_ids = [int(x.strip()) for x in raw.split(",") if x.strip()]


config = Config()
