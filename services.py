"""
Сервисы приложения - бизнес-логика.
Аналоги Java сервисов: SubscriberService и GifService
"""

import logging
from typing import List, Optional

from repositories import chat_repository, gif_repository, ChatRepository, GifRepository
from models import SkufGif

logger = logging.getLogger(__name__)


class SubscriberService:
    """Сервис для работы с подписчиками"""

    def __init__(self, repo: ChatRepository = chat_repository):
        self.repo = repo

    async def subscribe(self, chat_id: int) -> bool:
        """
        Подписывает чат на рассылку.
        Возвращает True, если это новый подписчик.
        """
        return await self.repo.save_new_chat(chat_id)

    async def unsubscribe(self, chat_id: int) -> bool:
        """Отписывает чат от рассылки"""
        return await self.repo.delete_by_id(chat_id)

    async def get_all_subscriber_ids(self) -> List[int]:
        """Возвращает список ID всех подписчиков для рассылки"""
        return await self.repo.get_all_subscriber_ids()

    async def is_subscribed(self, chat_id: int) -> bool:
        """Проверяет статус подписки"""
        return await self.repo.exists_by_id(chat_id)

    async def make_admin(self, chat_id: int) -> bool:
        """Выдает права на загрузку контента"""
        return await self.repo.make_admin(chat_id)

    async def is_admin(self, chat_id: int) -> bool:
        """Проверяет права на загрузку контента"""
        return await self.repo.is_admin(chat_id)


class GifService:
    """Сервис для работы с GIF"""

    def __init__(self, repo: GifRepository = gif_repository):
        self.repo = repo

    async def find_random_gif_by_day(self, day: int) -> Optional[SkufGif]:
        """
        Находит случайный GIF для указанного дня недели.
        Возвращает None если GIF не найден.
        """
        # Валидация дня недели
        if day < 1 or day > 7:
            logger.warning(f"⚠️ Попытка запросить GIF для неверного дня: {day}")
            return None

        return await self.repo.find_random_gif_by_day(day)

    async def exists_by_file_id(self, file_id: str) -> bool:
        """Проверяет существование GIF по file_id"""
        return await self.repo.exists_by_file_id(file_id)

    async def save_gif(self, file_id: str, description: Optional[str] = None, day: Optional[int] = None) -> SkufGif:
        """
        Сохраняет GIF в базу данных.
        Если GIF с таким file_id уже существует, возвращает существующий.
        """
        # Проверяем, существует ли уже такой GIF
        existing = await self.repo.find_by_file_id(file_id)

        if existing:
            logger.info(f"ℹ️ GIF уже существует: {file_id}")
            return existing

        # Создаем новый GIF
        new_gif = SkufGif(
            file_id=file_id,
            description=description,
            day_of_week=day
        )

        # Сохраняем в базу
        saved_gif = await gif_repository.save(new_gif)
        logger.info(f"✅ GIF сохранен для дня {day}: {file_id}")

        return saved_gif

    async def get_gif_info(self, file_id: str) -> Optional[SkufGif]:
        """Получает информацию о GIF по file_id"""
        return await self.repo.find_by_file_id(file_id)

    async def delete_gif(self, file_id: str) -> bool:
        """Удаляет GIF по file_id"""
        return await self.repo.delete(file_id)

    async def count_gifs_by_day(self, day: int) -> int:
        """Считает количество GIF для указанного дня недели"""
        return await self.repo.count_by_day_of_week(day)

# Создаем глобальные экземпляры сервисов
subscriber_service = SubscriberService()
gif_service = GifService()