import os
import logging
import asyncio
from flask import Flask, request, jsonify
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler
from telegram.request import HTTPXRequest
from bot import post_init, start, cancel, collect_data, process_data, WAITING_FOR_DATA

# Настройка логгера
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Переменные окружения
TOKEN = os.environ["BOT_TOKEN"]
WEBHOOK_URL = os.environ["WEBHOOK_URL"].rstrip("/")
WEBHOOK_PATH = f"/webhook/{TOKEN}"

app = Flask(__name__)
application = None

async def init_bot():
    global application
    application = (
        Application.builder()
        .token(TOKEN)
        .post_init(post_init)
        .build()
    )
    
    # Регистрация обработчиков из bot.py
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
    
    await application.initialize()
    await application.bot.set_webhook(
        url=f"{WEBHOOK_URL}{WEBHOOK_PATH}",
        max_connections=10,
        drop_pending_updates=True
    )
    logger.info(f"Webhook установлен: {WEBHOOK_URL}{WEBHOOK_PATH}")

# Инициализация при старте
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
loop.run_until_complete(init_bot())

@app.route("/")
def index():
    return "Бот работает!"

@app.route(WEBHOOK_PATH, methods=["POST"])
async def webhook():
    update = Update.de_json(await request.get_json(), application.bot)
    await application.process_update(update)
    return "OK", 200

if __name__ == "__main__":
    app.run()