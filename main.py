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
    user_id = q.from_user.id
    points = context.user_data.get("points", 0)
    current, next_rank = get_rank(points)
    text = f"🏆 <b>الرتب والمستويات</b>\n\nرتبتك: {current[2]} {current[0]}\nنقاطك: {points} نقطة\n"
    if next_rank:
        text += f"ضايلك {next_rank[1]-points} نقطة للرتبة الجاية: {next_rank[2]} {next_rank[0]}\n\n"
    text += "<b>كل الرتب:</b>\n"
    for name, req, emoji in RANKS:
        mark = "✅" if points >= req else "🔒"
        text += f"{mark} {emoji} {name} - {req} نقطة\n"
    text += "\n💡 كل رسالة = +1 نقطة"
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ رجوع", callback_data="back")]])
    await q.edit_message_caption(caption=text, parse_mode="HTML", reply_markup=kb)

async def show_mycard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    points = context.user_data.get("points", 0)
    current, next_rank = get_rank(points)
    name = q.from_user.first_name
    if next_rank:
        prog = int((points - current[1]) / (next_rank[1] - current[1]) * 10) if next_rank[1] != current[1] else 10
        bar = "🟩" * prog + "⬜" * (10-prog)
        nxt = f"\nللرتبة الجاية: {next_rank[2]} {next_rank[0]} ({next_rank[1]-points} نقطة)\n{bar}"
    else:
        nxt = "\n👑 وصلت لأعلى رتبة!"
    text = f"👤 <b>بطاقتك</b>\n\nالاسم: {name}\nالرتبة: {current[2]} {current[0]}\nالنقاط: {points}\n{nxt}"
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ رجوع", callback_data="back")]])
    await q.edit_message_caption(caption=text, parse_mode="HTML", reply_markup=kb)

async def back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.edit_message_caption(caption="👑 <b>أهلا فيك في بوت القيصر</b>\n\nاختر من الأسفل:", parse_mode="HTML", reply_markup=main_keyboard())

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    txt = update.message.text.strip()
    if txt.startswith("/"):
        return
    now = datetime.now().timestamp()
    last = context.user_data.get("last_msg", 0)
    if now - last < 3:
        return
    context.user_data["last_msg"] = now
    old_points = context.user_data.get("points", 0)
    old_rank, _ = get_rank(old_points)
    new_points = old_points + 1
    context.user_data["points"] = new_points
    new_rank, _ = get_rank(new_points)
    if new_rank[0] != old_rank[0]:
        await update.message.reply_text(f"🎉 مبروك! ارتقيت لرتبة جديدة: {new_rank[2]} {new_rank[0]} 🔥")

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    points = context.user_data.get("points", 0)
    current, _ = get_rank(points)
    await update.message.reply_text(f"رصيدك : {points} نقطة\nرتبتك: {current[2]} {current[0]}")

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("balance", balance))
    app.add_handler(CommandHandler("رصيد", balance))
    app.add_handler(CallbackQueryHandler(show_ranks, pattern="^ranks$"))
    app.add_handler(CallbackQueryHandler(show_mycard, pattern="^mycard$"))
    app.add_handler(CallbackQueryHandler(back, pattern="^back$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    # للـ Render
    from flask import Flask
    import threading
    flask_app = Flask(__name__)
    @flask_app.route("/")
    def home(): return "Bot is running"
    threading.Thread(target=lambda: flask_app.run(host="0.0.0.0", port=10000)).start()
    app.run_polling()

if __name__ == "__main__":
    main()
