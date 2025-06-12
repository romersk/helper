import os
import logging
import asyncio
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.request import HTTPXRequest  # Добавлен импорт
from bot import post_init, start, cancel, collect_data, process_data, WAITING_FOR_DATA

# Настройка логгера
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Переменные окружения
TOKEN = os.environ.get("BOT_TOKEN")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")  # Полный URL вашего приложения на Render
WEBHOOK_PATH = f"/webhook/{TOKEN}"

app = Flask(__name__)

# Глобальная переменная для хранения Application
application = None

async def initialize_application():
    """Инициализация Telegram Application"""
    global application
    
    request_obj = HTTPXRequest(connect_timeout=30, read_timeout=30)
    application = (
        Application.builder()
        .token(TOKEN)
        .request(request_obj)
        .post_init(post_init)
        .build()
    )
    
    # Добавляем обработчики
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
    
    # Инициализируем приложение
    await application.initialize()
    
    # Устанавливаем webhook
    await application.bot.set_webhook(f"{WEBHOOK_URL}{WEBHOOK_PATH}")
    logger.info("Webhook установлен")

def setup_application():
    """Синхронная обёртка для инициализации приложения"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(initialize_application())
    loop.close()

# Инициализация при запуске
setup_application()

@app.route("/")
def index():
    return "Бот работает!"

@app.route(WEBHOOK_PATH, methods=["POST"])
async def webhook():
    """Асинхронный обработчик webhook"""
    if application is None:
        return "Application not initialized", 500
    
    try:
        update = Update.de_json(await request.get_json(), application.bot)
        await application.process_update(update)
        return "OK", 200
    except Exception as e:
        logger.error(f"Ошибка обработки обновления: {e}")
        return "Error", 500

@app.route("/webhook_info")
async def webhook_info():
    """Проверка статуса webhook"""
    if application is None:
        return "Application not initialized", 500
    
    try:
        info = await application.bot.get_webhook_info()
        return {
            "url": info.url,
            "has_custom_certificate": info.has_custom_certificate,
            "pending_update_count": info.pending_update_count
        }
    except Exception as e:
        return {"error": str(e)}, 500

@app.route("/debug")
def debug():
    """Эндпоинт для отладки"""
    webhook_info = None
    if application:
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            webhook_info = loop.run_until_complete(application.bot.get_webhook_info())
            loop.close()
        except Exception as e:
            logger.error(f"Ошибка получения webhook info: {e}")

    return {
        "status": "running",
        "webhook_url": WEBHOOK_URL,
        "webhook_path": WEBHOOK_PATH,
        "full_webhook_url": f"{WEBHOOK_URL}{WEBHOOK_PATH}",
        "bot_token_set": bool(TOKEN),
        "app_initialized": application is not None,
        "webhook_info": {
            "url": webhook_info.url if webhook_info else None,
            "pending_updates": webhook_info.pending_update_count if webhook_info else None
        } if webhook_info else None
    }

if __name__ == "__main__":
    app.run()