import logging
from typing import Dict
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters
)

from algorithm.place_finder import PlaceFinder
from config.config import BOT_TOKEN, DB_CONFIG

# Логирование в файл
logging.basicConfig(
    filename="logs/bot.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

# Инициализация алгоритма
finder = PlaceFinder(DB_CONFIG)

# Состояния
SELECT_TYPE, GET_LOCATION = range(2)

# Типы мест
place_types = {
    "☕ Кафе": "cafe",
    "🏥 Аптека": "pharmacy",
}

user_choice: Dict[int, str] = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    buttons = [[KeyboardButton(text=t)] for t in place_types]
    markup = ReplyKeyboardMarkup(buttons, resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text("Что ищем?", reply_markup=markup)
    return SELECT_TYPE

async def select_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text not in place_types:
        await update.message.reply_text("Пожалуйста, выберите из предложенного списка.")
        return SELECT_TYPE
    user_choice[update.effective_user.id] = place_types[text]
    loc_btn = KeyboardButton("📍 Отправить геопозицию", request_location=True)
    markup = ReplyKeyboardMarkup([[loc_btn]], resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text("Отправьте свою геопозицию.", reply_markup=markup)
    return GET_LOCATION

async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_choice:
        await update.message.reply_text("Сначала выберите тип бизнеса: /start")
        return ConversationHandler.END

    place_type = user_choice[user_id]
    loc = update.message.location
    try:
        result = finder.find_optimal_location((loc.latitude, loc.longitude), place_type)
        if not result:
            await update.message.reply_text("Не удалось найти подходящую точку 😔")
        else:
            label, lat, lon, (ulat, ulon) = result
            gmap_link = f"https://www.google.com/maps?q={lat},{lon}"
            await update.message.reply_text(
                f"📍 *{label}*\n"
                f"🌐 [Открыть в Google Maps]({gmap_link})",
                parse_mode="Markdown"
            )
    except Exception as e:
        logger.error(f"Ошибка при поиске: {e}")
        await update.message.reply_text("Произошла ошибка. Попробуйте позже.")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Операция отменена.")
    return ConversationHandler.END

if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            SELECT_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_type)],
            GET_LOCATION: [MessageHandler(filters.LOCATION, handle_location)]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    app.add_handler(conv)
    logger.info("🚀 Bot started and running...")
    app.run_polling()