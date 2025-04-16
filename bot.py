import logging
import os
import locale
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

# Настройка логгирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния для диалога
WAITING_FOR_DATA = 1

def parse_time(ts):
    """Универсальный парсер для русскоязычных дат"""
    try:
        locale.setlocale(locale.LC_TIME, 'ru_RU.UTF-8')
    except locale.Error:
        try:
            locale.setlocale(locale.LC_TIME, 'Russian_Russia.1251')
        except locale.Error:
            pass
    
    # Нормализация строки
    ts = ' '.join(ts.strip().split())
    ts = ts.replace('..', '.').replace('.,', ',')
    
    # Все поддерживаемые форматы
    formats = [
        "%d %b., %H:%M",    # "16 апр., 10:39"
        "%d %B, %H:%M",     # "16 апреля, 10:39"
        "%d.%m., %H:%M",    # "16.04., 10:39"
        "%d %b. %H:%M",     # "16 апр. 10:39"
        "%d %B %H:%M",      # "16 апреля 10:39"
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(ts, fmt)
        except ValueError:
            continue
    
    raise ValueError(
        f"❌ Не удалось распознать время: `{ts}`\n"
        "Поддерживаемые форматы:\n"
        "• 16 апр., 10:39\n"
        "• 16 апреля, 10:39\n"
        "• 16.04., 10:39\n"
        "• 16 апр. 10:39"
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало диалога"""
    await update.message.reply_text(
        "🚕 **Анализатор поездок**\n\n"
        "Присылайте данные в формате:\n\n"
        "<b>Фамилия Имя Отчество</b>\n"
        "<i>Дата и время</i>\n\n"
        "Примеры времени:\n"
        "• 16 апр., 10:39\n"
        "• 16 апреля, 10:39\n"
        "• 16.04., 10:39\n\n"
        "Можно присылать данные несколькими сообщениями.\n"
        "Завершить ввод - /done\n"
        "Отмена - /cancel",
        parse_mode="HTML"
    )
    context.user_data["collected_data"] = []
    return WAITING_FOR_DATA

async def process_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка и анализ данных"""
    try:
        full_text = "\n".join(context.user_data["collected_data"])
        lines = [line.strip() for line in full_text.split("\n") if line.strip()]
        
        if len(lines) % 2 != 0:
            await update.message.reply_text(
                "⚠️ <b>Ошибка:</b> Непарное количество строк. "
                "Каждому ФИО должна соответствовать дата",
                parse_mode="HTML"
            )
            return ConversationHandler.END
        
        # Парсинг данных
        drivers = {}
        for i in range(0, len(lines), 2):
            name = lines[i]
            time_str = lines[i+1]
            
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
        
        # Формирование отчета
        if not drivers:
            await update.message.reply_text("ℹ️ Нет данных для анализа")
            return ConversationHandler.END
        
        report = ["<b>📊 Результаты анализа</b>\n"]
        for name, times in sorted(drivers.items(), key=lambda x: x[1]["first"]):
            report.append(
                f"\n👤 <b>{name}</b>\n"
                f"• Первая поездка: {times['first'].strftime('%H:%M')}\n"
                f"• Последняя поездка: {times['last'].strftime('%H:%M')}"
            )
        
        # Отправка частями если сообщение слишком длинное
        message = "\n".join(report)
        for i in range(0, len(message), 4096):
            await update.message.reply_text(
                message[i:i+4096],
                parse_mode="HTML"
            )
            
    except Exception as e:
        logger.exception("Ошибка обработки данных")
        await update.message.reply_text(
            "⚠️ <b>Ошибка обработки:</b> Попробуйте отправить данные еще раз",
            parse_mode="HTML"
        )
    finally:
        context.user_data.clear()
    
    return ConversationHandler.END

def main():
    """Запуск бота"""
    application = Application.builder().token(os.environ["BOT_TOKEN"]).build()
    
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
    application.run_polling()

if __name__ == "__main__":
    main()