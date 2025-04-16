import logging
import os
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
    """Парсит строку с датой в объект datetime"""
    month_replacements = {
        "января": "янв.",
        "февраля": "февр.",
        "марта": "мар.",
        "апреля": "апр.",
        "мая": "май",
        "июня": "июн.",
        "июля": "июл.",
        "августа": "авг.",
        "сентября": "сент.",
        "октября": "окт.",
        "ноября": "нояб.",
        "декабря": "дек."
    }
    
    # Нормализация формата месяца
    for full, short in month_replacements.items():
        ts = ts.replace(full, short)
    
    # Удаление лишних пробелов
    ts = ' '.join(ts.split())
    
    try:
        return datetime.strptime(ts, "%d %b., %H:%M")
    except ValueError as e:
        logger.error(f"Ошибка парсинга времени: {ts} - {str(e)}")
        raise ValueError(
            f"❌ Неверный формат времени: `{ts}`\n"
            "Правильный формат: `16 апр., 10:39` или `16 апреля, 10:39`"
        )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    await update.message.reply_text(
        "🚖 **Анализатор поездок**\n\n"
        "Присылайте данные поездок в формате:\n\n"
        "Фамилия Имя Отчество\n"
        "Дата и время (например: 16 апр., 10:39 или 16 апреля, 10:39)\n\n"
        "Можно присылать данные несколькими сообщениями.\n"
        "Когда закончите, введите /done\n"
        "Для отмены /cancel"
    )
    context.user_data["collected_data"] = []
    return WAITING_FOR_DATA

async def collect_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сбор данных из сообщений"""
    context.user_data["collected_data"].append(update.message.text)
    await update.message.reply_text(
        "✅ Данные сохранены. Можно присылать следующую часть "
        "или /done для обработки"
    )
    return WAITING_FOR_DATA

async def process_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка собранных данных"""
    try:
        # Объединяем все полученные данные
        full_text = "\n".join(context.user_data["collected_data"])
        lines = [line.strip() for line in full_text.split("\n") if line.strip()]
        
        if len(lines) % 2 != 0:
            await update.message.reply_text(
                "❌ Нечетное количество строк. Каждому ФИО должна соответствовать дата"
            )
            return ConversationHandler.END
        
        orders = []
        for i in range(0, len(lines), 2):
            name = lines[i]
            time_str = lines[i+1]
            try:
                time = parse_time(time_str)
                orders.append((name, time))
            except ValueError as e:
                await update.message.reply_text(str(e))
                return ConversationHandler.END
        
        if not orders:
            await update.message.reply_text("❌ Нет данных для анализа")
            return ConversationHandler.END
        
        # Анализ данных
        driver_times = {}
        for name, time in orders:
            if name not in driver_times:
                driver_times[name] = {"first": time, "last": time}
            else:
                driver_times[name]["first"] = min(driver_times[name]["first"], time)
                driver_times[name]["last"] = max(driver_times[name]["last"], time)
        
        # Формирование отчета
        response = ["📊 **Результаты анализа**\n"]
        for name, times in sorted(driver_times.items(), key=lambda x: x[1]["first"]):
            response.append(
                f"👤 **{name}**\n"
                f"⏱ Первая поездка: {times['first'].strftime('%H:%M')}\n"
                f"⏱ Последняя поездка: {times['last'].strftime('%H:%M')}\n"
            )
        
        # Разбивка длинных сообщений
        full_response = "\n".join(response)
        for i in range(0, len(full_response), 4096):
            await update.message.reply_text(full_response[i:i+4096])
            
    except Exception as e:
        logger.error(f"Ошибка обработки: {str(e)}")
        await update.message.reply_text("⚠️ Произошла ошибка при обработке данных")
    finally:
        context.user_data.clear()
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик отмены"""
    await update.message.reply_text("❌ Операция отменена")
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