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

LINK_EXPIRY = 15  # Link validity time in seconds
LOG_FILE = "unlocks.csv"
user_sessions = {}   # Stores user_id -> correct answer
active_links = {}    # Stores token -> expiry timestamp

# Ensure CSV logfile exists
if not os.path.exists(LOG_FILE):
    with open(LOG_FILE, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(["datetime", "user_id", "username", "main_link", "vouch_link"])


# Decorator to send typing action
def send_typing_action(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        await context.bot.send_chat_action(chat_id=update.effective_message.chat_id, action=ChatAction.TYPING)
        return await func(update, context, *args, **kwargs)
    return wrapper


# Generate simple math captcha
def generate_captcha():
    a, b = random.randint(3, 12), random.randint(3, 12)
    return a, b, a + b


# Create unique temporary link with expiry
def generate_temp_link(base_link):
    token = "".join(random.choices(string.ascii_letters + string.digits, k=8))
    expiry = time.time() + LINK_EXPIRY
    active_links[token] = expiry
    return f"{base_link}?token={token}"


# Check if link/token is still valid
def is_link_active(token: str) -> bool:
    if token in active_links and time.time() < active_links[token]:
        return True
    if token in active_links:
        del active_links[token]
    return False


# /start command
@send_typing_action
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    name = update.effective_user.first_name
    a, b, ans = generate_captcha()
    user_sessions[user_id] = ans

    welcome_text = (
        f"🎉 *Welcome, {name}!* \n\n"
        f"🔐 _Before unlocking the invite links, please verify you’re human._\n"
        f"🧠 Solve this simple puzzle:\n\n"
        f"*➡️ {a} + {b} = ?*\n\n"
        f"📩 _Reply with the correct answer below._\n"
        f"🔁 If needed, type /start to try again."
    )

    await update.message.reply_text(
        welcome_text, parse_mode="Markdown", disable_web_page_preview=True
    )


# Handle text/captcha answers
@send_typing_action
async def check_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_sessions:
        await update.message.reply_text("⚠️ Please start with /start first.")
        return

    text = update.message.text.strip()
    if not text.isdigit():
        await update.message.reply_text("✏️ Please reply with a *number*.", parse_mode="Markdown")
        return

    if int(text) != user_sessions[user_id]:
        keyboard = [[InlineKeyboardButton("🔁 Try Again", callback_data="/start")]]
        markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("❌ Oops! Incorrect answer.", reply_markup=markup)
        return

    # Correct answer
    main_temp = generate_temp_link(MAIN_LINK)
    vouch_temp = generate_temp_link(VOUCH_LINK)

    keyboard = [
        [InlineKeyboardButton("🥇 Join Main Channel", url=main_temp)],
        [InlineKeyboardButton("📦 Join Vouch Channel", url=vouch_temp)],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    msg_text = (
        f"✅ *Access Granted!*\n\n"
        f"⚠️ _These links expire in_ *{LINK_EXPIRY} seconds!* ⏳\n\n"
        f"📋 *Steps to follow:*\n"
        f"1️⃣ Tap both links below\n"
        f"2️⃣ Press *Join* in each channel\n"
        f"3️⃣ If links expire, type /start again\n\n"
        f"👇 *Click below to join:*"
    )

    msg = await update.message.reply_text(
        msg_text,
        parse_mode="Markdown",
        reply_markup=reply_markup,
        disable_web_page_preview=True
    )

    # Log to CSV
    with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            user_id,
            update.effective_user.username or "",
            main_temp,
            vouch_temp
        ])

    # Schedule message delete and link expiry
    asyncio.create_task(delete_after(msg, LINK_EXPIRY, context, [main_temp, vouch_temp]))
    user_sessions.pop(user_id, None)


# Delete message & invalidate links
async 
