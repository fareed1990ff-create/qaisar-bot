import os, json, random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters
from datetime import datetime
# ===== اضافة جديدة - للبطاقة صورة =====
from PIL import Image, ImageDraw, ImageFont
try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    HAS_ARABIC = True
except:
    HAS_ARABIC = False

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

# ===== اضافة جديدة - العملات الذهبية =====
def get_user_data(user_id):
    users = load_users()
    u = users.get(str(user_id), {})
    return {
        "points": u.get("points", 0),
        "coins": u.get("coins", 0),
        "messages": u.get("messages", 0),
        "last_msg": u.get("last_msg", 0)
    }

def get_coins(user_id):
    return get_user_data(user_id)["coins"]

def add_point(user_id):
    users = load_users()
    uid = str(user_id)
    if uid not in users:
        users[uid] = {"points": 0, "last_msg": 0, "coins": 0, "messages": 0}
    # تأمين للحسابات القديمة اللي ما فيها coins
    if "coins" not in users[uid]:
        users[uid]["coins"] = 0
    if "messages" not in users[uid]:
        users[uid]["messages"] = 0
    users[uid]["points"] += 1
    users[uid]["messages"] += 1
    # كل 10 رسائل = 1 عملة ذهبية
    if users[uid]["messages"] % 10 == 0:
        users[uid]["coins"] += 1
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

# ===== اضافة جديدة - توليد بطاقة الرصيد صورة =====
def fix_arabic(t):
    t = str(t)
    if HAS_ARABIC:
        return get_display(arabic_reshaper.reshape(t))
    return t

def create_balance_card(user_id, name):
    data = get_user_data(user_id)
    points, coins = data["points"], data["coins"]
    current, next_rank = get_rank(points)
    rank_name = current[0]
    next_points = next_rank[1] if next_rank else points
    percent = int(points / next_points * 100) if next_points else 100
    if percent > 100: percent = 100

    W, H = 800, 1100
    if os.path.exists("background.jpg"):
        img = Image.open("background.jpg").convert("RGB").resize((W, H))
    else:
        img = Image.new("RGB", (W, H), (12, 12, 14))
    draw = ImageDraw.Draw(img)
    gold, white, dark = (212,175,55), (255,255,255), (45,45,45)
    try:
        fb = ImageFont.truetype("Cairo-Bold.ttf", 62)
        fm = ImageFont.truetype("Cairo-Bold.ttf", 38)
        fs = ImageFont.truetype("Cairo-Bold.ttf", 30)
    except:
        try:
            fb = ImageFont.truetype("DejaVuSans-Bold.ttf", 62)
            fm = ImageFont.truetype("DejaVuSans-Bold.ttf", 38)
            fs = ImageFont.truetype("DejaVuSans.ttf", 30)
        except:
            fb = fm = fs = ImageFont.load_default()

    def center(y, txt, font, fill):
        t = fix_arabic(txt)
        w = draw.textbbox((0,0), t, font=font)[2]
        draw.text(((W-w)//2, y), t, font=font, fill=fill)

    draw.rectangle([25,25,W-25,H-25], outline=gold, width=4)
    draw.rectangle([40,40,W-40,H-40], outline=(120,100,30), width=1)
    center(110, "👑", fb, gold)
    center(200, "القيصر", fm, gold)
    center(260, "بطاقة رصيد القيصر", fs, white)
    center(350, name, fb, gold)
    # صندوق العملات الذهبية فوق النقاط
    draw.rounded_rectangle([100,480,W-100,580], radius=20, fill=(30,28,15), outline=gold, width=2)
    center(505, f"🪙 العملات الذهبية: {coins}", fm, gold)
    center(610, f"⭐ النقاط: {points} نقطة", fm, white)
    center(670, f"🎖️ الرتبة: {rank_name}", fm, white)
    center(780, f"التقدم: {percent}%", fs, gold)
    draw.rounded_rectangle([100,830,W-100,875], radius=20, fill=dark)
    bw = int((W-200)*percent/100)
    if bw>0:
        draw.rounded_rectangle([100,830,100+bw,875], radius=20, fill=gold)
    center(895, f"{points} / {next_points} نقطة", fs, white)
    center(960, "جاوب على الاسئلة عشان تجمع ذهب!", fs, gold)
    path = f"balance_{user_id}.png"
    img.save(path)
    return path

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
    coins = get_coins(q.from_user.id)  # اضافة - عرض العملات
    current, next_rank = get_rank(points)
    progress = make_progress(points, current, next_rank)
    text = f"🏆 <b>الرتب والمستويات</b>\n\nرتبتك: {current[2]} {current[0]}\nنقاطك: {points} نقطة\n🪙 عملاتك الذهبية: {coins}\n\n📊 <b>عداد التقدم:</b>\n{progress}\n\n<b>كل الرتب:</b>\n"
    for name, req, emoji in RANKS:
        mark = "✅" if points >= req else "🔒"
        text += f"{mark} {emoji} {name} - {req} نقطة\n"
    text += "\n💡 كل رسالة = +1 نقطة | كل 10 رسائل = +1 🪙"
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ رجوع", callback_data="back")]])
    try:
        await q.edit_message_caption(caption=text, parse_mode="HTML", reply_markup=kb)
    except:
        await q.edit_message_text(text=text, parse_mode="HTML", reply_markup=kb)

async def show_mycard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    # اضافة - هسا بطاقتي بتبعت صورة مش بس نص
    try:
        card = create_balance_card(q.from_user.id, q.from_user.first_name)
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ رجوع", callback_data="back")]])
        with open(card, "rb") as f:
            await q.message.reply_photo(photo=f, caption=f"بطاقتك يا {q.from_user.first_name} 👑", reply_markup=kb)
        try: os.remove(card)
        except: pass
        return
    except Exception as e:
        print("card error:", e)
    # اذا فشلت الصورة، بيرجع للنص القديم تبعك
    points = get_points(q.from_user.id)
    coins = get_coins(q.from_user.id)
    current, next_rank = get_rank(points)
    name = q.from_user.first_name
    progress = make_progress(points, current, next_rank)
    text = f"👤 <b>بطاقتك</b>\n\nالاسم: {name}\nالرتبة: {current[2]} {current[0]}\nالنقاط: {points}\n🪙 العملات الذهبية: {coins}\n\n📊 <b>عداد التقدم:</b>\n{progress}"
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
        # اضافة - رصيد هسا ببعت صورة البطاقة
        try:
            card = create_balance_card(user_id, update.message.from_user.first_name)
            with open(card, "rb") as f:
                await update.message.reply_photo(photo=f, caption=f"بطاقتك يا {update.message.from_user.first_name} 👑")
            try: os.remove(card)
            except: pass
            return
        except Exception as e:
            print("card error:", e)
        points = get_points(user_id)
        coins = get_coins(user_id)
        current, next_rank = get_rank(points)
        progress = make_progress(points, current, next_rank)
        await update.message.reply_text(f"👤 رصيدك: {points} نقطة\n🪙 عملاتك: {coins}\nرتبتك: {current[2]} {current[0]}\n\n📊 عداد التقدم:\n{progress}")
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
    # تأمين للحسابات القديمة
    if "coins" not in users[uid]:
        users[uid]["coins"] = 0
    if "messages" not in users[uid]:
        users[uid]["messages"] = 0
    users[uid]["last_msg"] = now
    save_users(users)
    old_points = get_points(user_id)
    old_rank, _ = get_rank(old_points)
    new_points = add_point(user_id)
    new_rank, _ = get_rank(new_points)
    # اضافة - اذا اخذ عملة جديدة، نبهه
    new_data = get_user_data(user_id)
    if new_data["messages"] % 10 == 0:
        await update.message.reply_text(f"🎉 +1 🪙 عملة ذهبية! صار معك {new_data['coins']} عملة\nاكتب رصيد وشوف بطاقتك")
    if new_rank[0] != old_rank[0]:
        mention = get_mention(update.message.from_user)
        if update.message.chat.type in ["group", "supergroup"]:
            await update.message.reply_text(f"🎉 مبروووك يا {mention} 🔥🔥\n\nارتقيت لرتبة جديدة: {new_rank[2]} {new_rank[0]} 👑\nصار عندك {new_points} نقطة ✨\nاستمر يا بطل!")
        else:
            await update.message.reply_text(f"🎉 مبروك! ارتقيت لرتبة جديدة: {new_rank[2]} {new_rank[0]} 🔥")

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # اضافة - /balance كمان صار صورة
    try:
        card = create_balance_card(update.effective_user.id, update.effective_user.first_name)
        with open(card, "rb") as f:
            await update.message.reply_photo(photo=f, caption=f"بطاقتك يا {update.effective_user.first_name} 👑")
        try: os.remove(card)
        except: pass
        return
    except Exception as e:
        print("card error:", e)
    points = get_points(update.effective_user.id)
    coins = get_coins(update.effective_user.id)
    current, next_rank = get_rank(points)
    progress = make_progress(points, current, next_rank)
    await update.message.reply_text(f"👤 رصيدك: {points} نقطة\n🪙 عملاتك: {coins}\nرتبتك: {current[2]} {current[0]}\n\n📊 عداد التقدم:\n{progress}")

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
