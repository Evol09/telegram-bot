import os
import random
import string
import asyncio
import csv
import time
from datetime import datetime
from collections import defaultdict

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
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
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))

LINK_EXPIRY = 20  # seconds
LOG_FILE = "invite_logs.csv"
MAX_FAILED_ATTEMPTS = 3

# In-memory storage
user_sessions = {}
failed_attempts = defaultdict(int)
active_links = {}

# Create logs if missing
if not os.path.exists(LOG_FILE):
    with open(LOG_FILE, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(["datetime", "user_id", "username", "main_link", "vouch_link", "status"])


def generate_token():
    return "".join(random.choices(string.ascii_letters + string.digits, k=10))


def generate_temp_link(base_link):
    token = generate_token()
    link = f"{base_link}?token={token}"
    active_links[token] = time.time() + LINK_EXPIRY
    return link


def cleanup_tokens():
    now = time.time()
    expired = [token for token, expiry in active_links.items() if now > expiry]
    for token in expired:
        del active_links[token]


def generate_question():
    a, b = random.randint(5, 15), random.randint(5, 15)
    correct = a + b
    choices = [correct] + random.sample(range(correct - 10, correct + 10), 3)
    choices = list(set(choices))
    random.shuffle(choices)
    return {"question": (a, b, correct), "choices": choices}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_sessions[user.id] = generate_question()

    await context.bot.send_chat_action(user.id, ChatAction.TYPING)
    num1, num2, _ = user_sessions[user.id]["question"]

    buttons = [
        [
            InlineKeyboardButton(
                text=str(choice),
                callback_data=f"captcha:{choice}"
            ) for choice in user_sessions[user.id]["choices"]
        ]
    ]

    markup = InlineKeyboardMarkup(buttons)

    welcome = (
        f"👋 Hello *{user.first_name}*!\n\n"
        f"🔒 Solve this to unlock your invite links:\n"
        f"*➡️ {num1} + {num2} = ?*"
    )

    await update.message.reply_text(welcome, parse_mode="Markdown", reply_markup=markup)


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if not data.startswith("captcha:"):
        return

    answer = int(data.split(":")[1])
    correct = user_sessions.get(user_id, {}).get("question", (0, 0, -1))[2]

    if answer == correct:
        cleanup_tokens()

        main = generate_temp_link(MAIN_LINK)
        vouch = generate_temp_link(VOUCH_LINK)

        buttons = [
            [InlineKeyboardButton("✅ Join Main Channel", url=main)],
            [InlineKeyboardButton("📦 Vouch Channel", url=vouch)]
        ]
        markup = InlineKeyboardMarkup(buttons)

        response = (
            f"🎉 *You passed the check!*\n\n"
            f"⚡ These links will expire in *{LINK_EXPIRY} seconds* ⏳\n\n"
            f"👉 Make sure to join fast!"
        )

        await query.message.edit_text(response, parse_mode="Markdown", reply_markup=markup)

        log_access(user_id, query.from_user.username, main, vouch, "PASS")
        asyncio.create_task(expire_links_only([main, vouch], user_id))

        if ADMIN_ID:
            await context.bot.send_message(ADMIN_ID, f"✅ @{query.from_user.username or user_id} passed captcha.")

        user_sessions.pop(user_id, None)
        failed_attempts[user_id] = 0

    else:
        failed_attempts[user_id] += 1
        tries_left = MAX_FAILED_ATTEMPTS - failed_attempts[user_id]

        if tries_left <= 0:
            await query.message.edit_text("🚫 Too many wrong attempts. Please try again later.")
            await context.bot.send_message(user_id, "🔒 You've been blocked temporarily due to multiple wrong answers.")
            user_sessions.pop(user_id, None)
        else:
            await query.message.edit_text(f"❌ Wrong! You have {tries_left} chance(s) left. Type /start to try again.")
            user_sessions.pop(user_id, None)


def log_access(user_id, username, main_link, vouch_link, status):
    with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            user_id,
            username,
            main_link,
            vouch_link,
            status,
        ])


async def expire_links_only(links, user_id):
    await asyncio.sleep(LINK_EXPIRY)

    for link in links:
        if "?token=" in link:
            token = link.split("?token=")[-1]
            active_links.pop(token, None)

    print(f"🔒 Links for user {user_id} have expired.")


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Please use /start to begin verification.")


async def error_handler(update, context: ContextTypes.DEFAULT_TYPE):
    print("Error:", context.error)


def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    app.add_error_handler(error_handler)

    print(f"🚀 Bot is running. Invite links are valid for {LINK_EXPIRY} seconds.")
    app.run_polling()


if __name__ == "__main__":
    main()
