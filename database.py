import logging
import asyncpg
from typing import Optional
from contextlib import asynccontextmanager

from config import settings

logger = logging.getLogger(__name__)

class Database:
    """
    Класс-обертка над пулом соединений asyncpg.
    Отвечает только за подключение и отключение.
    """
    def __init__(self):
        self._pool: Optional[asyncpg.Pool] = None

    async def connect(self):
        """Инициализация пула"""
        if self._pool:
            return

        logger.info("🔌 Подключение к базе данных...")
        try:
            self._pool = await asyncpg.create_pool(
                #dsn=settings.postgres_url, # Используем property из config.py
                host=settings.postgres_host,
                port=settings.postgres_port,
                user=settings.postgres_user,
                password=settings.postgres_password,
                database=settings.postgres_db,
                min_size=5,
                max_size=20,
                command_timeout=60
            )
            logger.info("✅ Успешное подключение к БД")
        except Exception as e:
            logger.critical(f"❌ Ошибка подключения к БД: {e}")
            raise e

    async def disconnect(self):
        """Закрытие пула"""
        if self._pool:
            await self._pool.close()
            logger.info("💤 Пул подключений закрыт")

    @asynccontextmanager
    async def session(self):
        """
        Контекстный менеджер для получения соединения.
        Использование: async with db.session() as conn:
        """
        if not self._pool:
            await self.connect()

        async with self._pool.acquire() as connection:
            yield connection

# Создаем глобальный экземпляр, который будем импортировать везде
db = Database()