import asyncio
from datetime import datetime, timedelta
import logging
import os
from flask import Flask
import pytz
import requests
from threading import Thread
from telegram import BotCommand, ReplyKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# 1. Flask Web Server
app = Flask("")

@app.route("/")
def home():
  return "Bot is alive and running!"

def run_flask():
  app.run(host="0.0.0.0", port=8080)

def keep_alive():
  t = Thread(target=run_flask, daemon=True)
  t.start()

# 2. Data & Settings
BOT_TOKEN = os.environ.get("BOT_TOKEN")
user_cities = {}
PRAYER_CACHE = {}

WILAYAS = {
    "1": {"ar": "أدرار", "en": "Adrar"},
    "2": {"ar": "الشلف", "en": "Chlef"},
    "3": {"ar": "الأغواط", "en": "Laghouat"},
    "4": {"ar": "أم البواقي", "en": "Oum El Bouaghi"},
    "5": {"ar": "باتنة", "en": "Batna"},
    "6": {"ar": "بجاية", "en": "Bejaia"},
    "7": {"ar": "بسكرة", "en": "Biskra"},
    "8": {"ar": "بشار", "en": "Bechar"},
    "9": {"ar": "البليدة", "en": "Blida"},
    "10": {"ar": "البويرة", "en": "Bouira"},
    "11": {"ar": "تمنراست", "en": "Tamanghasset"},
    "12": {"ar": "تبسة", "en": "Tebessa"},
    "13": {"ar": "تلمسان", "en": "Tlemcen"},
    "14": {"ar": "تيارت", "en": "Tiaret"},
    "15": {"ar": "تيزي وزو", "en": "Tizi Ouzou"},
    "16": {"ar": "الجزائر", "en": "Algiers"},
    "17": {"ar": "الجلفة", "en": "Djelfa"},
    "18": {"ar": "جيجل", "en": "Jijel"},
    "19": {"ar": "سطيف", "en": "Setif"},
    "20": {"ar": "سعيدة", "en": "Saida"},
    "21": {"ar": "سكيكدة", "en": "Skikda"},
    "22": {"ar": "سيدي بلعباس", "en": "Sidi Bel Abbes"},
    "23": {"ar": "عنابة", "en": "Annaba"},
    "24": {"ar": "قالمة", "en": "Guelma"},
    "25": {"ar": "قسنطينة", "en": "Constantine"},
    "26": {"ar": "المدية", "en": "Medea"},
    "27": {"ar": "مستغانم", "en": "Mostaganem"},
    "28": {"ar": "المسيلة", "en": "M'Sila"},
    "29": {"ar": "معسكر", "en": "Mascara"},
    "30": {"ar": "ورقلة", "en": "Ouargla"},
    "31": {"ar": "وهران", "en": "Oran"},
    "32": {"ar": "البيض", "en": "El Bayadh"},
    "33": {"ar": "إليزي", "en": "Illizi"},
    "34": {"ar": "برج بوعريريج", "en": "Bordj Bou Arreridj"},
    "35": {"ar": "بومرداس", "en": "Boumerdes"},
    "36": {"ar": "الطارف", "en": "El Tarf"},
    "37": {"ar": "تندوف", "en": "Tindouf"},
    "38": {"ar": "تسمسيلت", "en": "Tissemsilt"},
    "39": {"ar": "الوادي", "en": "El Oued"},
    "40": {"ar": "خنشلة", "en": "Khenchela"},
    "41": {"ar": "سوق أهراس", "en": "Souk Ahras"},
    "42": {"ar": "تيبازة", "en": "Tipaza"},
    "43": {"ar": "ميلة", "en": "Mila"},
    "44": {"ar": "عين الدفلى", "en": "Ain Defla"},
    "45": {"ar": "النعامة", "en": "Naama"},
    "46": {"ar": "عين تموشنت", "en": "Ain Temouchent"},
    "47": {"ar": "غرداية", "en": "Ghardaia"},
    "48": {"ar": "غليزان", "en": "Relizane"},
    "49": {"ar": "تيميمون", "en": "Timimoun"},
    "50": {"ar": "برج باجي مختار", "en": "Bordj Badji Mokhtar"},
    "51": {"ar": "أولاد جلال", "en": "Ouled Djellal"},
    "52": {"ar": "بني عباس", "en": "Beni Abbes"},
    "53": {"ar": "عين صالح", "en": "In Salah"},
    "54": {"ar": "عين قزام", "en": "In Guezzam"},
    "55": {"ar": "تقرت", "en": "Touggourt"},
    "56": {"ar": "جانت", "en": "Djanet"},
    "57": {"ar": "المغير", "en": "El M'Ghair"},
    "58": {"ar": "المنيعة", "en": "El Meniaa"},
}

def fetch_prayer_times(city_en):
  algeria_tz = pytz.timezone("Africa/Algiers")
  today_str = datetime.now(algeria_tz).strftime("%Y-%m-%d")
  cache_key = f"{city_en}_{today_str}"

  if cache_key in PRAYER_CACHE:
    return PRAYER_CACHE[cache_key]

  try:
    url = f"https://api.aladhan.com/v1/timingsByCity?city={city_en}&country=Algeria&method=3"
    response = requests.get(url, timeout=3)
    data = response.json()
    if data["code"] == 200:
      timings = data["data"]["timings"]
      PRAYER_CACHE[cache_key] = timings
      return timings
  except Exception as e:
    logger.error(f"Error fetching API for {city_en}: {e}")

  return {
      "Fajr": "05:15",
      "Sunrise": "06:41",
      "Dhuhr": "12:48",
      "Asr": "16:18",
      "Maghrib": "18:55",
      "Isha": "20:16",
  }

def get_next_prayer_info(prayer_times):
  algeria_tz = pytz.timezone("Africa/Algiers")
  now = datetime.now(algeria_tz)

  prayers = [
      ("الفجر", prayer_times.get("Fajr", "05:15")),
      ("الشروق", prayer_times.get("Sunrise", "06:41")),
      ("الظهر", prayer_times.get("Dhuhr", "12:48")),
      ("العصر", prayer_times.get("Asr", "16:18")),
      ("المغرب", prayer_times.get("Maghrib", "18:55")),
      ("العشاء", prayer_times.get("Isha", "20:16")),
  ]

  for name, time_str in prayers:
    prayer_time_obj = datetime.strptime(time_str[:5], "%H:%M").time()
    prayer_dt = algeria_tz.localize(datetime.combine(now.date(), prayer_time_obj))

    if prayer_dt > now:
      diff = prayer_dt - now
      hours, remainder = divmod(diff.seconds, 3600)
      minutes = remainder // 60
      time_left_str = ""
      if hours > 0:
        time_left_str += f"{hours} ساعة "
      if minutes > 0 or hours == 0:
        time_left_str += f"و {minutes} دقيقة" if hours > 0 else f"{minutes} دقيقة"
      return name, time_left_str.strip()

  fajr_time_obj = datetime.strptime(prayer_times.get("Fajr", "05:15")[:5], "%H:%M").time()
  tomorrow_fajr = algeria_tz.localize(datetime.combine(now.date() + timedelta(days=1), fajr_time_obj))
  diff = tomorrow_fajr - now
  hours, remainder = divmod(diff.seconds, 3600)
  minutes = remainder // 60

  return "الفجر (غداً)", f"{hours} ساعة و {minutes} دقيقة" if hours > 0 else f"{minutes} دقيقة"

def build_prayer_dashboard(city_ar, prayer_times):
  algeria_tz = pytz.timezone("Africa/Algiers")
  today_date = datetime.now(algeria_tz).strftime("%Y-%m-%d")
  next_prayer, time_remaining = get_next_prayer_info(prayer_times)

  return (
      f"🕌 **مواقيت الصلاة لولاية {city_ar}**\n"
      f"📅 **اليوم:** {today_date}\n\n"
      f"`الفـجـر   :` `{prayer_times.get('Fajr')[:5]}`\n"
      f"`الشروق  :` `{prayer_times.get('Sunrise')[:5]}`\n"
      f"`الظـهـر   :` `{prayer_times.get('Dhuhr')[:5]}`\n"
      f"`العـصـر   :` `{prayer_times.get('Asr')[:5]}`\n"
      f"`المغرب  :` `{prayer_times.get('Maghrib')[:5]}`\n"
      f"`العـشاء  :` `{prayer_times.get('Isha')[:5]}`\n\n"
      f"───────────────\n"
      f"⏳ **الصلاة القادمة:** صلاة {next_prayer}\n"
      f"⏱ **الوقت المتبقي:** {time_remaining}"
  )

def get_main_keyboard():
  return ReplyKeyboardMarkup([["🕌 مواقيت الصلاة", "⚙️ تغيير الولاية"]], resize_keyboard=True, persistent=True)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
  msg = (
      "أهلاً بك في بوت مواقيت الصلاة للجزائر 🇩🇿\n\n"
      "يرجى تحديد ولايتك بإرسال رقم الولاية (من 1 إلى 58) أو اسمها.\n"
      "مثال: أرسل `2` للشلف أو `16` للجزائر أو `44` لعين الدفلى."
  )
  await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=get_main_keyboard())

async def setcity_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
  await update.message.reply_text("يرجى إرسال رقم ولايتك (1-58) أو اسم الولاية لتحديثها:", reply_markup=get_main_keyboard())

async def salat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
  chat_id = update.effective_chat.id
  if chat_id not in user_cities:
    await update.message.reply_text("يرجى تحديد ولايتك أولاً بإرسال رقمها (1-58).", reply_markup=get_main_keyboard())
    return
  city_data = user_cities[chat_id]
  prayer_times = fetch_prayer_times(city_data["en"])
  dashboard = build_prayer_dashboard(city_data["ar"], prayer_times)
  await update.message.reply_text(dashboard, parse_mode="Markdown", reply_markup=get_main_keyboard())

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
  chat_id = update.effective_chat.id
  text = update.message.text.strip()

  if text == "🕌 مواقيت الصلاة":
    await salat_command(update, context)
    return
  elif text == "⚙️ تغيير الولاية":
    await setcity_command(update, context)
    return

  selected_city = None
  if text in WILAYAS:
    selected_city = WILAYAS[text]
  else:
    for code, data in WILAYAS.items():
      if data["ar"] in text or text in data["ar"]:
        selected_city = data
        break

  if selected_city:
    user_cities[chat_id] = selected_city
    await update.message.reply_text(
        f"✅ تم حفظ ولايتك: **{selected_city['ar']}**.\n\nاضغط على زر **🕌 مواقيت الصلاة** لعرض الجدول.",
        parse_mode="Markdown",
        reply_markup=get_main_keyboard(),
    )
  else:
    await update.message.reply_text("لم أتعرف على الولاية. يرجى إرسال رقم الولاية الصحيح (1-58).", reply_markup=get_main_keyboard())

# حلقة خلفية للتنبيهات تعمل بدون الحاجة لـ JobQueue
async def prayer_alerts_background_loop(app_bot):
  while True:
    try:
      algeria_tz = pytz.timezone("Africa/Algiers")
      now = datetime.now(algeria_tz)

      for chat_id, city_data in list(user_cities.items()):
        prayer_times = fetch_prayer_times(city_data["en"])
        prayers_check = {
            "الفجر": prayer_times.get("Fajr"),
            "الظهر": prayer_times.get("Dhuhr"),
            "العصر": prayer_times.get("Asr"),
            "المغرب": prayer_times.get("Maghrib"),
            "العشاء": prayer_times.get("Isha"),
        }
        for prayer_name, time_str in prayers_check.items():
          if not time_str:
            continue
          prayer_time_obj = datetime.strptime(time_str[:5], "%H:%M").time()
          prayer_dt = algeria_tz.localize(datetime.combine(now.date(), prayer_time_obj))
          diff_seconds = (prayer_dt - now).total_seconds()

          if 540 <= diff_seconds <= 600:
            alert_msg = (
                f"📢 **تنبيه بصلاة {prayer_name} (ولاية {city_data['ar']})**\n\n"
                f"باقي **10 دقائق** فقط على أذان صلاة {prayer_name}.\n"
                f"قم بالاستعداد والوضوء بارك الله فيك 🕌"
            )
            await app_bot.bot.send_message(chat_id=chat_id, text=alert_msg, parse_mode="Markdown")
    except Exception as e:
      logger.error(f"Error in background alerts: {e}")

    await asyncio.sleep(60)

async def post_init(application: Application):
  commands = [
      BotCommand("salat", "عرض مواقيت الصلاة لولايتك"),
      BotCommand("setcity", "تغيير الولاية الحالية"),
      BotCommand("start", "بدء استخدام البوت وإعداد البيانات"),
  ]
  await application.bot.set_my_commands(commands)
  # تشغيل حلقة التنبيهات في الخلفية
  asyncio.create_task(prayer_alerts_background_loop(application))

def main():
  keep_alive()

  # .job_queue(None) يمنع حدوث خطأ التعارض مع Python 3.14
  app_bot = (
      Application.builder()
      .token(BOT_TOKEN)
      .job_queue(None)
      .post_init(post_init)
      .build()
  )

  app_bot.add_handler(CommandHandler("start", start_command))
  app_bot.add_handler(CommandHandler("setcity", setcity_command))
  app_bot.add_handler(CommandHandler("salat", salat_command))
  app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

  logger.info("Bot is running successfully...")
  app_bot.run_polling()

if __name__ == "__main__":
  main()
