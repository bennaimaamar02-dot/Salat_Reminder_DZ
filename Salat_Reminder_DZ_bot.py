import datetime
import logging
import requests
from telegram import KeyboardButton, ReplyKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# إعداد التسجيل لتتبع الأخطاء
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

TOKEN = os.environ.get("BOT_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    button = KeyboardButton("📍 مشاركة موقعي الحالي", request_location=True)
    reply_markup = ReplyKeyboardMarkup([[button]], resize_keyboard=True)
    await update.message.reply_text(
        "أهلاً بك في بوت مواقيت الصلاة! 🕌\n\nاضغط على الزر أدناه لمشاركة موقعك الجغرافي ليتم ضبط مواقيت الصلاة بدقة.",
        reply_markup=reply_markup
    )

async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    location = update.message.location
    if not location:
        return

    lat = location.latitude
    lon = location.longitude

    # استعلام API مواقيت الصلاة
    url = f"http://api.aladhan.com/v1/timings?latitude={lat}&longitude={lon}&method=3"
    
    try:
        response = requests.get(url).json()
        timings = response['data']['timings']
        
        msg = (
            f"🕌 **مواقيت الصلاة لموقعك اليوم:**\n\n"
            f"🔹 **الفجر:** {timings['Fajr']}\n"
            f"🔹 **الشروق:** {timings['Sunrise']}\n"
            f"🔹 **الظهر:** {timings['Dhuhr']}\n"
            f"🔹 **العصر:** {timings['Asr']}\n"
            f"🔹 **المغرب:** {timings['Maghrib']}\n"
            f"🔹 **العشاء:** {timings['Isha']}\n\n"
            f"تقبل الله طاعتكم! 🤲"
        )
        await update.message.reply_text(msg, parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text("حدث خطأ أثناء جلب مواقيت الصلاة، يرجى المحاولة لاحقاً.")

def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    # استقبال أي نوع من أنواع رسائل الموقع (سواء ثابت أو حي)
    app.add_handler(MessageHandler(filters.LOCATION, handle_location))

    print("البوت يعمل بنجاح الآن...")
    app.run_polling()

if __name__ == "__main__":
    main()
