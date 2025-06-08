import os
import logging
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, ContextTypes
from telegram.request import HTTPXRequest
from bot import post_init, start, cancel, collect_data, process_data, WAITING_FOR_DATA
from telegram.ext import (
    CommandHandler,
    MessageHandler,
    filters,
    ConversationHandler,
)

# Настройка логгера
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("BOT_TOKEN")
WEBHOOK_PATH = f"/webhook/{TOKEN}"
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")  # полный публичный URL Render

app = Flask(__name__)

@app.before_first_request
async def setup_bot():
    request_obj = HTTPXRequest(connect_timeout=30, read_timeout=30)
    application = (
        Application.builder()
        .token(TOKEN)
        .request(request_obj)
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

    # Устанавливаем webhook
    await application.bot.set_webhook(f"{WEBHOOK_URL}{WEBHOOK_PATH}")

    # Flask хендлер будет проксировать запросы Telegram в PTB
    async def webhook_handler(request):
        data = request.get_data(as_text=True)
        update = Update.de_json(data, application.bot)
        await application.process_update(update)
        return "ok"

    app.add_url_rule(WEBHOOK_PATH, "webhook", lambda: webhook_handler(request), methods=["POST"])

    logger.info("Бот запущен в режиме Webhook")
