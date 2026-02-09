"""
Основной файл Telegram бота.
"""

import logging
import asyncio  # [cite: 1] Добавляем asyncio для управления ожиданием
from datetime import datetime
from typing import Dict, Optional
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    CallbackContext
)

from config import settings
from repositories import db_connection
from services import subscriber_service, gif_service
from telegram_utils import send_text_message
from scheduler import SimpleScheduler

logger = logging.getLogger(__name__)


class SkufBot:
    """Основной класс Telegram бота"""

    def __init__(self):
        self.application: Optional[Application] = None
        self.upload_modes: Dict[int, int] = {}
        self.scheduler: Optional[SimpleScheduler] = None
        self._stop_event = asyncio.Event()

    async def run(self):
        """Запуск бота - основная точка входа"""
        try:
            # Инициализация
            logger.info("🤖 Инициализация SkufBot...")

            # 👇 2. открываем постоянное соединение для работы бота
            await db_connection.connect()
            logger.info("✅ Подключение к базе данных установлено")

            # 3. Создаем приложение Telegram
            self.application = Application.builder().token(settings.telegram_bot_token).build()
            logger.info("✅ Приложение Telegram создано")

            # 4. Создаем и запускаем планировщик
            self.scheduler = SimpleScheduler(self.application.bot)
            await self.scheduler.start()
            logger.info("✅ Планировщик задач запущен")

            # 5. Регистрируем обработчики
            self._register_handlers()
            logger.info("✅ Обработчики команд зарегистрированы")

            self.application.add_error_handler(self.error_handler)

            # Запуск Polling (как мы исправили в прошлом шаге)
            logger.info("🚀 Запускаю polling (Async Mode)...")

            await self.application.initialize()
            await self.application.start()

            if self.application.updater:
                await self.application.updater.start_polling(
                    drop_pending_updates=True,
                    allowed_updates=Update.ALL_TYPES,
                    poll_interval=1
                )

            logger.info("✅ Бот успешно запущен и слушает обновления")

            await self._stop_event.wait()

        except asyncio.CancelledError:
            logger.info("🛑 Получен сигнал отмены asyncio")
        except Exception as e:
            logger.error(f"💥 Ошибка при запуске бота: {e}")
            raise
        finally:
            await self.shutdown()

    def _register_handlers(self):
        """Регистрация всех обработчиков команд"""
        app = self.application

        # Основные команды
        app.add_handler(CommandHandler("start", self.handle_start))
        app.add_handler(CommandHandler(["test", "t"], self.handle_test))
        app.add_handler(CommandHandler("stop", self.handle_stop))
        app.add_handler(CommandHandler("status", self.handle_status))
        app.add_handler(CommandHandler("help", self.handle_help))

        if settings.debug:
            app.add_handler(CommandHandler("testschedule", self.handle_test_schedule))
            app.add_handler(CommandHandler("stoptestschedule", self.handle_stop_test_schedule))

        # Команды для дней недели (загрузка GIF)
        day_commands = {
            "monday": 1, "mon": 1, "1": 1,
            "tuesday": 2, "tue": 2, "2": 2,
            "wednesday": 3, "wed": 3, "3": 3,
            "thursday": 4, "thu": 4, "4": 4,
            "friday": 5, "fri": 5, "5": 5,
            "saturday": 6, "sat": 6, "6": 6,
            "sunday": 7, "sun": 7, "7": 7,
        }

        for command, day in day_commands.items():
            async def day_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, day=day):
                await self.handle_day_command(update, day)
            app.add_handler(CommandHandler(command, day_handler))

        # Обработчик GIF (анимаций)
        app.add_handler(MessageHandler(filters.ANIMATION, self.handle_gif))

        # Обработчик неизвестных команд
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_unknown))

    async def handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        chat_id = update.effective_chat.id
        try:
            is_new = await subscriber_service.subscribe(chat_id)
            message = "🎉 Добро пожаловать! Чат зарегистрирован." if is_new else "ℹ️ Чат уже зарегистрирован."
            if is_new:
                logger.info(f"✅ Новый чат зарегистрирован: {chat_id}")
            await send_text_message(self.application.bot, chat_id, message)
        except Exception as e:
            logger.error(f"❌ Ошибка /start для чата {chat_id}: {e}")
            await send_text_message(self.application.bot, chat_id, "❌ Произошла ошибка при регистрации")

    async def handle_test(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /test"""
        chat_id = update.effective_chat.id
        try:
            if not context.args:
                await send_text_message(self.application.bot, chat_id, "❌ Укажите день недели (1-7)\nПример: /test 1")
                return
            try:
                day = int(context.args[0])
                if day < 1 or day > 7:
                    await send_text_message(self.application.bot, chat_id, "❌ День недели должен быть от 1 до 7")
                    return
            except ValueError:
                await send_text_message(self.application.bot, chat_id, "❌ День недели должен быть числом")
                return
            if self.scheduler:
                await self.scheduler.send_test_gif(chat_id, day)
        except Exception as e:
            logger.error(f"❌ Ошибка /test для чата {chat_id}: {e}")
            await send_text_message(self.application.bot, chat_id, "❌ Произошла ошибка при тестировании")

    async def handle_day_command(self, update: Update, day: int):
        """Обработчик команд дней недели"""
        chat_id = update.effective_chat.id
        try:
            self.upload_modes[chat_id] = day
            day_names = {1: "Понедельник", 2: "Вторник", 3: "Среда", 4: "Четверг", 5: "Пятница", 6: "Суббота", 7: "Воскресенье"}
            day_name = day_names.get(day, f"День {day}")
            message = f"📤 Режим загрузки установлен: {day_name}\nТеперь отправьте GIF для сохранения.\n/stop для отмены."
            await send_text_message(self.application.bot, chat_id, message)
            logger.info(f"⚙️ Установлен режим загрузки для чата {chat_id}: день {day}")
        except Exception as e:
            logger.error(f"❌ Ошибка установки режима для чата {chat_id}: {e}")
            await send_text_message(self.application.bot, chat_id, "❌ Произошла ошибка")

    async def handle_gif(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик загрузки GIF"""
        chat_id = update.effective_chat.id
        try:
            if chat_id not in self.upload_modes:
                await send_text_message(self.application.bot, chat_id, "❌ Сначала выберите день для загрузки (/monday, /tuesday и т.д.)")
                return
            day = self.upload_modes[chat_id]
            file_id = update.message.animation.file_id
            await gif_service.save_gif(file_id, None, day)
            day_names = {1: "Понедельник", 2: "Вторник", 3: "Среда", 4: "Четверг", 5: "Пятница", 6: "Суббота", 7: "Воскресенье"}
            day_name = day_names.get(day, f"День {day}")
            await send_text_message(self.application.bot, chat_id, f"✅ GIF сохранен для дня: {day_name}")
            logger.info(f"💾 GIF сохранен для чата {chat_id}: день {day}, file_id: {file_id}")
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения GIF для чата {chat_id}: {e}")
            await send_text_message(self.application.bot, chat_id, "❌ Ошибка при сохранении GIF")

    async def handle_stop(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /stop"""
        chat_id = update.effective_chat.id
        try:
            if chat_id in self.upload_modes:
                del self.upload_modes[chat_id]
                await send_text_message(self.application.bot, chat_id, "⏹️ Режим загрузки отключен")
                logger.info(f"⏹️ Режим загрузки отключен для чата {chat_id}")
            else:
                await send_text_message(self.application.bot, chat_id, "ℹ️ Режим загрузки не активен")
        except Exception as e:
            logger.error(f"❌ Ошибка /stop для чата {chat_id}: {e}")
            await send_text_message(self.application.bot, chat_id, "❌ Произошла ошибка")

    async def handle_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /status"""
        chat_id = update.effective_chat.id
        try:
            subscriber_count = len(await subscriber_service.get_all_subscriber_ids())
            gif_counts = {}
            for day in range(1, 8):
                count = await gif_service.count_gifs_by_day(day)
                gif_counts[day] = count
            message = ["🤖 *Статус SkufBot*", f"Подписчиков: {subscriber_count}", "", "📊 *GIF по дням:*"]
            day_names = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
            for i, day in enumerate(range(1, 8)):
                count = gif_counts[day]
                message.append(f"{day_names[i]}: {count} GIF")
            message.extend(["", "⚙️ *Режим загрузки:* " + ("активен" if chat_id in self.upload_modes else "не активен"), "", "_Используйте /help для списка команд_"])
            await send_text_message(self.application.bot, chat_id, "\n".join(message))
        except Exception as e:
            logger.error(f"❌ Ошибка /status для чата {chat_id}: {e}")
            await send_text_message(self.application.bot, chat_id, "❌ Произошла ошибка при получении статуса")

    async def handle_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /help"""
        chat_id = update.effective_chat.id
        help_text = """
        🤖 *Помощь по командам SkufBot*
        
        *Основные команды:*
        /start - Зарегистрировать чат
        /status - Статус бота и статистика
        /help - Эта справка
        
        *Тестирование:*
        /test <1-7> - Отправить тестовый GIF для указанного дня
        /t <1-7> - Краткая версия /test
        
        *Загрузка GIF:*
        /monday или /mon или /1 - Загрузить GIF для понедельника
        /tuesday или /tue или /2 - Для вторника
        /wednesday или /wed или /3 - Для среды
        /thursday или /thu или /4 - Для четверга
        /friday или /fri или /5 - Для пятницы
        /saturday или /sat или /6 - Для субботы
        /sunday или /sun или /7 - Для воскресенья
        /stop - Отменить режим загрузки
        
        *Как использовать:*
        1. Выберите день недели (/monday и т.д.)
        2. Отправьте GIF в чат
        3. Бот сохранит GIF для выбранного дня
        4. GIF будут автоматически отправляться каждый день в 8:30 утра
        
        *Пример:*
        /monday
        [отправляете GIF]
        ✅ GIF сохранен для понедельника
        """
        await send_text_message(self.application.bot, chat_id, help_text)

    async def handle_test_schedule(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /testschedule - тестирование планировщика"""
        chat_id = update.effective_chat.id

        try:
            # Добавляем тестовую задачу с интервалом 10 секунд
            async def test_task():
                timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                await send_text_message(self.application.bot, chat_id,
                                        f"⏱️ Тестовая задача планировщика\n"
                                        f"Время: {timestamp}\n"
                                        f"ID чата: {chat_id}")

            self.scheduler.add_custom_task(10, test_task)

            await send_text_message(self.application.bot, chat_id,
                                    f"✅ Добавлена тестовая задача!\n"
                                    f"• Интервал: 10 секунд\n"
                                    f"• Чат: {chat_id}\n"
                                    f"• Задача будет выполняться в фоне\n"
                                    f"Используйте /stoptestschedule для остановки")

            logger.info(f"✅ Добавлена тестовая задача для чата {chat_id} с интервалом 10 сек")

        except Exception as e:
            logger.error(f"❌ Ошибка /testschedule для чата {chat_id}: {e}")
            await send_text_message(self.application.bot, chat_id,
                                    "❌ Произошла ошибка при добавлении тестовой задачи")

    async def handle_stop_test_schedule(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /stoptestschedule - остановка тестовых задач"""
        chat_id = update.effective_chat.id

        try:
            # Очищаем все задачи планировщика
            import aioschedule as schedule
            schedule.clear()

            # Перезапускаем планировщик
            await self.scheduler.start()

            await send_text_message(self.application.bot, chat_id,
                                    "🛑 Все тестовые задачи остановлены\n"
                                    "✅ Планировщик перезапущен")

            logger.info(f"🛑 Тестовые задачи остановлены для чата {chat_id}")

        except Exception as e:
            logger.error(f"❌ Ошибка /stoptestschedule для чата {chat_id}: {e}")
            await send_text_message(self.application.bot, chat_id,
                                    "❌ Произошла ошибка при остановке тестовых задач")

    async def handle_unknown(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        if update.message and update.message.text:
            text = update.message.text
            if text.startswith('/'):
                logger.info(f"❓ Неизвестная команда от {chat_id}: {text}")
                await send_text_message(self.application.bot, chat_id, "❌ Неизвестная команда.")

    @staticmethod
    async def error_handler(update: Update, context: CallbackContext):
        try:
            logger.error(f"⚠️ Ошибка при обработке обновления: {context.error}")
        except Exception as e:
            logger.error(f"⚠️ Ошибка в обработчике ошибок: {e}")

    async def shutdown(self):
        """Корректное завершение работы"""
        logger.info("🛑 Завершение работы...")

        # Сигнализируем об остановке (если shutdown вызван извне)
        self._stop_event.set()

        # 1. Останавливаем Telegram Application (важно для очистки)
        if self.application:
            if self.application.updater and self.application.updater.running:
                logger.info("🛑 Остановка Updater...")
                await self.application.updater.stop()

            if self.application.running:
                logger.info("🛑 Остановка Application...")
                await self.application.stop()
                await self.application.shutdown()

        # 2. Останавливаем планировщик
        if self.scheduler:
            self.scheduler.stop()
            logger.info("✅ Планировщик остановлен")

        # 3. Отключаемся от базы данных
        await db_connection.disconnect()
        logger.info("✅ Отключение от базы данных")