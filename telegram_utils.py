"""
Утилиты для работы с Telegram API.
Аналоги Java классов: TelegramMessageService и TelegramBotService (частично)
"""

import logging
from typing import Optional

from telegram import Bot, InputFile
from telegram.error import TelegramError, BadRequest, RetryAfter
from telegram.request import HTTPXRequest

logger = logging.getLogger(__name__)


class TelegramBotError(Exception):
    """Кастомное исключение для ошибок Telegram бота"""
    pass


async def send_text_message(bot: Bot, chat_id: int, text: str,
                            parse_mode: Optional[str] = None) -> bool:
    """
    Отправляет текстовое сообщение в указанный чат.

    Args:
        bot: Экземпляр Telegram бота
        chat_id: ID чата для отправки
        text: Текст сообщения
        parse_mode: Режим парсинга (Markdown, HTML и т.д.)

    Returns:
        True если сообщение отправлено успешно, False в случае ошибки

    Аналог Java метода: TelegramBotService.sendMessage()
    """
    try:
        await bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode=parse_mode,
            disable_web_page_preview=True
        )
        logger.debug(f"✅ Текстовое сообщение отправлено в чат {chat_id}: {text[:50]}...")
        return True

    except TelegramError as e:
        logger.error(f"❌ Ошибка отправки текста в чат {chat_id}: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Неожиданная ошибка при отправке текста в чат {chat_id}: {e}")
        return False


# telegram_utils.py - функция send_gif_message
async def send_gif_message(bot: Bot, chat_id: int, file_id: str,
                           caption: Optional[str] = None,
                           max_retries: int = 3) -> bool:
    """
    Отправляет GIF (анимацию) в указанный чат с повторными попытками.
    """
    for attempt in range(max_retries):
        try:
            await bot.send_animation(
                chat_id=chat_id,
                animation=file_id,
                caption=caption,
                disable_notification=False,
                write_timeout=30,
                read_timeout=30,
                connect_timeout=30
            )
            logger.debug(f"✅ GIF отправлен в чат {chat_id}: file_id={file_id[:20]}...")
            return True

        except TimedOut:
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 5
                logger.warning(f"⏳ Таймаут при отправке GIF в чат {chat_id}, "
                               f"попытка {attempt + 1}/{max_retries}, жду {wait_time} сек")
                await asyncio.sleep(wait_time)
            else:
                logger.error(f"❌ Превышено максимальное количество попыток отправки GIF в чат {chat_id}")
                return False

        except RetryAfter as e:
            wait_time = e.retry_after
            logger.warning(f"⏳ Telegram просит подождать {wait_time} сек перед отправкой в чат {chat_id}")
            await asyncio.sleep(wait_time)

        except BadRequest as e:
            # Проверяем разные типы ошибок BadRequest
            error_msg = str(e).lower()
            if "chat not found" in error_msg or "chat_id" in error_msg:
                logger.error(f"❌ Чат {chat_id} не найден или недоступен")
            else:
                logger.error(f"❌ Ошибка запроса при отправке GIF в чат {chat_id}: {e}")
            return False

        except NetworkError as e:
            logger.error(f"❌ Сетевая ошибка при отправке GIF в чат {chat_id}: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(5)
            else:
                return False

        except Exception as e:
            logger.error(f"❌ Неожиданная ошибка при отправке GIF в чат {chat_id}: {e}")
            return False

    return False

from telegram.error import TimedOut, NetworkError

async def send_gif_with_retry(bot, chat_id, file_id, caption=None, max_retries=3):
    for attempt in range(max_retries):
        try:
            await bot.send_animation(
                chat_id=chat_id,
                animation=file_id,
                caption=caption,
                write_timeout=30  # Можно переопределить для конкретного файла
            )
            return True
        except (TimedOut, NetworkError) as e:
            if attempt == max_retries - 1:
                logger.error(f"Не удалось отправить GIF после {max_retries} попыток: {e}")
                return False
            wait_time = (attempt + 1) * 5  # Экспоненциальная задержка: 5, 10, 15...
            logger.warning(f"Сетевая ошибка, повтор через {wait_time} сек...")
            await asyncio.sleep(wait_time)
        except Exception as e:
            logger.error(f"Другая ошибка при отправке: {e}")
            return False

async def get_bot_info(bot: Bot) -> dict:
    """
    Получает информацию о боте.

    Returns:
        Словарь с информацией о боте или пустой словарь в случае ошибки
    """
    try:
        me = await bot.get_me()
        return {
            'id': me.id,
            'username': me.username,
            'first_name': me.first_name,
            'last_name': me.last_name,
            'is_bot': me.is_bot,
            'can_join_groups': me.can_join_groups,
            'can_read_all_group_messages': me.can_read_all_group_messages,
            'supports_inline_queries': me.supports_inline_queries
        }
    except TelegramError as e:
        logger.error(f"❌ Ошибка получения информации о боте: {e}")
        return {}
    except Exception as e:
        logger.error(f"❌ Неожиданная ошибка при получении информации о боте: {e}")
        return {}


async def send_markdown_message(bot: Bot, chat_id: int, markdown_text: str) -> bool:
    """
    Отправляет сообщение с Markdown разметкой.

    Args:
        bot: Экземпляр Telegram бота
        chat_id: ID чата для отправки
        markdown_text: Текст с Markdown разметкой

    Returns:
        True если сообщение отправлено успешно, False в случае ошибки
    """
    return await send_text_message(bot, chat_id, markdown_text, parse_mode='MarkdownV2')


async def send_html_message(bot: Bot, chat_id: int, html_text: str) -> bool:
    """
    Отправляет сообщение с HTML разметкой.

    Args:
        bot: Экземпляр Telegram бота
        chat_id: ID чата для отправки
        html_text: Текст с HTML разметкой

    Returns:
        True если сообщение отправлено успешно, False в случае ошибки
    """
    return await send_text_message(bot, chat_id, html_text, parse_mode='HTML')


def create_bot_instance(token: str, timeout: int = 30) -> Bot:
    """
    Создает экземпляр бота с настройками.

    Args:
        token: Токен бота от BotFather
        timeout: Таймаут запросов в секундах

    Returns:
        Экземпляр бота
    """
    try:
        # Используем HTTPXRequest для лучшей производительности
        request = HTTPXRequest(
            connection_pool_size=10,
            read_timeout=timeout,
            write_timeout=timeout,
            connect_timeout=timeout
        )

        bot = Bot(
            token=token,
            request=request
        )

        logger.info(f"✅ Экземпляр бота создан с таймаутом {timeout} сек")
        return bot

    except Exception as e:
        logger.error(f"❌ Ошибка создания экземпляра бота: {e}")
        raise TelegramBotError(f"Не удалось создать экземпляр бота: {e}")


async def test_bot_connection(bot: Bot) -> bool:
    """
    Проверяет подключение к Telegram API.

    Args:
        bot: Экземпляр Telegram бота

    Returns:
        True если подключение успешно, False в случае ошибки
    """
    try:
        info = await get_bot_info(bot)
        if info:
            logger.info(f"✅ Бот подключен: @{info.get('username', 'unknown')}")
            return True
        return False
    except Exception as e:
        logger.error(f"❌ Ошибка подключения бота: {e}")
        return False


# Для обратной совместимости с кодом, который может ожидать синхронные функции
class TelegramMessageService:
    """
    Сервис для отправки сообщений (синхронная обертка).
    Аналог Java класса TelegramMessageService.
    """

    def __init__(self, bot: Bot):
        self.bot = bot

    async def send_text_message(self, chat_id: int, text: str) -> bool:
        """Асинхронная отправка текстового сообщения"""
        return await send_text_message(self.bot, chat_id, text)

    async def send_gif_message(self, chat_id: int, file_id: str, caption: str = None) -> bool:
        """Асинхронная отправка GIF"""
        return await send_gif_message(self.bot, chat_id, file_id, caption)

    async def send_markdown(self, chat_id: int, markdown_text: str) -> bool:
        """Асинхронная отправка Markdown сообщения"""
        return await send_markdown_message(self.bot, chat_id, markdown_text)

    async def send_html(self, chat_id: int, html_text: str) -> bool:
        """Асинхронная отправка HTML сообщения"""
        return await send_html_message(self.bot, chat_id, html_text)


import asyncio