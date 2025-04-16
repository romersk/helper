import logging
from datetime import datetime
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, CallbackContext
from telegram.ext import filters
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

def parse_time(ts):
    return datetime.strptime(ts, "%d %b., %H:%M")

def start(update: Update, context: CallbackContext):
    update.message.reply_text(
        "🚖 **Бот для анализа поездок**\n\n"
        "Отправь данные в формате:\n\n"
        "Фамилия Имя Отчество\n"
        "(пустая строка или нет)\n"
        "Дата, время\n\n"
        "Пример:\n"
        "Иванов Иван Иванович\n\n"
        "16 апр., 10:39\n"
        "Петров Петр Петрович\n"
        "16 апр., 11:00"
    )

def process_data(update: Update, context: CallbackContext):
    text = update.message.text
    lines = [line.strip() for line in text.split('\n') if line.strip() != '']
    
    orders = []
    i = 0
    while i < len(lines):
        # Ищем имя (это строка, которая НЕ похожа на дату)
        if i + 1 >= len(lines):
            break  # Не хватает данных
            
        name = lines[i]
        i += 1
        
        # Следующая строка — это время (если она похожа на дату)
        time_str = lines[i]
        i += 1
        
        try:
            time = parse_time(time_str)
            orders.append((name, time_str))
        except ValueError:
            update.message.reply_text(f"❌ Ошибка в формате времени: `{time_str}`\n\n"
                                    "Правильный формат: `16 апр., 10:39`", parse_mode="Markdown")
            return
    
    if not orders:
        update.message.reply_text("❌ Нет данных для анализа.")
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
            update.message.reply_text(f"❌ Ошибка в данных: `{time_str}`")
            return
    
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
    
    update.message.reply_text(response, parse_mode="Markdown")

def error(update: Update, context: CallbackContext):
    logger.warning(f'Update {update} caused error {context.error}')

def main():
    updater = Updater("YOUR_BOT_TOKEN", use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(filters.TEXT & ~Filters.command, process_data))
    dp.add_error_handler(error)

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()