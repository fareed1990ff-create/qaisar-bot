import os, json, random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters
from datetime import datetime

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

# ردود القيصر لما حدا يناديه - كل مرة جواب غير
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

def get_points(user_id):
    users = load_users()
    return users.get(str(user_id), {}).get("points", 0)

def add_point(user_id):
    users = load_users()
    uid = str(user_id)
    if uid not in users:
        users[uid] = {"points": 0, "last_msg": 0}
    users[uid]["points"] += 1
    save_users(users)
    return users[uid]["points"]

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

def make_progress(points, current, next_rank):
    if not next_rank:
        return "👑 وصلت لأعلى رتبة!\n[🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩] 100%"
    total = next_rank[1] - current[1]
    done = points - current[1]
    percent = int(done / total * 100) if total > 0 else 100
    filled = int(done / total * 10) if total > 0 else 10
    bar = "🟩" * filled + "⬜" * (10 - filled)
    left = next_rank[1] - points
    return f"[{bar}] {percent}%\n{done} / {total} نقطة\nضايلك {left} نقطة لـ {next_rank[2]} {next_rank[0]}"

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
    points = get_points(q.from_user.id)
    current, next_rank = get_rank(points)
    progress = make_progress(points, current, next_rank)
    text = f"🏆 <b>الرتب والمستويات</b>\n\nرتبتك: {current[2]} {current[0]}\nنقاطك: {points} نقطة\n\n📊 <b>عداد التقدم:</b>\n{progress}\n\n<b>كل الرتب:</b>\n"
    for name, req, emoji in RANKS:
        mark = "✅" if points >= req else "🔒"
        text += f"{mark} {emoji} {name} - {req} نقطة\n"
    text += "\n💡 كل رسالة = +1 نقطة"
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ رجوع", callback_data="back")]])
    try:
        await q.edit_message_caption(caption=text, parse_mode="HTML", reply_markup=kb)
    except:
        await q.edit_message_text(text=text, parse_mode="HTML", reply_markup=kb)

async def show_mycard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    points = get_points(q.from_user.id)
    current, next_rank = get_rank(points)
    name = q.from_user.first_name
    progress = make_progress(points, current, next_rank)
    text = f"👤 <b>بطاقتك</b>\n\nالاسم: {name}\nالرتبة: {current[2]} {current[0]}\nالنقاط: {points}\n\n📊 <b>عداد التقدم:</b>\n{progress}"
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ رجوع", callback_data="back")]])
    try:
        await q.edit_message_caption(caption=text, parse_mode="HTML", reply_markup=kb)
    except:
        await q.edit_message_text(text=text, parse_mode="HTML", reply_markup=kb)

async def back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    try:
        await q.edit_message_caption(caption="👑 <b>أهلا فيك في بوت القيصر</b>\n\nاختر من الأسفل:", parse_mode="HTML", reply_markup=main_keyboard())
    except:
        await q.edit_message_text(text="👑 <b>أهلا فيك في بوت القيصر</b>\n\nاختر من الأسفل:", parse_mode="HTML", reply_markup=main_keyboard())

async def welcome_new(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.new_chat_members:
        return
    for member in update.message.new_chat_members:
        if member.is_bot:
            continue
        mention = get_mention(member)
        current, _ = get_rank(0)
        await update.message.reply_text(f"👑 أهلا نورت يا {mention} 🔥\n\nأهلا فيك في مملكة القيصر 👑\nرتبتك: {current[2]} {current[0]}\nنقاطك: 0 نقطة 🌱\n\nاكتب /start عشان تشوف بطاقتك ✨")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    txt = update.message.text.strip()
    user_id = update.message.from_user.id
    if txt in ["رصيد", "رصيدك", "/رصيد"]:
        points = get_points(user_id)
        current, next_rank = get_rank(points)
        progress = make_progress(points, current, next_rank)
        await update.message.reply_text(f"👤 رصيدك: {points} نقطة\nرتبتك: {current[2]} {current[0]}\n\n📊 عداد التقدم:\n{progress}")
        return
    if txt.startswith("/"):
        return

    # اذا حدا نادى القيصر - يرد عليه بجواب عشوائي كل مرة
    lower_txt = txt.lower()
    if "قيصر" in lower_txt or "qaysar" in lower_txt or "qaisar" in lower_txt:
        reply = random.choice(QAYSAR_REPLIES)
        await update.message.reply_text(reply)

    # حماية سبام 3 ثواني
    users = load_users()
    uid = str(user_id)
    now = datetime.now().timestamp()
    last = users.get(uid, {}).get("last_msg", 0)
    if now - last < 3:
        return
    users[uid] = users.get(uid, {"points": 0, "last_msg": 0})
    users[uid]["last_msg"] = now
    save_users(users)
    old_points = get_points(user_id)
    old_rank, _ = get_rank(old_points)
    new_points = add_point(user_id)
    new_rank, _ = get_rank(new_points)
    if new_rank[0] != old_rank[0]:
        mention = get_mention(update.message.from_user)
        if update.message.chat.type in ["group", "supergroup"]:
            await update.message.reply_text(f"🎉 مبروووك يا {mention} 🔥🔥\n\nارتقيت لرتبة جديدة: {new_rank[2]} {new_rank[0]} 👑\nصار عندك {new_points} نقطة ✨\nاستمر يا بطل!")
        else:
            await update.message.reply_text(f"🎉 مبروك! ارتقيت لرتبة جديدة: {new_rank[2]} {new_rank[0]} 🔥")

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    points = get_points(update.effective_user.id)
    current, next_rank = get_rank(points)
    progress = make_progress(points, current, next_rank)
    await update.message.reply_text(f"👤 رصيدك: {points} نقطة\nرتبتك: {current[2]} {current[0]}\n\n📊 عداد التقدم:\n{progress}")

def main():
    print("Starting bot...")
    if not TOKEN:
        print("ERROR: BOT_TOKEN not found!")
        return
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("balance", balance))
    app.add_handler(CallbackQueryHandler(show_ranks, pattern="^ranks$"))
    app.add_handler(CallbackQueryHandler(show_mycard, pattern="^mycard$"))
    app.add_handler(CallbackQueryHandler(back, pattern="^back$"))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_new))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    from flask import Flask
    import threading
    flask_app = Flask(__name__)
    @flask_app.route("/")
    def home():
        return "Bot is running"
    port = int(os.environ.get("PORT", 10000))
    threading.Thread(target=lambda: flask_app.run(host="0.0.0.0", port=port), daemon=True).start()
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
