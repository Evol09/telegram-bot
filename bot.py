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

# Ensure CSV file exists
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
        f"1️⃣ Click all links below\n"
        f"2️⃣ Press Join in both\n"
        f"3️⃣ If you didn’t make it in time, type /start again\n\n"
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
        writer.writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            user_id,
            update.effective_user.username or "",
            main_temp,
            vouch_temp
        ])

    # Start countdown updater (updates text every second)
    asyncio.create_task(update_countdown(msg, LINK_EXPIRY, context))

    # Clear user session
    del user_sessions[user_id]

# Countdown updater (edits message text live)
async def update_countdown(message, seconds, context):
    try:
        for remaining in range(seconds, 0, -1):
            await asyncio.sleep(1)
            countdown_text = (
                f"✅ Correct!\n\n"
                f"⏳ Links valid for *{remaining} seconds only!*\n\n"
                f"⚙️ Steps:\n"
                f"1️⃣ Click all links below\n"
                f"2️⃣ Press Join in both\n"
                f"3️⃣ If you didn’t make it in time, type /start again\n\n"
                f"👇 Click below to join:"
            )
            await context.bot.edit_message_text(
                chat_id=message.chat_id,
                message_id=message.message_id,
                text=countdown_text,
                parse_mode="Markdown",
                reply_markup=message.reply_markup,
                disable_web_page_preview=True
            )

        # After countdown ends, disable buttons
        expired_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔒 Main Channel Link Expired", callback_data="expired")],
            [InlineKeyboardButton("🔒 Vouch Channel Link Expired", callback_data="expired")]
        ])
        expired_text = (
            f"✅ Correct!\n\n"
            f"⏳ Links have *expired!*\n\n"
            f"⚙️ Steps:\n"
            f"1️⃣ Type /start again to get new links\n"
            f"👇 Links are no longer valid."
        )

        await context.bot.edit_message_text(
            chat_id=message.chat_id,
            message_id=message.message_id,
            text=expired_text,
            parse_mode="Markdown",
            reply_markup=expired_keyboard,
            disable_web_page_preview=True
        )

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
        app.run_polling()
    except KeyboardInterrupt:
        print("🛑 Bot stopped manually.")

if __name__ == "__main__":
    main()
