import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

class Settings(BaseSettings):
    """Конфигурация приложения"""

    # Telegram Bot
    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    telegram_bot_username: str = os.getenv("TELEGRAM_BOT_USERNAME", "")

    # Database
    postgres_user: str = os.getenv("POSTGRES_USER", "postgres")
    postgres_password: str = os.getenv("POSTGRES_PASSWORD", "postgres")
    postgres_db: str = os.getenv("POSTGRES_DB", "skufobot_db")
    postgres_host: str = os.getenv("POSTGRES_HOST", "db")
    postgres_port: int = int(os.getenv("POSTGRES_PORT", "5432"))

    # Таймауты для запросов (в секундах)
    tg_request_connect_timeout: float = 30.0
    tg_request_read_timeout: float = 10.0
    tg_request_write_timeout: float = 20.0
    tg_request_pool_timeout: float = 5.0
    # Таймаут для long-polling (параметр timeout в run_polling)
    tg_polling_timeout: int = 5
    # Интервал между попытками опроса
    tg_polling_interval: int = 1

    # Database URL для SQLAlchemy
    @property
    def database_url(self) -> str:
        return f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"

    # Настройки приложения
    debug: bool = os.getenv("DEBUG", "False").lower() == "true"
    timezone: str = os.getenv("TIMEZONE", "Europe/Moscow")

    # Network settings
    telegram_timeout: int = int(os.getenv("TELEGRAM_TIMEOUT", "30"))
    telegram_connect_timeout: int = int(os.getenv("TELEGRAM_CONNECT_TIMEOUT", "10"))

    # Scheduler settings (добавляем эти поля)
    scheduler_min_interval: int = int(os.getenv("SCHEDULER_MIN_INTERVAL", "10"))
    scheduler_debug_interval: int = int(os.getenv("SCHEDULER_DEBUG_INTERVAL", "30"))

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"  # Игнорировать лишние поля

# Создаем глобальный объект конфигурации
settings = Settings()

# Проверяем обязательные переменные
def validate_config():
    """Проверяет наличие обязательных переменных окружения"""
    if not settings.telegram_bot_token:
        raise ValueError("TELEGRAM_BOT_TOKEN не установлен!")
    if not settings.telegram_bot_username:
        print("⚠️  TELEGRAM_BOT_USERNAME не установлен, бот будет использовать username из getMe")

    print("✅ Конфигурация загружена успешно")
