import os
import logging
import asyncio
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler
from telegram.request import HTTPXRequest
from bot import post_init, start, cancel, collect_data, process_data, WAITING_FOR_DATA

# Настройка логгера
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Переменные окружения
TOKEN = os.environ.get("BOT_TOKEN")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")  # https://your-app-name.onrender.com
WEBHOOK_PATH = f"/webhook/{TOKEN}"

# Flask app
app = Flask(__name__)

# Telegram Application
request_obj = HTTPXRequest(connect_timeout=30, read_timeout=30)
application = (
    Application.builder()
    .token(TOKEN)
    .request(request_obj)
    .post_init(post_init)
    .build()
)

# Обработчики
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

async def set_webhook():
    logger.info("Установка Webhook...")
    await application.bot.set_webhook(f"{WEBHOOK_URL}{WEBHOOK_PATH}")

def sync_set_webhook():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(set_webhook())
    loop.close()

# Устанавливаем webhook при старте
@app.route("/")
def index():
    return "Bot is running"

# Вызываем установку webhook при старте приложения
sync_set_webhook()

# Webhook endpoint (синхронная версия)
@app.route(WEBHOOK_PATH, methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    asyncio.run(application.process_update(update))
    return "OK", 200

if __name__ == "__main__":
    app.run()