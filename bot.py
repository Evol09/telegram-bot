import os
import random
import string
import asyncio
import csv
import time
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
MAIN_LINK = os.getenv("MAIN_LINK")
VOUCH_LINK = os.getenv("VOUCH_LINK")

LINK_EXPIRY = 15  # seconds
LOG_FILE = "unlocks.csv"
user_sessions = {}   # {user_id: answer}
active_links = {}    # {token: expiry_timestamp}

# Ensure CSV exists
if not os.path.exists(LOG_FILE):
    with open(LOG_FILE, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(["datetime", "user_id", "username", "main_link", "vouch_link"])

# Generate random math captcha
def generate_captcha():
    a, b = random.randint(3, 12), random.randint(3, 12)
    return a, b, a + b

# Generate temporary unique link with expiry
def generate_temp_link(base_link):
    token = "".join(random.choices(string.ascii_letters + string.digits, k=8))
    expiry = time.time() + LINK_EXPIRY
    active_links[token] = expiry
    return f"{base_link}?token={token}"

# Check if link is still active
def is_link_active(token: str) -> bool:
    if token in active_links and time.time() < active_links[token]:
        return True
    if token in active_links:
        del active_links[token]
    return False

# /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    name = update.effective_user.first_name
    a, b, ans = generate_captcha()
    user_sessions[user_id] = ans

    welcome_text = (
        f"👋 Hello {name}!\n\n"
        f"🔒 Solve this to unlock your invite links:\n"
        f"🧮 `{a} + {b} = ?`\n\n"
        f"Reply with the correct answer."
    )

    await update.message.reply_text(
        welcome_text, parse_mode="Markdown", disable_web_page_preview=True
    )

# Check answer
async def check_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_sessions:
        await update.message.reply_text("⚠️ Please start with /start first.")
        return

    text = update.message.text.strip()
    if not text.isdigit():
        await update.message.reply_text("✏️ Please reply with a number.")
        return

    if int(text) != user_sessions[user_id]:
        await update.message.reply_text("❌ Incorrect answer. Try again!")
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
        f"✅ Correct!\n\n"
        f"⏳ Links valid for *{LINK_EXPIRY} seconds only!*\n\n"
        f"⚙️ Steps:\n"
        f"1️⃣ Click *all links* below\n"
        f"2️⃣ Press *Join* in both\n"
        f"3️⃣ If you didn’t make it in time, type */start* again\n\n"
        f"👇 Click below to join:"
    )

    await update.message.reply_text(
        msg_text,
        parse_mode="Markdown",
        rep
