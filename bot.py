import logging
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Time parsing function
def parse_time(ts):
    return datetime.strptime(ts, "%d %b., %H:%M")

# Command handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚖 **Helper Bot**\n\n"
        "Отправь данные для анализа:\n\n"
    )

# Message handler
async def process_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    
    orders = []
    i = 0
    while i < len(lines):
        if i + 1 >= len(lines):
            break
            
        name = lines[i]
        time_str = lines[i+1]
        i += 2
        
        try:
            time = parse_time(time_str)
            orders.append((name, time_str))
        except ValueError:
            await update.message.reply_text(f"❌ Ошибка в формате времени: `{time_str}`")
            return
    
    if not orders:
        await update.message.reply_text("❌ Нет данных для анализа")
        return
    
    driver_times = {}
    for name, time_str in orders:
        try:
            time = parse_time(time_str)
            if name not in driver_times:
                driver_times[name] = {"first": time, "last": time}
            else:
                driver_times[name]["first"] = min(driver_times[name]["first"], time)
                driver_times[name]["last"] = max(driver_times[name]["last"], time)
        except ValueError:
            await update.message.reply_text(f"❌ Ошибка в данных: `{time_str}`")
            return
    
    sorted_drivers = sorted(driver_times.items(), key=lambda x: x[1]["first"])
    
    response = "📊 **Результат**\n\n"
    for name, times in sorted_drivers:
        first_time = times["first"].strftime("%H:%M")
        last_time = times["last"].strftime("%H:%M")
        response += (
            f"👤 **{name}**\n"
            f"⏱ Первая поездка: `{first_time}`\n"
            f"⏱ Последняя поездка: `{last_time}`\n\n"
        )
    
    await update.message.reply_text(response)

# Error handler
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error: {context.error}")

def main():
    # Create Application
    application = Application.builder().token("YOUR_BOT_TOKEN").build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, process_data))
    application.add_error_handler(error_handler)
    
    # Run bot
    application.run_polling()

if __name__ == '__main__':
    main()