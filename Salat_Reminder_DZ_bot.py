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
# 1. خادم Flask للحفاظ على استمرار تشغيل البوت على Render
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
# 2. إعدادات البوت والبيانات
# ---------------------------------------------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN")

# قاعدة بيانات مصغرة لحفظ ولاية كل مستخدم
user_cities = {}


# دالة حساب الوقت المتبقي بتوقيت الجزائر (UTC+1)
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

  # في حال انتهت صلوات اليوم، تكون الصلاة القادمة فجر الغد
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


# دالة بناء شاشة جدول المواقيت بتنسيق محاذى ونظيف بدون صندوق رمادي
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
# 3. الأوامر والمعالجات التفاعلية
# ---------------------------------------------------------


async def salat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
  chat_id = update.effective_chat.id
  city = user_cities.get(chat_id, "الشلف")

  dummy_times = {
      "Fajr": "05:15",
      "Sunrise": "06:41",
      "Dhuhr": "12:48",
      "Asr": "16:18",
      "Maghrib": "18:55",
      "Isha": "20:16",
  }

  text = build_prayer_dashboard(city, dummy_times)
  keyboard = [[InlineKeyboardButton("تحديث الوقت 🔄", callback_data="refresh_time")]]
  reply_markup = InlineKeyboardMarkup(keyboard)

  await update.message.reply_text(
      text=text, reply_markup=reply_markup, parse_mode="Markdown"
  )


# دالة التنبيه المسبق (5 دقائق قبل الصلاة)
async def send_pre_prayer_alert(
    context: ContextTypes.DEFAULT_TYPE, chat_id: int, prayer_name: str
):
  keyboard = [[
      InlineKeyboardButton(
          "نعم سأستعد للصلاة 🕌",
          callback_data=f"prepare_salat_{prayer_name}",
      )
  ]]
  reply_markup = InlineKeyboardMarkup(keyboard)

  message_text = (
      f"📢 **تنبيه:** اقترب موعد صلاة **{prayer_name}**!\n"
      f"باقي 5 دقائق على الأذان. قم بالاستعداد للصلاة."
  )

  await context.bot.send_message(
      chat_id=chat_id,
      text=message_text,
      reply_markup=reply_markup,
      parse_mode="Markdown",
  )


# معالج الأزرار التفاعلية
async def button_callback_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
  query = update.callback_query
  chat_id = update.effective_chat.id

  # 1. زر "نعم سأستعد للصلاة 🕌"
  if query.data.startswith("prepare_salat_"):
    await query.answer("تم تسجيل استجابتك! تقبل الله.")
    prayer_name = query.data.split("_")[-1]
    await query.edit_message_text(
        text=f"🤲 **تقبل الله صلاتكم وطاعاتكم!**\nدعواتك معنا في صلاة {prayer_name}.",
        parse_mode="Markdown",
    )

  # 2. زر "تحديث الوقت 🔄"
  elif query.data == "refresh_time":
    city = user_cities.get(chat_id, "الشلف")

    dummy_times = {
        "Fajr": "05:15",
        "Sunrise": "06:41",
        "Dhuhr": "12:48",
        "Asr": "16:18",
        "Maghrib": "18:55",
        "Isha": "20:16",
    }

    updated_text = build_prayer_dashboard(city, dummy_times)
    keyboard = [
        [InlineKeyboardButton("تحديث الوقت 🔄", callback_data="refresh_time")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
      await query.edit_message_text(
          text=updated_text, reply_markup=reply_markup, parse_mode="Markdown"
      )
      await query.answer("تم تحديث الوقت بنجاح 🔄")
    except Exception as e:
      if "Message is not modified" in str(e):
        await query.answer("الوقت محدّث بالفعل ⏱️")
      else:
        await query.answer("حدث خطأ أثناء التحديث.")


# ---------------------------------------------------------
# 4. تشغيل البوت
# ---------------------------------------------------------
def main():
  keep_alive()

  app_bot = Application.builder().token(BOT_TOKEN).build()

  app_bot.add_handler(CommandHandler("salat", salat_command))
  app_bot.add_handler(CallbackQueryHandler(button_callback_handler))

  print("Bot is working successfully...")
  app_bot.run_polling()


if __name__ == "__main__":
  main()
