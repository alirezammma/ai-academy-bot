import os
import re
import html
import logging
import google.generativeai as genai
from datetime import date
from pymongo import MongoClient

from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)
from telegram.constants import ParseMode

logging.basicConfig(level=logging.INFO)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
ADMIN_ID = os.environ.get("ADMIN_ID")
PRIVATE_CHANNEL_ID = os.environ.get("PRIVATE_CHANNEL_ID")
MONGODB_URI = os.environ.get("MONGODB_URI")
CHANNEL_USERNAME = "@AiAcademyLearning"

client = MongoClient(MONGODB_URI)
db = client["ai_academy"]
users_col = db["users"]
news_col = db["news"]

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-3.1-flash-lite")

SYSTEM_PROMPT = """تو یه دستیار هوش مصنوعی فارسی‌زبان هستی برای بات AI Academy.
همیشه به فارسی جواب بده مگه کاربر انگلیسی بنویسه.
جواب‌هات کوتاه، مفید و کاربردی باشه."""

CHAT_LIMIT = 10
PROMPT_LIMIT = 3

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

def get_join_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 عضویت در کانال", url="https://t.me/AiAcademyLearning")],
        [InlineKeyboardButton("✅ عضو شدم", callback_data="check_join")]
    ])

def get_user(user_id):
    user = users_col.find_one({"user_id": user_id})
    if not user:
        user = {
            "user_id": user_id,
            "chat_count": 0,
            "prompt_count": 0,
            "usage_date": str(date.today()),
            "chat_history": [],
            "prompt_history": [],
            "mode": None
        }
        users_col.insert_one(user)
    return user

def reset_if_new_day(user):
    today = str(date.today())
    if user.get("usage_date") != today:
        users_col.update_one(
            {"user_id": user["user_id"]},
            {"$set": {"chat_count": 0, "prompt_count": 0, "usage_date": today}}
        )
        user["chat_count"] = 0
        user["prompt_count"] = 0
        user["usage_date"] = today
    return user

def check_limit(user, mode):
    if mode == "chat":
        return user["chat_count"] < CHAT_LIMIT
    return user["prompt_count"] < PROMPT_LIMIT

def get_remaining(user, mode):
    if mode == "chat":
        return max(0, CHAT_LIMIT - user["chat_count"])
    return max(0, PROMPT_LIMIT - user["prompt_count"])

def add_usage(user_id, mode):
    field = "chat_count" if mode == "chat" else "prompt_count"
    users_col.update_one({"user_id": user_id}, {"$inc": {field: 1}})

def get_history(user, mode):
    return user.get(f"{mode}_history", [])[-10:]

def add_to_history(user_id, mode, role, text):
    field = f"{mode}_history"
    users_col.update_one(
        {"user_id": user_id},
        {"$push": {field: {"$each": [{"role": role, "text": text}], "$slice": -20}}}
    )

def get_news_id():
    doc = news_col.find_one({"key": "latest"})
    return doc["message_id"] if doc else None

def set_news_id_db(message_id):
    news_col.update_one(
        {"key": "latest"},
        {"$set": {"message_id": message_id}},
        upsert=True
    )

async def is_member(bot, user_id):
    try:
        member = await bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return member.status in ["member", "administrator", "creator"]
    except:
        return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    args = context.args

    if not await is_member(context.bot, user_id):
        if args:
            context.user_data["pending_post"] = args[0]
        await update.message.reply_text(
            "👋 سلام!\n\nبرای استفاده از بات باید عضو کانال AI Academy بشی 👇",
            reply_markup=get_join_keyboard()
        )
        return

    get_user(user_id)
    users_col.update_one({"user_id": user_id}, {"$set": {"mode": None}})

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

async def check_join_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    if await is_member(context.bot, user_id):
        await query.edit_message_text("✅ عضویت تأیید شد!\n\n🎓 به AI Academy خوش آمدید")
        get_user(user_id)

        pending = context.user_data.get("pending_post")
        if pending:
            try:
                message_id = int(pending.replace("post_", ""))
                await context.bot.copy_message(
                    chat_id=query.message.chat_id,
                    from_chat_id=PRIVATE_CHANNEL_ID,
                    message_id=message_id
                )
                context.user_data["pending_post"] = None
                return
            except:
                pass

        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="یکی از گزینه‌ها رو انتخاب کن:",
            reply_markup=MAIN_KEYBOARD
        )
    else:
        await query.answer("❌ هنوز عضو نشدی! اول عضو کانال بشو.", show_alert=True)

async def set_news_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id != str(ADMIN_ID):
        return
    if not context.args:
        await update.message.reply_text("❌ مثال: /setnewsid 6")
        return
    msg_id = int(context.args[0])
    set_news_id_db(msg_id)
    await update.message.reply_text(f"✅ AI News آپدیت شد! ID: {msg_id}")

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id != str(ADMIN_ID):
        return
    if not context.args:
        await update.message.reply_text("❌ مثال:\n/broadcast ربات آپدیت شد!")
        return

    text = " ".join(context.args)
    all_users = users_col.find({}, {"user_id": 1})
    success = 0
    fail = 0

    await update.message.reply_text("⏳ در حال ارسال...")

    for u in all_users:
        try:
            await context.bot.send_message(
                chat_id=u["user_id"],
                text=text,
                reply_markup=MAIN_KEYBOARD
            )
            success += 1
        except:
            fail += 1

    await update.message.reply_text(
        f"✅ ارسال تموم شد!\n\nموفق: {success}\nناموفق: {fail}"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_message = update.message.text

    if not await is_member(context.bot, user_id):
        await update.message.reply_text(
            "برای استفاده از بات باید عضو کانال بشی 👇",
            reply_markup=get_join_keyboard()
        )
        return

    user = get_user(user_id)
    user = reset_if_new_day(user)

    if user_message == "🏠 منوی اصلی":
        users_col.update_one({"user_id": user_id}, {"$set": {"mode": None}})
        await update.message.reply_text("🏠 منوی اصلی", reply_markup=MAIN_KEYBOARD)
        return

    elif user_message == "🤖 چت با AI":
        users_col.update_one({"user_id": user_id}, {"$set": {"mode": "chat"}})
        await update.message.reply_text("🤖 بفرمایید، هر سوالی داری در خدمتم:")
        return

    elif user_message == "✍️ ساخت پرامپت":
        users_col.update_one({"user_id": user_id}, {"$set": {"mode": "prompt"}})
        await update.message.reply_text("✍️ موضوعی که میخوای پرامپتش رو بسازم بگو:")
        return

    elif user_message == "📰 AI News":
        news_id = get_news_id()
        if news_id:
            try:
                await context.bot.copy_message(
                    chat_id=update.effective_chat.id,
                    from_chat_id=PRIVATE_CHANNEL_ID,
                    message_id=news_id
                )
            except Exception as e:
                logging.error(f"News error: {e}")
                await update.message.reply_text("❌ خبری پیدا نشد.")
        else:
            await update.message.reply_text("📰 هنوز خبری ثبت نشده.")
        return

    elif user_message == "💡 پیشنهاد موضوع":
        users_col.update_one({"user_id": user_id}, {"$set": {"mode": "suggest"}})
        await update.message.reply_text("💡 پیشنهادت رو بنویس:")
        return

    mode = user.get("mode")

    if not mode:
        await update.message.reply_text(
            "برای استفاده از بات لطفاً یکی از گزینه‌های منو رو انتخاب کن 👇",
            reply_markup=MAIN_KEYBOARD
        )
        return

    if mode == "suggest":
        if ADMIN_ID:
            username = update.effective_user.username or "بدون_یوزرنیم"
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"💡 پیشنهاد جدید\n\n@{username}\n\n{user_message}",
            )
        await update.message.reply_text("✅ پیشنهادت ثبت شد. ممنون 🙏")
        return

    if not check_limit(user, mode):
        limit = CHAT_LIMIT if mode == "chat" else PROMPT_LIMIT
        await update.message.reply_text(
            f"⚠️ به سقف روزانه رسیدی!\n\n"
            f"{'🤖 چت با AI' if mode == 'chat' else '✍️ ساخت پرامپت'}: {limit} بار در روز\n\n"
            f"فردا دوباره میتونی استفاده کنی 🕐"
        )
        return

    history = get_history(user, mode)

    if mode == "chat":
        full_prompt = SYSTEM_PROMPT + "\n\n"
        for msg in history:
            role = "کاربر" if msg["role"] == "user" else "دستیار"
            full_prompt += f"{role}: {msg['text']}\n"
        full_prompt += f"کاربر: {user_message}\nدستیار:"
    else:
        full_prompt = f"""
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

    try:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        response = model.generate_content(full_prompt)
        result = response.text
        result = re.sub(r"###\s*(.*)", r"<b>\1</b>", result)
        result = re.sub(r"##\s*(.*)", r"<b>\1</b>", result)
        result = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", result)

        add_usage(user_id, mode)
        user = get_user(user_id)
        remaining = get_remaining(user, mode)

        if mode == "prompt":
            match = re.search(r"PROMPT_START(.*?)PROMPT_END", result, re.DOTALL)
            if match:
                prompt_text = match.group(1).strip()
                normal_text = re.sub(r"PROMPT_START.*?PROMPT_END", "", result, flags=re.DOTALL).strip()
                normal_text += f"\n\n🎯 پرامپت‌های باقی‌مانده: {remaining}"
                final_message = (
                    normal_text
                    + "\n\n<b>📋 پرامپت نهایی:</b>\n\n"
                    + f"<pre>{html.escape(prompt_text)}</pre>"
                )
                await update.message.reply_text(final_message, parse_mode=ParseMode.HTML)
            else:
                result += f"\n\n🎯 پرامپت‌های باقی‌مانده: {remaining}"
                await update.message.reply_text(result, parse_mode=ParseMode.HTML)

            add_to_history(user_id, "prompt", "user", user_message)
            add_to_history(user_id, "prompt", "model", result)

        else:
            result += f"\n\n💬 پیام‌های باقی‌مانده: {remaining}"
            await update.message.reply_text(result, parse_mode=ParseMode.HTML)
            add_to_history(user_id, "chat", "user", user_message)
            add_to_history(user_id, "chat", "model", result)

    except Exception as e:
        logging.error(f"Gemini error: {e}")
        await update.message.reply_text("❌ مشکلی پیش اومد، دوباره امتحان کن!")

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setnewsid", set_news_id))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CallbackQueryHandler(check_join_callback, pattern="check_join"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("✅ بات شروع به کار کرد!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
