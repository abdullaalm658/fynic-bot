import os
import sqlite3
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters
)

# ================= CONFIG =================
TOKEN = os.getenv("TOKEN")   # 🚨 Railway Environment Variable
if not TOKEN:
    raise RuntimeError("TOKEN not found in environment variables")

BOT_USERNAME = "FynixTokenBot_bot"   # without @

COIN_NAME = "Fynix Token"
JOIN_BONUS = 100
REFER_BONUS = 500
MIN_WITHDRAW = 20000

REQUIRED_CHANNELS = [
    "@FynixTokenBot",
    "@FynixTokenBot_News",
]

ADMIN_IDS = [8573670035]
# =========================================

# ---------- DATABASE ----------
conn = sqlite3.connect("fynix.db", check_same_thread=False)
cur = conn.cursor()
cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    referrals INTEGER DEFAULT 0,
    balance INTEGER DEFAULT 0,
    wallet TEXT DEFAULT ''
)
""")
conn.commit()

# ---------- UI ----------
MAIN_MENU = ReplyKeyboardMarkup(
    [
        ["💰 Balance", "🤝 Invite"],
        ["👛 Wallet", "💸 Withdraw"],
        ["ℹ️ Information"],
    ],
    resize_keyboard=True
)

def is_admin(uid: int) -> bool:
    return uid in ADMIN_IDS

def join_keyboard():
    rows = []
    for ch in REQUIRED_CHANNELS:
        rows.append([
            InlineKeyboardButton(
                f"📢 Join {ch}",
                url=f"https://t.me/{ch.replace('@','')}"
            )
        ])
    rows.append([
        InlineKeyboardButton(
            "🔍 Continue / Verify Join",
            callback_data="verify_join"
        )
    ])
    return InlineKeyboardMarkup(rows)

async def is_joined_all(app, user_id: int) -> bool:
    for ch in REQUIRED_CHANNELS:
        try:
            member = await app.bot.get_chat_member(ch, user_id)
            if member.status in ("left", "kicked"):
                return False
        except:
            return False
    return True

def ensure_user(uid: int):
    cur.execute("SELECT user_id FROM users WHERE user_id=?", (uid,))
    if not cur.fetchone():
        cur.execute("INSERT INTO users(user_id) VALUES(?)", (uid,))
        conn.commit()

def get_user(uid: int):
    ensure_user(uid)
    cur.execute("SELECT referrals, balance, wallet FROM users WHERE user_id=?", (uid,))
    return cur.fetchone()

def add_balance(uid: int, amount: int):
    cur.execute(
        "UPDATE users SET balance = balance + ? WHERE user_id=?",
        (amount, uid)
    )
    conn.commit()

def referral_link(uid: int):
    return f"https://t.me/{BOT_USERNAME}?start={uid}"

# ---------- HANDLERS ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    ensure_user(uid)

    joined = await is_joined_all(context.application, uid)
    if not joined:
        await update.message.reply_text(
            "🚫 Must join all channels first!",
            reply_markup=join_keyboard()
        )
        return

    refs, bal, wallet = get_user(uid)
    if bal == 0 and refs == 0 and wallet == "":
        add_balance(uid, JOIN_BONUS)

    await update.message.reply_text(
        f"🎉 Welcome to {COIN_NAME} Airdrop\n\n"
        f"✅ Join Bonus: {JOIN_BONUS}\n"
        f"🎁 Refer Bonus: {REFER_BONUS}\n\n"
        "Use menu below 👇",
        reply_markup=MAIN_MENU
    )

async def verify_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id

    if not await is_joined_all(context.application, uid):
        await q.edit_message_text(
            "❌ You have not joined all channels",
            reply_markup=join_keyboard()
        )
        return

    await q.edit_message_text("✅ Verified successfully!")
    await context.application.bot.send_message(
        uid, "🎉 Access granted!", reply_markup=MAIN_MENU
    )

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text

    ensure_user(uid)
    refs, bal, wallet = get_user(uid)

    if text == "💰 Balance":
        await update.message.reply_text(
            f"👤 ID: {uid}\n"
            f"💎 Balance: {bal} {COIN_NAME}\n"
            f"👥 Referrals: {refs}"
        )

    elif text == "🤝 Invite":
        await update.message.reply_text(
            f"🤝 Invite Friends\n\n"
            f"🎁 {REFER_BONUS} {COIN_NAME} per referral\n\n"
            f"🔗 Your Link:\n{referral_link(uid)}"
        )

    elif text == "ℹ️ Information":
        await update.message.reply_text(
            f"{COIN_NAME} Airdrop Bot\n"
            f"Join: {JOIN_BONUS}\nRefer: {REFER_BONUS}"
        )

    else:
        await update.message.reply_text(
            "Use menu buttons 👇",
            reply_markup=MAIN_MENU
        )

# ---------- ADMIN ----------
async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Admin only")
        return
    await update.message.reply_text(
        "🛠 Admin Panel\n"
        "/userinfo <id>\n"
        "/addbal <id> <amount>"
    )

async def userinfo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    uid = int(context.args[0])
    refs, bal, wallet = get_user(uid)
    await update.message.reply_text(
        f"User: {uid}\nBalance: {bal}\nRefs: {refs}\nWallet: {wallet}"
    )

async def addbal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    uid = int(context.args[0])
    amount = int(context.args[1])
    add_balance(uid, amount)
    await update.message.reply_text("✅ Balance added")

# ---------- MAIN ----------
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(verify_join, pattern="^verify_join$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, menu))

    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CommandHandler("userinfo", userinfo))
    app.add_handler(CommandHandler("addbal", addbal))

    app.run_polling()

if __name__ == "__main__":
    main()
