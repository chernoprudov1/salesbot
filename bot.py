import os
import sqlite3
import csv
import asyncio
import nest_asyncio
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
    ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler,
    filters, ContextTypes
)
from aiohttp import web

# ========================== НАСТРОЙКИ ==========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
ALLOWED_USERS = list(map(int, os.getenv("ALLOWED_USERS", "").split(",")))  # Список ID через запятую в ENV

DB_FILE = "sales.db"

# ========================== ЛОГИ ===============================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ========================== БАЗА ДАННЫХ ========================
def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                item TEXT,
                category TEXT,
                amount REAL,
                quantity INTEGER,
                timestamp TEXT
            )
        """)

def is_allowed(user_id):
    return user_id in ALLOWED_USERS

def add_sale(user_id, item, category, amount, quantity=1):
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute(
            "INSERT INTO sales (user_id, item, category, amount, quantity, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, item, category, amount, quantity, datetime.now().isoformat())
        )

def get_sales():
    with sqlite3.connect(DB_FILE) as conn:
        return conn.execute("SELECT * FROM sales").fetchall()

def get_sales_between(start_time, end_time):
    with sqlite3.connect(DB_FILE) as conn:
        return conn.execute(
            "SELECT * FROM sales WHERE timestamp BETWEEN ? AND ?",
            (start_time.isoformat(), end_time.isoformat())
        ).fetchall()

def delete_last_sale(user_id):
    with sqlite3.connect(DB_FILE) as conn:
        last = conn.execute("SELECT id FROM sales WHERE user_id=? ORDER BY id DESC LIMIT 1", (user_id,)).fetchone()
        if last:
            conn.execute("DELETE FROM sales WHERE id=?", (last[0],))
            return True
        return False

def reset_db():
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("DELETE FROM sales")

def export_csv():
    data = get_sales()
    filename = f"sales_export_{datetime.now().strftime('%Y%m%d%H%M%S')}.csv"
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["ID", "User ID", "Item", "Category", "Amount", "Quantity", "Timestamp"])
        writer.writerows(data)
    return filename

def export_excel():
    data = get_sales()
    df = pd.DataFrame(data, columns=["ID", "User ID", "Item", "Category", "Amount", "Quantity", "Timestamp"])
    filename = f"sales_export_{datetime.now().strftime('%Y%m%d%H%M%S')}.xlsx"
    df.to_excel(filename, index=False)
    return filename

# ========================== ГРАФИКИ ============================
def generate_sales_chart(sales, title):
    dates = [datetime.fromisoformat(r[6]).date() for r in sales]
    amounts = [r[4] * r[5] for r in sales]
    daily_summary = {}
    for d, a in zip(dates, amounts):
        daily_summary[d] = daily_summary.get(d, 0) + a
    sorted_dates = sorted(daily_summary)
    values = [daily_summary[day] for day in sorted_dates]

    plt.figure(figsize=(10, 4))
    plt.plot(sorted_dates, values, marker='o')
    plt.title(title)
    plt.xlabel("Дата")
    plt.ylabel("Сумма, ₽")
    plt.grid(True)
    plt.tight_layout()

    buffer = BytesIO()
    plt.savefig(buffer, format="png")
    buffer.seek(0)
    plt.close()
    return buffer

# ========================== КНОПКИ =============================
def main_keyboard(is_admin):
    buttons = [
        [KeyboardButton("🏦 Товары"), KeyboardButton("🚲 Услуги")],
        [KeyboardButton("📊 Общая сумма"), KeyboardButton("📜 История")],
        [KeyboardButton("📝 Заметка")],
        [KeyboardButton("⚙️ Админ-панель")]
    ]
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

# ========================== СОСТОЯНИЯ ==========================
user_states = {}

# ========================== ХЕНДЛЕРЫ ===========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_allowed(user_id):
        await update.message.reply_text("🚫 У вас нет доступа.")
        return
    await update.message.reply_text("Привет! Выбери действие:", reply_markup=main_keyboard(True))

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    logger.info(f"Получен текст от {user_id}: {text}")

    if not is_allowed(user_id):
        await update.message.reply_text("🚫 У вас нет доступа.")
        return

    if text == "🏦 Товары":
        user_states[user_id] = {"step": "enter_price", "item": "Программа", "category": "product"}
        await update.message.reply_text("Введите цену для 'Программа':\n\nОтправьте 'Отмена' для отмены.")

    elif text == "🚲 Услуги":
        user_states[user_id] = {"step": "enter_price", "item": "Настройка ПК", "category": "service"}
        await update.message.reply_text("Введите цену для 'Настройка ПК':\n\nОтправьте 'Отмена' для отмены.")

    elif text == "📝 Заметка":
        user_states[user_id] = {"step": "enter_note"}
        await update.message.reply_text("Введите текст заметки:\n\nОтправьте 'Отмена' для отмены.")

    elif text == "Отмена":
        if user_states.get(user_id):
            user_states.pop(user_id)
            await update.message.reply_text("Действие отменено.", reply_markup=main_keyboard(True))
        else:
            await update.message.reply_text("Нет активных действий.")

    elif text == "📜 История":
        rows = get_sales()
        if rows:
            msg = "\n".join([f"{r[2]} — {r[4]}₽" for r in rows[-10:]])
            await update.message.reply_text(f"📃 Последние продажи:\n{msg}")
        else:
            await update.message.reply_text("История пуста.")

    elif text == "📊 Общая сумма":
        total = sum(r[4] * r[5] for r in get_sales())
        await update.message.reply_text(f"💰 Общая сумма: {total} ₽")

    elif text == "⚙️ Админ-панель":
        kb = [
            [InlineKeyboardButton("📄 Экспорт CSV", callback_data="export_csv")],
            [InlineKeyboardButton("📊 Экспорт Excel", callback_data="export_excel")],
            [InlineKeyboardButton("🗑 Удалить последнюю", callback_data="delete_last")],
            [InlineKeyboardButton("♻️ Сбросить базу", callback_data="reset")],
            [InlineKeyboardButton("📈 График продаж", callback_data="chart")]
        ]
        await update.message.reply_text("⚙️ Админ-панель:", reply_markup=InlineKeyboardMarkup(kb))

    else:
        state = user_states.get(user_id)
        if state:
            if state.get("step") == "enter_price":
                if text.lower() == "отмена":
                    user_states.pop(user_id)
                    await update.message.reply_text("Действие отменено.", reply_markup=main_keyboard(True))
                    return
                try:
                    amount = float(text)
                    add_sale(user_id, state["item"], state["category"], amount)
                    await update.message.reply_text(f"✅ Продажа добавлена: {state['item']} — {amount}₽", reply_markup=main_keyboard(True))
                    user_states.pop(user_id)
                except:
                    await update.message.reply_text("Введите корректную сумму или 'Отмена' для отмены.")

            elif state.get("step") == "enter_note":
                if text.lower() == "отмена":
                    user_states.pop(user_id)
                    await update.message.reply_text("Действие отменено.", reply_markup=main_keyboard(True))
                    return
                # Здесь просто сохраняем заметку в базу как item='Заметка' для примера (можно доработать)
                add_sale(user_id, "Заметка", "note", 0, 1)
                await update.message.reply_text(f"📝 Заметка сохранена: {text}", reply_markup=main_keyboard(True))
                user_states.pop(user_id)
        else:
            await update.message.reply_text("Неизвестная команда. Выберите действие из меню.", reply_markup=main_keyboard(True))

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id
    logger.info(f"Callback от {user_id}: {data}")
    await query.answer()

    if not is_allowed(user_id):
        await query.edit_message_text("🚫 Нет доступа")
        return

    if data == "export_csv":
        file = export_csv()
        await query.message.reply_document(document=open(file, "rb"))
        os.remove(file)

    elif data == "export_excel":
        file = export_excel()
        await query.message.reply_document(document=open(file, "rb"))
        os.remove(file)

    elif data == "delete_last":
        msg = "Удалено." if delete_last_sale(user_id) else "Нечего удалять."
        await query.edit_message_text(msg)

    elif data == "reset":
        reset_db()
        await query.edit_message_text("База очищена.")

    elif data == "chart":
        now = datetime.now()
        start = now - timedelta(days=30)
        sales = get_sales_between(start, now)
        if sales:
            chart = generate_sales_chart(sales, "Продажи за месяц")
            await query.message.reply_photo(photo=InputFile(chart, filename="chart.png"))
        else:
            await query.edit_message_text("Нет данных для графика.")

# ======== Веб-сервер для Render (чтобы Render не останавливал сервис) =======
async def handle(request):
    return web.Response(text="Bot is running")

async def start_web_server():
    app_web = web.Application()
    app_web.add_routes([web.get('/', handle)])
    runner = web.AppRunner(app_web)
    await runner.setup()
    port = int(os.getenv("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"Web server started on port {port}")

# ========== Основной асинхронный запуск ==========
async def main_async():
    init_db()
    global app
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.job_queue.run_daily(send_daily_report, time(hour=22, minute=0))
    await start_web_server()
    await app.run_polling()

# ========== Ежедневный отчёт ==========
async def send_daily_report(context: ContextTypes.DEFAULT_TYPE):
    rows = get_sales()
    total = sum(r[4] * r[5] for r in rows)
    if total > 0:
        msg = "\n".join([f"{r[2]} — {r[4]}₽" for r in rows[-10:]])
        for admin_id in ALLOWED_USERS:
            await context.bot.send_message(admin_id, f"📊 Ежедневный отчёт:\nОбщая сумма: {total}₽\n\n{msg}")

if __name__ == "__main__":
    import nest_asyncio
    nest_asyncio.apply()
    asyncio.run(main_async())
