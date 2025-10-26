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

LINK_EXPIRY = 15  # seconds (reduced from 60)
LOG_FILE = "unlocks.csv"
user_sessions = {}  # {user_id: (answer, timestamp)}
user_cooldowns = {}  # {user_id: timestamp of last action}

# Ensure CSV file exists
if not os.path.exists(LOG_FILE):
    with open(LOG_FILE, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(["datetime", "user_id", "username", "main_link", "vouch_link"])

# Generate random math captcha with random operations
def generate_captcha():
    operations = ['+', '-', '*', ]
    op = random.choice(operations)
    a, b = random.randint(3, 12), random.randint(3, 12)
    if op == '/':
        a *= b  # Ensure no float answers
    result = eval(f"{a} {op} {b}")
    return a, b, op, result

# Generate temporary unique link
def generate_temp_link(base_link):
    random_str = "".join(random.choices(string.ascii_letters + string.digits, k=6))
    return f"{base_link}?token={random_str}"

# /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    name = update.effective_user.first_name

    # Check for cooldown
    if user_id in user_cooldowns and (datetime.now() - user_cooldowns[user_id]).seconds < 10:
        await update.message.reply_text("⏳ Please wait a moment before trying again.")
        return

    # Set cooldown
    user_cooldowns[user_id] = datetime.now()

    a, b, op, ans = generate_captcha()
    user_sessions[user_id] = (ans, datetime.now())

    welcome_text = (
        f"👋 Hello {name}!\n\n"
        f"🔒 Solve this to unlock your invite links:\n"
        f"🧮 `{a} {op} {b} = ?`\n\n"
        f"Reply with the correct answer.\n"
        f"🔁 Or type /start to refresh."
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

    ans, start_time = user_sessions[user_id]
    if int(text) != ans:
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

    msg = await update.message.reply_text(
        msg_text,
        parse_mode="Markdown",
        reply_markup=reply_markup,
        disable_web_page_preview=True
    )

    # Log unlock to CSV
    with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                         user_id, update.effective_user.username or "", main_temp, vouch_temp])

    # Schedule message deletion
    asyncio.create_task(delete_after(msg, LINK_EXPIRY, context))

    # Clear user session
    del user_sessions[user_id]

# Delete message after delay
async def delete_after(message, delay, context):
    try:
        await asyncio.sleep(delay)
        await context.bot.delete_message(chat_id=message.chat_id, message_id=message.message_id)
    except Exception:
        pass

# Error handler
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    print(f"⚠️ Error: {context.error}")

# Main
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, check_answer))
    app.add_error_handler(error_handler)

    print(f"🚀 Invite bot running — links expire after {LINK_EXPIRY}s!")

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(app.run_polling())
    except KeyboardInterrupt:
        print("🛑 Bot stopped manually.")
    finally:
        loop.close()

if __name__ == "__main__":
    main()

