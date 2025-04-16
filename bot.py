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
    """Универсальный парсер для русскоязычных дат"""
    # Нормализация строки
    ts = ts.strip().lower()
    
    # Заменяем варианты написания месяца
    month_map = {
        'января': '01', 'февраля': '02', 'марта': '03',
        'апреля': '04', 'мая': '05', 'июня': '06',
        'июля': '07', 'августа': '08', 'сентября': '09',
        'октября': '10', 'ноября': '11', 'декабря': '12',
        'янв': '01', 'фев': '02', 'мар': '03',
        'апр': '04', 'май': '05', 'июн': '06',
        'июл': '07', 'авг': '08', 'сен': '09',
        'окт': '10', 'ноя': '11', 'дек': '12'
    }
    
    try:
        # Обрабатываем разные форматы разделителей
        if ',' in ts:
            day_part, time_part = [x.strip() for x in ts.split(',', 1)]
        else:
            parts = ts.split()
            if len(parts) < 2:
                raise ValueError("Недостаточно частей в дате")
            day_part = ' '.join(parts[:-1])
            time_part = parts[-1]
        
        # Извлекаем день и месяц
        if '.' in day_part:
            day, month = day_part.split('.')
            month = month_map.get(month, month)
        else:
            parts = day_part.split()
            day = parts[0]
            if len(parts) > 1:
                month = month_map.get(parts[1], parts[1])
            else:
                raise ValueError("Не указан месяц")
        
        day = day.zfill(2)
        if len(month) > 2:  # Если месяц был указан текстом
            month = month_map.get(month, '')
            if not month:
                raise ValueError("Неверное название месяца")
        
        # Собираем дату
        current_year = datetime.now().year
        datetime_str = f"{current_year}-{month}-{day} {time_part}"
        return datetime.strptime(datetime_str, "%Y-%m-%d %H:%M")
        
    except Exception as e:
        raise ValueError(
            f"❌ Не удалось распознать время: `{ts}`\n"
            "Примеры правильных форматов:\n"
            "• 16 апр, 16:15\n"
            "• 16 апр., 16:15\n"
            "• 16 апреля, 16:15\n"
            "• 16.04, 16:15\n"
            "• 16 апр 16:15"
        )
    
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало диалога"""
    await update.message.reply_text(
        "🚕 **Анализатор поездок**\n\n"
        "Присылайте данные в формате:\n\n"
        "<b>Фамилия Имя Отчество</b>\n"
        "<i>Дата и время</i>\n\n"
        "Примеры времени:\n"
        "• 16 апр, 16:15\n"
        "• 16 апреля, 16:15\n"
        "• 16.04, 16:15\n\n"
        "Можно присылать данные несколькими сообщениями.\n"
        "Завершить ввод - /done\n"
        "Отмена - /cancel",
        parse_mode="HTML"
    )
    context.user_data["collected_data"] = []
    return WAITING_FOR_DATA

async def collect_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сбор данных от пользователя"""
    context.user_data["collected_data"].append(update.message.text)
    await update.message.reply_text(
        "✅ Данные получены. Можно присылать следующую часть или /done для обработки",
        parse_mode="HTML"
    )
    return WAITING_FOR_DATA

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик отмены"""
    await update.message.reply_text(
        "❌ Операция отменена. Все собранные данные удалены.",
        parse_mode="HTML"
    )
    context.user_data.clear()
    return ConversationHandler.END

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
                f"• Первая поездка: {times['first'].strftime('%d.%m %H:%M')}\n"
                f"• Последняя поездка: {times['last'].strftime('%d.%m %H:%M')}"
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
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise ValueError("Не задан BOT_TOKEN в переменных окружения")
    
    application = Application.builder().token(token).build()
    
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