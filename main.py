import os
import json
import random
import copy
import io
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from PIL import Image, ImageDraw, ImageFont, ImageOps
import arabic_reshaper
from bidi.algorithm import get_display

TOKEN = os.environ.get("BOT_TOKEN")
import urllib.request
JSONBIN_ID = (os.environ.get("JSONBIN_ID") or "").strip().strip('"').strip("'")
JSONBIN_KEY = (os.environ.get("JSONBIN_KEY") or "").strip().strip('"').strip("'")
print(f"DEBUG ID={JSONBIN_ID} KEY={JSONBIN_KEY}")

# هاي عشان Render المجاني ما يطفي البوت - بيفتح بورت وهمي
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running")
    def log_message(self, *args):
        pass

def keep_alive():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()

# هاي بس للصورة، مش للنص 
def fix_arabic_img(text):
    try:
        reshaped = arabic_reshaper.reshape(str(text))
        return get_display(reshaped)
    except:
        return str(text)
_LOCK = threading.Lock()
USERS = {}
_LOADED_OK = False

def load_users_once():
    global USERS, _LOADED_OK
    try:
        req = urllib.request.Request(
            f"https://api.jsonbin.io/v3/b/{JSONBIN_ID}/latest",
            headers={"X-Master-Key": JSONBIN_KEY, "Cache-Control": "no-cache"}
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            rec = json.loads(r.read()).get("record", {})
            if rec == {"test": 1}:
                rec = {}
            USERS = copy.deepcopy(rec) if isinstance(rec, dict) else {}
            USERS.pop("test", None)
            _LOADED_OK = True
            print(f"Loaded {len(USERS)} users from JSONBin")
    except Exception as e:
        print(f"Load error: {e}")
        _LOADED_OK = False

def save_users():
    if not _LOADED_OK:
        print("Skip save - not loaded yet")
        return
    if not USERS:
        print("Skip save - USERS empty, protecting data")
        return
    try:
        data = json.dumps(USERS).encode()
        req = urllib.request.Request(
            f"https://api.jsonbin.io/v3/b/{JSONBIN_ID}",
            data=data, method="PUT",
            headers={"Content-Type": "application/json", "X-Master-Key": JSONBIN_KEY}
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            r.read()
    except Exception as e:
        print(f"Save error: {e}")

def add_points(user_id, amount):
    with _LOCK:
        uid = str(user_id)
        if uid not in USERS:
            USERS[uid] = {"points": 0, "name": "", "coins": 0, "msg_count": 0}
        u = USERS[uid]
        u.setdefault("coins", 0)
        u.setdefault("msg_count", 0)
        u["points"] += amount
        u["msg_count"] += 1
        got_coin = False
        if u["msg_count"] >= 50:
            u["coins"] += 1
            u["msg_count"] = 0
            got_coin = True
        save_users()
        return u["points"], got_coin

def add_coins(user_id, amount):
    with _LOCK:
        uid = str(user_id)
        if uid not in USERS:
            USERS[uid] = {"points": 0, "name": "", "coins": 0, "msg_count": 0}
        USERS[uid].setdefault("coins", 0)
        USERS[uid]["coins"] += amount
        save_users()
        return USERS[uid]["coins"]

def get_user(user_id):
    return USERS.get(str(user_id), {"points": 0, "coins": 0, "name": ""})

def make_card(name, points, coins, rank):
    W, H = 1200, 700
    img = Image.new("RGB", (W, H), (15, 10, 5))
    d = ImageDraw.Draw(img)
    d.rectangle([20, 20, W-20, H-20], outline=(212, 175, 55), width=5)

    if points < 100:
        rank_name = "عضو جديد"
    elif points < 300:
        rank_name = "مبتدئ"
    elif points < 600:
        rank_name = "بطل"
    elif points < 1000:
        rank_name = "نجم صاعد"
    elif points < 1600:
        rank_name = "محارب ذهبي"
    elif points < 2400:
        rank_name = "قائد"
    elif points < 3600:
        rank_name = "أسطورة"
    elif points < 5000:
        rank_name = "النخبة"
    elif points < 7000:
        rank_name = "محلل"
    else:
        rank_name = "خبير استراتيجي"
    try:
        import urllib.request
        if not os.path.exists("Amiri-Regular.ttf"):
            urllib.request.urlretrieve("https://github.com/google/fonts/raw/main/ofl/amiri/Amiri-Regular.ttf", "Amiri-Regular.ttf")
        font_big = ImageFont.truetype("Amiri-Regular.ttf", 70)
        font_mid = ImageFont.truetype("Amiri-Regular.ttf", 45)
    except:
        font_big = ImageFont.load_default()
        font_mid = font_big

    def center(y, text, font, color=(255, 255, 255)):
        t = str(text)
        bbox = d.textbbox((0, 0), t, font=font)
        w = bbox[2] - bbox[0]
        d.text(((W - w) // 2, y), t, font=font, fill=color)

    def center_at(x_center, y, text, font, color):
        t = str(text)
        bbox = d.textbbox((0, 0), t, font=font)
        w = bbox[2] - bbox[0]
        d.text((x_center - w//2, y), t, font=font, fill=color)

    # 1. الاسم فوق
    center(50, name, font_big, (212, 175, 55))
    # 2. 3 خانات جنب بعض بالعرض
    center_at(250, 200, "النقاط", font_mid, (200, 200, 200))
    center_at(250, 260, str(points), font_big, (90, 180, 255))

    center_at(600, 200, "الرتبة", font_mid, (200, 200, 200))
    center_at(600, 235, rank_name, font_big, (190, 140, 255))

    center_at(950, 200, "الترتيب", font_mid, (200, 200, 200))
    center_at(950, 260, f"#{rank}", font_big, (212, 175, 55))
    # --- عداد الرتبة هون ---
    limits = [0, 100, 300, 600, 1000, 1600, 2400, 3600, 5000, 7000]
    # وين انت هسا ووين الرتبة الجاية
    cur_limit = 0
    next_limit = 100
    for i, lim in enumerate(limits):
        if points >= lim:
            cur_limit = lim
            if i + 1 < len(limits):
                next_limit = limits[i+1]
            else:
                next_limit = lim
        else:
            break
    if points >= 7000:
        percent = 100
    else:
        percent = int((points - cur_limit) / (next_limit - cur_limit) * 100)

    # الشريط - بنفس مكان الأحمر
    bar_x1, bar_y1, bar_x2, bar_y2 = 250, 410, 950, 442
    d.rounded_rectangle([bar_x1, bar_y1, bar_x2, bar_y2], radius=17, fill=(45, 35, 10), outline=(212, 175, 55), width=3)
    fill_w = int((bar_x2 - bar_x1) * percent / 100)
    if fill_w > 10:
        d.rounded_rectangle([bar_x1+3, bar_y1+3, bar_x1+fill_w-3, bar_y2-3], radius=14, fill=(212, 175, 55))
    center(440, f"{percent}%  -  {points} / {next_limit}", font_mid, (255, 255, 255))
    # 3. الذهب تحت بصندوق عريض - زي المربع الاحمر
    d.rounded_rectangle([300, 510, W-300, 610], radius=30, fill=(212, 175, 55))
    d.rounded_rectangle([310, 520, W-310, 600], radius=25, fill=(60, 40, 5))
    center(528, "العملات الذهبية", font_mid, (212, 175, 55))
    center(580, str(coins), font_big, (255, 215, 0))

    bio = io.BytesIO()
    img.save(bio, format="PNG")
    bio.seek(0)
    return bio

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    keyboard = [
        [InlineKeyboardButton("🪙 العملات الذهبية", callback_data="coins_info"),
         InlineKeyboardButton("🎮 قريبا", callback_data="soon")],
        [InlineKeyboardButton("💰 رصيدي", callback_data="balance"),
         InlineKeyboardButton("🏆 ترتيب الأبطال", callback_data="leaderboard")]
    ]
    markup = InlineKeyboardMarkup(keyboard)
    caption = f"👑 أهلين فيك يا {user.first_name} 🔥\nنورت مملكة القيصر!"
    img = Image.open("main.jpg")
    img = ImageOps.fit(img, (1080, 1350), Image.LANCZOS)
    bio = io.BytesIO()
    img.save(bio, format="JPEG")
    bio.seek(0)
    try:
        await update.message.reply_photo(photo=bio, caption=caption, reply_markup=markup)
    except:
        await update.message.reply_text(caption, reply_markup=markup)
async def buttons_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    data = USERS.get(str(user.id), {"points": 0, "coins": 0})
    points = data.get("points", 0)
    coins = data.get("coins", 0)
    if query.data == "balance":
        card = make_card(user.first_name, points, coins, 1)
        await query.message.reply_photo(photo=card, caption=f"رصيدك: {points} نقطة | {coins} عملة 🪙")
    elif query.data == "leaderboard":
        sorted_users = sorted(USERS.items(), key=lambda x: x[1].get("points", 0), reverse=True)[:10]
        text = "🏆 ترتيب الأبطال:\n\n"
        for i, (uid, udata) in enumerate(sorted_users, 1):
            text += f"{i}. {udata.get('name', 'بطل')} - {udata.get('points', 0)} نقطة\n"
        try:
            await query.message.reply_photo(photo="https://raw.githubusercontent.com/fareed1990ff/qaisar-bot/main/ranks.jpg", caption=text)
        except:
            await query.message.reply_text(text)
    elif query.data == "coins_info":
        try:
            await query.message.reply_photo(photo="https://raw.githubusercontent.com/fareed1990ff/qaisar-bot/main/coins.jpg", caption=f"معك {coins} عملة ذهبية 🪙\nكل 50 رسالة = 1 عملة")
        except:
            await query.message.reply_text(f"معك {coins} عملة ذهبية 🪙")
    elif query.data == "rank":
        await query.message.reply_text(f"نقاطك: {points} 🔥\nاستمر عشان تصعد للرتبة الأعلى!")
    elif query.data == "rules":
       await query.message.reply_text("📜 القوانين:\n1. كل رسالة = نقطة\n2. كل 50 رسالة = 1 عملة ذهبية\n3. ممنوع السب والشتم\n4. استمتع واصعد للصدارة 👑")
    elif query.data == "soon":
        await query.message.reply_text("🎮 قريبا... استنونا 🔥")
async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
        
    user = update.effective_user
    points, got_coin = add_points(user.id, 1)
    USERS[str(user.id)]["name"] = user.first_name
    data = USERS.get(str(user.id), {"points": 0, "coins": 0, "name": user.first_name})
    coins = data.get("coins", 0)
    sorted_users = sorted(USERS.items(), key=lambda x: x[1].get("points", 0), reverse=True)
    rank = 1
    for uid, udata in sorted_users:
        if uid == str(user.id):
            break
        rank += 1
    card = make_card(user.first_name, points, coins, rank)
    await update.message.reply_photo(photo=card, caption=f"👑 بطاقتك يا {user.first_name}")

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sorted_users = sorted(USERS.items(), key=lambda x: x[1].get("points", 0), reverse=True)[:10]
    text = "🏆 ترتيب الأبطال:\n\n"
    for i, (uid, data) in enumerate(sorted_users, 1):
        name = data.get("name", "لاعب") or "لاعب"
        pts = data.get("points", 0)
        emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "▫️"
        text += f"{emoji} {i}. {name} - {pts} نقطة\n"
    await update.message.reply_text(text)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    text = update.message.text
    user = update.effective_user
    lower = text.lower()
    points, got_coin = add_points(user.id, 1)
    USERS[str(user.id)]["name"] = user.first_name
    if got_coin:
        await update.message.reply_text(f"🪙 مبروووك! أخذت 1 عملة ذهبية - نقاطك: {points}")
    if "قيصر" in text or "qaysar" in lower or "qaisar" in lower:
        replies = [
            "نعم؟ القيصر موجود 👑",
            "أمرني يا بطل، القيصر هون 🔥",
            "هلا هلا، ناديتني؟ 😎",
            "القيصر سامعك، شو بدك؟",
            "أنا هون، لا تخاف 😂👑",
            "نعم نعم، القيصر بالخدمة",
            "شو في؟ حد نادى القيصر؟ 👀",
            "أهلين بالبطل، شو الأخبار؟",
            "القيصر موجود، احكي يا معلم",
            "عيون القيصر، أمرني",
            "وصلت وصلت، شو القصة؟ 🔥",
            "نعم يا ملك، القيصر معك",
            "هلا والله، نورت يا بطل",
            "القيصر هون، لا حد يزعج البطل",
            "سمعت اسمي؟ أنا جاهز 👑",
            "احكي احكي، القيصر سامعك",
            "يا هلا، القيصر وصل",
            "أنا القيصر، مين بده خدمة؟ 😎",
            "نعم؟ بدك نقاط ولا بدك ذهب؟ 💰",
            "القيصر لا ينام، أنا هون 😂"
        ]
        await update.message.reply_text(random.choice(replies))
        return
        if "احبك" in text or "بحبك" in text or "اعشقك" in text or "بموت فيك" in text:
            replies_love = [
            "وأنا بموت فيك يا قلبي ❤️",
            "القيصر كمان بيحبك، يا روحي 😍",
            "قلبي داب خلص، شو هالحب هاد؟ ❤️",
            "وأنا بحبك أكتر، لا تغار 😘",
            "عيونك الحلوة، القيصر صار أحمر خجلان 🙈❤️",
            "حبك ولع قلبي يا بطل 🔥❤️",
            "وأنا بعشقك، بس لا تحكي لحد 🤫❤️",
            "القيصر وقع بالحب خلص، شو نعمل؟ 😍",
            "انت حبيبي وروحي وكل دنيتي ❤️",
            "بحبك قد البحر وقد السما ❤️",
            "قلبي صار يدق بسرعة، وقف 😂❤️",
            "وأنا بحبك، تعال خد حضن 🤗❤️",
            "انت أغلى واحد عند القيصر 👑❤️",
            "حبك لحاله بيكفي يخليني أطير 😍",
            "وأنا بموت فيك، لا تتركني ❤️"
        ]
        await update.message.reply_text(random.choice(replies_love))
        return
    async def is_admin(update, context):
     try:
        member = await context.bot.get_chat_member(update.effective_chat.id, update.effective_user.id)
        return member.status in ["administrator", "creator"]
     except:
        return False

async def kick_user(update, context):
    if update.effective_chat.type == "private":
        await update.message.reply_text("❌ هاد الأمر بس بالجروب")
        return
    if not await is_admin(update, context):
        await update.message.reply_text("❌ بس الأدمن بيقدر يطير")
        return
    if not update.message.reply_to_message:
        await update.message.reply_text("❌ رد على رسالة الشخص واكتب /طير")
        return
    target = update.message.reply_to_message.from_user
    try:
        await context.bot.ban_chat_member(update.effective_chat.id, target.id)
        await context.bot.unban_chat_member(update.effective_chat.id, target.id)
        await update.message.reply_text(f"🦅 طاااار {target.first_name} برا الجروب 😂👋")
    except:
        await update.message.reply_text("❌ ما قدرت أطيره، تأكد اني أدمن")

async def mute_user(update, context):
    if not update.message.reply_to_message:
        await update.message.reply_text("رد على رسالة الشخص اللي بدك تكتمه")
        return

    # تشخيص - عشان نشوف حالتك
    try:
        member = await context.bot.get_chat_member(update.effective_chat.id, update.effective_user.id)
    except Exception as e:
        await update.message.reply_text(f"خطأ بفحص المشرف: {e}")
        return

    if member.status not in ["administrator", "creator"]:
        await update.message.reply_text("انت مش مشرف عندي")
        return

    target = update.message.reply_to_message.from_user
    try:
        from telegram import ChatPermissions
        await context.bot.restrict_chat_member(update.effective_chat.id, target.id, ChatPermissions(can_send_messages=False))
        await update.message.reply_text(f"😁 تم كتم {target.first_name}")
    except Exception as e:
        await update.message.reply_text(f"❌ ما قدرت اكتمه، تأكد اني أدمن: {e}")
async def unmute_user(update, context):
    if not update.message.reply_to_message:
        await update.message.reply_text("رد على رسالة الشخص اللي بدك تفك عنه")
        return

    try:
        member = await context.bot.get_chat_member(update.effective_chat.id, update.effective_user.id)
    except Exception as e:
        await update.message.reply_text(f"خطأ بفحص المشرف: {e}")
        return

    if member.status not in ["administrator", "creator"]:
        await update.message.reply_text("انت مش مشرف عندي")
        return

    target = update.message.reply_to_message.from_user
    try:
        from telegram import ChatPermissions
        await context.bot.restrict_chat_member(update.effective_chat.id, target.id, ChatPermissions(can_send_messages=True, can_send_audios=True, can_send_documents=True, can_send_photos=True, can_send_videos=True, can_send_video_notes=True, can_send_voice_notes=True, can_send_polls=True, can_send_other_messages=True, can_add_web_page_previews=True))
        await update.message.reply_text(f"🔊 تم فك كتم {target.first_name}")
    except Exception as e:
        await update.message.reply_text(f"❌ ما قدرت افك عنه: {e}")
def main():
    keep_alive()
    global USERS
    load_users_once()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Regex(r"^ترتيب$"), leaderboard))
    app.add_handler(MessageHandler(filters.Regex("^رصيد$"), balance))
    app.add_handler(MessageHandler(filters.Regex(r"^طير$"), kick_user))
    app.add_handler(MessageHandler(filters.Regex(r"^اسكت$"), mute_user))
    app.add_handler(MessageHandler(filters.Regex(r"^احكي$"), unmute_user))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(buttons_handler))
    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
