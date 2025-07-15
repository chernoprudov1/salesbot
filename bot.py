
import sqlite3
import os
import nest_asyncio
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler,
    filters, ContextTypes
)
from datetime import datetime

BOT_TOKEN = "7522847009:AAF-qxmfLJvbFognsXapzgOSOeqofWne7rA"
ALLOWED_USERS = [872585742]

def is_allowed(user_id):
    return user_id in ALLOWED_USERS

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update.effective_user.id):
        await update.message.reply_text("🚫 У вас нет доступа.")
        return
    await update.message.reply_text("Бот запущен.")

def main():
    nest_asyncio.apply()
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.run_polling()

if __name__ == "__main__":
    main()
