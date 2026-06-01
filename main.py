import os
import re
import html
import logging
import google.generativeai as genai

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from telegram.constants import ParseMode

logging.basicConfig(level=logging.INFO)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
ADMIN_ID = os.environ.get("ADMIN_ID")
PRIVATE_CHANNEL_ID = os.environ.get("PRIVATE_CHANNEL_ID")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-3-flash-preview")

SYSTEM_PROMPT = """تو یه دستیار هوش مصنوعی فارسی‌زبان هستی برای کانال AI Academy.
همیشه به فارسی جواب بده مگه کاربر انگلیسی بنویسه.
جواب‌هات کوتاه، مفید و کاربردی باشه."""

latest_news = {"text": "هنوز خبری ثبت نشده."}

MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["🤖 چت با AI"],
        ["✍️ ساخت پرامپت"],
        ["📰 AI News"],
        ["💡 پیشنهاد موضوع"],
        ["🏠 منوی اصلی"],
    ],
    resize_keyboard=True,
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["mode"] = "chat"
    args = context.args

    if args:
        post_id = args[0]
        try:
            message_id = int(post_id.replace("post_", ""))
            await context.bot.copy_message(
                chat_id=update.effective_chat.id,
                from_chat_id=PRIVATE_CHANNEL_ID,
                message_id=message_id
            )
            return
        except Exception as e:
            logging.error(f"Post error: {e}")
            await update.message.reply_text("❌ پست پیدا نشد.")
            return

    await update.message.reply_text(
        "🎓 به AI Academy خوش اومدی\n\nیکی از گزینه‌ها رو انتخاب کن:",
        reply_markup=MAIN_KEYBOARD,
    )

async def set_news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id != str(ADMIN_ID):
        await update.message.reply_text("❌ دسترسی ندارید.")
        return
    if not context.args:
        await update.message.reply_text("❌ متن خبر رو بعد از /setnews بنویس.")
        return
    news_text = " ".join(context.args)
    latest_news["text"] = news_text
    await update.message.reply_text("✅ AI News آپدیت شد!")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text

    if user_message == "🏠 منوی اصلی":
        context.user_data["mode"] = "chat"
        await update.message.reply_text("🏠 منوی اصلی", reply_markup=MAIN_KEYBOARD)
        return

    elif user_message == "🤖 چت با AI":
        context.user_data["mode"] = "chat"
        await update.message.reply_text("🤖 سوالت رو بپرس:")
        return

    elif user_message == "✍️ ساخت پرامپت":
        context.user_data["mode"] = "prompt"
        await update.message.reply_text("✍️ موضوعی که میخوای پرامپتش رو بسازم بگو:")
        return

    elif user_message == "📰 AI News":
        await update.message.reply_text(
            f"📰 آخرین اخبار AI:\n\n{latest_news['text']}",
            parse_mode=ParseMode.HTML
        )
        return

    elif user_message == "💡 پیشنهاد موضوع":
        context.user_data["mode"] = "suggest"
        await update.message.reply_text("💡 پیشنهادت رو بنویس:")
        return

    mode = context.user_data.get("mode", "chat")

    if mode == "suggest":
        if ADMIN_ID:
            username = update.effective_user.username or "بدون_یوزرنیم"
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"💡 پیشنهاد جدید\n\n@{username}\n\n{user_message}",
            )
        await update.message.reply_text("✅ پیشنهادت ثبت شد. ممنون 🙏")
        return

    prompts = {
        "chat": f"{SYSTEM_PROMPT}\n\nسوال:\n{user_message}",
        "prompt": f"""
{SYSTEM_PROMPT}

یه پرامپت حرفه‌ای بساز برای: {user_message}

مهم: اگه پرامپت برای تصویرسازی هست، ابزارهای Nano Banana یا GPT Images رو پیشنهاد بده نه Midjourney یا Leonardo.

فرمت پاسخ:
توضیح کوتاه

PROMPT_START
Only the final prompt here in English
PROMPT_END

نکات کاربردی
"""
    }

    try:
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id,
            action="typing"
        )
        response = model.generate_content(prompts.get(mode, prompts["chat"]))
        result = response.text
        result = re.sub(r"###\s*(.*)", r"<b>\1</b>", result)
        result = re.sub(r"##\s*(.*)", r"<b>\1</b>", result)
        result = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", result)

        if mode == "prompt":
            match = re.search(r"PROMPT_START(.*?)PROMPT_END", result, re.DOTALL)
            if match:
                prompt_text = match.group(1).strip()
                normal_text = re.sub(
                    r"PROMPT_START.*?PROMPT_END", "", result, flags=re.DOTALL
                ).strip()
                final_message = (
                    normal_text
                    + "\n\n<b>📋 پرامپت نهایی:</b>\n\n"
                    + f"<pre>{html.escape(prompt_text)}</pre>"
                )
                await update.message.reply_text(
                    final_message, parse_mode=ParseMode.HTML
                )
            else:
                await update.message.reply_text(result, parse_mode=ParseMode.HTML)
        else:
            await update.message.reply_text(result, parse_mode=ParseMode.HTML)

    except Exception as e:
        logging.error(f"Gemini error: {e}")
        await update.message.reply_text("❌ مشکلی پیش اومد، دوباره امتحان کن!")

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setnews", set_news))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("✅ بات شروع به کار کرد!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
