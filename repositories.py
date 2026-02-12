"""
Репозитории для работы с базой данных.
Аналоги Java репозиториев: ChatRepository и GifRepository
"""

import logging
from typing import List, Optional
from database import db
from models import ChatSubscriber, SkufGif

logger = logging.getLogger(__name__)

class ChatRepository:
    """Репозиторий для работы с подписчиками"""

    def __init__(self, database=db):
        self.db = database

    async def save_new_chat(self, chat_id: int) -> bool:
        """
        Сохраняет новый чат.
        Используем ON CONFLICT для атомарности (быстрее и надежнее, чем SELECT+INSERT).
        """
        async with self.db.session() as conn:
            # Пытаемся вставить. Если есть конфликт (уже существует) — ничего не делаем.
            result = await conn.execute(
                """
                INSERT INTO chat_subscriber (chat_id, registered_at)
                VALUES ($1, NOW())
                ON CONFLICT (chat_id) DO NOTHING
                """,
                chat_id
            )
            # Если вставлена 1 строка -> True (новый), иначе False (старый)
            is_new = result == "INSERT 0 1"

            if is_new:
                logger.info(f"!✅! Новый чат зарегистрирован: {chat_id}")
            return is_new

    async def exists_by_id(self, chat_id: int) -> bool:
        """Проверяет существование чата по ID"""
        async with self.db.session() as conn:
            val = await conn.fetchval(
                "SELECT 1 FROM chat_subscriber WHERE chat_id = $1",
                chat_id
            )
            return val is not None

    async def find_all(self) -> List[ChatSubscriber]:
        """Возвращает список всех подписчиков"""
        async with self.db.session() as conn:
            try:
                rows = await conn.fetch("SELECT * FROM chat_subscriber")
                return [
                    ChatSubscriber(
                        chat_id=row['chat_id'],
                        registered_at=row['registered_at']
                    )
                    for row in rows
                ]
            except Exception as e:
                logger.error(f"❌ Ошибка при получении подписчиков: {e}")
                return []

    async def get_all_subscriber_ids(self) -> List[int]:
        """Возвращает список всех chat_id подписчиков"""
        async with self.db.session() as conn:
            try:
                rows = await conn.fetch("SELECT chat_id FROM chat_subscriber")
                return [row['chat_id'] for row in rows]
            except Exception as e:
                logger.error(f"❌ Ошибка при получении ID подписчиков: {e}")
                return []

    async def delete_by_id(self, chat_id: int) -> bool:
        """Удаляет подписчика по chat_id"""
        async with self.db.session() as conn:
            try:
                result = await conn.execute(
                    "DELETE FROM chat_subscriber WHERE chat_id = $1",
                    chat_id
                )
                # Проверяем, была ли удалена хотя бы одна строка
                deleted = result.split()[-1]
                success = int(deleted) > 0

                if success:
                    logger.info(f"✅ Чат удален: {chat_id}")
                return success

            except Exception as e:
                logger.error(f"❌ Ошибка при удалении чата {chat_id}: {e}")
                return False


class GifRepository:
    """Репозиторий для работы с GIF"""

    def __init__(self, database=db):
        self.db = database

    async def find_random_gif_by_day(self, day: int) -> Optional[SkufGif]:
        """
        Находит случайный GIF для указанного дня недели.
        Использует SQL RANDOM() для получения случайной записи.
        """
        async with self.db.session() as conn:
            try:
                row = await conn.fetchrow(
                    """
                    SELECT * FROM skuf_gif 
                    WHERE day_of_week = $1 
                    ORDER BY RANDOM() 
                    LIMIT 1
                    """,
                    day
                )

                if row:
                    return SkufGif(**row)
                return None

            except Exception as e:
                logger.error(f"❌ Ошибка при поиске GIF для дня {day}: {e}")
                return None

    async def exists_by_file_id(self, file_id: str) -> bool:
        """Проверяет существование GIF по file_id"""
        async with self.db.session() as conn:
            try:
                return await conn.fetchval(
                    "SELECT EXISTS(SELECT 1 FROM skuf_gif WHERE file_id = $1)",
                    file_id
                )
            except Exception as e:
                logger.error(f"❌ Ошибка при проверке GIF {file_id}: {e}")
                return False

    async def find_by_file_id(self, file_id: str) -> Optional[SkufGif]:
        """Находит GIF по file_id"""
        async with self.db.session() as conn:
            try:
                row = await conn.fetchrow(
                    "SELECT * FROM skuf_gif WHERE file_id = $1",
                    file_id
                )

                if row:
                    return SkufGif(**row)
                return None

            except Exception as e:
                logger.error(f"❌ Ошибка при поиске GIF по file_id {file_id}: {e}")
                return None

    async def save(self, gif: SkufGif) -> SkufGif:
        """Сохраняет GIF в базу данных"""
        async with self.db.session() as conn:
            try:
                if gif.id is None:
                    # Вставка новой записи
                    row = await conn.fetchrow(
                        """
                        INSERT INTO skuf_gif (file_id, description, day_of_week) 
                        VALUES ($1, $2, $3) 
                        RETURNING id
                        """, #, file_id, description, day_of_week
                        gif.file_id, gif.description, gif.day_of_week
                    )
                    gif.id = row['id']
                    logger.info(f"✅ GIF сохранен: {gif.file_id}")
                else:
                    # Обновление существующей записи
                    await conn.execute(
                        """
                        UPDATE skuf_gif 
                        SET file_id = $1, description = $2, day_of_week = $3 
                        WHERE id = $4
                        """,
                        gif.file_id, gif.description, gif.day_of_week, gif.id
                    )
                    logger.info(f"✅ GIF обновлен: {gif.file_id}")

                return gif

            except Exception as e:
                logger.error(f"❌ Ошибка при сохранении GIF {gif.file_id}: {e}")
                raise

    async def count_by_day_of_week(self, day: int) -> int:
        """Считает количество GIF для указанного дня недели"""
        async with self.db.session() as conn:
            try:
                return await conn.fetchval(
                    "SELECT COUNT(*) FROM skuf_gif WHERE day_of_week = $1",
                    day
                )
            except Exception as e:
                logger.error(f"❌ Ошибка при подсчете GIF для дня {day}: {e}")
                return 0

    async def delete(self, file_id: str) -> bool:
        """Удаляет GIF по file_id"""
        async with self.db.session() as conn:
            try:
                result = await conn.execute(
                    "DELETE FROM skuf_gif WHERE file_id = $1",
                    file_id
                )
                deleted = result.split()[-1]
                success = int(deleted) > 0

                if success:
                    logger.info(f"✅ GIF удален: {file_id}")
                return success

            except Exception as e:
                logger.error(f"❌ Ошибка при удалении GIF {file_id}: {e}")
                return False


# Создаем глобальные экземпляры для использования в приложении
chat_repository = ChatRepository()
gif_repository = GifRepository()