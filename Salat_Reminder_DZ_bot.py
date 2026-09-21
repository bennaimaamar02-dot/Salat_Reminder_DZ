from datetime import datetime, timedelta
import os
from flask import Flask
import pytz
import requests
from threading import Thread
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

# ---------------------------------------------------------
# 1. خادم Flask للحفاظ على استمرار التشغيل
# ---------------------------------------------------------
app = Flask("")


@app.route("/")
def home():
  return "Bot is alive and running!"


def run_flask():
  app.run(host="0.0.0.0", port=8080)


def keep_alive():
  t = Thread(target=run_flask)
  t.start()


# ---------------------------------------------------------
# 2. البيانات والولايات
# ---------------------------------------------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN")

# قاعدة بيانات لحفظ ولاية كل مستخدم {chat_id: "اسم الولاية"}
user_cities = {}

# قائمة بعض الولايات الجزائرية كمثال (يمكن توسيعها لتشمل الـ 58 ولاية)
ALGERIA_CITIES = [
    "الجزائر",
    "وهران",
    "قسنطينة",
    "عنابة",
    "الشلف",
    "باتنة",
    "سطيف",
    "سيدي بلعباس",
    "بسكرة",
    "تلمسان",
    "ورقلة",
    "تيزي وزو",
]


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
    prayer_time_obj = datetime.strptime(time_str, "%H:%M").time()
    prayer_dt = algeria_tz.localize(
        datetime.combine(now.date(), prayer_time_obj)
    )

    if prayer_dt > now:
      diff = prayer_dt - now
      hours, remainder = divmod(diff.seconds, 3600)
      minutes = remainder // 60

      time_left_str = ""
      if hours > 0:
        time_left_str += f"{hours} ساعة "
      if minutes > 0 or hours == 0:
        time_left_str += (
            f"و {minutes} دقيقة" if hours > 0 else f"{minutes} دقيقة"
        )

      return name, time_left_str.strip()

  fajr_time_obj = datetime.strptime(
      prayer_times.get("Fajr", "05:15"), "%H:%M"
  ).time()
  tomorrow_fajr = algeria_tz.localize(
      datetime.combine(now.date() + timedelta(days=1), fajr_time_obj)
  )

  diff = tomorrow_fajr - now
  hours, remainder = divmod(diff.seconds, 3600)
  minutes = remainder // 60

  return (
      "الفجر (غداً)",
      (
          f"{hours} ساعة و {minutes} دقيقة"
          if hours > 0
          else f"{minutes} دقيقة"
      ),
  )


def build_prayer_dashboard(city_name, prayer_times):
  algeria_tz = pytz.timezone("Africa/Algiers")
  today_date = datetime.now(algeria_tz).strftime("%Y-%m-%d")
  next_prayer, time_remaining = get_next_prayer_info(prayer_times)

  message = (
      f"🕌 **مواقيت الصلاة لولاية {city_name}**\n"
      f"📅 **اليوم:** {today_date}\n\n"
      f"`الفـجـر   :` `{prayer_times.get('Fajr', '05:15')}`\n"
      f"`الشروق  :` `{prayer_times.get('Sunrise', '06:41')}`\n"
      f"`الظـهـر   :` `{prayer_times.get('Dhuhr', '12:48')}`\n"
      f"`العـصـر   :` `{prayer_times.get('Asr', '16:18')}`\n"
      f"`المغرب  :` `{prayer_times.get('Maghrib', '18:55')}`\n"
      f"`العـشاء  :` `{prayer_times.get('Isha', '20:16')}`\n\n"
      f"───────────────\n"
      f"⏳ **الصلاة القادمة:** صلاة {next_prayer}\n"
      f"⏱️ **الوقت المتبقي:** {time_remaining}"
  )
  return message


# ---------------------------------------------------------
# 3. اختيار الولاية والأوامر
# ---------------------------------------------------------


async def set_city_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
  keyboard = []
  row = []
  for city in ALGERIA_CITIES:
    row.append(InlineKeyboardButton(city, callback_data=f"set_city_{city}"))
    if len(row) == 2:
      keyboard.append(row)
      row = []
  if row:
    keyboard.append(row)

  reply_markup = InlineKeyboardMarkup(keyboard)
  await update.message.reply_text(
      "اختر ولايتك لضبط مواقيت الصلاة والتنبيهات الخاصة بك:",
      reply_markup=reply_markup,
  )


async def city_callback_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
  query = update.callback_query
  chat_id = update.effective_chat.id

  if query.data.startswith("set_city_"):
    selected_city = query.data.split("set_city_")[-1]
    user_cities[chat_id] = selected_city
    await query.answer(f"تم اختيار ولاية {selected_city} بنجاح!")
    await query.edit_message_text(
        f"✅ تم حفظ ولايتك: **{selected_city}**.\nاستخدم الأمر /salat"
        " لعرض المواقيت.",
        parse_mode="Markdown",
    )


async def salat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
  chat_id = update.effective_chat.id

  # إذا لم يحدد المستخدم ولايته بعد، يطلب منه تحديدها أولاً
  if chat_id not in user_cities:
    await set_city_command(update, context)
    return

  city = user_cities[chat_id]

  # مواقيت استرشادية لولايته (يمكن جلبها من API)
  dummy_times = {
      "Fajr": "05:15",
      "Sunrise": "06:41",
      "Dhuhr": "12:48",
      "Asr": "16:18",
      "Maghrib": "18:55",
      "Isha": "20:16",
  }

  text = build_prayer_dashboard(city, dummy_times)
  await update.message.reply_text(text=text, parse_mode="Markdown")


async def check_and_send_alerts(context: ContextTypes.DEFAULT_TYPE):
  try:
    algeria_tz = pytz.timezone("Africa/Algiers")
    now = datetime.now(algeria_tz)

    dummy_times = {
        "الفجر": "05:15",
        "الظهر": "12:48",
        "العصر": "16:18",
        "المغرب": "18:55",
        "العشاء": "20:16",
    }

    for prayer_name, time_str in dummy_times.items():
      prayer_time_obj = datetime.strptime(time_str, "%H:%M").time()
      prayer_dt = algeria_tz.localize(
          datetime.combine(now.date(), prayer_time_obj)
      )

      diff_seconds = (prayer_dt - now).total_seconds()

      if 540 <= diff_seconds <= 600:
        for chat_id, city_name in user_cities.items():
          try:
            alert_msg = (
                f"📢 **تنبيه بصلاة {prayer_name} (ولاية {city_name})**\n\n"
                f"باقي **10 دقائق** فقط على أذان صلاة {prayer_name}.\n"
                f"قم بالاستعداد والوضوء بارك الله فيك 🕌"
            )
            await context.bot.send_message(
                chat_id=chat_id, text=alert_msg, parse_mode="Markdown"
            )
          except Exception:
            pass
  except Exception as e:
    print(f"Error in scheduler: {e}")


def main():
  keep_alive()

  app_bot = Application.builder().token(BOT_TOKEN).build()

  if app_bot.job_queue:
    app_bot.job_queue.run_repeating(
        check_and_send_alerts, interval=60, first=10
    )

  app_bot.add_handler(CommandHandler("start", set_city_command))
  app_bot.add_handler(CommandHandler("setcity", set_city_command))
  app_bot.add_handler(CommandHandler("salat", salat_command))
  app_bot.add_handler(CallbackQueryHandler(city_callback_handler))

  print("Bot is working successfully...")
  app_bot.run_polling()


if __name__ == "__main__":
  main()
