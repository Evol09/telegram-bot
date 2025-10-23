import os
import random
import string
import asyncio
import csv
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
user_sessions = {}  # {user_id: answer}

# Ensure CSV exists
if not os.path.exists(LOG_FILE):
    with open(LOG_FILE, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(["datetime", "user_id", "username", "main_link", "vouch_link"])

# Generate random math captcha
def generate_captcha():
    a, b = random.randint(3, 12), random.randint(3, 12)
    return a, b, a + b

# Generate temporary unique link
def generate_temp_link(base_link):
    random_str = "".join(random.choices(string.ascii_letters + string.digits, k=6))
    return f"{base_link}?token={random_str}"

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

# Check user answer
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
    main_temp = generate_temp_lin_
