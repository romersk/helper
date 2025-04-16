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
    """Универсальный парсер для русскоязычных дат с гибким форматом"""
    # Нормализация строки
    ts = ts.strip()
    
    # Заменяем возможные варианты написания месяца
    month_replacements = {
        'января': 'янв', 'февраля': 'фев', 'марта': 'мар',
        'апреля': 'апр', 'мая': 'май', 'июня': 'июн',
        'июля': 'июл', 'августа': 'авг', 'сентября': 'сен',
        'октября': 'окт', 'ноября': 'ноя', 'декабря': 'дек'
    }
    
    for full, short in month_replacements.items():
        ts = ts.replace(full, short)
    
    # Удаляем лишние пробелы и точки
    ts = ' '.join(ts.split())
    ts = ts.replace(' ,', ',').replace('.,', ',').replace('.,', ',')
    
    # Поддерживаемые форматы даты
    formats = [
        "%d %b, %H:%M",     # "16 апр, 16:15"
        "%d %b., %H:%M",    # "16 апр., 16:15"
        "%d %b %H:%M",      # "16 апр 16:15"
        "%d.%m., %H:%M",    # "16.04., 16:15"
        "%d.%m, %H:%M",     # "16.04, 16:15"
        "%d %B, %H:%M",     # "16 апреля, 16:15"
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(ts, fmt)
        except ValueError:
            continue
    
    raise ValueError(
        f"❌ Не удалось распознать время: `{ts}`\n"
        "Поддерживаемые форматы:\n"
        "• 16 апр, 16:15\n"
        "• 16 апр., 16:15\n"
        "• 16 апреля, 16:15\n"
        "• 16.04, 16:15\n"
        "• 16 апр 16:15"
    )

# ... (остальные функции остаются без изменений, как в предыдущем полном коде)

if __name__ == "__main__":
    main()