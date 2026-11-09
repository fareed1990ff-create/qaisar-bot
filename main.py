import os
import json
import random
import io
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from PIL import Image, ImageDraw, ImageFont
import arabic_reshaper
from bidi.algorithm import get_display

TOKEN = os.environ.get("BOT_TOKEN")
DATA_FILE = "users.json"

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
    center_at(250, 260, str(points), font_big, (212, 175, 55))

    center_at(600, 200, "الرتبة", font_mid, (200, 200, 200))
    center_at(600, 260, rank_name, font_big, (255, 255, 255))

    center_at(950, 200, "الترتيب", font_mid, (200, 200, 200))
    center_at(950, 260, f"#{rank}", font_big, (212, 175, 55))

    # 3. الذهب تحت بصندوق عريض - زي المربع الاحمر
    d.rounded_rectangle([60, 430, W-60, 620], radius=30, fill=(212, 175, 55))
    d.rounded_rectangle([70, 440, W-70, 610], radius=25, fill=(60, 40, 5))
    center(460, "العملات الذهبية", font_mid, (212, 175, 55))
    center(520, str(coins), font_big, (255, 215, 0))

    bio = io.BytesIO()
    img.save(bio, format="PNG")
    bio.seek(0)
    return bio

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("اهلا فيك ببوت قيصر 👑\nاكتب اي شي واجمع نقاط وذهب!\nكل 10 رسايل = 1 ذهبة 🪙\n/balance - شوف بطاقتك\n/leaderboard - ترتيب الأبطال")

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    users = load_users()
    data = users.get(str(user.id), {"points": 0, "coins": 0, "name": user.first_name})
    points = data.get("points", 0)
    coins = data.get("coins", 0)
    sorted_users = sorted(users.items(), key=lambda x: x[1].get("points", 0), reverse=True)
    rank = 1
    for uid, udata in sorted_users:
        if uid == str(user.id):
            break
        rank += 1
    card = make_card(user.first_name, points, coins, rank)
    await update.message.reply_photo(photo=card, caption=f"👑 بطاقتك يا {user.first_name}")

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = load_users()
    sorted_users = sorted(users.items(), key=lambda x: x[1].get("points", 0), reverse=True)[:10]
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
    if "قيصر" in text or "qaysar" in lower or "qaisar" in lower:
        await update.message.reply_text(random.choice(["هلا بالقيصر 👑", "قيصر موجود 😎", "نعم يا قيصر؟ 👑"]))
        return
    if "احبك" in text or "بحبك" in text:
        await update.message.reply_text("وانا بحبك اكتر ❤️")
        return
    points, got_coin = add_points(user.id, 1)
    users = load_users()
    uid = str(user.id)
    if uid in users:
        users[uid]["name"] = user.first_name
        save_users(users)
    if got_coin:
        await update.message.reply_text(f"🪙 مبروووك! أخذت 1 عملة ذهبية - نقاطك: {points}")
def main():
    keep_alive()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("balance", balance))
    app.add_handler(CommandHandler("leaderboard", leaderboard))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
