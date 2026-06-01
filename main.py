import os
import logging
import google.generativeai as genai
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

logging.basicConfig(level=logging.INFO)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
ADMIN_ID = os.environ.get("ADMIN_ID")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-3-flash-preview')

SYSTEM_PROMPT = """تو یه دستیار هوش مصنوعی فارسی‌زبان هستی برای کانال AI Academy.
همیشه به فارسی جواب بده مگه کاربر انگلیسی بنویسه.
جواب‌هات کوتاه، مفید و کاربردی باشه."""

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🤖 چت با AI", callback_data="chat")],
        [InlineKeyboardButton("✍️ ساخت پرامپت", callback_data="prompt")],
        [InlineKeyboardButton("📝 خلاصه‌سازی", callback_data="summary")],
        [InlineKeyboardButton("💡 پیشنهاد موضوع", callback_data="suggest")],
    ]
    await update.message.reply_text(
        "سلام! به AI Academy خوش اومدی 🎓\n\nچیکار میتونم برات انجام بدم؟",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["mode"] = query.data
    messages = {
        "chat": "🤖 حالت چت فعاله! هر سوالی داری بپرس:",
        "prompt": "✍️ موضوعی که میخوای پرامپتش رو بسازم بگو:",
        "summary": "📝 متنی که میخوای خلاصه بشه رو بفرست:",
        "suggest": "💡 پیشنهادت رو بنویس:"
    }
    await query.edit_message_text(messages.get(query.data, "بفرما:"))

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    mode = context.user_data.get("mode", "chat")

    if mode == "suggest":
        if ADMIN_ID:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"💡 پیشنهاد از @{update.message.from_user.username}:\n\n{user_message}"
            )
        await update.message.reply_text("✅ پیشنهادت ثبت شد! ممنون 🙏")
        return

    prompts = {
        "prompt": f"{SYSTEM_PROMPT}\n\nیه پرامپت حرفه‌ای بساز برای: {user_message}",
        "summary": f"{SYSTEM_PROMPT}\n\nاین متن رو خلاصه کن:\n{user_message}",
        "chat": f"{SYSTEM_PROMPT}\n\nسوال: {user_message}"
    }

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    try:
        response = model.generate_content(prompts.get(mode, prompts["chat"]))
        await update.message.reply_text(response.text)
    except Exception as e:
        logging.error(f"Gemini error: {e}")
        await update.message.reply_text("❌ مشکلی پیش اومد، دوباره امتحان کن!")

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("✅ بات شروع به کار کرد!")
    app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
