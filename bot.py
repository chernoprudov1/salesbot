import logging
import sqlite3
import asyncio
from datetime import datetime, time

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CallbackQueryHandler, CommandHandler,
    ContextTypes, MessageHandler, filters, ConversationHandler, JobQueue
)

from aiohttp import web
import nest_asyncio
import pandas as pd
import matplotlib.pyplot as plt
from io import BytesIO

nest_asyncio.apply()

# === Настройки ===
TOKEN = "ТВОЙ_ТОКЕН_СЮДА"
ADMIN_ID = 872585742
DB_FILE = "sales.db"

CATEGORY, ITEM, QUANTITY, PRICE, NOTE = range(5)


def init_db():
    conn = sqlite3.connect(DB_FILE)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            category TEXT,
            item TEXT,
            quantity INTEGER,
            price INTEGER,
            note TEXT,
            date TEXT
        )
    ''')
    conn.commit()
    conn.close()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Товары", callback_data="category_Товары")],
        [InlineKeyboardButton("Услуги", callback_data="category_Услуги")]
    ]
    await update.message.reply_text("Выберите категорию:", reply_markup=InlineKeyboardMarkup(keyboard))
    return CATEGORY


async def category_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    category = query.data.split("_")[1]
    context.user_data['category'] = category

    if category == "Товары":
        context.user_data['item'] = "Программа"
        context.user_data['quantity'] = 1
        await query.message.reply_text("Введите цену продажи:")
        return PRICE
    elif category == "Услуги":
        context.user_data['item'] = "Настройка ПК"
        context.user_data['quantity'] = 1
        await query.message.reply_text("Введите цену услуги:")
        return PRICE


async def price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['price'] = int(update.message.text)
    await update.message.reply_text("Введите примечание (например: клиент, детали и т.д.):")
    return NOTE


async def note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['note'] = update.message.text

    conn = sqlite3.connect(DB_FILE)
    conn.execute('''
        INSERT INTO sales (user_id, username, category, item, quantity, price, note, date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        update.effective_user.id,
        update.effective_user.username,
        context.user_data['category'],
        context.user_data['item'],
        context.user_data['quantity'],
        context.user_data['price'],
        context.user_data['note'],
        datetime.now().strftime('%Y-%m-%d')
    ))
    conn.commit()
    conn.close()

    await update.message.reply_text("Продажа сохранена!")
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Операция отменена.")
    return ConversationHandler.END


async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT * FROM sales", conn)
    conn.close()

    if df.empty:
        await update.message.reply_text("Нет данных для отчета.")
        return

    output = BytesIO()
    df.to_excel(output, index=False)
    output.seek(0)

    await update.message.reply_document(document=output, filename="sales_report.xlsx")


async def send_daily_report(context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT * FROM sales WHERE date = ?", conn, params=[datetime.now().strftime('%Y-%m-%d')])
    conn.close()

    if df.empty:
        return

    total = df['price'].sum()
    text = f"📊 Ежедневный отчет:\n\nКоличество продаж: {len(df)}\nОбщая сумма: {total}₽"

    await context.bot.send_message(chat_id=ADMIN_ID, text=text)


async def main():
    init_db()

    application = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CATEGORY: [CallbackQueryHandler(category_selected)],
            PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, price)],
            NOTE: [MessageHandler(filters.TEXT & ~filters.COMMAND, note)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("report", report))

    # Настроим ежедневный отчёт
    application.job_queue.run_daily(send_daily_report, time(hour=22, minute=0))

    # Запуск веб-сервера для Render
    async def index(request):
        return web.Response(text="Бот работает!")

    web_app = web.Application()
    web_app.add_routes([web.get("/", index)])
    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 10000)
    await site.start()

    print("✅ Бот запущен на сервере!")
    await application.run_polling()


if __name__ == "__main__":
    asyncio.run(main())
