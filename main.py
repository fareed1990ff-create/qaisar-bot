import os
import json
import random
import datetime
from zoneinfo import ZoneInfo
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
# ===== نظام التوقعات اليومي - ايران =====
PREDICTIONS = {}  # user_id -> {"name":..., "ans": "ah" / "la"}
POLL_MESSAGES = {}  # chat_id -> message_id
POLL_BASE_TEXT = """🎯 توقع اليوم - 8 مساءً

هل تتوقع تجدد الحرب الليلة على أيران ؟!

━━━━━━━━━━━━━━
🗳️ كيف تصوت؟

اكبس على الزر تحت 👇
✅ آه بتوقع
❌ لا ما بتوقع

اللي بتوقع صح بياخد +10 نقاط 🏆"""
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
    {"q": "ما هو المدى الفعال لنظام باتريوت PAC-3؟", "options": ["35 كم ضد الصواريخ الباليستية و 160 كم ضد الطائرات", "400 كم ضد كل الأهداف", "15 كم فقط ضد الدرونات", "70 كم ضد الصواريخ والطائرات"], "correct": 0, "explain": "PAC-3 متخصص بالباليستي بمدى 35 كم، لكن ضد الطائرات يوصل لـ 160 كم.", "level": "صعب جدا", "cat": "دفاع جوي"},
    {"q": "شو الفرق الأساسي بين THAAD وباتريوت؟", "options": ["THAAD يعترض خارج الغلاف الجوي وباتريوت داخله", "THAAD للدرونات وباتريوت للطائرات", "THAAD قصير المدى وباتريوت بعيد المدى", "لا يوجد فرق، الاثنين نفس النظام"], "correct": 0, "explain": "THAAD يضرب الصاروخ في الفضاء الخارجي، باتريوت يضربه داخل الغلاف الجوي.", "level": "صعب جدا", "cat": "دفاع جوي"},
    {"q": "كم تبلغ سرعة صاروخ أرو 3 الإسرائيلي؟", "options": ["أكثر من ماخ 9 وخارج الغلاف الجوي", "ماخ 2 داخل الغلاف الجوي", "ماخ 5 فقط", "أقل من سرعة الصوت"], "correct": 0, "explain": "أرو 3 يعترض في الفضاء بسرعة تتجاوز ماخ 9.", "level": "صعب جدا", "cat": "صواريخ"},
    {"q": "ما هي نقطة ضعف القبة الحديدية؟", "options": ["تتشبع إذا أُطلقت رشقات كثيفة بنفس الوقت", "لا تعمل في الليل", "لا تعمل ضد الصواريخ فقط ضد الطائرات", "لا تعمل في المطر"], "correct": 0, "explain": "القبة ممتازة لكن إذا أُطلقت عشرات الصواريخ دفعة واحدة، بعضها سيمر.", "level": "صعب جدا", "cat": "دفاع جوي"},
    {"q": "ما هو نظام مقلاع داوود؟", "options": ["نظام إسرائيلي للمدى المتوسط 40-300 كم", "نظام أمريكي للمدى القصير", "نظام روسي للمدى البعيد", "نظام بحري للغواصات"], "correct": 0, "explain": "مقلاع داوود يغطي الفجوة بين القبة الحديدية وأرو.", "level": "صعب جدا", "cat": "دفاع جوي"},
    {"q": "شو يعني Hit-to-Kill؟", "options": ["تدمير الهدف بالاصطدام المباشر بدون متفجرات", "تدمير الهدف بانفجار قريب منه", "تدمير الهدف بالليزر", "تدمير الهدف بالتشويش"], "correct": 0, "explain": "Hit-to-Kill يعني الصاروخ يصدم الهدف جسديا، مثل PAC-3 و THAAD.", "level": "صعب جدا", "cat": "صواريخ"},
    {"q": "أي نظام يستخدم للتصدي للصواريخ فرط الصوتية؟", "options": ["لا يوجد نظام فعال 100% حتى الآن", "القبة الحديدية تكفي", "باتريوت PAC-2 يكفي", "كل أنظمة الدفاع الجوي تتصدى لها"], "correct": 0, "explain": "الفرط صوتي سريع ومناور، لذلك لا يوجد دفاع مضمون ضده حتى الآن.", "level": "صعب جدا", "cat": "صواريخ"},
    {"q": "كم عدد الصواريخ الاعتراضية في بطارية باتريوت واحدة؟", "options": ["حتى 128 صاروخ حسب نوع القاذف", "8 صواريخ فقط", "16 صاروخ فقط", "1000 صاروخ"], "correct": 0, "explain": "البطارية فيها 8 قواذف، كل قاذف 16 صاروخ PAC-3، يعني 128.", "level": "صعب جدا", "cat": "دفاع جوي"},
    {"q": "ما هو مدى صاروخ كينجال الروسي؟", "options": ["2000 كم وسرعة ماخ 10", "300 كم وسرعة ماخ 2", "500 كم وسرعة ماخ 1", "100 كم وسرعة ماخ 5"], "correct": 0, "explain": "كينجال فرط صوتي مداه 2000 كم وسرعته ماخ 10.", "level": "صعب جدا", "cat": "صواريخ"},
    {"q": "لماذا الرادار لا يكشف الطائرات الشبحية بسهولة؟", "options": ["لأن تصميمها يشتت موجات الرادار بعيدا عنه", "لأنها تطير تحت الأرض", "لأنها تطير بسرعة الضوء", "لأنها لا تصدر أي حرارة"], "correct": 0, "explain": "الشبحية تعتمد على زوايا تمتص وتشتت الموجات، فلا تعود للرادار.", "level": "صعب جدا", "cat": "رادار"},
    {"q": "ما هو نظام S-500 الروسي؟", "options": ["دفاع جوي يتصدى للصواريخ الباليستية والأقمار الصناعية", "دبابة روسية جديدة", "طائرة مسيرة", "غواصة نووية"], "correct": 0, "explain": "S-500 هو الجيل الجديد، يضرب أهداف في الفضاء وعلى ارتفاع 200 كم.", "level": "صعب جدا", "cat": "دفاع جوي"},
    {"q": "شو وظيفة صاروخ تامير في القبة الحديدية؟", "options": ["اعتراض الصواريخ القصيرة بتكلفة 50 ألف دولار للصاروخ", "اعتراض الطائرات المقاتلة", "كشف الرادار", "إطلاق الصواريخ الهجومية"], "correct": 0, "explain": "تامير هو الصاروخ الاعتراضي للقبة، رخيص نسبيا مقارنة بالباتريوت.", "level": "صعب جدا", "cat": "دفاع جوي"},
    {"q": "ما هو الفرق بين صاروخ باليستي وصاروخ مجنح (كروز)؟", "options": ["الباليستي يخرج للفضاء ويسقط، والكروز يطير منخفض كالطائرة", "الباليستي يطير منخفض والكروز يخرج للفضاء", "الاثنين نفس الشي", "الباليستي أبطأ من الكروز"], "correct": 0, "explain": "الباليستي مساره قوسي عالي، الكروز يطير منخفض ويتابع التضاريس.", "level": "صعب جدا", "cat": "صواريخ"},
    {"q": "أي دولة صنعت نظام HQ-9؟", "options": ["الصين، وهو مشابه لـ S-300 الروسي", "أمريكا", "إسرائيل", "فرنسا"], "correct": 0, "explain": "HQ-9 صيني، مستوحى من S-300 لكن بتطوير صيني.", "level": "صعب جدا", "cat": "دفاع جوي"},
    {"q": "كم تبلغ تكلفة صاروخ باتريوت واحد؟", "options": ["حوالي 4 مليون دولار لـ PAC-3", "50 ألف دولار", "100 ألف دولار", "10 مليون دولار لـ PAC-2"], "correct": 0, "explain": "PAC-3 غالي جدا، حوالي 3-4 مليون، لذلك لا يستخدم ضد الدرونات الرخيصة.", "level": "صعب جدا", "cat": "دفاع جوي"},
    {"q": "ما هو نظام الليزر Iron Beam؟", "options": ["نظام إسرائيلي يستخدم الليزر لإسقاط الدرونات والصواريخ بتكلفة منخفضة", "نظام رادار جديد", "نظام صواريخ بحري", "نظام تشويش"], "correct": 0, "explain": "Iron Beam يضرب بالليزر، تكلفة الطلقة دولارين فقط بدل 50 ألف.", "level": "صعب جدا", "cat": "دفاع جوي"},
    {"q": "لماذا الدرونات الصغيرة صعبة على الدفاع الجوي؟", "options": ["لأن بصمتها الرادارية صغيرة وتطير منخفضة وبطيئة", "لأنها تطير بسرعة ماخ 10", "لأنها تطير في الفضاء", "لأنها لا تظهر على الرادار أبدا"], "correct": 0, "explain": "الرادارات مصممة للطائرات الكبيرة السريعة، الدرون الصغير يختفي بين المباني.", "level": "صعب جدا", "cat": "درونات"},
    {"q": "ما هو نظام أرو 2؟", "options": ["دفاع إسرائيلي ضد الصواريخ الباليستية داخل الغلاف الجوي", "دفاع ضد الدرونات", "نظام هجومي", "رادار بحري"], "correct": 0, "explain": "أرو 2 يعترض داخل الغلاف، أرو 3 يعترض خارجه.", "level": "صعب جدا", "cat": "دفاع جوي"},
    {"q": "ما هي سرعة صاروخ شهاب 3 الإيراني تقريبا؟", "options": ["حوالي ماخ 7 ومدى 2000 كم", "ماخ 1 ومدى 300 كم", "ماخ 2 ومدى 500 كم", "ماخ 10 ومدى 5000 كم"], "correct": 0, "explain": "شهاب 3 باليستي متوسط المدى 1300-2000 كم.", "level": "صعب جدا", "cat": "صواريخ"},
    {"q": "شو يعني نظام دفاع طبقي؟", "options": ["عدة أنظمة بمديات مختلفة تحمي نفس المنطقة", "نظام واحد فقط يحمي كل شي", "نظام بحري فقط", "نظام للطائرات فقط"], "correct": 0, "explain": "الدفاع الطبقي: قبة + مقلاع + أرو + باتريوت، كل واحد يغطي طبقة.", "level": "صعب جدا", "cat": "دفاع جوي"},
    {"q": "أي نظام هو الأفضل ضد الصواريخ الباليستية بعيدة المدى؟", "options": ["THAAD وأرو 3، لأنهما يعترضان في الفضاء", "القبة الحديدية", "S-300", "نظام المدفعية"], "correct": 0, "explain": "الباليستي البعيد يجب اعتراضه خارج الغلاف قبل أن يسرع بالعودة.", "level": "صعب جدا", "cat": "دفاع جوي"},
    {"q": "ما هو رادار AN/TPY-2؟", "options": ["رادار أمريكي لـ THAAD يكشف الصواريخ من 1000 كم", "رادار للغواصات", "رادار للدرونات فقط", "رادار للطقس"], "correct": 0, "explain": "AN/TPY-2 هو عين THAAD، يرى الصاروخ من مسافة بعيدة جدا.", "level": "صعب جدا", "cat": "رادار"},
    {"q": "لماذا لا يستخدم باتريوت ضد الدرونات الرخيصة؟", "options": ["لأن صاروخه بـ 4 مليون والدرون بـ 500 دولار، خسارة اقتصادية", "لأنه لا يستطيع كشفها", "لأنه لا يعمل ليلا", "لأنه نظام هجومي"], "correct": 0, "explain": "المعادلة الاقتصادية: لا ترمي 4 مليون على درون بـ 500 دولار.", "level": "صعب جدا", "cat": "دفاع جوي"},
    {"q": "ما هو صاروخ ستينغر؟", "options": ["صاروخ محمول على الكتف ضد الطائرات المنخفضة", "صاروخ باليستي عابر للقارات", "صاروخ بحري", "صاروخ فرط صوتي"], "correct": 0, "explain": "ستينغر MANPADS، يحمله جندي واحد ويسقط طائرة على ارتفاع منخفض.", "level": "صعب جدا", "cat": "صواريخ"},
    {"q": "كم ارتفاع اعتراض THAAD؟", "options": ["حتى 150 كم فوق الأرض، أي خارج الغلاف الجوي", "5 كم فقط", "20 كم فقط", "400 كم"], "correct": 0, "explain": "THAAD يعترض على ارتفاع 40-150 كم.", "level": "صعب جدا", "cat": "دفاع جوي"},
    {"q": "ما هو نظام باراك 8؟", "options": ["دفاع جوي هندي-إسرائيلي بحري وبري متوسط المدى", "دبابة إسرائيلية", "طائرة إسرائيلية", "غواصة"], "correct": 0, "explain": "باراك 8 مشترك بين الهند وإسرائيل، يحمي السفن والمدن.", "level": "صعب جدا", "cat": "دفاع جوي"},
    {"q": "شو الفرق بين رادار AESA ورادار PESA؟", "options": ["AESA كل وحدة ترسل وتستقبل لوحدها، PESA وحدة واحدة للكل", "AESA أقدم من PESA", "PESA أغلى من AESA", "لا يوجد فرق"], "correct": 0, "explain": "AESA أحدث وأصعب على التشويش، لأن كل عنصر مستقل.", "level": "صعب جدا", "cat": "رادار"},
    {"q": "ما هو صاروخ ذو الفقار الإيراني؟", "options": ["باليستي بمدى 700 كم ودقة عالية", "صاروخ كروز", "درون", "صاروخ فضائي"], "correct": 0, "explain": "ذو الفقار باليستي تكتيكي، يستخدم ضد أهداف أرضية بدقة.", "level": "صعب جدا", "cat": "صواريخ"},
    {"q": "أي نظام دفاع جوي عند السعودية؟", "options": ["باتريوت و THAAD", "S-400 فقط", "القبة الحديدية فقط", "لا يوجد"], "correct": 0, "explain": "السعودية تعتمد على باتريوت واشترت THAAD لحماية المنشآت.", "level": "صعب جدا", "cat": "دفاع جوي"},
    {"q": "ما هو التشويش الإلكتروني؟", "options": ["إرسال موجات تمنع الرادار من رؤية الهدف الحقيقي", "إطلاق صواريخ كثيرة", "تدمير الرادار بالصواريخ", "إطفاء الرادار"], "correct": 0, "explain": "التشويش يعمى الرادار، فيرى أهداف وهمية أو لا يرى شيئا.", "level": "صعب جدا", "cat": "رادار"},
    {"q": "كم تبلغ سرعة صاروخ توماهوك؟", "options": ["880 كم/ساعة، أي أقل من سرعة الصوت", "ماخ 5", "ماخ 10", "ماخ 3"], "correct": 0, "explain": "توماهوك كروز بطيء لكنه يطير منخفض جدا ويصعب كشفه.", "level": "صعب جدا", "cat": "صواريخ"},
    {"q": "ما هو نظام NASAMS؟", "options": ["دفاع جوي نرويجي-أمريكي قصير ومتوسط المدى", "دفاع روسي", "دفاع صيني", "دفاع إسرائيلي"], "correct": 0, "explain": "NASAMS يحمي واشنطن وأوكرانيا، يستخدم صواريخ AMRAAM.", "level": "صعب جدا", "cat": "دفاع جوي"},
    {"q": "شو يعني MIRV؟", "options": ["صاروخ واحد يحمل عدة رؤوس نووية تنفصل وتضرب أهداف مختلفة", "صاروخ واحد برأس واحد", "صاروخ يطير منخفض", "صاروخ بدون رأس"], "correct": 0, "explain": "MIRV يجعل الاعتراض أصعب، لأن صاروخ واحد يصير 10 أهداف.", "level": "صعب جدا", "cat": "صواريخ"},
    {"q": "ما هو نظام S-300؟", "options": ["دفاع جوي روسي بعيد المدى 150-300 كم", "دفاع قصير المدى 10 كم", "طائرة مقاتلة", "صاروخ كروز"], "correct": 0, "explain": "S-300 هو سلف S-400، منتشر في سوريا وإيران وغيرها.", "level": "صعب جدا", "cat": "دفاع جوي"},
    {"q": "لماذا صواريخ الكروز صعبة الكشف؟", "options": ["تطير على ارتفاع 30 متر وتتبع التضاريس", "تطير في الفضاء", "تطير بسرعة ماخ 10", "لا تصدر حرارة"], "correct": 0, "explain": "الكروز يطير تحت مستوى الرادار، بين الجبال والمباني.", "level": "صعب جدا", "cat": "صواريخ"},
    {"q": "ما هو نظام Aegis؟", "options": ["نظام دفاع جوي بحري أمريكي على السفن", "نظام بري روسي", "نظام دفاع جوي إسرائيلي", "نظام درونات"], "correct": 0, "explain": "Aegis على المدمرات الأمريكية، يحمي الأساطيل والمدن الساحلية.", "level": "صعب جدا", "cat": "دفاع جوي"},
    {"q": "كم مدى رادار القبة الحديدية؟", "options": ["يكشف الصواريخ من 40 كم فقط، لأنه مخصص للقصير", "يكشف من 1000 كم", "يكشف من 400 كم", "يكشف من 200 كم"], "correct": 0, "explain": "القبة لا تحتاج رادار بعيد، لأنها تعترض صواريخ قريبة جدا.", "level": "صعب جدا", "cat": "رادار"},
    {"q": "ما هو صاروخ خيبر شكن الإيراني؟", "options": ["باليستي بمدى 1450 كم", "درون", "صاروخ كروز بحري", "صاروخ فضائي"], "correct": 0, "explain": "خيبر شكن هو تطوير لشهاب، مداه يغطي إسرائيل.", "level": "صعب جدا", "cat": "صواريخ"},
    {"q": "شو وظيفة الـ IFF في الدفاع الجوي؟", "options": ["تمييز الطائرة الصديقة من العدو حتى لا تُسقط بالخطأ", "إطلاق الصواريخ", "تشويش الرادار", "تدمير الأهداف"], "correct": 0, "explain": "IFF يسأل الطائرة: من أنت؟ إذا لم تجب صح، تعتبر عدو.", "level": "صعب جدا", "cat": "دفاع جوي"},
    {"q": "ما هو نظام MIM-23 هوك؟", "options": ["نظام دفاع جوي أمريكي قديم متوسط المدى، استبدله باتريوت", "نظام روسي جديد", "نظام إسرائيلي", "نظام ليزر"], "correct": 0, "explain": "هوك كان قبل باتريوت، وما زال موجودا في بعض الدول.", "level": "صعب جدا", "cat": "دفاع جوي"},
    {"q": "كم عدد طبقات الدفاع الجوي الإسرائيلي؟", "options": ["4 طبقات: قبة، مقلاع، أرو 2، أرو 3", "طبقة واحدة", "طبقتين فقط", "6 طبقات"], "correct": 0, "explain": "إسرائيل عندها 4 طبقات، كل طبقة تغطي مدى وارتفاع مختلف.", "level": "صعب جدا", "cat": "دفاع جوي"},
    {"q": "ما هو صاروخ فتاح الإيراني؟", "options": ["صاروخ فرط صوتي بمدى 1400 كم وسرعة ماخ 13", "صاروخ كروز بطيء", "درون", "صاروخ قصير المدى"], "correct": 0, "explain": "فتاح أول فرط صوتي إيراني، مناور ويصعب اعتراضه.", "level": "صعب جدا", "cat": "صواريخ"},
    {"q": "لماذا إسرائيل تستخدم 4 أنظمة وليس نظام واحد؟", "options": ["لأن كل نظام يغطي مدى وارتفاع مختلف، ولا نظام يغطي الكل", "لأنها غنية", "لأن الأنظمة ضعيفة", "لأنها تحب التنويع"], "correct": 0, "explain": "لا يوجد نظام واحد يغطي من 4 كم لـ 2400 كم، لازم طبقات.", "level": "صعب جدا", "cat": "دفاع جوي"},
    {"q": "ما هو نظام C-RAM؟", "options": ["مدفع سريع يطلق 4500 طلقة بالدقيقة لاعتراض القذائف", "صاروخ باليستي", "رادار", "درون"], "correct": 0, "explain": "C-RAM هو آخر خط دفاع، يدمر القذيفة قبل ثواني من سقوطها.", "level": "صعب جدا", "cat": "دفاع جوي"},
    {"q": "شو الفرق بين صاروخ أرض-جو وصاروخ جو-جو؟", "options": ["أرض-جو يُطلق من الأرض، جو-جو يُطلق من طائرة", "لا فرق", "أرض-جو أسرع", "جو-جو أطول مدى"], "correct": 0, "explain": "باتريوت أرض-جو، AMRAAM جو-جو، لكن NASAMS يستخدم AMRAAM من الأرض.", "level": "صعب جدا", "cat": "صواريخ"},
    {"q": "ما هو نظام بانتسير الروسي؟", "options": ["نظام قصير المدى يجمع مدفع وصاروخ لحماية الأنظمة الكبيرة", "نظام بعيد المدى", "دبابة", "طائرة"], "correct": 0, "explain": "بانتسير يحمي S-400 من الدرونات والصواريخ القريبة.", "level": "صعب جدا", "cat": "دفاع جوي"},
    {"q": "كم تبلغ دقة صاروخ القبة الحديدية؟", "options": ["حوالي 90% ضد الصواريخ المتجهة لمناطق سكنية", "100% ضد كل الصواريخ", "50% فقط", "20%"], "correct": 0, "explain": "القبة لا تعترض كل شي، فقط الصواريخ التي ستسقط في مناطق مأهولة، ونسبة نجاحها 90%.", "level": "صعب جدا", "cat": "دفاع جوي"},
    {"q": "ما هو صاروخ سكود؟", "options": ["صاروخ باليستي سوفيتي قديم مداه 300-700 كم", "صاروخ أمريكي جديد", "صاروخ كروز", "درون"], "correct": 0, "explain": "سكود استخدم في حرب الخليج، وهو أساس كثير من الصواريخ الإيرانية.", "level": "صعب جدا", "cat": "صواريخ"},
    {"q": "شو يعني CEP في الصواريخ؟", "options": ["مقياس الدقة، يعني نصف الصواريخ تسقط داخل هذه الدائرة", "سرعة الصاروخ", "مدى الصاروخ", "وزن الرأس"], "correct": 0, "explain": "CEP 10 متر يعني دقة عالية جدا، CEP 500 متر يعني دقة سيئة.", "level": "صعب جدا", "cat": "صواريخ"},
    {"q": "ما هو نظام Spyder الإسرائيلي؟", "options": ["دفاع جوي قصير المدى يستخدم صواريخ جو-جو من الأرض", "نظام بحري", "نظام هجومي", "رادار"], "correct": 0, "explain": "Spyder يستخدم صواريخ بايثون وديربي، سريع الانتشار.", "level": "صعب جدا", "cat": "دفاع جوي"},
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

# ===== نظام الأسئلة V3 - كامل =====
USED_QUESTIONS = []
QUIZ_STREAK = {}
QUIZ_STATS = {}
WRONG_STREAK = {}

LEVEL_INFO = {
    "easy": {"emoji": "🟢 سهل", "coins": 1, "color": "🟢"},
    "medium": {"emoji": "🟡 متوسط", "coins": 2, "color": "🟡"},
    "hard": {"emoji": "🔴 صعب", "coins": 3, "color": "🔴"},
}

FUNNY_LEVEL_1 = [
    "😅 {name} هالمرة ما زبطت معك، الجاي أحسن!",
    "🤏 {name} كنت قريب! بس الرادار خدعك",
]
FUNNY_LEVEL_2 = [
    "😂😂 {name} تاني غلطة ورا بعض! شكلك بتحلل وانت نايم!",
    "🤦 {name} مرتين غلط! حتى الدرون ضحك عليك!",
]
FUNNY_LEVEL_3 = [
    "🚨🚨 فضيحة! {name} غلط 3 مرات ورا بعض! 👑 ملك الهبد الرسمي!",
    "😂😂😂 {name} خلص، القيصر قرر يسحب منك الرتبة العسكرية الوهمية!",
]

def get_funny_message(name, uid):
    wrong = WRONG_STREAK.get(str(uid), 0)
    if wrong >= 3:
        return random.choice(FUNNY_LEVEL_3).format(name=name)
    elif wrong == 2:
        return random.choice(FUNNY_LEVEL_2).format(name=name)
    else:
        return random.choice(FUNNY_LEVEL_1).format(name=name)

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
        await asyncio.sleep(21600)

async def send_quiz_for_chat(context, chat_id):
    if chat_id in ACTIVE_QUIZZES:
        return
    global USED_QUESTIONS
    if len(USED_QUESTIONS) >= len(QUESTIONS):
        USED_QUESTIONS = []
    available = [i for i in range(len(QUESTIONS)) if i not in USED_QUESTIONS]
    q_index = random.choice(available)
    USED_QUESTIONS.append(q_index)
    q = QUESTIONS[q_index]
    options_shuffled = q["options"][:]
    correct_text = options_shuffled[q["correct"]]
    random.shuffle(options_shuffled)
    correct_index = options_shuffled.index(correct_text)
    q = dict(q)
    q["options"] = options_shuffled
    q["correct"] = correct_index
    labels = ["أ", "ب", "ج", "د"]
    lvl = LEVEL_INFO.get(q.get("level", "easy"), LEVEL_INFO["easy"])
    cat = q.get("cat", "عام")
    options_text = "".join([f"{labels[i]} - {opt}\n" for i, opt in enumerate(q["options"])])
    keyboard = [[InlineKeyboardButton(f"\u200f{labels[i]} - {opt}", callback_data=f"quiz_{q_index}_{i}")] for i, opt in enumerate(q["options"])]
    text = f"{lvl['color']} سؤال {lvl['emoji']} | 📂 {cat}\n\n❓ {q['q']}\n\n{options_text}\n⏳ معك 2 دقيقة!\n🪙 صح = {lvl['coins']} عملة | ⚡ أول واحد صح = ضعف العملات\n🔥 3 صح ورا بعض = +5 عملات"
    try:
        msg = await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=InlineKeyboardMarkup(keyboard))
        ACTIVE_QUIZZES[chat_id] = {"q_index": q_index, "message_id": msg.message_id, "chat_id": chat_id, "answers": {}, "level": q.get("level", "easy")}
        asyncio.create_task(finish_after_120_for_chat(context, chat_id))
        asyncio.create_task(quiz_countdown(context, chat_id, msg.message_id))
    except Exception as e:
        print(f"Send quiz failed {chat_id}: {e}")

async def send_quiz(context):
    for chat_id in list(GROUP_IDS):
        await send_quiz_for_chat(context, chat_id)

async def quiz_countdown(context, chat_id, message_id):
    for remaining in [90, 60, 30]:
        await asyncio.sleep(30)
        if chat_id not in ACTIVE_QUIZZES:
            return
        try:
            quiz = ACTIVE_QUIZZES[chat_id]
            q = QUESTIONS[quiz["q_index"]]
            labels = ["أ", "ب", "ج", "د"]
            options_text = "".join([f"{labels[i]} - {opt}\n" for i, opt in enumerate(q["options"])])
            lvl = LEVEL_INFO.get(quiz.get("level", "easy"), LEVEL_INFO["easy"])
            keyboard = [[InlineKeyboardButton(f"\u200f{labels[i]} - {opt}", callback_data=f"quiz_{quiz['q_index']}_{i}")] for i, opt in enumerate(q["options"])]
            new_text = f"{lvl['color']} سؤال {lvl['emoji']} | 📂 {q.get('cat','عام')}\n\n❓ {q['q']}\n\n{options_text}\n⏰ باقي {remaining} ثانية! سارعوا 🔥"
            await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=new_text, reply_markup=InlineKeyboardMarkup(keyboard))
        except:
            pass

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
    labels = ["أ", "ب", "ج", "د"]
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
    lvl_coins = LEVEL_INFO.get(quiz.get("level", "easy"), LEVEL_INFO["easy"])["coins"]
    winners_text = ""
    if winners:
        first_uid = winners[0][0]
        for uid, name in winners:
            was_habid = WRONG_STREAK.get(str(uid), 0) >= 3
            bonus = lvl_coins * 2 if str(uid) == str(first_uid) else lvl_coins
            new_coins = add_coins(int(uid), bonus)
            WEEKLY[str(uid)] = WEEKLY.get(str(uid), 0) + 10
            QUIZ_STATS.setdefault(str(uid), {"right": 0, "wrong": 0})
            QUIZ_STATS[str(uid)]["right"] += 1
            QUIZ_STREAK[str(uid)] = QUIZ_STREAK.get(str(uid), 0) + 1
            streak_msg = ""
            if QUIZ_STREAK[str(uid)] % 3 == 0:
                add_coins(int(uid), 5)
                streak_msg = " 🔥 بونص سلسلة +5!"
            tag = " ⚡ أسرع محلل!" if str(uid) == str(first_uid) else ""
            comeback_msg = ""
            if was_habid:
                comeback_msg = f"\n🎉🎉 عودة الأسطورة! {name} رجع للطريق الصح بعد الهبد! 😂🔥\n👑 تم سحب لقب ملك الهبد من {name}! مبروك التوبة!"
                if QUIZ_STREAK[str(uid)] >= 2:
                    add_coins(int(uid), 3)
                    comeback_msg += f"\n🏆 بونص العودة +3 عملات!"
            winners_text += f"🏆 {name}{tag} - ربح {bonus} عملة 🪙 (صار معو {new_coins}){streak_msg}{comeback_msg}\n"
            WRONG_STREAK[str(uid)] = 0
        for uid, name in losers:
            QUIZ_STREAK[str(uid)] = 0
            QUIZ_STATS.setdefault(str(uid), {"right": 0, "wrong": 0})
            QUIZ_STATS[str(uid)]["wrong"] += 1
    else:
        winners_text = "😴 ما حد جاوب صح هالمرة!"
    funny_text = ""
    if losers:
        funny_text = "\n😂 اللي جاوبو غلط:\n"
        for uid, name in losers:
            WRONG_STREAK[str(uid)] = WRONG_STREAK.get(str(uid), 0) + 1
            funny_text += get_funny_message(name, uid) + "\n"
            if WRONG_STREAK[str(uid)] >= 3:
                funny_text += f"🏷️ لقب جديد لـ {name}: ملك الهبد 👑😂\n"
    final_text = f"⏰ انتهى الوقت!\n\n✅ الجواب الصح: {labels[correct]} - {q['options'][correct]}\n\n📚 الشرح:\n{q['explain']}\n\n{winners_text}{funny_text}\n\nالسؤال الجاي بعد ساعتين 🔥"
    try:
        await context.bot.send_message(chat_id=chat_id, text=final_text)
    except Exception as e:
        print(f"Finish quiz send failed: {e}")
    del ACTIVE_QUIZZES[chat_id]

async def quiz_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    try:
        _, q_idx_str, choice_str = data.split("_")
        q_idx = int(q_idx_str)
        choice = int(choice_str)
    except:
        await query.answer()
        return
    user = query.from_user
    quiz = ACTIVE_QUIZZES.get(query.message.chat_id)
    if not quiz or quiz["q_index"] != q_idx:
        await query.answer("انتهى وقت السؤال!", show_alert=True)
        return
    if str(user.id) in quiz["answers"]:
        await query.answer("انت جاوبت قبل هيك! ممنوع تغيير الجواب 😂", show_alert=True)
        return
    quiz["answers"][str(user.id)] = (choice, user.first_name)
    with _LOCK:
        if str(user.id) not in USERS:
            USERS[str(user.id)] = {"points": 0, "name": user.first_name, "coins": 0, "msg_count": 0}
        else:
            USERS[str(user.id)]["name"] = user.first_name
    save_one_user(user.id)
    await query.answer("تم تسجيل جوابك! استنى انتهاء الوقت 🔥", show_alert=False)

async def quiz_stats_cmd(update, context):
    uid = str(update.effective_user.id)
    s = QUIZ_STATS.get(uid, {"right": 0, "wrong": 0})
    total = s["right"] + s["wrong"]
    perc = int(s["right"]/total*100) if total > 0 else 0
    streak = QUIZ_STREAK.get(uid, 0)
    wrong = WRONG_STREAK.get(uid, 0)
    title = " 👑 ملك الهبد" if wrong >= 3 else ""
    await update.message.reply_text(f"📊 احصائياتك بالأسئلة يا {update.effective_user.first_name}{title}:\n\n✅ صح: {s['right']}\n❌ غلط: {s['wrong']}\n🎯 نسبة ذكائك: {perc}%\n🔥 سلسلتك: {streak}\n😂 غلطات ورا بعض: {wrong}")

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
    if query.data.startswith("senario_"):
        await senario_callback(update, context)
        return
    # اذا كان جواب سؤال، حوله لدالة الأسئلة
    if query.data.startswith("war_"):
        await war_callback(update, context)
        return
    if query.data.startswith("quiz_"):
        await quiz_callback(update, context)
        return
    if query.data.startswith("vote_"):
        await vote_callback(update, context)
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
    await update.message.reply_text(text)

OWNER_ID = 5684337197
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
    asyncio.create_task(prediction_loop(a))
    asyncio.create_task(senario_loop(a))
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
def war_power(uid):
    w = get_war(uid)
    total = 0
    for k, count in w["army"].items():
        total += ARMY[k]["power"] * count
    return total

async def war_callback(update, context):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    uid = str(user.id)
    w = get_war(uid)
    data = query.data

    # زر الرجوع للقائمة الرئيسية
    if data == "war_back":
        text = (f"⚔️ <b>إمبراطورية الحرب</b>\n\n"
                f"👤 {user.first_name}\n"
                f"🏆 نقاط حرب: {w['war_points']}\n\n"
                f"🛢️ نفط: {w['oil']} | 🔩 حديد: {w['iron']} | 🌾 قمح: {w['wheat']}\n\n"
                f"🏗️ مباني: {sum(w['buildings'].values())} | 🪖 جنود: {sum(w['army'].values())}")
        kb = [[InlineKeyboardButton("🏗️ مباني", callback_data="war_buildings"),
               InlineKeyboardButton("🪖 جيش", callback_data="war_army")],
              [InlineKeyboardButton("🎁 جمع الموارد", callback_data="war_collect"),
               InlineKeyboardButton("🏆 ترتيب الحرب", callback_data="war_top")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
        return

    # قائمة المباني
    if data == "war_buildings":
        text = f"🏗️ <b>مبانيك</b>\n\n🪙 معك: {USERS.get(uid, {}).get('coins', 0)} عملة\n\nاضغط على مبنى لشرائه:\n"
        kb = []
        for key, b in BUILDINGS.items():
            lvl = w["buildings"].get(key, 0)
            kb.append([InlineKeyboardButton(f"{b['name']} - Lv {lvl} | {b['cost']} 🪙", callback_data=f"war_buy_{key}")])
        kb.append([InlineKeyboardButton("🔙 رجوع", callback_data="war_back")])
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
        return

    # قائمة الجيش
    if data == "war_army":
        text = f"🪖 <b>جيشك - القوة: {war_power(uid)}</b>\n\n🪙 عملات: {USERS.get(uid, {}).get('coins', 0)} | 🛢️ {w['oil']} | 🔩 {w['iron']} | 🌾 {w['wheat']}\n\nاضغط لشراء:"
        kb = []
        for key, a in ARMY.items():
            cnt = w["army"].get(key, 0)
            kb.append([InlineKeyboardButton(f"{a['name']} - عندك {cnt} | {a.get('cost_gold',0)} 🪙 قوة {a['power']}", callback_data=f"war_buyarmy_{key}")])
        kb.append([InlineKeyboardButton("🔙 رجوع", callback_data="war_back")])
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
        return

    # جمع الموارد
    if data == "war_collect":
        now = int(_time.time())
        passed = now - w["last_collect"]
        if passed < 60:
            await query.answer(f"استنى {60-passed} ثانية!", show_alert=True)
            return
        gain_oil = w["buildings"].get("oil_factory",0) * 5 + 5
        gain_iron = w["buildings"].get("iron_mine",0) * 5 + 5
        gain_wheat = w["buildings"].get("farm",0) * 8 + 10
        w["oil"] += gain_oil; w["iron"] += gain_iron; w["wheat"] += gain_wheat
        w["last_collect"] = now
        save_war(uid)
        await query.answer(f"تم الجمع! +{gain_oil} نفط +{gain_iron} حديد +{gain_wheat} قمح", show_alert=True)
        return

    # ترتيب الحرب
    if data == "war_top":
        sorted_war = sorted(WAR.items(), key=lambda x: x[1].get("war_points",0), reverse=True)[:10]
        text = "🏆 <b>ترتيب الحرب:</b>\n\n"
        for i, (uid2, wd) in enumerate(sorted_war, 1):
            nm = USERS.get(uid2, {}).get("name", "بطل")
            text += f"{i}. {nm} - {wd.get('war_points',0)} نقطة | قوة {war_power(uid2)}\n"
        if not sorted_war:
            text += "لسا ما حد لعب!"
        kb = [[InlineKeyboardButton("🔙 رجوع", callback_data="war_back")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
        return

    # شراء مبنى
    if data.startswith("war_buy_"):
        key = data.replace("war_buy_", "")
        b = BUILDINGS.get(key)
        if not b:
            return
        coins = USERS.get(uid, {}).get("coins", 0)
        if coins < b["cost"]:
            await query.answer(f"ما معك عملات كفاية! بدك {b['cost']} ومعك {coins}", show_alert=True)
            return
        USERS[uid]["coins"] -= b["cost"]
        w["buildings"][key] = w["buildings"].get(key, 0) + 1
        save_one_user(uid); save_war(uid)
        await query.answer(f"تم شراء {b['name']} بنجاح! 🔥", show_alert=True)
        return

    # شراء جندي
    if data.startswith("war_buyarmy_"):
        key = data.replace("war_buyarmy_", "")
        a = ARMY.get(key)
        if not a:
            return
        coins = USERS.get(uid, {}).get("coins", 0)
        need_gold = a.get("cost_gold", 0)
        need_oil = a.get("cost_oil", 0)
        need_iron = a.get("cost_iron", 0)
        need_wheat = a.get("cost_wheat", 0)
        if coins < need_gold or w["oil"] < need_oil or w["iron"] < need_iron or w["wheat"] < need_wheat:
            await query.answer("مواردك ما بتكفي! اجمع موارد أول", show_alert=True)
            return
        USERS[uid]["coins"] -= need_gold
        w["oil"] -= need_oil; w["iron"] -= need_iron; w["wheat"] -= need_wheat
        w["army"][key] = w["army"].get(key, 0) + 1
        save_one_user(uid); save_war(uid)
        await query.answer(f"تم شراء {a['name']}! 🪖", show_alert=True)
        return
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
    
    # ===== دالة التوقع اليومي =====
async def send_daily_prediction(context):
    PREDICTIONS.clear()
    keyboard = [[
        InlineKeyboardButton("✅ آه بتوقع", callback_data="vote_ah"),
        InlineKeyboardButton("❌ لا ما بتوقع", callback_data="vote_la"),
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = POLL_BASE_TEXT + "\n\n📊 التصويت الحالي:\n✅ آه: 0\n❌ لا: 0\n👥 مجموع: 0"
    for gid in list(GROUP_IDS):
        try:
            msg = await context.bot.send_message(chat_id=gid, text=text, reply_markup=reply_markup)
            POLL_MESSAGES[gid] = msg.message_id
        except Exception as e:
            print(f"Prediction send failed {gid}: {e}")

async def update_poll_message(context, chat_id):
    if chat_id not in POLL_MESSAGES:
        return
    ah = sum(1 for v in PREDICTIONS.values() if v["ans"] == "ah")
    la = sum(1 for v in PREDICTIONS.values() if v["ans"] == "la")
    total = ah + la
    new_text = POLL_BASE_TEXT + f"\n\n📊 التصويت الحالي:\n✅ آه: {ah}\n❌ لا: {la}\n👥 مجموع: {total}"
    keyboard = [[
        InlineKeyboardButton(f"✅ آه ({ah})", callback_data="vote_ah"),
        InlineKeyboardButton(f"❌ لا ({la})", callback_data="vote_la"),
    ]]
    try:
        await context.bot.edit_message_text(chat_id=chat_id, message_id=POLL_MESSAGES[chat_id], text=new_text, reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e:
       print(f"Update poll failed: {e}")

async def vote_callback(update, context):
    query = update.callback_query
    ans = "ah" if query.data == "vote_ah" else "la"
    chat_id = query.message.chat.id
    save_group_id(chat_id)
    PREDICTIONS[query.from_user.id] = {"name": query.from_user.first_name, "ans": ans}
    word = "آه بتوقع ✅" if ans == "ah" else "لا ما بتوقع ❌"
    await query.answer(f"تم تسجيل توقعك: {word}")
    await update_poll_message(context, chat_id)

async def prediction_loop(app):
    while True:
        try:
            now = datetime.datetime.now(ZoneInfo("Asia/Hebron"))
            # الساعة 8 المسا كل يوم
            if now.hour == 20 and now.minute < 10:
                fake_context = type("C", (), {"bot": app.bot})()
                await send_daily_prediction(fake_context)
                await asyncio.sleep(3600)
        except Exception as e:
            print(f"Prediction loop error: {e}")
        await asyncio.sleep(600)
async def test_prediction(update, context):
    chat_id = update.effective_chat.id
    save_group_id(chat_id)
    await send_daily_prediction(context)
    await update.message.reply_text("تم ارسال سؤال التوقع التجريبي 🔥")

async def natija_command(update, context):
    if not context.args:
        await update.message.reply_text("اكتب: /natija ah  أو  /natija la")
        return
    correct = context.args[0].lower()
    if correct not in ["ah", "la"]:
        await update.message.reply_text("اكتب ah أو la بس")
        return
    if not PREDICTIONS:
        await update.message.reply_text("ما في توقعات اليوم")
        return
    
    winners = []
    losers = []
    for uid, data in PREDICTIONS.items():
        if data["ans"] == correct:
            winners.append(data["name"])
            # هون بنضيف النقاط - إذا عندك دالة نقاط غيرها قلي
            try:
                add_points(uid, data["name"], 10)
            except:
                pass
        else:
            losers.append(data["name"])
    
    word = "آه - تجددت الحرب ✅" if correct == "ah" else "لا - ما تجددت الحرب ❌"
    text = f"🏁 نتيجة التوقع: {word}\n\n🏆 اللي توقعوا صح (+10 نقاط):\n"
    text += "\n".join([f"• {n}" for n in winners]) if winners else "ما حدا توقع صح 😅"
    text += f"\n\n😢 اللي توقعوا غلط:\n"
    text += "\n".join([f"• {n}" for n in losers]) if losers else "ما حدا"
    await update.message.reply_text(text)
    PREDICTIONS.clear()

def make_card(name, points, coins, rank):
    # بطاقة بسيطة بدون صورة لحد ما نعمل تصميم
    try:
        from PIL import Image, ImageDraw, ImageFont
        img = Image.new("RGB", (800, 400), (20, 20, 30))
        d = ImageDraw.Draw(img)
        d.text((50, 50), f"{name}", fill=(255, 215, 0))
        d.text((50, 150), f"Points: {points} | Coins: {coins} | Rank: #{rank}", fill=(255, 255, 255))
        path = f"card_{rank}.png"
        img.save(path)
        return path
    except Exception as e:
        print(f"Card error: {e}")
        return "main.jpg"

# ===== مولد سيناريو حرب عشوائي - شغال لحاله =====
import random as _rnd2

SCENARIO_ENEMIES = [
    "300 درون انتحاري", "50 دبابة", "20 طائرة مقاتلة", "100 صاروخ باليستي",
    "10 غواصات", "500 جندي قوات خاصة", "30 راجمة صواريخ", "15 مروحية هجومية",
    "200 صاروخ كروز", "40 مدرعة", "سرب درونات FPV", "3 فرق مشاة كاملة",
]
SCENARIO_TARGETS = [
    "مصفاة نفط", "قاعدة جوية", "مخزن ذخيرة", "ميناء عسكري",
    "جسر استراتيجي", "مقر قيادة", "محطة كهرباء", "مطار مدني",
    "مخزن وقود", "رتل عسكري", "مدينة حدودية", "رادار إنذار مبكر",
]
SCENARIO_WEATHER = [
    "الجو عاصف ومطر", "الجو صافي تماماً", "ضباب كثيف", "الجو ليلي وحالك",
    "عاصفة رملية", "الجو حار جداً 45 درجة", "ثلج وبرد قارس", "الجو مغيم",
]
SCENARIO_STATUS = [
    "دفاعك ناقص 50%", "دفاعك كامل 100%", "ما عندك غطاء جوي",
    "ذخيرتك رح تخلص بعد ساعة", "قواتك تعبانة من 3 أيام قتال",
    "عندك دعم جوي جاهز", "راداراتك معطلة", "عندك 10 دقائق بس تتصرف",
]
SCENARIO_DECISIONS = [
    ["انسحب فوراً واحمي القوات", "اضرب بالصواريخ قبل ما يوصلوا", "شغل التشويش الإلكتروني", "اطلب دعم جوي عاجل"],
    ["افخخ الطريق واعمل كمين", "وزع القوات وشتتها", "اهجم هجوم مضاد مفاجئ", "احتمي بالأنفاق واستنى"],
    ["اقصف مقر قيادتهم أول", "اقطع الإمدادات عنهم", "فاوض واكسب وقت", "فجر الجسر وامنع تقدمهم"],
]

ACTIVE_SENARIO = {}
SCENARIO_COUNT = [0]

def build_random_scenario():
    enemy = _rnd2.choice(SCENARIO_ENEMIES)
    target = _rnd2.choice(SCENARIO_TARGETS)
    weather = _rnd2.choice(SCENARIO_WEATHER)
    status = _rnd2.choice(SCENARIO_STATUS)
    decisions = _rnd2.choice(SCENARIO_DECISIONS)
    SCENARIO_COUNT[0] += 1
    return {"num": SCENARIO_COUNT[0], "enemy": enemy, "target": target, "weather": weather, "status": status, "decisions": decisions}

async def send_scenario_for_chat(context, chat_id):
    if chat_id in ACTIVE_SENARIO:
        return
    s = build_random_scenario()
    labels = ["أ", "ب", "ج", "د"]
    options_text = "".join([f"{labels[i]} - {opt}\n" for i, opt in enumerate(s["decisions"])])
    keyboard = [[InlineKeyboardButton(f"{labels[i]} - {opt}", callback_data=f"senario_{s['num']}_{i}")] for i, opt in enumerate(s["decisions"])]
    text = f"⚔️ سيناريو حرب #{s['num']} ⚔️\n\n🚨 العدو هجم بـ {s['enemy']} على {s['target']}!\n\n🌦️ {s['weather']}\n🛡️ وضعك: {s['status']}\n\n🧠 شو أول قرار بتاخده يا قائد؟\n\n{options_text}\n⏳ معك 2 دقيقة!\n🏆 أكثر قرار اختاروه الناس = القرار الفائز\n🪙 اللي صوت = +1 نقطة"
    try:
        msg = await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=InlineKeyboardMarkup(keyboard))
        ACTIVE_SENARIO[chat_id] = {"num": s["num"], "msg_id": msg.message_id, "scenario": s, "votes": {}}
        asyncio.create_task(finish_scenario_after(context, chat_id))
    except Exception as e:
        print(f"Senario failed: {e}")

async def finish_scenario_after(context, chat_id):
    await asyncio.sleep(120)
    await finish_scenario(context, chat_id)

async def finish_scenario(context, chat_id):
    data = ACTIVE_SENARIO.get(chat_id)
    if not data:
        return
    s = data["scenario"]
    labels = ["أ", "ب", "ج", "د"]
    try:
        await context.bot.edit_message_reply_markup(chat_id=chat_id, message_id=data["msg_id"], reply_markup=None)
    except:
        pass
    counts = [0,0,0,0]
    for uid, (choice, name) in data["votes"].items():
        counts[choice] += 1
    max_votes = max(counts) if counts else 0
    winner_idx = counts.index(max_votes) if max_votes > 0 else 0
    winners_text = ""
    for uid, (choice, name) in data["votes"].items():
        if choice == winner_idx and max_votes > 0:
            try:
                new_coins = add_coins(int(uid), 2)
                winners_text += f"🏆 {name} - قرارك كان قرار الأغلبية! +2 عملة (صار معو {new_coins})\n"
            except:
                winners_text += f"🏆 {name} - قرارك كان قرار الأغلبية!\n"
    if not winners_text:
                winners_text = "😅 ما حد صوت هالمرة!"
        
    result_text = f"انتهى سيناريو #{s['num']}!\n\nالقرار الفائز: {labels[winner_idx]} - {s['decisions'][winner_idx]}\n\n{winners_text}"
    try:
        await context.bot.send_message(chat_id=chat_id, text=result_text)
    except Exception as e:
        print(f"Finish senario failed: {e}")
    del ACTIVE_SENARIO[chat_id]
async def post_init(a):
    asyncio.create_task(quiz_loop(a))
    asyncio.create_task(weekly_hero_loop(a))
    asyncio.create_task(prediction_loop(a))
    asyncio.create_task(senario_loop(a))

async def senario_callback(update, context):
    query = update.callback_query
    try:
        _, num_str, choice_str = query.data.split("_")
        choice = int(choice_str)
    except:
        await query.answer()
        return
    chat_id = query.message.chat_id
    sc = ACTIVE_SENARIO.get(chat_id)
    if not sc:
        await query.answer("انتهى السيناريو!", show_alert=True)
        return
    if str(query.from_user.id) in sc["votes"]:
        await query.answer("صوتت قبل هيك!", show_alert=True)
        return
    sc["votes"][str(query.from_user.id)] = (choice, query.from_user.first_name)
    await query.answer("تم تسجيل صوتك!")
    try:
        add_points(query.from_user.id, 1)
    except:
        pass

async def cmd_senario(update, context):
    chat_id = update.effective_chat.id
    save_group_id(chat_id)
    await send_scenario_for_chat(context, chat_id)
    await update.message.reply_text("تم ارسال سيناريو تجريبي")

async def senario_loop(app):
    await asyncio.sleep(10)
    while True:
        try:
            fake = type("C", (), {"bot": app.bot})()
            for chat_id in list(GROUP_IDS):
                await send_scenario_for_chat(fake, chat_id)
        except Exception as e:
            print(f"Senario loop error: {e}")
        await asyncio.sleep(21600)

async def fix_tag(update, context):
    user = update.effective_user
    chat_id = update.effective_chat.id
    points = USERS.get(str(user.id), {}).get("points", 0)
    rank = get_rank_name(points)
    ok = await update_user_tag(context, chat_id, user.id, rank)
    if ok:
        await update.message.reply_text(f"تم ✅ وسمك هسا صار: {rank}\nشوف اسمك بالجروب")
    else:
        await update.message.reply_text(f"فشل الوسم ❌\nالرتبة: {rank}\nابعثلي سكرين للوج بالـ Render")

async def auto_question_job(context):
    if not GROUP_IDS:
        return
    for chat_id in list(GROUP_IDS):
        try:
            me = await context.bot.get_me()
            member = await context.bot.get_chat_member(chat_id, me.id)
            if member.status not in ["administrator", "creator"]:
                continue
            await send_quiz_for_chat(context, chat_id)
        except Exception as e:
            print(f"auto_q {chat_id}: {e}")

async def auto_scenario_job(context):
    if not GROUP_IDS:
        return
    for chat_id in list(GROUP_IDS):
        try:
            me = await context.bot.get_me()
            member = await context.bot.get_chat_member(chat_id, me.id)
            if member.status not in ["administrator", "creator"]:
                continue
            s = random.choice(SCENARIOS)
            text = s.get("text") if isinstance(s, dict) else str(s)
            if isinstance(s, dict) and s.get("title"):
                text = f"{s.get('title')}\n\n{text}"
            await context.bot.send_message(chat_id=chat_id, text=f"🎭 سيناريو جديد\n\n{text}")
        except Exception as e:
            print(f"auto_s {chat_id}: {e}")

import random
from datetime import time as dtime
from zoneinfo import ZoneInfo

WHEEL = {"active": False, "players": {}} # user_id -> name

WHEEL_PRIZES = [
    ("🎰 جاكبوت 10+ 🪙", 10, 5),
    ("🔥 ربح كبير 5+ 🪙", 5, 15),
    ("✨ ربح 3+ 🪙", 3, 30),
    ("🎁 ربح 1+ 🪙", 1, 30),
    ("🙂 حظ أوفر", 0, 15),
    ("💀 نحس! 1- عملة", -1, 5),
]

def spin_wheel():
    r = random.randint(1, 100)
    s = 0
    for label, coins, chance in WHEEL_PRIZES:
        s += chance
        if r <= s:
            return label, coins
    return WHEEL_PRIZES[2]

async def send_wheel(context):
    global WHEEL
    chat_id = CHAT_ID  # نفس الـ CHAT_ID اللي عندك تبع القروب
    WHEEL = {"active": True, "players": {}}
    keyboard = [[InlineKeyboardButton("🎡 شارك بالعجلة", callback_data="wheel_join")]]
    text = "🎡🎡 عجلة الحظ فتحت! 🎡🎡\n\n⏰ معكم 10 دقايق بس!\n🪙 جوائز اليوم:\n👑 جاكبوت 50 | 🪙 ذهبي 25 | 🪙 فضي 10 | 🪙 برونزي 5\n💨 حظ أوفر | 💀 نحس -5\n\nكبسة وحدة وبتدخل السحب!"
    msg = await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=InlineKeyboardMarkup(keyboard))
    # بعد 10 دقايق بنقفل
    import asyncio
    await asyncio.sleep(10*60)
    await close_wheel(context, chat_id, msg.message_id)

async def close_wheel(context, chat_id, msg_id):
    if not WHEEL["active"]:
        return
    WHEEL["active"] = False
    players = WHEEL["players"]
    if not players:
        await context.bot.send_message(chat_id=chat_id, text="🎡 خلص وقت العجلة، وما حد شارك اليوم 😢 بكرة 9 المسا بنرجع!")
        return

    # اعلان القفل
    await context.bot.send_message(chat_id=chat_id, text=f"⏳ خلص التسجيل! {len(players)} لاعب مشارك... عم نلف العجلة... 🎡")
    
    results = []
    for uid, name in players.items():
        label, coins = spin_wheel()
        # هون بنستخدم نفس دالة العملات اللي عندك
        try:
            new_coins = add_coins(int(uid), coins)
        except:
            new_coins = coins
        results.append((name, label, coins, new_coins))
    
    # ترتيب الفايزين من الأعلى للأقل
    results.sort(key=lambda x: x[2], reverse=True)
    
    text = "🎡🎡 نتائج عجلة الحظ اليوم! 🎡🎡\n\n"
    for name, label, coins, total in results:
        text += f"• {name} - {label} | صار معه {total} 🪙\n"
    
    # ملك اليوم
    if results and results[0][2] > 0:
        text += f"\n👑 ملك الحظ اليوم: {results[0][0]} 🔥"
    
    await context.bot.send_message(chat_id=chat_id, text=text)
    WHEEL = {"active": False, "players": {}}

async def wheel_join(update, context):
    query = update.callback_query
    uid = str(query.from_user.id)
    name = query.from_user.first_name
    if not WHEEL["active"]:
        await query.answer("العجلة مسكرة، استنى بكرة 9 المسا!", show_alert=True)
        return
    if uid in WHEEL["players"]:
        await query.answer("انت مشارك أصلا! استنى النتايج 🎡", show_alert=True)
        return
    WHEEL["players"][uid] = name
    await query.answer(f"تم! انت رقم {len(WHEEL['players'])} بالعجلة 🎡", show_alert=True)


def main():
    keep_alive()
    global USERS
    load_users_once()
    load_group_ids()
    load_war()
    app = Application.builder().token(TOKEN).post_init(post_init).build()
    app.add_handler(CallbackQueryHandler(wheel_join, pattern="^wheel_join$"))
    app.job_queue.run_repeating(auto_question_job, interval=3*60*60, first=15)
    app.job_queue.run_repeating(auto_scenario_job, interval=8*60*60, first=30)
    # # عجلة الحظ كل يوم 9 المسا بتوقيت فلسطين
    tz = ZoneInfo("Asia/Hebron")
    app.job_queue.run_daily(send_wheel, time=dtime(hour=21, minute=0, tzinfo=tz))
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("harb", cmd_harb))
    app.add_handler(CommandHandler("attack", cmd_attack))
    app.add_handler(CommandHandler("sual", test_quiz))
    app.add_handler(CommandHandler("tawaqa_test", test_prediction))
    app.add_handler(CommandHandler("natija", natija_command))
    app.add_handler(CommandHandler("stats", quiz_stats_cmd))
    app.add_handler(CommandHandler("senario", cmd_senario))
    app.add_handler(CommandHandler("tag", fix_tag))
    app.add_handler(MessageHandler(filters.Regex(r"^(وسمي|/وسمي)$"), fix_tag))
    h1 = MessageHandler(filters.Regex(r"^(ترتيب|/ترتيب|/top)$"), leaderboard)
    h2 = MessageHandler(filters.Regex(r"^(رصيد|رصيدي|/رصيد|/balance)$"), balance)
    h3 = MessageHandler(filters.Regex(r"^(/طير|طير)$"), kick_user)
    h4 = MessageHandler(filters.Regex(r"^(/اسكت|اسكت)$"), mute_user)
    h5 = MessageHandler(filters.Regex(r"^(/احكي|احكي)$"), unmute_user)
    h7 = MessageHandler(filters.Regex(r"^(نقاطي|/نقاطي)$"), weekly_points)
    h8 = MessageHandler(filters.Regex(r"^(بطل الأسبوع|/بطل)$"), weekly_leaderboard)
    h9 = MessageHandler(filters.Regex(r"^(الزوار|/زوار|عداد الزوار)$"), visitors_count)
    h10 = MessageHandler(filters.Regex(r"^(احصائياتي|/احصائياتي|احصائيات)$"), quiz_stats_cmd)
    app.add_handler(h9)
    app.add_handler(h1)
    app.add_handler(h2)
    app.add_handler(h3)
    app.add_handler(h4)
    app.add_handler(h5)
    app.add_handler(h7)
    app.add_handler(h8)
    app.add_handler(h10)
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_new_member))
    h6 = MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    app.add_handler(h6)
    app.add_handler(CallbackQueryHandler(buttons_handler))
    print("Bot is running...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
