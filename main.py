def get_points(user_id):
    users = load_users()
    return users.get(str(user_id), {}).get("points", 0)

def add_points(user_id, amount):
    users = load_users()
    uid = str(user_id)
    if uid not in users:
        users[uid] = {"points": 0, "coins": 0}
    users[uid]["points"] = users[uid].get("points", 0) + amount
    save_users(users)
    return users[uid]["points"]

def get_coins(user_id):
    users = load_users()
    return users.get(str(user_id), {}).get("coins", 0)

def add_coins(user_id, amount):
    users = load_users()
    uid = str(user_id)
    if uid not in users:
        users[uid] = {"points": 0, "coins": 0}
    users[uid]["coins"] = users[uid].get("coins", 0) + amount
    save_users(users)
    return users[uid]["coins"]

def get_rank(points):
    rank = RANKS[0]
    for r in RANKS:
        if points >= r[1]:
            rank = r
    return rank

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(f"اهلا {user.first_name} 👑\nانا بوت القيصر.\nاكتب /رصيد لتشوف نقاطك\nاكتب /ترتيب لتشوف الابطال")

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    pts = get_points(user.id)
    coins = get_coins(user.id)
    name, need, emoji = get_rank(pts)
    await update.message.reply_text(f"👑 رصيدك يا {user.first_name}\n\n⭐ نقاطك: {pts}\n🪙 عملاتك: {coins}\n🏆 رتبتك: {emoji} {name}")

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = load_users()
    if not users:
        await update.message.reply_text("لسا ما في حدا جمع نقاط")
        return
    sorted_users = sorted(users.items(), key=lambda x: x[1].get("points", 0), reverse=True)[:10]
    text = "🏆 ترتيب الابطال 🏆\n\n"
    for i, (uid, data) in enumerate(sorted_users, 1):
        pts = data.get("points", 0)
        name, need, emoji = get_rank(pts)
        try:
            member = await context.bot.get_chat_member(update.effective_chat.id, int(uid))
            uname = member.user.first_name
        except:
            uname = f"لاعب {uid[:4]}"
        text += f"{i}. {uname} - {pts} نقطة - {emoji} {name}\n"
    await update.message.reply_text(text)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    text = update.message.text
    user = update.effective_user
    lower = text.lower()
    if "قيصر" in text or "qaysar" in lower or "qaisar" in lower:
        await update.message.reply_text(random.choice(QAYSAR_REPLIES))
        return
    if "احبك" in text or "بحبك" in text:
        add_points(user.id, 5)
        await update.message.reply_text("وانا بحبك اكتر ❤️ +5 نقاط")
        return
    add_points(user.id, 1)

async def daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    coins = add_coins(user.id, 50)
    await update.message.reply_text(f"🎁 اخدت مكافأتك اليومية!\n+50 عملة\nصار معك: {coins} عملة")

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("رصيد", balance))
    app.add_handler(CommandHandler("ترتيب", leaderboard))
    app.add_handler(CommandHandler("يومي", daily))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("Bot started...")
    app.run_polling()

if __name__ == "__main__":
    main()

def fix_arabic(text):
    try:
        return get_display(reshaper.reshape(text))
    except:
        return text

