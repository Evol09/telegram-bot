import os
import random
import string
import asyncio
import csv
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
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
user_sessions = {}  # {user_id: correct_answer}
active_links = {}   # {token: {"link": url, "expires": datetime}}

# Ensure CSV file exists
if not os.path.exists(LOG_FILE):
    with open(LOG_FILE, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(["datetime", "user_id", "username", "main_link", "vouch_link"])

# Generate math captcha
def generate_captcha():
    a, b = random.randint(3, 12), random.randint(3, 12)
    return a, b, a + b

# Create short unique token
def create_token(link):
    token = "".join(random.choices(string.ascii_letters + string.digits, k=8))
    active_links[token] = {"link": link, "expires": datetime.now() + timedelta(seconds=LINK_EXPIRY)}
    return token

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    name = update.effective_user.first_name
    a, b, ans = generate_captcha()
    user_sessions[user_id] = ans

    text = (
        f"👋 Hello {name}!\n\n"
        f"🔒 Solve this to unlock your invite links:\n"
        f"🧮 `{a} + {b} = ?`\n\n"
        f"Reply with the correct answer."
    )
    await update.message.reply_text(text, parse_mode="Markdown")

# Handle answer
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

    # Create temporary tokens
    main_token = create_token(MAIN_LINK)
    vouch_token = create_token(VOUCH_LINK)

    keyboard = [
        [InlineKeyboardButton("🥇 Join Main Channel", callback_data=f"link_{main_token}")],
        [InlineKeyboardButton("📦 Join Vouch Channel", callback_data=f"link_{vouch_token}")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    msg_text = (
        f"✅ Correct!\n\n"
        f"⏳ Links valid for *{LINK_EXPIRY} seconds only!*\n\n"
        f"⚙️ Steps:\n"
        f"1️⃣ Click all links below\n"
        f"2️⃣ Press Join in both\n"
        f"3️⃣ If you didn’t make it in time, type /start again\n\n"
        f"👇 Click below to join:"
    )

    await update.message.reply_text(msg_text, parse_mode="Markdown", reply_markup=reply_markup)

    # Log unlocks
    with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            user_id,
            update.effective_user.username or "",
            MAIN_LINK,
            VOUCH_LINK
        ])

    del user_sessions[user_id]

# Handle link button click
async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    token = query.data.replace("link_", "")
    await query.answer()  # to stop Telegram loading animation

    if token not in active_links:
        await query.message.reply_text("❌ Link expired! Please type /start again.")
        return

    data = active_links[token]
    if datetime.now() > data["expires"]:
        del active_links[token]
        await query.message.reply_text("❌ Link expired! Please type /start again.")
        return

    # Link still valid
    await query.message.reply_text(f"🔗 Here’s your link:\n{data['link']}")
    del active_links[token]

# Error handler
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    print(f"⚠️ Error: {context.error}")

# Main
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, check_answer))
    app.add_handler(CallbackQueryHandler(handle_link, pattern="^link_"))
    app.add_error_handler(error_handler)

    print(f"🚀 Invite bot running — links expire after {LINK_EXPIRY}s!")

    app.run_polling()

if __name__ == "__main__":
    main()
