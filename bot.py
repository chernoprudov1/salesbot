import os
import sqlite3
import csv
import asyncio
import matplotlib.pyplot as plt
import pandas as pd
import logging
from datetime import datetime, time, timedelta
from io import BytesIO
from telegram import (
    Update, ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton, InputFile
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, ContextTypes
)
from aiohttp import web

# Настройки
BOT_TOKEN = os.getenv("BOT_TOKEN")
ALLOWED_USERS = list(map(int, os.getenv("ALLOWED_USERS", "").split(",")))
DB_FILE = "sales.db"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# (Тут все функции init_db, add_sale, и т. д. такие же, как были)

# Добавим заметки и кнопку
def main_keyboard(is_admin):
    buttons = [
        [KeyboardButton("🏦 Товары"), KeyboardButton("🚲 Услуги")],
        [KeyboardButton("📊 Общая сумма"), KeyboardButton("📜 История")],
        [KeyboardButton("📝 Заметка")],
        [KeyboardButton("⚙️ Админ-панель")]
    ]
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

# Хендлеры такие же – handle_text, handle_callback, start, send_daily_report

# HTTP-сервер для Render
async def handle(request):
    return web.Response(text="Bot is running")

async def start_web_server():
    app = web.Application()
    app.add_routes([web.get('/', handle)])
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logger.info(f"Web server started on port {port}")

# Основной async
async def main():
    init_db()
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Настройка JobQueue
    app.job_queue.run_daily(send_daily_report, time(hour=22, minute=0))

    # Обработчики
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(handle_callback))

    # Запускаем HTTP + Telegram
    await start_web_server()
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
