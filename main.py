import os
import json
import random
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

try:
    from arabic_reshaper import reshaper
    from bidi.algorithm import get_display
    HAS_ARABIC = True
except:
    HAS_ARABIC = False

TOKEN = os.environ.get("BOT_TOKEN")
DATA_FILE = "users.json"

def fix_arabic(text):
    if not HAS_ARABIC:
        return text
    try:
        return get_display(reshaper.reshape(text))
    except:
        return text

def load_users():
    if not os.path.exists(DATA_FILE):
        return {}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_users(users):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

def add_points(user_id, amount):
    users = load_users()
    uid = str(user_id)
    if uid not in users:
        users[uid] = {"points": 0, "name": "", "coins": 0, "msg_count": 0}
    if "coins" not in users[uid]:
        users[uid]["coins"] = 0
    if "msg_count" not in users[uid]:
        users[uid]["msg_count"] = 0
    users[uid]["points"] += amount
    users[uid]["msg_count"] += 1
    # كل 10 رسائل = 1 ذهبة
    if users[uid]["msg_count"] >= 10:
        users[uid]["coins"] += 1
        users[uid]["msg_count"] = 0
        save_users(users)
        return users[uid]["points"], True
    save_users(users)
    return users[uid]["points"], False

def add_coins(user_id, amount):
    users = load_users()
    uid = str(user_id)
    if uid not in users:
        users[uid] = {"points": 0, "name": "", "coins": 0, "msg_count": 0}
    if "coins" not in users[uid]:
        users[uid]["coins"] = 0
    users[uid]["coins"] += amount
    save_users(users)
    return users[uid]["coins"]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(fix_arabic("اهلا فيك ببوت قيصر 👑\nاكتب اي شي واجمع نقاط وذهب!\n/يومي - مكافأة يومية\n/رصيدي - شوف رصيدك"))

async def daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    coins = add_coins(user.id, 2)
    await update.message.reply_text(fix_arabic(f"🎁 مكافأتك اليومية: 2 عملة ذهبية\nصار معك: {coins} 🪙"))

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    users = load_users()
    uid = str(user.id)
    data = users.get(uid, {"points": 0, "coins": 0})
    await update.message.reply_text(fix_arabic(f"👑 رصيدك يا {user.first_name}\n⭐ نقاطك: {data.get('points', 0)}\n🪙 ذهبك: {data.get('coins', 0)}"))

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = load_users()
    sorted_users = sorted(users.items(), key=lambda x: x[1].get("points", 0), reverse=True)[:10]
    text = "🏆 ترتيب الأبطال:\n\n"
    for i, (uid, data) in enumerate(sorted_users, 1):
        name = data.get("name", "لاعب") or "لاعب"
        pts = data.get("points", 0)
        emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "▫️"
        text += f"{emoji} {i}. {name} - {pts} نقطة\n"
    await update.message.reply_text(fix_arabic(text))

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    text = update.message.text
    user = update.effective_user
    lower = text.lower()

    if "قيصر" in text or "qaysar" in lower or "qaisar" in lower:
        await update.message.reply_text(random.choice(["هلا بالقيصر 👑", "قيصر موجود 😎", "نعم يا قيصر؟ 👑"]))
        return

    if "احبك" in text or "بحبك" in text:
        await update.message.reply_text(random.choice(["وانا بحبك اكتر ❤️", "احبك يا قيصر 👑"]))
        return

    points, got_coin = add_points(user.id, 1)

    users = load_users()
    uid = str(user.id)
    if uid in users:
        users[uid]["name"] = user.first_name
        save_users(users)

    if got_coin:
        await update.message.reply_text(fix_arabic(f"🪙 مبروووك! أخذت 1 عملة ذهبية\nنقاطك: {points}"))

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("يومي", daily))
    app.add_handler(CommandHandler("رصيدي", balance))
    app.add_handler(CommandHandler("ترتيب", leaderboard))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
