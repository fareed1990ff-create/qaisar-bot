import os, json, random, urllib.request, time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
import arabic_reshaper
from bidi.algorithm import get_display

TOKEN = os.environ.get("BOT_TOKEN")
DATA_FILE = "users.json"

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

QAYSAR_REPLIES = [
    "نعم؟ انا هون 👑",
    "عيوني، شو بدك؟",
    "هلا فيك، ناديت علي؟",
    "انا موجود، احكي",
    "أمرني، شو في؟",
    "سامعك، شو بدك؟",
    "هلا هلا، شو في جديد؟",
    "نعم يا بطل، انا سامعك 🔥",
    "احكي، القيصر موجود 👑",
    "عيون القيصر، تفضل",
    "اهلا اهلا، شو صار معك؟",
    "موجود موجود، لا تخاف 😎",
]

def load_users():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_users(users):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False)

def
