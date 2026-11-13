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
    try:
        reshaped = arabic_reshaper.reshape(str(text))
        return get_display(reshaped)
    except:
        return str(text)

_LOCK = threading.Lock()
USERS = {}
_LOADED_OK = False

# ===== نظام الأسئلة =====
GROUP_IDS = set()
ACTIVE_QUIZZES = {}

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
    global USERS, _LOADED_OK
    try:
        rows = supabase_req("users?select=*")
        USERS = {}
        for row in rows:
            uid = str(row.get("user_id"))
            USERS[uid] = {"points": row.get("points", 0) or 0, "name": row.get("name", "") or "", "coins": row.get("coins", 0) or 0, "msg_count": row.get("msg_count", 0) or 0}
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
        for uid, u in USERS.items():
            data = {"user_id": str(uid), "points": int(u.get("points", 0)), "name": str(u.get("name", "")), "coins": int(u.get("coins", 0)), "msg_count": int(u.get("msg_count", 0))}
            supabase_req("users?on_conflict=user_id", method="POST", data=[data])
        print(f"Saved {len(USERS)} users to Supabase")
    except Exception as e:
        print(f"Save error Supabase: {e}")

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
        rank_up = new_rank != old_rank
        got_coin = False
        if u["msg_count"] >= 50:
            u["coins"] += 1
            u["msg_count"] = 0
            got_coin = True
        save_users()
        return u["points"], got_coin, rank_up, new_rank

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
    W, H = 1200, 820
    img = Image.new("RGB", (W, H), (15, 10, 5))
    d = ImageDraw.Draw(img)
    d.rectangle([20, 20, W-20, H-20], outline=(212, 175, 55), width=5)
    if points < 100: rank_name = "عضو جديد"
    elif points < 300: rank_name = "مبتدئ"
    elif points < 600: rank_name = "بطل"
    elif points < 1000: rank_name = "نجم صاعد"
    elif points < 1600: rank_name = "محارب ذهبي"
    elif points < 2400: rank_name = "قائد"
    elif points < 3600: rank_name = "أسطورة"
    elif points < 5000: rank_name = "النخبة"
    elif points < 7000: rank_name = "محلل"
    else: rank_name = "خبير استراتيجي"
    money_level = get_money_level(coins)
    try:
        import urllib.request
        if not os.path.exists("Amiri-Regular.ttf"):
            urllib.request.urlretrieve("https://github.com/google/fonts/raw/main/ofl/amiri/Amiri-Regular.ttf", "Amiri-Regular.ttf")
        font_big = ImageFont.truetype("Amiri-Regular.ttf", 70)
        font_mid = ImageFont.truetype("Amiri-Regular.ttf", 45)
        font_small = ImageFont.truetype("Amiri-Regular.ttf", 38)
    except:
        font_big = ImageFont.load_default()
        font_mid = font_big
        font_small = font_big
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
    center(50, name, font_big, (212, 175, 55))
    center_at(250, 200, "النقاط", font_mid, (200, 200, 200))
    center_at(250, 260, str(points), font_big, (90, 180, 255))
    center_at(600, 200, "الرتبة", font_mid, (200, 200, 200))
    center_at(600, 235, rank_name, font_big, (190, 140, 255))
    center_at(950, 200, "الترتيب", font_mid, (200, 200, 200))
    center_at(950, 260, f"#{rank}", font_big, (212, 175, 55))
    limits = [0, 100, 300, 600, 1000, 1600, 2400, 3600, 5000, 7000]
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
    bar_x1, bar_y1, bar_x2, bar_y2 = 250, 410, 950, 442
    d.rounded_rectangle([bar_x1, bar_y1, bar_x2, bar_y2], radius=17, fill=(45, 35, 10), outline=(212, 175, 55), width=3)
    fill_w = int((bar_x2 - bar_x1) * percent / 100)
    if fill_w > 10:
        d.rounded_rectangle([bar_x1+3, bar_y1+3, bar_x1+fill_w-3, bar_y2-3], radius=14, fill=(212, 175, 55))
    center(440, f"{percent}%  -  {points} / {next_limit}", font_mid, (255, 255, 255))
    d.rounded_rectangle([300, 500, W-300, 620], radius=30, fill=(40, 20, 60))
    d.rounded_rectangle([310, 510, W-310, 610], radius=25, fill=(25, 10, 35))
    center(528, "العملات الذهبية", font_mid, (212, 175, 55))
    center_at(350, 525, str(coins), font_big, (255, 215, 0))
    d.rounded_rectangle([300, 650, W-300, 760], radius=30, fill=(40, 20, 60))
    d.rounded_rectangle([310, 660, W-310, 750], radius=25, fill=(25, 10, 35))
    center_at(760, 695, "المستوى المالي", font_small, (200, 200, 200))
    center_at(420, 690, money_level, font_mid, (255, 215, 0))
    bio = io.BytesIO()
    img.save(bio, format="PNG")
    bio.seek(0)
    return bio

# ===== دوال الأسئلة =====
async def finish_after_120(context):
    await asyncio.sleep(120)
    await finish_quiz(context)

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
        context.job_queue.run_once(lambda c: finish_quiz_for_chat(c, chat_id), when=120)
        print(f"Quiz sent: {q_index} to {chat_id}")
    except Exception as e:
        print(f"Send quiz failed {chat_id}: {e}")

async def send_quiz(context):
    for chat_id in list(GROUP_IDS):
        await send_quiz_for_chat(context, chat_id)

async def finish_quiz(context):
    global ACTIVE_QUIZ
    if ACTIVE_QUIZ is None:
        return
    q_index = ACTIVE_QUIZ["q_index"]
    chat_id = ACTIVE_QUIZ["chat_id"]
    answers = ACTIVE_QUIZ["answers"]
    message_id = ACTIVE_QUIZ["message_id"]
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
    ACTIVE_QUIZ = None

async def quiz_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global ACTIVE_QUIZ
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
    if ACTIVE_QUIZ is None or ACTIVE_QUIZ["q_index"] != q_idx:
        await query.answer("انتهى وقت السؤال!", show_alert=True)
        return
    # ممنوع تغيير الجواب
    if str(user.id) in ACTIVE_QUIZ["answers"]:
        await query.answer("انت جاوبت قبل هيك! ممنوع تغيير الجواب 😂", show_alert=True)
        return
    # حفظ الجواب
    ACTIVE_QUIZ["answers"][str(user.id)] = (choice, user.first_name)
    # حفظ اسم المستخدم
    with _LOCK:
        if str(user.id) not in USERS:
            USERS[str(user.id)] = {"points": 0, "name": user.first_name, "coins": 0, "msg_count": 0}
        else:
            USERS[str(user.id)]["name"] = user.first_name
    save_users()
    await query.answer("تم تسجيل جوابك! استنى انتهاء الوقت 🔥", show_alert=False)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    with _LOCK:
        if str(user.id) not in USERS:
            USERS[str(user.id)] = {"points": 0, "name": user.first_name, "coins": 0, "msg_count": 0}
        else:
            USERS[str(user.id)]["name"] = user.first_name
    save_users()
    keyboard = [[InlineKeyboardButton("🪙 العملات الذهبية", callback_data="coins_info"), InlineKeyboardButton("🎮 قريبا", callback_data="soon")], [InlineKeyboardButton("💰 رصيدي", callback_data="balance"), InlineKeyboardButton("🏆 ترتيب الأبطال", callback_data="leaderboard")]]
    markup = InlineKeyboardMarkup(keyboard)
    caption = f"👑 أهلين فيك يا {user.first_name} 🔥\nنورت مملكة القيصر!"
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
    points, got_coin, rank_up, new_rank = add_points(user.id, 1)
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

async def test_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # أمر للتجربة: /سؤال - بينزل سؤال فورا للتجربة
    global GROUP_CHAT_ID
    GROUP_CHAT_ID = update.effective_chat.id
    await send_quiz(context)
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
    USERS[str(user.id)]["name"] = user.first_name
    if got_coin:
        await update.message.reply_text(f"🪙 مبروووك! أخذت 1 عملة ذهبية - نقاطك: {points}")
    if rank_up:
        await update.message.reply_text(f"🎉 مبرووووك! ترقيت لرتبة {new_rank} 👑\nنقاطك: {points}")
    if "احبك" in text or "بحبك" in text or "اعشقك" in text or "بموت فيك" in text:
        replies_love = ["وأنا بموت فيك يا قلبي ❤️", "القيصر كمان بيحبك، يا روحي 😍", "قلبي داب خلص، شو هالحب هاد؟ ❤️", "وأنا بحبك أكتر، لا تغار 😘", "عيونك الحلوة، القيصر صار أحمر خجلان 🙈❤️", "حبك ولع قلبي يا بطل 🔥❤️", "وأنا بعشقك، بس لا تحكي لحد 🤫❤️", "القيصر وقع بالحب خلص، شو نعمل؟ 😍", "انت حبيبي وروحي وكل دنيتي ❤️", "بحبك قد البحر وقد السما ❤️", "قلبي صار يدق بسرعة، وقف 😂❤️", "وأنا بحبك، تعال خد حضن 🤗❤️", "انت أغلى واحد عند القيصر 👑❤️", "حبك لحاله بيكفي يخليني أطير 😍", "وأنا بموت فيك، لا تتركني ❤️"]
        await update.message.reply_text(random.choice(replies_love))
        return
    if "قيصر" in text or "qaysar" in lower or "qaisar" in lower:
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

async def post_init(a):
    asyncio.create_task(quiz_loop(a))

def main():
    keep_alive()
    global USERS
    load_users_once()
    app = Application.builder().token(TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("sual", test_quiz))
    h1 = MessageHandler(filters.Regex("ترتيب"), leaderboard)
    app.add_handler(h1)
    h2 = MessageHandler(filters.Regex("رصيد"), balance)
    app.add_handler(h2)
    h3 = MessageHandler(filters.Regex("طير"), kick_user)
    app.add_handler(h3)
    h4 = MessageHandler(filters.Regex("اسكت"), mute_user)
    app.add_handler(h4)
    h5 = MessageHandler(filters.Regex("احكي"), unmute_user)
    app.add_handler(h5)
    h6 = MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    app.add_handler(h6)
    app.add_handler(CallbackQueryHandler(buttons_handler))
    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
