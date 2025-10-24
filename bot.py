import os
import random
import string
import asyncio
import csv
import time
from datetime import datetime
from functools import wraps

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from telegram.constants import ChatAction
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
MAIN_LINK = os.getenv("MAIN_LINK")
VOUCH_LINK = os.getenv("VOUCH_LINK")

LINK_EXPIRY = 15  # seconds
LOG_FILE = "unlocks.csv"
user_sessions = {}
active_links = {}

# Create CSV file if not exists
if not os.path.exists(LOG_FILE):
    with open(LOG_FILE, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(["datetime", "user_id", "username", "main_link", "vouch_link"])


# Typing indicator decorator
def send_typing_action(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        await context.bot.send_chat_action(chat_id=update.effective_message.chat_id, action=ChatAction.TYPING)
        return await func(update, context, *args, **kwargs)
    return wrapper


# Create a captcha
def generate_captcha():
    a, b = random.randint(3, 12), random.randint(3, 12)
    return a, b, a + b


# Generate a time-limited unique link
def generate_temp_link(base_link):
    token = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
    expiry = time.time() + LINK_EXPIRY
    active_links[token] = expiry
    return f"{base_link}?token={token}"


# Clean expired links
def is_link_active(token: str) -> bool:
    if token in active_links and time.time() < active_links[token]:
        return True
    if token in active_links:
        del active_links[token]
    return False


@send_typing_action
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    name = update.effective_user.first_name
    a, b, ans = generate_captcha()
    user_sessions[user_id] = ans

    text = (
        f"🎉 *Welcome, {name}!* \n\n"
        f"🔒 Solve to get invites Links:_\n\n"
        f"*➡️ {a} + {b} = ?*\n\n"
        f"📩 _Send your answer below._\n"
        f"🔁 Or type /start to refresh."
    )

    await update.message.reply_text(
        text, parse_mode="Markdown", disable_web_page_preview=True
    )


@send_typing_action
async def check_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id not in user_sessions:
        await update.message.reply_text("⚠️ Please type /start first.")
        return

    answer = update.message.text.strip()
    if not answer.isdigit():
        await update.message.reply_text("✏️ Reply with a *number* only.", parse_mode="Markdown")
        return

    if int(answer) != user_sessions[user_id]:
        keyboard = [[InlineKeyboardButton("🔁 Try Again", callback_data="/start")]]
        await update.message.reply_text("❌ Wrong answer!", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # Success
    main_link = generate_temp_link(MAIN_LINK)
    vouch_link = generate_temp_link(VOUCH_LINK)

    msg_text = (
        f"✅ *Success!*\n\n"
        f"🔗 _Links are active for_ *{LINK_EXPIRY} seconds* ⏳\n\n"
        f"📌 Steps:\n"
        f"1️⃣ Tap both links\n"
        f"2️⃣ Press *Join* in each\n"
        f"3️⃣ Didn't make it? Type /start again\n\n"
        f"👇 Click to join:"
    )

    buttons = [
        [InlineKeyboardButton("🥇 Join Main Channel", url=main_link)],
        [InlineKeyboardButton("📦 Join Vouch Channel", url=vouch_link)]
    ]

    reply_markup = InlineKeyboardMarkup(buttons)

    msg = await update.message.reply_text(
        text=msg_text,
        parse_mode="Markdown",
        reply_markup=reply_markup,
        disable_web_page_preview=True
    )

    # Log it
    with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            user_id,
            update.effective_user.username or "",
            main_link,
            vouch_link
        ])

    asyncio.create_task(delete_after(msg, context, [main_link, vouch_link]))
    del user_sessions[user_id]


async def delete_after(msg, context, links):
    await asyncio.sleep(LINK_EXPIRY)
    try:
        await context.bot.delete_message(chat_id=msg.chat.id, message_id=msg.message_id)
    except Exception:
        pass

    # Clean the tokens
    for link in links:
        if "?token=" in link:
            token = link.split("?token=")[-1]
            active_links.pop(token, None)


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "/start":
        await start(update, context)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    print(f"⚠️ Error: {context.error}")


# Start the bot
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, check_answer))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_error_handler(error_handler)

    print(f"🚀 Bot is live. Temporary links expire in {LINK_EXPIRY}s!")

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(app.run_polling())
    except KeyboardInterrupt:
        print("🛑 Bot stopped.")
    finally:
        loop.close()


if __name__ == "__main__":
    main()

