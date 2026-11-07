import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters
from datetime import datetime

TOKEN = os.environ.get("BOT_TOKEN")

RANKS = [
    ("عضو جديد", 0, "🌱"),
    ("عضو نشيط", 50, "🔥"),
    ("عضو مميز", 150, "⭐"),
    ("عضو ذهبي", 300, "🥇"),
    ("عضو بلاتيني", 500, "💎"),
    ("قائد فريق", 800, "👑"),
    ("نائب القيصر", 1200, "⚔️"),
    ("القيصر", 1800, "👑"),
    ("أسطورة", 2500, "🌟"),
    ("خبير استراتيجي", 3500, "🧠"),
]

def get_rank(points):
    current = RANKS[0]
    next_rank = None
    for i, r in enumerate(RANKS):
        if points >= r[1]:
            current = r
            if i + 1 < len(RANKS):
                next_rank = RANKS[i+1]
        else:
            break
    return current, next_rank

def main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏆 الرتب والمستويات", callback_data="ranks")],
        [InlineKeyboardButton("👤 بطاقتي", callback_data="mycard")],
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "👑 <b>أهلا فيك في بوت القيصر</b>\n\nاختر من الأسفل:"
    if os.path.exists("banner.jpg"):
        with open("banner.jpg", "rb") as f:
            await update.message.reply_photo(photo=f, caption=text, parse_mode="HTML", reply_markup=main_keyboard())
    else:
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=main_keyboard())

async def show_ranks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    points = context.user_data.get("points", 0)
    current, next_rank = get_rank(points)
    text = f"🏆 <b>الرتب والمستويات</b>\n\nرتبتك: {current[2]} {current[0]}\nنقاطك: {points} نقطة\n"
