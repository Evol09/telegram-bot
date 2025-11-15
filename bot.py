import os
import random
import string
import asyncio
import csv
from dataclasses import dataclass
from datetime import datetime, timedelta

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
    CallbackQueryHandler,
)
from dotenv import load_dotenv

# ================== CONFIG & ENV ==================

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
MAIN_LINK = os.getenv("MAIN_LINK")      # VIP / main sales channel
VOUCH_LINK = os.getenv("VOUCH_LINK")    # proof / vouch / feedback channel
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))  # optional: for /stats

if not BOT_TOKEN or not MAIN_LINK or not VOUCH_LINK:
    raise RuntimeError("BOT_TOKEN, MAIN_LINK, and VOUCH_LINK must be set in .env")

LINK_EXPIRY = 15            # seconds for temporary links
COOLDOWN_SECONDS = 10       # seconds between /start
MAX_ATTEMPTS_PER_CAPTCHA = 3
LOG_FILE = "unlocks.csv"

# ================== DATA STRUCTURES ==================

@dataclass
class UserSession:
    answer: int
    created_at: datetime
    attempts: int = 0

user_sessions: dict[int, UserSession] = {}
user_cooldowns: dict[int, datetime] = {}
total_unlocks: int = 0

# Ensure CSV exists
if not os.path.exists(LOG_FILE):
    with open(LOG_FILE, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(
            ["datetime", "user_id", "username", "main_link", "vouch_link"]
        )

# ================== HELPERS ==================

def generate_captcha() -> tuple[int, int, str, int]:
    """Generate a simple + / - captcha without using eval."""
    operations = ["+", "-"]
    op = random.choice(operations)
    a = random.randint(3, 12)
    b = random.randint(3, 12)

    if op == "+":
        result = a + b
    else:  # "-"
        result = a - b

    return a, b, op, result


def generate_temp_link(base_link: str) -> str:
    random_str = "".join(random.choices(string.ascii_letters + string.digits, k=6))
    return f"{base_link}?token={random_str}"

def is_on_cooldown(user_id: int) -> tuple[bool, int]:
    """Return (on_cooldown, remaining_seconds)."""
    now = datetime.now()
    last = user_cooldowns.get(user_id)
    if not last:
        return False, 0
    delta = now - last
    if delta < timedelta(seconds=COOLDOWN_SECONDS):
        remaining = COOLDOWN_SECONDS - int(delta.total_seconds())
        return True, remaining
    return False, 0

def set_cooldown(user_id: int) -> None:
    user_cooldowns[user_id] = datetime.now()

async def send_captcha(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Create and send a new captcha for the user."""
    user_id = update.effective_user.id
    name = update.effective_user.first_name or "there"

    a, b, op, ans = generate_captcha()
    user_sessions[user_id] = UserSession(answer=ans, created_at=datetime.now())

    text = (
        f"👋 Hi {name},\n\n"
        "🔒 Solve this to unlock your invite links:\n\n"
        "Solve this:\n"
        f"🧮 `{a} {op} {b} = ?`\n\n"
        "Send your answer as a number (for example: `24`).\n"
        "You can type /start anytime to get a new question."
    )

    keyboard = [
        [InlineKeyboardButton("🔁 New question", callback_data="refresh_captcha")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.effective_message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=reply_markup,
        disable_web_page_preview=True,
    )

async def delete_after(message, delay: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        await asyncio.sleep(delay)
        await context.bot.delete_message(
            chat_id=message.chat_id,
            message_id=message.message_id,
        )
    except Exception:
        pass

def log_unlock(update: Update, main_temp: str, vouch_temp: str) -> None:
    with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                update.effective_user.id,
                update.effective_user.username or "",
                main_temp,
                vouch_temp,
            ]
        )

# ================== COMMAND HANDLERS ==================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start command: checks cooldown and sends captcha."""
    user_id = update.effective_user.id

    on_cd, remaining = is_on_cooldown(user_id)
    if on_cd:
        await update.message.reply_text(
            f"⏳ Please wait {remaining} more seconds before requesting a new question."
        )
        return

    set_cooldown(user_id)
    await send_captcha(update, context)

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "ℹ️ How this private sales access bot works:\n\n"
        "1️⃣ Send /start to receive a simple math question.\n"
        "2️⃣ Reply with the correct answer (only the number).\n"
        "3️⃣ If your answer is correct, you will receive temporary invite links:\n"
        "   • VIP Sales Channel (exclusive deals / offers)\n"
        "   • Proof / Vouch Channel (screenshots, feedback, updates)\n\n"
        f"⏳ The links are valid for {LINK_EXPIRY} seconds only.\n"
        "If they expire, just send /start again.\n\n"
        "This system helps keep the community private and safe."
    )
    await update.message.reply_text(text)

async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin-only stats command."""
    if ADMIN_ID == 0 or update.effective_user.id != ADMIN_ID:
        return

    active_sessions = len(user_sessions)
    text = (
        "📊 Bot Stats (current runtime):\n\n"
        f"🔓 Total successful unlocks: {total_unlocks}\n"
        f"🧮 Active pending questions: {active_sessions}\n"
        f"⏱ Cooldown (seconds): {COOLDOWN_SECONDS}\n"
        f"⏳ Link expiry (seconds): {LINK_EXPIRY}"
    )
    await update.message.reply_text(text)

# ================== MESSAGE / CALLBACK HANDLERS ==================

async def check_answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Checks numeric answer from the user."""
    user_id = update.effective_user.id
    message = update.message

    if user_id not in user_sessions:
        await message.reply_text(
            "⚠️ You don’t have an active question.\n"
            "Send /start to receive a new one."
        )
        return

    session = user_sessions[user_id]

    text = message.text.strip()
    if not text.lstrip("-").isdigit():
        session.attempts += 1
        await message.reply_text("✏️ Please reply with a valid number only.")
        return

    user_answer = int(text)
    session.attempts += 1

    if user_answer != session.answer:
        if session.attempts >= MAX_ATTEMPTS_PER_CAPTCHA:
            await message.reply_text(
                "❌ Wrong answer.\n"
                "You have used all attempts for this question.\n"
                "🔁 Generating a new question for you..."
            )
            await send_captcha(update, context)
        else:
            remaining_attempts = MAX_ATTEMPTS_PER_CAPTCHA - session.attempts
            await message.reply_text(
                "❌ Wrong answer. Please try again.\n"
                f"Attempts left for this question: {remaining_attempts}"
            )
        return

    # Correct answer
    global total_unlocks
    total_unlocks += 1

    main_temp = generate_temp_link(MAIN_LINK)
    vouch_temp = generate_temp_link(VOUCH_LINK)

    keyboard = [
        [InlineKeyboardButton("💎 Enter VIP Sales Channel", url=main_temp)],
        [InlineKeyboardButton("📸 View Proof / Vouch Channel", url=vouch_temp)],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    msg_text = (
        "✅ Verified successfully.\n\n"
        f"⏳ Your private access links are valid for *{LINK_EXPIRY} seconds* only.\n\n"
        "Follow these steps carefully:\n"
        "1️⃣ Tap both buttons below (VIP channel + proof channel).\n"
        "2️⃣ Press *Join* in each channel.\n"
        "3️⃣ Once joined, check pinned messages / instructions in the VIP channel.\n\n"
        "If the links expire, simply send */start* again."
    )

    msg = await message.reply_text(
        msg_text,
        parse_mode="Markdown",
        reply_markup=reply_markup,
        disable_web_page_preview=True,
    )

    log_unlock(update, main_temp, vouch_temp)
    context.application.create_task(delete_after(msg, LINK_EXPIRY, context))
    user_sessions.pop(user_id, None)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline buttons."""
    query = update.callback_query
    await query.answer()

    if query.data == "refresh_captcha":
        fake_update = Update(
            update.update_id,
            message=query.message
        )
        await send_captcha(fake_update, context)

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    print(f"⚠️ Error: {context.error}")

# ================== MAIN ==================

def main() -> None:
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(CallbackQueryHandler(button_callback))

    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, check_answer)
    )

    app.add_error_handler(error_handler)

    print(f"🚀 Private sales access bot running — links expire after {LINK_EXPIRY}s!")
    app.run_polling()

if __name__ == "__main__":
    main()

