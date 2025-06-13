import os
import logging
from flask import Flask, request
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ConversationHandler
)
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
bot_application = None

def setup_bot():
    """Синхронная инициализация бота"""
    global bot_application
    
    try:
        bot_application = (
            Application.builder()
            .token(TOKEN)
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
        
        bot_application.add_handler(conv_handler)
        
        # Синхронная установка webhook
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        loop.run_until_complete(bot_application.initialize())
        loop.run_until_complete(
            bot_application.bot.set_webhook(
                url=f"{WEBHOOK_URL}{WEBHOOK_PATH}",
                max_connections=5,
                drop_pending_updates=True
            )
        )
        logger.info(f"Webhook установлен: {WEBHOOK_URL}{WEBHOOK_PATH}")
        
    except Exception as e:
        logger.error(f"Ошибка инициализации бота: {e}")
        raise

# Инициализация при старте
setup_bot()

@app.route("/")
def index():
    return "Бот работает! /debug для проверки"

@app.route("/debug")
def debug():
    """Проверка состояния бота"""
    if not bot_application:
        return "Бот не инициализирован", 500
    
    try:
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        webhook_info = loop.run_until_complete(
            bot_application.bot.get_webhook_info()
        )
        
        return {
            "status": "active",
            "bot": bot_application.bot.username,
            "webhook_url": webhook_info.url,
            "pending_updates": webhook_info.pending_update_count
        }
    except Exception as e:
        return {"error": str(e)}, 500

@app.route(WEBHOOK_PATH, methods=["POST"])
def webhook():
    """Синхронный обработчик webhook"""
    if not bot_application:
        return "Bot not initialized", 503
        
    try:
        update = Update.de_json(request.get_json(), bot_application.bot)
        
        # Создаем новый event loop для каждого запроса
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        loop.run_until_complete(bot_application.process_update(update))
        return "OK", 200
        
    except Exception as e:
        logger.error(f"Ошибка обработки обновления: {e}")
        return "Error", 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))