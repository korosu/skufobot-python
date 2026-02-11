"""
Утилиты для работы с Telegram API.
"""

from telegram.error import TelegramError, BadRequest, RetryAfter
from telegram.request import HTTPXRequest
import asyncio
import logging
from typing import Optional
from telegram import Bot, error
from telegram.constants import ParseMode
from telegram.error import TimedOut, NetworkError

from config import settings
logger = logging.getLogger(__name__)


class TelegramBotError(Exception):
    """Кастомное исключение для ошибок Telegram бота"""
    pass

async def create_bot() -> Bot:
    """
    Создает и настраивает экземпляр бота.
    """
    request = HTTPXRequest(
        connection_pool_size=8,
        connect_timeout=settings.tg_request_connect_timeout,
        read_timeout=settings.tg_request_read_timeout,
        write_timeout=settings.tg_request_write_timeout,
        pool_timeout=settings.tg_request_pool_timeout
    )

    bot = Bot(token=settings.telegram_bot_token, request=request)

    # Проверка соединения при старте
    try:
        me = await bot.get_me()
        logger.info(f"🤖 Бот инициализирован: @{me.username} (ID: {me.id})")
    except error.TelegramError as e:
        logger.critical(f"❌ Ошибка авторизации бота. Проверьте токен! Детали: {e}")
        raise e

    return bot

async def send_text(
        bot: Bot,
        chat_id: int,
        text: str,
        parse_mode: Optional[str] = None,
        disable_preview: bool = True) -> bool:
    """
    Отправляет текстовое сообщение в указанный чат.

    Args:
    bot: Экземпляр Telegram бота
    chat_id: ID чата для отправки
    text: Текст сообщения
    parse_mode: Режим парсинга (Markdown, HTML и т.д.)

    Returns:
    True если сообщение отправлено успешно, False в случае ошибки

    """
    try:
        await bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode=parse_mode,
            disable_web_page_preview=disable_preview
        )
        logger.debug(f"✅ Текстовое сообщение отправлено в чат {chat_id}: {text[:50]}...")
        return True
    except error.Forbidden:
        logger.warning(f"🚫 Пользователь {chat_id} заблокировал бота")
        return False
    except error.TelegramError as e:
        logger.error(f"❌ Ошибка отправки текста в {chat_id}: {e}")
        return False

async def send_gif(
        bot: Bot,
        chat_id: int,
        file_id: str,
        caption: Optional[str] = None,
        max_retries: int = 3) -> bool:
    """
    Отправляет GIF с механизмом повторных попыток (Retry).
    """
    for attempt in range(1, max_retries + 1):
        try:
            await bot.send_animation(
                chat_id=chat_id,
                animation=file_id,
                caption=caption,
                parse_mode=ParseMode.HTML,
                write_timeout=settings.tg_request_write_timeout
            )
            logger.info(f"📤 GIF отправлен в {chat_id}")
            return True

        # --- Фатальные ошибки (не имеет смысла повторять) ---
        except error.BadRequest as e:
            if "chat not found" in str(e).lower():
                logger.error(f"❌ Чат {chat_id} не существует")
            else:
                logger.error(f"❌ Ошибка запроса (BadRequest) для {chat_id}: {e}")
            return False

        except error.Forbidden:
            logger.warning(f"🚫 Бот заблокирован пользователем {chat_id}")
            return False

        # --- Временные ошибки (можно повторить) ---
        except (error.TimedOut, error.NetworkError) as e:
            logger.warning(f"⏳ Попытка {attempt}/{max_retries} не удалась (сеть): {e}")
            if attempt < max_retries:
                sleep_time = attempt * 2  # 2сек, 4сек, 6сек...
                await asyncio.sleep(sleep_time)
            else:
                logger.error(f"❌ Не удалось отправить GIF в {chat_id} после {max_retries} попыток")

        except error.RetryAfter as e:
            logger.warning(f"🛑 Telegram Rate Limit. Ждем {e.retry_after} сек.")
            await asyncio.sleep(e.retry_after)
            # В данном случае можно попробовать еще раз на следующей итерации цикла

        except Exception as e:
            logger.error(f"❌ Неизвестная ошибка при отправке GIF в {chat_id}: {e}")
            return False

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
    return await send_text(bot, chat_id, markdown_text, ParseMode.MARKDOWN)


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
    return await send_text(bot, chat_id, html_text, ParseMode.HTML)


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
