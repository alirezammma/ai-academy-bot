import os
import re
import html
import json
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

NEWS_FILE = "news.json"
POSTS_FILE = "posts.json"

def load_json(filename):
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_json(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

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
        posts = load_json(POSTS_FILE)
        if post_id in posts:
            post = posts[post_id]
            caption = post.get("caption", "")
            photo = post.get("photo", None)
            if photo:
                await update.message.reply_photo(photo=photo, caption=caption)
            else:
                await update.message.reply_text(caption)
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
    data = load_json(NEWS_FILE)
    data["latest"] = news_text
    save_json(NEWS_FILE, data)
    await update.message.reply_text("✅ AI News آپدیت شد!")

async def set_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id != str(ADMIN_ID):
        await update.message.reply_text("❌ دسترسی ندارید.")
        return
    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "❌ فرمت درست:\n/setpost post1 متن پرامپت و توضیحات\n\nبرای پست با عکس، عکس رو با کپشن بفرست."
        )
        return
    post_id = context.args[0]
    caption = " ".join(context.args[1:])
    posts = load_json(POSTS_FILE)
    posts[post_id] = {"caption": caption, "photo": None}
    save_json(POSTS_FILE, posts)
    await update.message.reply_text(f"✅ پست {post_id} ذخیره شد!\n\nلینک:\nt.me/{context.bot.username}?start={post_id}")

async def set_post_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id != str(ADMIN_ID):
        return
    if not update.message.caption or not update.message.caption.startswith("/setpost"):
        return
    parts = update.message.caption.split(" ", 2)
    if len(parts) < 3:
        await update.message.reply_text("❌ فرمت: /setpost post1 متن توضیحات")
        return
    post_id = parts[1]
    caption = parts[2]
    photo_id = update.message.photo[-1].file_id
    posts = load_json(POSTS_FILE)
    posts[post_id] = {"caption": caption, "photo": photo_id}
    save_json(POSTS_FILE, posts)
    await update.message.reply_text(
        f"✅ پست {post_id} با عکس ذخیره شد!\n\nلینک:\nt.me/{context.bot.username}?start={post_id}"
    )

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
        data = load_json(NEWS_FILE)
        news = data.get("latest", "هنوز خبری ثبت نشده.")
        await update.message.reply_text(f"📰 آخرین اخبار AI:\n\n{news}")
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
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        response = model.generate_content(prompts.get(mode, prompts["chat"]))
        result = response.text
        result = re.sub(r"###\s*(.*)", r"<b>\1</b>", result)
        result = re.sub(r"##\s*(.*)", r"<b>\1</b>", result)
        result = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", result)

        if mode == "prompt":
            match = re.search(r"PROMPT_START(.*?)PROMPT_END", result, re.DOTALL)
            if match:
                prompt_text = match.group(1).strip()
                normal_text = re.sub(r"PROMPT_START.*?PROMPT_END", "", result, flags=re.DOTALL).strip()
                final_message = normal_text + "\n\n<b>📋 پرامپت نهایی:</b>\n\n" + f"<pre>{html.escape(prompt_text)}</pre>"
                await update.message.reply_text(final_message, parse_mode=ParseMode.HTML)
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
    app.add_handler(CommandHandler("setpost", set_post))
    app.add_handler(MessageHandler(filters.PHOTO & filters.Caption(r"^/setpost"), set_post_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("✅ بات شروع به کار کرد!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
