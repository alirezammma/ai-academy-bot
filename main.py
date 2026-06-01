import os
import google.generativeai as genai
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# تنظیمات
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# راه‌اندازی Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-pro')

SYSTEM_PROMPT = """تو یه دستیار هوش مصنوعی فارسی‌زبان هستی برای کانال AI Academy.
کارات اینه:
- به سوالات درباره هوش مصنوعی جواب بدی
- پرامپت بسازی
- مطالب رو خلاصه کنی
- همیشه به فارسی جواب بدی مگه کاربر انگلیسی بنویسه
- جواب‌هات کوتاه، مفید و کاربردی باشه"""

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🤖 چت با AI", callback_data="chat")],
        [InlineKeyboardButton("✍️ ساخت پرامپت", callback_data="prompt")],
        [InlineKeyboardButton("📝 خلاصه‌سازی", callback_data="summary")],
        [InlineKeyboardButton("💡 پیشنهاد موضوع", callback_data="suggest")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "سلام! به AI Academy خوش اومدی 🎓\n\nچیکار میتونم برات انجام بدم؟",
        reply_markup=reply_markup
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "chat":
        context.user_data["mode"] = "chat"
        await query.edit_message_text("🤖 حالت چت فعاله! هر سوالی داری بپرس:")
    
    elif query.data == "prompt":
        context.user_data["mode"] = "prompt"
        await query.edit_message_text("✍️ موضوع یا تصویری که میخوای پرامپتش رو بسازم بگو:")
    
    elif query.data == "summary":
        context.user_data["mode"] = "summary"
        await query.edit_message_text("📝 متن یا لینکی که میخوای خلاصه بشه رو بفرست:")
    
    elif query.data == "suggest":
        context.user_data["mode"] = "suggest"
        await query.edit_message_text("💡 پیشنهادت رو بنویس، مستقیم برای ادمین ارسال میشه:")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    mode = context.user_data.get("mode", "chat")
    
    # پیشنهاد کاربر
    if mode == "suggest":
        admin_id = os.environ.get("ADMIN_ID")
        if admin_id:
            await context.bot.send_message(
                chat_id=admin_id,
                text=f"💡 پیشنهاد جدید از @{update.message.from_user.username}:\n\n{user_message}"
            )
        await update.message.reply_text("✅ پیشنهادت ثبت شد! ممنون که کمک میکنی بهتر بشیم 🙏")
        return
    
    # ساخت پرامپت مناسب
    if mode == "prompt":
        full_prompt = f"{SYSTEM_PROMPT}\n\nکاربر میخواد پرامپت بسازی برای: {user_message}\nیه پرامپت حرفه‌ای و کاربردی بساز"
    elif mode == "summary":
        full_prompt = f"{SYSTEM_PROMPT}\n\nاین متن رو خلاصه کن:\n{user_message}"
    else:
        full_prompt = f"{SYSTEM_PROMPT}\n\nسوال کاربر: {user_message}"
    
    # نشون دادن حالت تایپ
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    
    try:
        response = model.generate_content(full_prompt)
        await update.message.reply_text(response.text)
    except Exception as e:
        await update.message.reply_text("❌ مشکلی پیش اومد، دوباره امتحان کن!")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎓 AI Academy Bot\n\n"
        "دستورات:\n"
        "/start - منوی اصلی\n"
        "/help - راهنما\n\n"
        "قابلیت‌ها:\n"
        "🤖 چت با هوش مصنوعی\n"
        "✍️ ساخت پرامپت حرفه‌ای\n"
        "📝 خلاصه‌سازی متن\n"
        "💡 ارسال پیشنهاد به ادمین"
    )

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("✅ بات شروع به کار کرد!")
    app.run_polling()

if __name__ == "__main__":
    main()
