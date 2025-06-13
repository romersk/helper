import os
import logging
import asyncio
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler
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
loop = None  # Глобальная переменная для event loop

async def init_bot():
    """Инициализация бота с обработкой ошибок"""
    global application, loop
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        application = (
            Application.builder()
            .token(TOKEN)
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
        
        await application.initialize()
        await application.bot.set_webhook(
            url=f"{WEBHOOK_URL}{WEBHOOK_PATH}",
            max_connections=5,  # Уменьшено для Render
            drop_pending_updates=True
        )
        logger.info(f"Webhook установлен: {WEBHOOK_URL}{WEBHOOK_PATH}")
        
    except Exception as e:
        logger.error(f"FATAL: Ошибка инициализации бота: {e}")
        raise

# Инициализация при старте
try:
    asyncio.run(init_bot())
except Exception as e:
    logger.critical(f"Не удалось запустить бота: {e}")
    exit(1)

@app.route("/")
def index():
    return "Бот работает! /debug для проверки"

@app.route("/debug")
def debug():
    """Эндпоинт для проверки состояния"""
    if not application:
        return "Бот не инициализирован", 500
    
    try:
        return {
            "status": "active",
            "bot": application.bot.username if application.bot else None,
            "webhook": f"{WEBHOOK_URL}{WEBHOOK_PATH}"
        }
    except Exception as e:
        return f"Ошибка: {str(e)}", 500

@app.route(WEBHOOK_PATH, methods=["POST"])
def webhook():
    """Синхронный обработчик для совместимости с sync worker"""
    if not application:
        return "Bot not initialized", 503
        
    try:
        update = Update.de_json(request.get_json(), application.bot)
        loop.run_until_complete(application.process_update(update))
        return "OK", 200
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return "Error", 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))