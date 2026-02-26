import logging
import sqlite3
from datetime import datetime
import re

from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder, ContextTypes,
    CommandHandler, MessageHandler,
    filters, ConversationHandler
)

import os
BOT_TOKEN = os.getenv("BOT_TOKEN")

SELECT_CATEGORY, OTHER_TYPE, AMOUNT = range(3)

CATEGORIES = [
    ["ovqatlanish"],
    ["transport"],
    ["kiyim"],
    ["boshqalar"],
    ["bekor qilish"]
]

logging.basicConfig(level=logging.INFO)
DB = "expenses.db"


# -------- DATABASE --------
def init_db():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            ts TEXT,
            amount INTEGER,
            category TEXT,
            other TEXT
        )
    """)
    conn.commit()
    conn.close()


def valid_amount(text):
    return bool(re.fullmatch(r"\d+", text))


# -------- COMMANDS --------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Salom 👋\n\n"
        "/add - yangi harajat qo'shish\n"
        "/daily - bugungi hisobot"
    )


async def add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = ReplyKeyboardMarkup(CATEGORIES, resize_keyboard=True)
    await update.message.reply_text(
        "Bo'limni tanlang:",
        reply_markup=keyboard
    )
    return SELECT_CATEGORY


async def select_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "bekor qilish":
        await update.message.reply_text(
            "Bekor qilindi.",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END

    context.user_data["category"] = text

    if text == "boshqalar":
        await update.message.reply_text(
            "Qaysi turdagi sarf?",
            reply_markup=ReplyKeyboardRemove()
        )
        return OTHER_TYPE
    else:
        await update.message.reply_text(
            "Sarf miqdori (probelsiz):",
            reply_markup=ReplyKeyboardRemove()
        )
        return AMOUNT


async def other_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["other"] = update.message.text
    await update.message.reply_text("Sarf miqdori (probelsiz):")
    return AMOUNT


async def amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if not valid_amount(text):
        await update.message.reply_text(
            "error: faqat raqam va probelsiz yozilsin, qaytadan boshlang"
        )
        return ConversationHandler.END

    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    cur.execute(
        "INSERT INTO expenses (user_id, ts, amount, category, other) VALUES (?, ?, ?, ?, ?)",
        (
            update.effective_user.id,
            datetime.utcnow().isoformat(),
            int(text),
            context.user_data.get("category"),
            context.user_data.get("other")
        )
    )

    conn.commit()
    conn.close()

    await update.message.reply_text("Saqlandi ✅")
    return ConversationHandler.END


async def daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    today = datetime.utcnow().date().isoformat()

    cur.execute(
        "SELECT category, other, SUM(amount) FROM expenses WHERE date(ts)=? GROUP BY category, other",
        (today,)
    )

    rows = cur.fetchall()
    conn.close()

    if not rows:
        await update.message.reply_text("Bugun harajat yo'q.")
        return

    text = "Bugungi harajatlar:\n"
    total = 0

    for cat, other, amount in rows:
        name = other if cat == "boshqalar" else cat
        text += f"{name}: {amount}\n"
        total += amount

    text += f"\nUmumiy: {total}"

    await update.message.reply_text(text)


# -------- MAIN --------
def main():
    init_db()
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("add", add_start)],
        states={
            SELECT_CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_category)],
            OTHER_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, other_type)],
            AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, amount)],
        },
        fallbacks=[]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("daily", daily))

    print("Bot ishga tushdi...")
    app.run_polling()


if __name__ == "__main__":

    main()
