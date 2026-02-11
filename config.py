from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    """
    Конфигурация приложения.
    Pydantic автоматически считывает переменные из .env файла или системного окружения.
    """

    # --- Telegram Bot ---
    # Не указываем значение по умолчанию -> поле обязательно.
    # Если токена нет, приложение упадет с понятной ошибкой при запуске.
    telegram_bot_token: str
    telegram_bot_username: Optional[str] = None

    # --- Database ---
    postgres_user: str = "postgres"
    postgres_password: str = "postgres"
    postgres_db: str = "skufobot_db"
    postgres_host: str = "db"  # Хост 'db' для Docker compose, для локалки можно 'localhost'
    postgres_port: int = 5432

    # --- Timeouts & Polling (Float для точности) ---
    tg_request_connect_timeout: float = 30.0
    tg_request_read_timeout: float = 10.0
    tg_request_write_timeout: float = 20.0
    tg_request_pool_timeout: float = 5.0

    tg_polling_timeout: int = 5 # Long-polling обычно в int
    tg_polling_interval: float = 1.0

    # --- Application Settings ---
    debug: bool = False
    timezone_moscow: str = "Europe/Moscow"

    # --- Scheduler Settings ---
    scheduler_min_interval: int = 10
    scheduler_debug_interval: int = 30

    @property
    def database_url(self) -> str:
        """Сборка URL для SQLAlchemy / asyncpg"""
        # Если пароль пустой, не добавляем двоеточие
        auth = f"{self.postgres_user}:{self.postgres_password}" if self.postgres_password else self.postgres_user
        return f"postgresql+asyncpg://{auth}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"

    # Настройки загрузки конфигурации (Modern Pydantic v2 style)
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"  # Игнорировать лишние переменные в .env
    )

# Создаем глобальный объект конфигурации
# При создании Pydantic сам проверит наличие обязательных полей (telegram_bot_token)
try:
    settings = Settings()
    print("✅ Конфигурация загружена успешно")
except Exception as e:
    print("❌ Ошибка загрузки конфигурации. Проверьте файл .env или переменные окружения.")
    print(f"Детали: {e}")
    exit(1)