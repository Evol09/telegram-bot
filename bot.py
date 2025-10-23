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
user_sessions = {}  # {user_id: answer}
active_links = {}   # {token: expiry_timestamp}

# Ensure CSV file exists
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

# Validate if a temp link is still active
def is_link_active(token: str) -> bool:
    if token in active_links and time.time() < active_links[token]:
        return True
    # Clean expired tokens
    if token in active_links:
        del active_links[token]
    return False

# /sta
