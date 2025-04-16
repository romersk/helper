import logging
import os
import sys
import asyncio
import re
from datetime import datetime
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)
from telegram.request import HTTPXRequest

# Настройка логгирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

WAITING_FOR_DATA = 1

async def post_init(application: Application):
    """Проверка подключения к Telegram API с таймаутом"""
    try:
        await asyncio.wait_for(application.bot.get_me(), timeout=30)
        logger.info("Успешное подключение к Telegram API")
    except Exception as e:
        logger.error(f"FATAL: Ошибка подключения: {e}")
        sys.exit(1)

def parse_time(ts: str) -> datetime:
    """Парсит только формат '16 апр., 16:15'"""
    ts = ts.strip().lower()
    pattern = r'^(\d{1,2}) (\w{3})\., (\d{1,2}:\d{2})$'
    match = re.match(pattern, ts)
    if not match:
        raise ValueError(
            f"❌ Неверный формат: `{ts}`\n"
            "Ожидается только формат: 16 апр., 16:15"
        )
    
    day, month_str, time_part = match.groups()

    month_map = {
        'янв': '01', 'фев': '02', 'мар': '03',
        'апр': '04', 'май': '05', 'июн': '06',
        'июл': '07', 'авг': '08', 'сен': '09',
        'окт': '10', 'ноя': '11', 'дек': '12'
    }

    month = month_map.get(month_str)
    if not month:
        raise ValueError(f"❌ Неверный месяц: {month_str}")

    day = day.zfill(2)
    current_year = datetime.now().year
    datetime_str = f"{current_year}-{month}-{day} {time_part}"

    try:
        return datetime.strptime(datetime_str, "%Y-%m-%d %H:%M")
    except Exception:
        raise ValueError(
            f"❌ Не удалось разобрать дату: `{ts}`"
        )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚕 <b>Анализатор поездок</b>\n\n"
        "Присылайте данные в формате:\n\n"
        "<b>Фамилия Имя Отчество</b>\n"
        "<i>Дата и время</i>\n\n"
        "Допустимый формат:\n"
        "• 16 апр., 16:15\n\n"
        "Завершить ввод — /done\n"
        "Отмена — /cancel",
        parse_mode="HTML"
    )
    context.user_data["collected_data"] = []
    return WAITING_FOR_DATA

async def collect_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["collected_data"].append(update.message.text)
    await update.message.reply_text(
        "✅ Данные получены. Можно присылать следующую часть или /done для завершения",
        parse_mode="HTML"
    )
    return WAITING_FOR_DATA

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "❌ Операция отменена. Все данные удалены.",
        parse_mode="HTML"
    )
    context.user_data.clear()
    return ConversationHandler.END

async def process_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        full_text = "\n".join(context.user_data["collected_data"])
        lines = [line.strip() for line in full_text.split("\n") if line.strip()]

        if len(lines) % 2 != 0:
            await update.message.reply_text(
                "⚠️ <b>Ошибка:</b> Непарное количество строк. Каждому ФИО должна соответствовать дата.",
                parse_mode="HTML"
            )
            return ConversationHandler.END

        drivers = {}
        for i in range(0, len(lines), 2):
            name = lines[i]
            time_str = lines[i + 1]
            try:
                time = parse_time(time_str)
                if name not in drivers:
                    drivers[name] = {"first": time, "last": time}
                else:
                    drivers[name]["first"] = min(drivers[name]["first"], time)
                    drivers[name]["last"] = max(drivers[name]["last"], time)
            except ValueError as e:
                await update.message.reply_text(str(e))
                return ConversationHandler.END

        if not drivers:
            await update.message.reply_text("ℹ️ Нет данных для анализа")
            return ConversationHandler.END

        report = ["<b>📊 Результаты анализа</b>\n"]
        for name, times in sorted(drivers.items(), key=lambda x: x[1]["first"]):
            report.append(
                f"\n👤 <b>{name}</b>\n"
                f"• Первая поездка: {times['first'].strftime('%d.%m %H:%M')}\n"
                f"• Последняя поездка: {times['last'].strftime('%d.%m %H:%M')}"
            )

        message = "\n".join(report)
        for i in range(0, len(message), 4096):
            await update.message.reply_text(
                message[i:i + 4096],
                parse_mode="HTML"
            )

    except Exception as e:
        logger.exception("Ошибка обработки данных")
        await update.message.reply_text(
            "⚠️ <b>Ошибка обработки:</b> Попробуйте отправить данные снова.",
            parse_mode="HTML"
        )
    finally:
        context.user_data.clear()

    return ConversationHandler.END

async def main():
    try:
        token = os.getenv("BOT_TOKEN")
        if not token:
            raise ValueError("Не задан BOT_TOKEN в переменных окружения")

        request = HTTPXRequest(connect_timeout=30, read_timeout=30)
        application = (
            Application.builder()
            .token(token)
            .request(request)
            .post_init(post_init)
            .build()
        )

        conv_handler = ConversationHandler(
            entry_points=[CommandHandler("start", start)],
            states={
                WAITING_FOR_DATA: [
                    CommandHandler("done", process_data),
                    CommandHandler("cancel", cancel),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, collect_data),
                ],
            },
            fallbacks=[CommandHandler("cancel", cancel)],
        )

        application.add_handler(conv_handler)

        logger.info("Запуск бота...")
        await application.run_polling()

    except Exception as e:
        logger.error(f"ОШИБКА ПРИ ЗАПУСКЕ: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
