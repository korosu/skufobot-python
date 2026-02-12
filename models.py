"""
Модели данных для приложения.
Аналоги Java классов: ChatSubscriber и SkufGif
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import pytz

TIMEZONE = pytz.timezone("Europe/Moscow")

@dataclass
class ChatSubscriber:
    """
    Модель подписчика чата.
    Используем dataclass для автоматической генерации методов
    """
    chat_id: int
    registered_at: Optional[datetime] = None

    def __post_init__(self):
        """Инициализация после создания объекта"""
        if self.registered_at is None:
            self.registered_at = datetime.now(TIMEZONE)


@dataclass
class SkufGif:
    """
    Модель GIF (аналог Java класса SkufGif)
    """
    id: Optional[int] = None
    file_id: Optional[str] = None
    description: Optional[str] = None
    day_of_week: Optional[int] = None

    def __post_init__(self):
        """Валидация дня недели"""
        if self.day_of_week is not None and (self.day_of_week < 1 or self.day_of_week > 7):
            raise ValueError("День недели должен быть от 1 до 7")