import os
import logging
import asyncio
from flask import Flask, request, jsonify
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ConversationHandler
)
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
loop = None

async def init_bot():
    """Инициализация бота"""
    global application, loop
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    application = (
        Application.builder()
        .token(TOKEN)
        .request(HTTPXRequest(connect_timeout=30, read_timeout=30))
        .post_init(post_init)
        .build()
    )
    
    # Регистрация обработчиков
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
    await application.bot.set_webhook(f"{WEBHOOK_URL}{WEBHOOK_PATH}")
    logger.info(f"Webhook установлен: {WEBHOOK_URL}{WEBHOOK_PATH}")

# Инициализация при старте
try:
    asyncio.run(init_bot())
except Exception as e:
    logger.error(f"Ошибка инициализации бота: {e}")
    raise

@app.route("/")
def index():
    return "Бот работает! Проверьте /debug для информации"

@app.route("/debug")
def debug():
    """Эндпоинт для отладки"""
    if not application:
        return jsonify({"error": "Application not initialized"}), 500
    
    try:
        webhook_info = loop.run_until_complete(application.bot.get_webhook_info())
        return jsonify({
            "status": "running",
            "bot_username": application.bot.username,
            "webhook_url": f"{WEBHOOK_URL}{WEBHOOK_PATH}",
            "webhook_info": {
                "url": webhook_info.url,
                "pending_updates": webhook_info.pending_update_count,
                "last_error": str(webhook_info.last_error_message),
                "max_connections": webhook_info.max_connections
            }
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route(WEBHOOK_PATH, methods=["POST"])
def webhook():
    """Синхронный обработчик webhook"""
    if not application:
        return "Application not initialized", 500
    
    try:
        update = Update.de_json(request.get_json(), application.bot)
        loop.run_until_complete(application.process_update(update))
        return "OK", 200
    except Exception as e:
        logger.error(f"Ошибка обработки обновления: {e}")
        return "Error", 500

if __name__ == "__main__":
    app.run()