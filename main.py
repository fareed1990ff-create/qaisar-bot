import os
import json
import random
import copy
import io
import threading
import time
import asyncio
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from PIL import Image, ImageDraw, ImageFont, ImageOps
import arabic_reshaper
from bidi.algorithm import get_display

TOKEN = os.environ.get("BOT_TOKEN")
import urllib.request
SUPABASE_URL = (os.environ.get("SUPABASE_URL") or "").strip().rstrip("/")
SUPABASE_KEY = (os.environ.get("SUPABASE_KEY") or "").strip()
print(f"DEBUG SUPABASE_URL={SUPABASE_URL[:30]} KEY_LEN={len(SUPABASE_KEY)}")

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

def fix_arabic_img(text):
    return str(text)

_LOCK = threading.Lock()
USERS = {}
_LOADED_OK = False

# ===== نظام الأسئلة =====
GROUP_IDS = set()
ACTIVE_QUIZZES = {}
WEEKLY = {}
HERO_JOB_STARTED = False

FUNNY_MESSAGES = [
    "😂 يا {name} شكلك كنت تحلل وانت نايم!",
    "😂 {name} تحليلك راح فيها، روح نام وارجع!",
    "😂 القيصر بقولك يا {name}: ركز المرة الجاية يا محلل!",
    "🤦 {name} لو كان الصاروخ بيعرف انك هيك جاوبت كان وقع لحالو!",
    "😂 {name} انت متأكد انك بتتابع تحليل عسكري؟ ولا بتتابع طبخ؟",
    "🫣 {name} هاد الجواب خلّى الرادار يطفي من الخجل!",
    "😂 {name} حتى الدرون ضحك على جوابك!",
    "💀 {name} تحليلك وصل لمرحلة الخطر، لازم دورة انعاش!",
    "😂 {name} انت جاوبت صح؟ لا والله، جاوبت غلط بثقة!",
    "🪖 {name} القيصر قرر يخصم منك رتبة عسكرية وهمية لهالجواب!"
]

QUESTIONS = [
    {"q": "ما هي المهمة الأساسية لنظام الدفاع الجوي S-400؟", "options": ["اعتراض الطائرات والصواريخ بعيدة المدى", "اعتراض الطائرات والصواريخ قصيرة المدى", "اعتراض الدبابات والصواريخ الأرضية", "اعتراض السفن والغواصات البحرية"], "correct": 0, "explain": "S-400 مصمم لاعتراض الطائرات والمسيرات والصواريخ الباليستية على مدى بعيد، وهو من أقوى أنظمة الدفاع الجوي في العالم."},
    {"q": "ما هو مدى صاروخ HIMARS بالنسخة الأساسية GMLRS؟", "options": ["حوالي 45 كم", "حوالي 80 كم", "حوالي 150 كم", "حوالي 300 كم"], "correct": 1, "explain": "HIMARS بالصواريخ الأساسية GMLRS مداه حوالي 80 كم، وهو ما جعله سلاح دقيق وسريع الحركة في أوكرانيا."},
    {"q": "لماذا تعتبر الدرونات الانتحارية خطيرة رغم رخص ثمنها؟", "options": ["لأنها رخيصة وسريعة وصعبة الرصد", "لأنها رخيصة ودقيقة وصعبة الرصد", "لأنها غالية ودقيقة وسهلة الرصد", "لأنها رخيصة وثقيلة وسهلة الرصد"], "correct": 1, "explain": "الدرون الانتحاري رخيص، يطير منخفض، وصعب على الرادار، وبضرب بدقة عالية، لذلك غيّر شكل الحرب الحديثة."},
    {"q": "ما هو الفرق بين الدبابة والمدرعة؟", "options": ["الدبابة لنقل الجنود والمدرعة للهجوم الثقيل", "الدبابة للهجوم الثقيل والمدفع الكبير، والمدرعة لنقل الجنود وحمايتهم", "الدبابة للاستطلاع والمدرعة للهجوم الثقيل", "الدبابة للدفاع الجوي والمدرعة لنقل الجنود"], "correct": 1, "explain": "الدبابة هي قوة نارية ثقيلة بمدفع كبير، بينما المدرعة مهمتها نقل الجنود وحمايتهم والتحرك السريع."},
    {"q": "ما هي أهم نقطة ضعف للدبابة في حرب المدن؟", "options": ["الجانب الأيمن، لأنه مكشوف للصواريخ", "الأعلى والسطح، لأنها مكشوفة للدرونات والصواريخ من فوق", "الأسفل والجنزير، لأنها مكشوفة للألغام فقط", "المقدمة، لأنها مكشوفة للمدفعية"], "correct": 1, "explain": "في حرب المدن، الدبابة ضعيفة من الأعلى، لذلك الدرونات والصواريخ المضادة للدروع تضربها من السطح."},
    {"q": "ما هو دور الأقمار الصناعية في الحرب الحديثة؟", "options": ["مراقبة تحركات العدو وتوجيه المدفعية والاتصالات", "مراقبة تحركات العدو وتوجيه الصواريخ والاتصالات", "مراقبة تحركات المدنيين وتوجيه الصواريخ والإنترنت", "مراقبة تحركات العدو وتوجيه الطائرات المدنية فقط"], "correct": 1, "explain": "الأقمار الصناعية هي عيون الجيش: بتراقب تحركات العدو، وبتوجه الصواريخ، وبتأمن الاتصالات."},
    {"q": "لماذا تستخدم الجيوش التمويه والخداع؟", "options": ["لخداع العدو وإجباره على ضرب أهداف حقيقية", "لخداع العدو وإجباره على ضرب أهداف وهمية", "لخداع المدنيين وإجبارهم على الهروب", "لخداع الأقمار الصناعية فقط بدون ضرب"], "correct": 1, "explain": "الخداع العسكري يخلي العدو يضرب دبابات وهمية ورادارات مزيفة، ويكشف مكانه بدون فائدة."},
    {"q": "ما هو صاروخ كروز؟", "options": ["صاروخ يطير مرتفع ويتتبع الأقمار الصناعية", "صاروخ يطير منخفض ويتتبع التضاريس ليصل لهدفه بدقة", "صاروخ يطير منخفض ويتتبع الحرارة فقط", "صاروخ يطير بالفضاء ويتتبع الرادار"], "correct": 1, "explain": "صاروخ الكروز يطير منخفض جدا ويتبع التضاريس ليصعب رصده، ويصل لهدفه بدقة عالية."},
    {"q": "ما هي الحرب الإلكترونية؟", "options": ["التشويش على اتصالات وطائرات العدو وتعطيلها", "التشويش على اتصالات ورادارات العدو وتعطيلها", "التشويش على اتصالات المدنيين فقط وتعطيلها", "التشويش على GPS الخاص فقط بدون رادارات"], "correct": 1, "explain": "الحرب الإلكترونية هي التشويش على رادارات واتصالات العدو، وقطع GPS والدرونات، بدون إطلاق رصاصة."},
    {"q": "لماذا يعتبر مضيق هرمز مهم عسكريا؟", "options": ["لأنه يمر منه معظم غاز العالم، والسيطرة عليه تعني ضغط عالمي", "لأنه يمر منه معظم نفط العالم، والسيطرة عليه تعني ضغط عالمي", "لأنه يمر منه معظم غذاء العالم، والسيطرة عليه تعني ضغط عالمي", "لأنه يمر منه معظم سلاح العالم، والسيطرة عليه تعني ضغط عالمي"], "correct": 1, "explain": "مضيق هرمز يمر منه حوالي 20% من نفط العالم، لذلك أي توتر فيه يرفع أسعار النفط ويهدد الاقتصاد العالمي."},
    {"q": "ما هي ميزة المقاتلة الشبحية F-35؟", "options": ["صعبة الرصد على الرادار وتجمع معلومات وترسلها للطائرات فقط", "صعبة الرصد على الرادار وتجمع معلومات وترسلها لباقي الجيش", "سهلة الرصد على الرادار وتجمع معلومات وترسلها لباقي الجيش", "صعبة الرصد على العين وتجمع معلومات بدون إرسال"], "correct": 1, "explain": "F-35 ليست فقط شبحية، بل هي كمبيوتر طائر يجمع معلومات ويرسلها لكل الجيش لحظة بلحظة."},
    {"q": "ما هو نظام القبة الحديدية؟", "options": ["نظام دفاع جوي بعيد المدى لاعتراض الصواريخ الباليستية", "نظام دفاع جوي قصير المدى لاعتراض الصواريخ قصيرة المدى", "نظام دفاع جوي متوسط المدى لاعتراض الطائرات فقط", "نظام هجوم جوي قصير المدى لضرب الصواريخ"], "correct": 1, "explain": "القبة الحديدية نظام دفاع جوي قصير المدى، يعترض الصواريخ والقذائف قبل وصولها للمدن."},
    {"q": "لماذا تفشل الهجمات البرية الكبيرة بدون غطاء جوي؟", "options": ["لأن القوات تصبح مكشوفة للطيران والدرونات والمدفعية", "لأن القوات تصبح محمية من الطيران والدرونات والمدفعية", "لأن القوات تصبح مكشوفة للدبابات فقط بدون طيران", "لأن القوات تصبح مكشوفة للبحرية والغواصات فقط"], "correct": 0, "explain": "بدون غطاء جوي، أي رتل دبابات يصبح هدف سهل للطيران والدرونات والمدفعية."},
    {"q": "ما هو دور القوات الخاصة؟", "options": ["عمليات دقيقة خلف خطوط العدو: تخريب، حماية، جمع معلومات", "عمليات دقيقة خلف خطوط العدو: تخريب، اغتيال، جمع معلومات", "عمليات واسعة أمام خطوط العدو: تخريب، اغتيال، جمع معلومات", "عمليات دقيقة داخل المدن: تخريب، اغتيال، نقل طعام"], "correct": 1, "explain": "القوات الخاصة تنفذ عمليات صغيرة ودقيقة خلف خطوط العدو، هدفها تأثير كبير بقوة صغيرة."},
    {"q": "ما هو الـ ATGM؟", "options": ["صاروخ مضاد للدبابات غير موجه", "صاروخ مضاد للطائرات موجه", "صاروخ مضاد للدبابات موجه", "صاروخ مضاد للسفن موجه"], "correct": 2, "explain": "ATGM هو صاروخ موجه مضاد للدبابات، مثل جافلين وكورنيت، يستطيع تدمير دبابة من مسافة بعيدة."},
    {"q": "لماذا تستخدم الجيوش الأنفاق؟", "options": ["للتحرك السري وتخزين الأسلحة والحماية من القصف البحري", "للتحرك السري وتخزين الأسلحة والحماية من القصف الجوي", "للتحرك العلني وتخزين الطعام والحماية من القصف الجوي", "للتحرك السري وتخزين الجنود والهجوم على المدنيين"], "correct": 1, "explain": "الأنفاق تعطي حماية من القصف الجوي، وتسمح بالتحرك السري ونقل الأسلحة بدون أن يراها العدو."},
    {"q": "ما هي نقطة قوة الغواصة؟", "options": ["التخفي تحت الماء والقدرة على ضرب أهداف قريبة بدون أن تُرصد", "التخفي تحت الماء والقدرة على ضرب أهداف بعيدة بدون أن تُرصد", "الظهور فوق الماء والقدرة على ضرب أهداف بعيدة بدون أن تُرصد", "التخفي تحت الماء والقدرة على نقل الجنود بدون أن تُرصد"], "correct": 1, "explain": "الغواصة قوتها بالتخفي، تستطيع الاقتراب من العدو وضربه بصواريخ دون أن يكتشفها أحد."},
    {"q": "ما هو الـ AWACS؟", "options": ["طائرة إنذار مبكر ورادار أرضي", "طائرة نقل جنود ورادار طائر", "طائرة إنذار مبكر ورادار طائر", "طائرة قتال جوي ورادار طائر"], "correct": 2, "explain": "AWACS هي طائرة تحمل رادار ضخم، ترى كل شيء من الجو وتدير المعركة الجوية."},
    {"q": "لماذا يعتبر الوقود واللوجستيات أهم من السلاح نفسه؟", "options": ["لأن السلاح بدون وقود وذخيرة وطعام يقاتل ببطء", "لأن السلاح بدون وقود وذخيرة وطعام لا يتحرك ولا يقاتل", "لأن السلاح بدون وقود وذخيرة وطعام يتحرك ولا يقاتل", "لأن السلاح بدون وقود وذخيرة وطعام يتحرك ويقاتل"], "correct": 1, "explain": "أي جيش بدون وقود وذخيرة وطعام يتوقف خلال أيام، لذلك اللوجستيات هي التي تحسم الحرب الطويلة."},
    {"q": "ما هو التكتيك الأفضل ضد رتل عسكري؟", "options": ["ضرب المقدمة والوسط أولا لحصره، ثم تدميره", "ضرب المقدمة والمؤخرة أولا لحصره، ثم تدميره", "ضرب المؤخرة والوسط أولا لحصره، ثم تدميره", "ضرب المقدمة والمؤخرة أولا لتحريره، ثم تدميره"], "correct": 1, "explain": "أفضل تكتيك ضد الرتل هو ضرب أول وآخر آلية لحصره في الطريق، ثم تدميره وهو عالق."},
]

def supabase_req(path, method="GET", data=None):
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json", "Prefer": "resolution=merge-duplicates"}
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=10) as r:
        txt = r.read().decode()
        return json.loads(txt) if txt else []

def load_users_once():
    global USERS, _LOADED_OK, WEEKLY
    try:
        rows = supabase_req("users?select=*")
        USERS = {}
        WEEKLY = {}
        for row in rows:
            uid = str(row.get("user_id"))
            USERS[uid] = {"points": row.get("points", 0) or 0, "name": row.get("name", "") or "", "coins": row.get("coins", 0) or 0, "msg_count": row.get("msg_count", 0) or 0}
            wp = row.get("weekly_points", 0) or 0
            if wp > 0:
                WEEKLY[uid] = int(wp)
        _LOADED_OK = True
        print(f"Loaded {len(USERS)} users from Supabase")
    except Exception as e:
        print(f"Load error Supabase: {e}")
        _LOADED_OK = False 
def save_group_id(chat_id):
    GROUP_IDS.add(chat_id)
    try:
        supabase_req("settings?on_conflict=key", method="POST", data=[{"key": f"group_{chat_id}", "value": str(chat_id)}])
    except:
        pass

def load_group_ids():
    try:
        rows = supabase_req("settings?key=like.group_%&select=*")
        for r in rows:
            GROUP_IDS.add(int(r["value"]))
        print(f"Loaded groups: {GROUP_IDS}")
    except Exception as e:
        print(f"Load groups error: {e}")

def save_users():
    if not USERS:
        return
    try:
        data_list = []
        for uid, u in USERS.items():
            data_list.append({"user_id": str(uid), "points": int(u.get("points", 0)), "name": str(u.get("name", "")), "coins": int(u.get("coins", 0)), "msg_count": int(u.get("msg_count", 0)), "weekly_points": int(WEEKLY.get(str(uid), 0))})
        supabase_req("users?on_conflict=user_id", method="POST", data=data_list)
        print(f"Saved {len(USERS)} users in 1 request")
    except Exception as e:
        print(f"Save error Supabase: {e}")

def save_one_user(uid):
    try:
        u = USERS.get(str(uid))
        if not u:
            return
        data = {"user_id": str(uid), "points": int(u.get("points", 0)), "name": str(u.get("name", "")), "coins": int(u.get("coins", 0)), "msg_count": int(u.get("msg_count", 0)), "weekly_points": int(WEEKLY.get(str(uid), 0))}
        supabase_req("users?on_conflict=user_id", method="POST", data=[data])
    except Exception as e:
        print(f"Save one error: {e}")

def save_weekly_only(uid):
    try:
        wp = WEEKLY.get(str(uid), 0)
        supabase_req(f"users?user_id=eq.{uid}", method="PATCH", data={"weekly_points": int(wp)})
    except Exception as e:
        print(f"Save weekly error: {e}")

def get_rank_name(points):
    if points < 100: return "عضو جديد"
    elif points < 300: return "مبتدئ"
    elif points < 600: return "بطل"
    elif points < 1000: return "نجم صاعد"
    elif points < 1600: return "محارب ذهبي"
    elif points < 2400: return "قائد"
    elif points < 3600: return "أسطورة"
    elif points < 5000: return "النخبة"
    elif points < 7000: return "محلل"
    else: return "خبير استراتيجي"
        
def get_money_level(coins):
    if coins == 0:
        return "تحت الأرض 💀"
    elif coins <= 10:
        return "طفران 😂"
    elif coins <= 25:
        return "فقير 🥲"
    elif coins <= 50:
        return "ماشي حالو 🙂"
    elif coins <= 100:
        return "غني 💰"
    elif coins <= 150:
        return "عظامو ذهب 🦴✨"
    else:
        return "زنكيل 👑💰"

def get_real_rank(user_id):
    sorted_users = sorted(USERS.items(), key=lambda x: x[1].get("points", 0), reverse=True)
    for i, (uid, udata) in enumerate(sorted_users, 1):
        if uid == str(user_id):
            return i
    return len(sorted_users) + 1

async def update_user_tag(context, chat_id, user_id, rank_name):
    try:
        await context.bot.set_chat_member_tag(chat_id=chat_id, user_id=user_id, tag=rank_name)
        return True
    except Exception as e:
        print(f"Tag failed: {e}")
        try:
            url = f"https://api.telegram.org/bot{TOKEN}/setChatMemberTag"
            data = json.dumps({"chat_id": chat_id, "user_id": user_id, "tag": rank_name}).encode()
            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=10) as r:
                print(r.read())
                return True
        except Exception as e2:
            print(f"Tag direct failed: {e2}")
            return False

def add_points(user_id, amount):
    with _LOCK:
        uid = str(user_id)
        if uid not in USERS:
            USERS[uid] = {"points": 0, "name": "", "coins": 0, "msg_count": 0}
        u = USERS[uid]
        u.setdefault("coins", 0)
        u.setdefault("msg_count", 0)
        old_rank = get_rank_name(u["points"])
        u["points"] += amount
        u["msg_count"] += 1
        
        new_rank = get_rank_name(u["points"])
        WEEKLY[str(uid)] = WEEKLY.get(str(uid), 0) + amount
        rank_up = new_rank != old_rank
        got_coin = False
        if u["msg_count"] >= 50:
            u["coins"] += 1
            u["msg_count"] = 0
            got_coin = True
            save_one_user(user_id)
        return u["points"], got_coin, rank_up, new_rank

def add_coins(user_id, amount):
    with _LOCK:
        uid = str(user_id)
        if uid not in USERS:
            USERS[uid] = {"points": 0, "name": "", "coins": 0, "msg_count": 0}
        USERS[uid].setdefault("coins", 0)
        USERS[uid]["coins"] += amount
        save_one_user(user_id)
        return USERS[uid]["coins"]
from PIL import Image, ImageDraw, ImageFont
import os
import urllib.request

from PIL import Image, ImageDraw, ImageFont
import os
import urllib.request
 
from PIL import Image, ImageDraw, ImageFont
import os
import urllib.request

# ===== دوال الأسئلة =====
async def finish_after_120(context):
    await asyncio.sleep(120)
    await finish_quiz(context)
    
async def finish_after_120_for_chat(context, chat_id):
    await asyncio.sleep(120)
    await finish_quiz(context, chat_id)
async def quiz_loop(app):
    await asyncio.sleep(10)
    while True:
        try:
            fake_context = type("C", (), {"bot": app.bot})()
            await send_quiz(fake_context)
        except Exception as e:
            print(f"Quiz loop error: {e}")
        await asyncio.sleep(7200)

async def send_quiz_for_chat(context, chat_id):
    if chat_id in ACTIVE_QUIZZES:
        return
    q_index = random.randrange(len(QUESTIONS))
    q = QUESTIONS[q_index]
    labels = ["A", "B", "C", "D"]
    keyboard = [[InlineKeyboardButton(f"{labels[i]} - {opt}", callback_data=f"quiz_{q_index}_{i}")] for i, opt in enumerate(q["options"])]
    markup = InlineKeyboardMarkup(keyboard)
    text = f"🎖️ سؤال عسكري جديد! 🎖️\n\n❓ {q['q']}\n\n⏳ معك 2 دقيقة فقط!\n🪙 اللي بجاوب صح بياخد 1 عملة ذهبية\n⚠️ ممنوع تغيير الجواب!"
    try:
        msg = await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=markup)
        ACTIVE_QUIZZES[chat_id] = {"q_index": q_index, "message_id": msg.message_id, "chat_id": chat_id, "answers": {}}
        asyncio.create_task(finish_after_120_for_chat(context, chat_id))
        print(f"Quiz sent: {q_index} to {chat_id}")
    except Exception as e:
        print(f"Send quiz failed {chat_id}: {e}")

async def send_quiz(context):
    for chat_id in list(GROUP_IDS):
        await send_quiz_for_chat(context, chat_id)

async def send_quiz(context):
    for chat_id in list(GROUP_IDS):
        await send_quiz_for_chat(context, chat_id)

async def finish_quiz(context, chat_id=None):
    if chat_id is None:
        return
    quiz = ACTIVE_QUIZZES.get(chat_id)
    if not quiz:
        return
    q_index = quiz["q_index"]
    answers = quiz["answers"]
    message_id = quiz["message_id"]
    q = QUESTIONS[q_index]
    correct = q["correct"]
    labels = ["A", "B", "C", "D"]
    # قفل الأزرار
    try:
        await context.bot.edit_message_reply_markup(chat_id=chat_id, message_id=message_id, reply_markup=None)
    except:
        pass
    winners = []
    losers = []
    for uid, (choice, name) in answers.items():
        if choice == correct:
            winners.append((uid, name))
        else:
            losers.append((uid, name))
    # توزيع العملات
    winners_text = ""
    if winners:
        for uid, name in winners:
            new_coins = add_coins(int(uid), 1)
            WEEKLY[str(uid)] = WEEKLY.get(str(uid), 0) + 10
            winners_text += f"🏆 @{name} - ربح 1 عملة ذهبية 🪙 (صار معو {new_coins})\n"
    else:
        winners_text = "😔 ما حد جاوب صح هالمرة!"
    # رسائل مضحكة
    funny_text = ""
    if losers:
        funny_text = "\n😂 اللي جاوبو غلط:\n"
        for uid, name in losers:
            funny_text += random.choice(FUNNY_MESSAGES).format(name=name) + "\n"
    correct_text = q["options"][correct]
    final_text = f"⏰ انتهى الوقت!\n\n✅ الجواب الصح: {labels[correct]} - {correct_text}\n\n📚 الشرح:\n{q['explain']}\n\n{winners_text}{funny_text}\n\nالسؤال الجاي بعد ساعتين 🔥"
    try:
        await context.bot.send_message(chat_id=chat_id, text=final_text)
    except Exception as e:
        print(f"Finish quiz send failed: {e}")
    del ACTIVE_QUIZZES[chat_id]

async def quiz_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data  # quiz_qindex_choice
    try:
        _, q_idx_str, choice_str = data.split("_")
        q_idx = int(q_idx_str)
        choice = int(choice_str)
    except:
        await query.answer()
        return
    user = query.from_user
    # اذا ما في سؤال فعال
    quiz = ACTIVE_QUIZZES.get(query.message.chat_id)
    if not quiz or quiz["q_index"] != q_idx:
        await query.answer("انتهى وقت السؤال!", show_alert=True)
        return
    # ممنوع تغيير الجواب
    if str(user.id) in quiz["answers"]:
        await query.answer("انت جاوبت قبل هيك! ممنوع تغيير الجواب 😂", show_alert=True)
        return
    # حفظ الجواب
    quiz["answers"][str(user.id)] = (choice, user.first_name)
    # حفظ اسم المستخدم
    with _LOCK:
        if str(user.id) not in USERS:
            USERS[str(user.id)] = {"points": 0, "name": user.first_name, "coins": 0, "msg_count": 0}
        else:
            USERS[str(user.id)]["name"] = user.first_name
    save_one_user(user.id)
    await query.answer("تم تسجيل جوابك! استنى انتهاء الوقت 🔥", show_alert=False)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    with _LOCK:
        if str(user.id) not in USERS:
            USERS[str(user.id)] = {"points": 0, "name": user.first_name, "coins": 0, "msg_count": 0}
        else:
            USERS[str(user.id)]["name"] = user.first_name
    save_one_user(user.id)
    keyboard = [
        [InlineKeyboardButton("🪙 العملات الذهبية", callback_data="coins_info"), InlineKeyboardButton("🎮 قريبا", callback_data="soon")],
        [InlineKeyboardButton("💰 رصيدي", callback_data="balance"), InlineKeyboardButton("🏆 ترتيب الأبطال", callback_data="leaderboard")],
        [InlineKeyboardButton("➕ ضيفنا لقناتك ✨", url="https://t.me/QaisarNewBot?startgroup=true"), InlineKeyboardButton("📢 القناة الرسمية 🔥", url="https://t.me/QaisarBotOfficial")],
    ]
    markup = InlineKeyboardMarkup(keyboard)
    caption = f"👑 أهلين فيك يا {user.first_name} 🔥\nنورت مملكة القيصر!\n\n👀 أنت الزائر رقم #{len(USERS)}\n👥 عدد أبطال المملكة: {len(USERS)} بطل"
    try:
        img = Image.open("main.jpg")
        img = ImageOps.fit(img, (1080, 1350), Image.LANCZOS)
        bio = io.BytesIO()
        img.save(bio, format="JPEG")
        bio.seek(0)
        await update.message.reply_photo(photo=bio, caption=caption, reply_markup=markup)
    except:
        await update.message.reply_text(caption, reply_markup=markup)

async def buttons_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    # اذا كان جواب سؤال، حوله لدالة الأسئلة
    if query.data.startswith("war_"):
        await war_callback(update, context)
        return
    if query.data.startswith("quiz_"):
        await quiz_callback(update, context)
        return
    await query.answer()
    user = query.from_user
    data = USERS.get(str(user.id), {"points": 0, "coins": 0})
    points = data.get("points", 0)
    coins = data.get("coins", 0)
    if query.data == "balance":
        real_rank = get_real_rank(user.id)
        card = make_card(user.first_name, points, coins, real_rank)
        with open(card, "rb") as f:
          await query.message.reply_photo(photo=f, caption=f"رصيدك: {points} نقطة | {coins} عملة 🪙")
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
    points, got_coin, rank_up, new_rank = add_points(user.id, 1)
    USERS[str(user.id)]["name"] = user.first_name
    data = USERS.get(str(user.id), {"points": 0, "coins": 0, "name": user.first_name})
    coins = data.get("coins", 0)
    rank_name = get_rank_name(points)
    money_level = get_money_level(coins)
    real_rank = get_real_rank(user.id)
    text = (
        f"<b>🪙 الرصيد:</b> {coins} عملة ذهبية\n"
        f"<b>💰 الحالة المادية:</b> {money_level}\n"
        f"<b>🏆 الرتبة:</b> {rank_name}\n"
        f"<b>⭐ النقاط:</b> {points} نقطة\n"
        f"<b>📊 الترتيب:</b> #{real_rank}"
    )
    await update.message.reply_text(text, parse_mode="HTML")

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sorted_users = sorted(USERS.items(), key=lambda x: x[1].get("points", 0), reverse=True)[:10]
    text = "🏆 ترتيب الأبطال:\n\n"
    for i, (uid, data) in enumerate(sorted_users, 1):
        name = data.get("name", "لاعب") or "لاعب"
        pts = data.get("points", 0)
        emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "▫️"
        text += f"{emoji} {i}. {name} - {pts} نقطة\n"
    with open(card, "rb") as f:
       await update.message.reply_photo(photo=f, caption=f"👑 بطاقتك يا {user.first_name}")

async def test_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    save_group_id(chat_id)
    await send_quiz_for_chat(context, chat_id)
    await update.message.reply_text("تم ارسال سؤال تجريبي 🔥")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global GROUP_CHAT_ID
    if not update.message or not update.message.text:
        return
    # تعرف على الجروب تلقائيا
    if update.effective_chat.type in ["group", "supergroup"]:
                save_group_id(update.effective_chat.id)
    text = update.message.text
    user = update.effective_user
    lower = text.lower()
    points, got_coin, rank_up, new_rank = add_points(user.id, 1)
    save_weekly_only(user.id)
    USERS[str(user.id)]["name"] = user.first_name
    if got_coin:
        await update.message.reply_text(f"🪙 مبروووك! أخذت 1 عملة ذهبية - نقاطك: {points}")
    if rank_up:
        await update.message.reply_text(f"🎉 مبرووووك! ترقيت لرتبة {new_rank} 👑\nنقاطك: {points}") 
        await update_user_tag(context, update.effective_chat.id, user.id, new_rank)
    if text.strip() in ["احبك", "بحبك", "اعشقك", "بموت فيك"]:
        replies_love = ["وأنا بموت فيك يا قلبي ❤️", "القيصر كمان بيحبك، يا روحي 😍", "قلبي داب خلص، شو هالحب هاد؟ ❤️", "وأنا بحبك أكتر، لا تغار 😘", "عيونك الحلوة، القيصر صار أحمر خجلان 🙈❤️", "حبك ولع قلبي يا بطل 🔥❤️", "وأنا بعشقك، بس لا تحكي لحد 🤫❤️", "القيصر وقع بالحب خلص، شو نعمل؟ 😍", "انت حبيبي وروحي وكل دنيتي ❤️", "بحبك قد البحر وقد السما ❤️", "قلبي صار يدق بسرعة، وقف 😂❤️", "وأنا بحبك، تعال خد حضن 🤗❤️", "انت أغلى واحد عند القيصر 👑❤️", "حبك لحاله بيكفي يخليني أطير 😍", "وأنا بموت فيك، لا تتركني ❤️"]
        await update.message.reply_text(random.choice(replies_love))
        return
    is_mentioned = any(e.type == "mention" and text[e.offset:e.offset+e.length] == "@QaisarNewBot" for e in (update.message.entities or []))
    if is_mentioned or text.strip() in ["يا قيصر", "قيصر"]:
        replies = ["نعم؟ القيصر موجود 👑", "أمرني يا بطل، القيصر هون 🔥", "هلا هلا، ناديتني؟ 😎", "القيصر سامعك، شو بدك؟", "أنا هون، لا تخاف 😂👑", "نعم نعم، القيصر بالخدمة", "شو في؟ حد نادى القيصر؟ 👀", "أهلين بالبطل، شو الأخبار؟", "القيصر موجود، احكي يا معلم", "عيون القيصر، أمرني", "وصلت وصلت، شو القصة؟ 🔥", "نعم يا ملك، القيصر معك", "هلا والله، نورت يا بطل", "القيصر هون، لا حد يزعج البطل", "سمعت اسمي؟ أنا جاهز 👑", "احكي احكي، القيصر سامعك", "يا هلا، القيصر وصل", "أنا القيصر، مين بده خدمة؟ 😎", "نعم؟ بدك نقاط ولا بدك ذهب؟ 💰", "القيصر لا ينام، أنا هون 😂"]
        await update.message.reply_text(random.choice(replies))
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

async def welcome_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.new_chat_members:
        return
    for member in update.message.new_chat_members:
        if member.id == context.bot.id:
            continue
        save_group_id(update.effective_chat.id)
        text = f"👑 أهلين وسهلين يا {member.first_name} 🔥\nنورت مملكة القيصر!\n\nاكتب `رصيد` عشان تشوف بطاقتك\nوكل رسالة = 1 نقطة، وكل 50 رسالة = 1 عملة ذهبية 🪙"
        try:
            await update.message.reply_text(text)
        except Exception as e:
            print(f"Welcome failed: {e}")
async def post_init(a):
    asyncio.create_task(quiz_loop(a))
    asyncio.create_task(weekly_hero_loop(a))
# ===== بطل الأسبوع =====
async def announce_weekly_hero(context):
    if not WEEKLY:
        return
    # ترتيب الأسبوعي
    sorted_weekly = sorted(WEEKLY.items(), key=lambda x: x[1], reverse=True)
    winner_id, winner_points = sorted_weekly[0]
    winner_data = USERS.get(str(winner_id), {})
    winner_name = winner_data.get("name", "بطل") or "بطل"
    # الجائزة 10 عملات
    new_coins = add_coins(int(winner_id), 10)
    # نص الترتيب Top 5
    top_text = ""
    for i, (uid, pts) in enumerate(sorted_weekly[:5], 1):
        nm = USERS.get(str(uid), {}).get("name", "بطل") or "بطل"
        emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "▫️"
        top_text += f"{emoji} {i}. {nm} - {pts} نقطة أسبوعية\n"
    # بطاقة البطل
    try:
        card = make_card(winner_name, winner_data.get("points", 0), new_coins, get_real_rank(winner_id))
    except:
        card = None
    caption = f"👑 بطل الأسبوع 👑\n\n🏆 {winner_name}\n⭐ {winner_points} نقطة أسبوعية\n🪙 الجائزة: +10 عملات ذهبية (صار معو {new_coins})\n\n🏆 ترتيب الأسبوع:\n{top_text}\n\nمبروووك يا بطل! 🔥"
    for chat_id in list(GROUP_IDS):
        try:
            if card:
              with open(card, "rb") as f:
                await context.bot.send_photo(chat_id=chat_id, photo=f, caption=caption)
            else:
                await context.bot.send_message(chat_id=chat_id, text=caption)
        except Exception as e:
            print(f"Hero announce failed {chat_id}: {e}")
    # تصفير الأسبوع
    WEEKLY.clear()
    try:
        supabase_req("users?weekly_points=gt.0", method="PATCH", data={"weekly_points": 0})
        print("Weekly reset in Supabase OK")
    except Exception as e:
        print(f"Reset weekly error: {e}")

async def weekly_hero_loop(app):
    global HERO_JOB_STARTED
    if HERO_JOB_STARTED:
        return
    HERO_JOB_STARTED = True
    while True:
        try:
            import datetime
            now = datetime.datetime.now()
            # الجمعة = 4 في بايثون (الاثنين=0)
            # بنفحص كل 10 دقائق، إذا كان جمعة والساعة 20
            if now.weekday() == 4 and now.hour == 20 and now.minute < 10:
                fake_context = type("C", (), {"bot": app.bot})()
                await announce_weekly_hero(fake_context)
                await asyncio.sleep(3600)
        except Exception as e:
            print(f"Hero loop error: {e}")
        await asyncio.sleep(600) 
async def weekly_points(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    pts = WEEKLY.get(str(user.id), 0)
    sorted_weekly = sorted(WEEKLY.items(), key=lambda x: x[1], reverse=True)
    rank = 1
    for uid, _ in sorted_weekly:
        if uid == str(user.id):
            break
        rank += 1
    else:
        rank = len(sorted_weekly) + 1
    await update.message.reply_text(f"⭐ نقاطك الأسبوعية يا {user.first_name}: {pts} نقطة\n🏆 ترتيبك الأسبوعي: #{rank}\n\n👑 بطل الأسبوع بياخد 10 عملات ذهبية كل جمعة 8 المسا!")

async def weekly_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not WEEKLY:
        await update.message.reply_text("😔 لسه ما حد جمع نقاط هالأسبوع!\nاكتب أي رسالة عشان تبلش تجمع.")
        return
    sorted_weekly = sorted(WEEKLY.items(), key=lambda x: x[1], reverse=True)[:10]
    text = "🏆 ترتيب بطل الأسبوع:\n\n"
    for i, (uid, pts) in enumerate(sorted_weekly, 1):
        nm = USERS.get(str(uid), {}).get("name", "بطل") or "بطل"
        emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "▫️"
        text += f"{emoji} {i}. {nm} - {pts} نقطة أسبوعية\n"
    text += "\n👑 الفائز كل جمعة 8 المسا بياخد 10 عملات ذهبية 🪙"
    await update.message.reply_text(text)

async def visitors_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    total = len(USERS)
    sorted_users = sorted(USERS.items(), key=lambda x: x[1].get("points", 0), reverse=True)[:5]
    text = f"👀 عداد زوار مملكة القيصر 👑\n\n👥 العدد الكلي: {total} زائر\n\n🏆 أكثر 5 أبطال تفاعلاً:\n"
    for i, (uid, udata) in enumerate(sorted_users, 1):
        nm = udata.get("name", "بطل") or "بطل"
        emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "▫️"
        text += f"{emoji} {i}. {nm} - {udata.get('points', 0)} نقطة\n"
    text += f"\n🔥 أنت الزائر رقم #{total}، ادعي صحابك يكبروا المملكة!"
    await update.message.reply_text(text)
# ===== ===== نظام الحرب - أزرار + خاص فقط ===== =====
import time as _time

WAR = {}

BUILDINGS = {
    "oil_factory": {"name": "🛢️ مصنع نفط", "cost": 50, "prod": "oil", "prod_per_lvl": 5},
    "iron_mine": {"name": "⛏️ منجم حديد", "cost": 50, "prod": "iron", "prod_per_lvl": 5},
    "farm": {"name": "🌾 مزرعة", "cost": 40, "prod": "wheat", "prod_per_lvl": 8},
    "barracks": {"name": "🏛️ ثكنة عسكرية", "cost": 80, "prod": None, "prod_per_lvl": 0},
    "airbase": {"name": "✈️ قاعدة جوية", "cost": 100, "prod": None, "prod_per_lvl": 0},
    "weapon_factory": {"name": "🎯 مصنع أسلحة", "cost": 90, "prod": None, "prod_per_lvl": 0},
    "wall": {"name": "🧱 سور المدينة", "cost": 60, "prod": None, "prod_per_lvl": 0},
    "warehouse": {"name": "📦 مخزن", "cost": 60, "prod": None, "prod_per_lvl": 0},
    "hq": {"name": "🏰 مقر القيادة", "cost": 100, "prod": None, "prod_per_lvl": 0},
}

ARMY = {
    "soldier": {"name": "🪖 جندي", "cost_gold": 1, "cost_wheat": 1, "power": 10},
    "tank": {"name": "🚜 دبابة", "cost_gold": 10, "cost_iron": 5, "power": 50},
    "cannon": {"name": "💣 مدفع", "cost_gold": 15, "cost_iron": 8, "power": 70},
    "plane": {"name": "✈️ طائرة", "cost_gold": 25, "cost_iron": 10, "cost_oil": 5, "power": 120},
    "missile": {"name": "🚀 صاروخ", "cost_gold": 40, "cost_iron": 15, "cost_oil": 10, "power": 200},
    "defense": {"name": "🛡️ دفاع جوي", "cost_gold": 20, "cost_iron": 10, "power": 0},
}

def get_war(uid):
    uid = str(uid)
    if uid not in WAR:
        WAR[uid] = {"oil": 0, "iron": 0, "wheat": 0, "buildings": {k: 0 for k in BUILDINGS}, "army": {k: 0 for k in ARMY}, "war_points": 0, "last_collect": int(_time.time())}
        WAR[uid]["buildings"]["hq"] = 1
    return WAR[uid]

def save_war(uid):
    try:
        w = get_war(uid)
        supabase_req("war_users?on_conflict=user_id", method="POST", data=[{
            "user_id": str(uid), "oil": int(w["oil"]), "iron": int(w["iron"]), "wheat": int(w["wheat"]),
            "buildings": w["buildings"], "army": w["army"], "war_points": int(w["war_points"]), "last_collect": int(w["last_collect"])
        }])
    except Exception as e:
        print(f"Save war error: {e}")

def load_war():
    global WAR
    try:
        rows = supabase_req("war_users?select=*")
        for r in rows:
            WAR[str(r["user_id"])] = {"oil": r.get("oil",0) or 0, "iron": r.get("iron",0) or 0, "wheat": r.get("wheat",0) or 0,
                "buildings": r.get("buildings") or {k:0 for k in BUILDINGS}, "army": r.get("army") or {k:0 for k in ARMY},
                "war_points": r.get("war_points",0) or 0, "last_collect": r.get("last_collect",0) or 0}
        print(f"Loaded war {len(WAR)}")
    except Exception as e:
        print(f"Load war error: {e}")

async def cmd_attack(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == "private":
        await update.message.reply_text("❌ الهجوم بس بالجروب، رد على رسالة خصمك واكتب /هجوم")
        return
    if not update.message.reply_to_message:
        await update.message.reply_text("❌ رد على رسالة الشخص اللي بدك تهجم عليه واكتب /هجوم")
        return
    attacker = update.effective_user
    defender = update.message.reply_to_message.from_user
    if attacker.id == defender.id:
        await update.message.reply_text("😂 بدك تهجم على حالك؟")
        return
    atk_power = war_power(attacker.id)
    def_power = war_power(defender.id)
    def_w = get_war(defender.id)
    def_power = int(def_power * (1 + def_w["buildings"].get("wall",0)*0.08))
    if atk_power == 0:
        await update.message.reply_text("❌ ما عندك جيش! اكتب /حرب واشتري جيش من المتجر بالخاص")
        return
    import random as _rnd
    atk_roll = atk_power * _rnd.uniform(0.8, 1.3)
    def_roll = def_power * _rnd.uniform(0.8, 1.3)
    if atk_roll > def_roll:
        atk_w = get_war(attacker.id)
        steal_oil = int(def_w["oil"] * 0.2)
        steal_iron = int(def_w["iron"] * 0.2)
        steal_wheat = int(def_w["wheat"] * 0.2)
        atk_w["oil"] += steal_oil; atk_w["iron"] += steal_iron; atk_w["wheat"] += steal_wheat
        def_w["oil"] -= steal_oil; def_w["iron"] -= steal_iron; def_w["wheat"] -= steal_wheat
        for k in def_w["army"]:
            def_w["army"][k] = int(def_w["army"][k] * 0.8)
        for k in atk_w["army"]:
            atk_w["army"][k] = int(atk_w["army"][k] * 0.9)
        atk_w["war_points"] += 20
        save_war(attacker.id); save_war(defender.id)
        await update.message.reply_text(f"⚔️ هجوووم!\n\n🔥 {attacker.first_name} فاز على {defender.first_name}!\n💰 سرق: 🛢️ {steal_oil} | ⛏️ {steal_iron} | 🌾 {steal_wheat}\n💥 دمر 20% من جيشو\n🏆 +20 نقطة حرب")
    else:
        atk_w = get_war(attacker.id)
        for k in atk_w["army"]:
            atk_w["army"][k] = int(atk_w["army"][k] * 0.7)
        def_w["war_points"] += 10
        save_war(attacker.id); save_war(defender.id)
        await update.message.reply_text(f"⚔️ هجوووم!\n\n🛡️ {defender.first_name} صد الهجوم ودمر 30% من جيش {attacker.first_name}!\n🏆 {defender.first_name} +10 نقطة حرب")
async def cmd_harb(update, context):
    uid = str(update.effective_user.id)
    d = get_war(uid)
    text = (f"⚔️ <b>إمبراطورية الحرب</b>\n\n"
            f"👤 {update.effective_user.first_name}\n"
            f"🏆 نقاط حرب: {d['war_points']}\n\n"
            f"🛢️ نفط: {d['oil']} | 🔩 حديد: {d['iron']} | 🌾 قمح: {d['wheat']}\n\n"
            f"🏗️ مباني: {sum(d['buildings'].values())} | 🪖 جنود: {sum(d['army'].values())}")
    kb = [[InlineKeyboardButton("🏗️ مباني", callback_data="war_buildings"),
           InlineKeyboardButton("🪖 جيش", callback_data="war_army")],
          [InlineKeyboardButton("🎁 جمع الموارد", callback_data="war_collect"),
           InlineKeyboardButton("🏆 ترتيب الحرب", callback_data="war_top")]]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
def main():
    keep_alive()
    global USERS
    load_users_once()
    load_group_ids()
    load_war()
    app = Application.builder().token(TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("harb", cmd_harb))
    app.add_handler(CommandHandler("attack", cmd_attack))
    app.add_handler(CommandHandler("sual", test_quiz))
    h1 = MessageHandler(filters.Regex(r"^(ترتيب|/ترتيب|/top)$"), leaderboard)
    h2 = MessageHandler(filters.Regex(r"^(رصيد|رصيدي|/رصيد|/balance)$"), balance)
    h3 = MessageHandler(filters.Regex(r"^(/طير|طير)$"), kick_user)
    h4 = MessageHandler(filters.Regex(r"^(/اسكت|اسكت)$"), mute_user)
    h5 = MessageHandler(filters.Regex(r"^(/احكي|احكي)$"), unmute_user)
    h7 = MessageHandler(filters.Regex(r"^(نقاطي|/نقاطي)$"), weekly_points)
    h8 = MessageHandler(filters.Regex(r"^(بطل الأسبوع|/بطل)$"), weekly_leaderboard)
    h9 = MessageHandler(filters.Regex(r"^(الزوار|/زوار|عداد الزوار)$"), visitors_count) 
    app.add_handler(h9)
    app.add_handler(h1)
    app.add_handler(h2)
    app.add_handler(h3)
    app.add_handler(h4)
    app.add_handler(h5)
    app.add_handler(h7)
    app.add_handler(h8)
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_new_member))
    h6 = MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    app.add_handler(h6)
    app.add_handler(CallbackQueryHandler(buttons_handler))
    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
