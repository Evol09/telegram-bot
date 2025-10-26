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

LINK_EXPIRY = 15
LOG_FILE = "unlocks.csv"
user_sessions = {}
user_cooldowns = {}

if not os.path.exists(LOG_FILE):
    with open(LOG_FILE, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(["datetime", "user_id", "username", "main_link", "vouch_link"])

def generate_captcha():
    operations = ['+', '*']
    op = random.choice(operations)
    a, b = random.randint(3, 12), random.randint(3, 12)
    result = eval(f"{a} {op} {b}")
    return a, b, op, result

def generate_temp_link(base_link):
    random_str = "".join(random.choices(string.ascii_letters + string.digits, k=6))
    return f"{base_link}?token={random_str}"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    name = update.effective_user.first_name

    if user_id in user_cooldowns and (datetime.now() - user_cooldowns[user_id]).seconds < 10:
        await update.message.reply_text("⏳ Please wait a moment before trying again.")
        return

    user_coold_
