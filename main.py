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

def get_mention(user):
    if user.username:
        return f"@{user.username}"
    return f"{user.first_name}"

# --- العداد ---
def make_progress(points, current, next_rank):
    if not next_rank:
        return "👑 وصلت لأعلى رتبة!\n[🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩] 100%"
    total = next_rank[1] - current[1]
    done = points - current[1]
    percent = int(done / total * 100) if total > 0 else 100
    filled
