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

genai.configure(api_key=GEMINI_API_KEY)

model = genai.GenerativeModel("gemini-3-flash-preview")

SYSTEM_PROMPT = """تو یه دستیار هوش مصنوعی فارسی‌زبان هستی برای کانال AI Academy.
همیشه به فارسی جواب بده مگه کاربر انگلیسی بنویسه.
جواب‌هات کوتاه، مفید و کاربردی باشه."""

MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["🤖 چت با AI"],
        ["✍️ ساخت پرامپت"],
        ["📝 خلاصه‌سازی"],
        ["💡 پیشنهاد موضوع"],
        ["🏠 منوی اصلی"],
    ],
    resize_keyboard=True,
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    context.user_data["mode"] = "chat"

    await update.message.reply_text(
        "🎓 به AI Academy خوش اومدی\n\nیکی از گزینه‌ها رو انتخاب کن:",
        reply_markup=MAIN_KEYBOARD,
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_message = update.message.text

    if user_message == "🏠 منوی اصلی":

        context.user_data["mode"] = "chat"

        await update.message.reply_text(
            "🏠 منوی اصلی\n\nیکی از گزینه‌ها رو انتخاب کن:",
            reply_markup=MAIN_KEYBOARD,
        )
        return

    elif user_message == "🤖 چت با AI":

        context.user_data["mode"] = "chat"

        await update.message.reply_text(
            "🤖 سوالت رو بپرس:"
        )
        return

    elif user_message == "✍️ ساخت پرامپت":

        context.user_data["mode"] = "prompt"

        await update.message.reply_text(
            "✍️ موضوعی که میخوای پرامپتش رو بسازم بگو:"
        )
        return

    elif user_message == "📝 خلاصه‌سازی":

        context.user_data["mode"] = "summary"

        await update.message.reply_text(
            "📝 متنی که میخوای خلاصه بشه رو بفرست:"
        )
        return

    elif user_message == "💡 پیشنهاد موضوع":

        context.user_data["mode"] = "suggest"

        await update.message.reply_text(
            "💡 پیشنهادت رو بنویس:"
        )
        return

    mode = context.user_data.get("mode", "chat")

    if mode == "suggest":

        if ADMIN_ID:

            username = (
                update.effective_user.username
                if update.effective_user.username
                else "بدون_یوزرنیم"
            )

            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"💡 پیشنهاد جدید\n\n@{username}\n\n{user_message}",
            )

        await update.message.reply_text(
            "✅ پیشنهادت ثبت شد. ممنون 🙏"
        )
        return

    prompts = {
        "chat":
            f"{SYSTEM_PROMPT}\n\nسوال:\n{user_message}",

        "summary":
            f"{SYSTEM_PROMPT}\n\nاین متن رو خلاصه کن:\n{user_message}",

        "prompt":
            f"""
{SYSTEM_PROMPT}

یه پرامپت حرفه‌ای بساز برای:

{user_message}

فرمت پاسخ:

توضیح کوتاه

PROMPT_START
Only the final prompt here
PROMPT_END

بعدش نکات کاربردی رو بنویس.
"""
    }

    try:

        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id,
            action="typing"
        )

        response = model.generate_content(
            prompts.get(mode, prompts["chat"])
        )

        result = response.text

        result = re.sub(
            r"###\s*(.*)",
            r"<b>\1</b>",
            result
        )

        result = re.sub(
            r"##\s*(.*)",
            r"<b>\1</b>",
            result
        )

        result = re.sub(
            r"\*\*(.*?)\*\*",
            r"<b>\1</b>",
            result
        )

        if mode == "prompt":

            match = re.search(
                r"PROMPT_START(.*?)PROMPT_END",
                result,
                re.DOTALL
            )

            if match:

                prompt_text = match.group(1).strip()

                normal_text = re.sub(
                    r"PROMPT_START.*?PROMPT_END",
                    "",
                    result,
                    flags=re.DOTALL
                ).strip()

                if normal_text:

                    await update.message.reply_text(
                        normal_text,
                        parse_mode=ParseMode.HTML
                    )

                await update.message.reply_text(
                    f"<pre>{html.escape(prompt_text)}</pre>",
                    parse_mode=ParseMode.HTML
                )

            else:

                await update.message.reply_text(
                    result,
                    parse_mode=ParseMode.HTML
                )

        else:

            await update.message.reply_text(
                result,
                parse_mode=ParseMode.HTML
            )

    except Exception as e:

        logging.error(f"Gemini error: {e}")

        await update.message.reply_text(
            "❌ مشکلی پیش اومد، دوباره امتحان کن!"
        )


def main():

    app = Application.builder().token(
        TELEGRAM_TOKEN
    ).build()

    app.add_handler(
        CommandHandler("start", start)
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_message
        )
    )

    print("✅ بات شروع به کار کرد!")

    app.run_polling(
        drop_pending_updates=True
    )


if __name__ == "__main__":
    main()
