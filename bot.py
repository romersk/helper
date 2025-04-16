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

# Set up logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# States for conversation
WAITING_FOR_DATA, PROCESSING = range(2)

# Time parsing function
def parse_time(ts):
    return datetime.strptime(ts, "%d %b., %H:%M")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚖 **Helper Bot**\n\n"
        "Отправляйте данные для анализа по частям. Каждая запись должна быть в формате:\n\n"
        "Фамилия Имя Отчество\n"
        "Дата, время\n\n"
        "Когда все данные будут отправлены, введите команду /done\n"
        "Для отмены введите /cancel"
    )
    context.user_data["collected_data"] = []
    return WAITING_FOR_DATA

async def collect_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    context.user_data["collected_data"].append(text)
    await update.message.reply_text(
        "Данные получены. Можно отправлять следующую часть или /done для обработки"
    )
    return WAITING_FOR_DATA

async def process_collected_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    collected_lines = []
    for part in context.user_data["collected_data"]:
        collected_lines.extend(part.split("\n"))
    
    # Remove empty lines and strip whitespace
    lines = [line.strip() for line in collected_lines if line.strip()]
    
    orders = []
    i = 0
    while i < len(lines):
        if i + 1 >= len(lines):
            break
            
        name = lines[i]
        time_str = lines[i + 1]
        i += 2
        
        try:
            time = parse_time(time_str)
            orders.append((name, time_str))
        except ValueError:
            await update.message.reply_text(
                f"❌ Ошибка в формате времени: `{time_str}`\n"
                "Правильный формат: `16 апр., 10:39`"
            )
            context.user_data.clear()
            return ConversationHandler.END
    
    if not orders:
        await update.message.reply_text("❌ Нет валидных данных для анализа")
        context.user_data.clear()
        return ConversationHandler.END
    
    driver_times = {}
    for name, time_str in orders:
        try:
            time = parse_time(time_str)
            if name not in driver_times:
                driver_times[name] = {"first": time, "last": time}
            else:
                driver_times[name]["first"] = min(
                    driver_times[name]["first"], time
                )
                driver_times[name]["last"] = max(
                    driver_times[name]["last"], time
                )
        except ValueError:
            await update.message.reply_text(f"❌ Ошибка в данных: `{time_str}`")
            context.user_data.clear()
            return ConversationHandler.END
    
    sorted_drivers = sorted(driver_times.items(), key=lambda x: x[1]["first"])
    
    response = "📊 **Результат анализа**\n\n"
    for name, times in sorted_drivers:
        first_time = times["first"].strftime("%H:%M")
        last_time = times["last"].strftime("%H:%M")
        response += (
            f"👤 **{name}**\n"
            f"⏱ Первая поездка: `{first_time}`\n"
            f"⏱ Последняя поездка: `{last_time}`\n\n"
        )
    
    # Split long messages
    max_length = 4096  # Telegram message limit
    if len(response) > max_length:
        parts = [
            response[i:i + max_length] 
            for i in range(0, len(response), max_length)
        ]
        for part in parts:
            await update.message.reply_text(part)
    else:
        await update.message.reply_text(response)
    
    context.user_data.clear()
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Операция отменена")
    context.user_data.clear()
    return ConversationHandler.END

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error: {context.error}")

def main():
    # Create Application
    application = Application.builder().token(os.environ["BOT_TOKEN"]).build()
    
    # Add conversation handler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            WAITING_FOR_DATA: [
                CommandHandler("done", process_collected_data),
                CommandHandler("cancel", cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, collect_data),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    
    application.add_handler(conv_handler)
    application.add_error_handler(error_handler)
    
    # Run bot
    application.run_polling()

if __name__ == "__main__":
    main()