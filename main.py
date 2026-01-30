from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters
)
import sqlite3

# ===== EDIT THESE =====
TOKEN = "8529982079:AAGx_cdHsdNw8vyEWS6AQJ-tVAKtBOGTYaM"
ADMIN_IDS = [8573670035]
BOT_USERNAME = "FynixTokenBot_bot"  # without @

COIN_NAME = "Fynix Token"
JOIN_BONUS = 100
REFER_BONUS = 500
MIN_WITHDRAW = 10000  # ইচ্ছা করলে বদলাও

REQUIRED_CHANNELS = [
    "@FynixTokenBot",
    "@FynixTokenBot_News",
]
# ======================

# ---------- DB ----------
conn = sqlite3.connect("fynix.db", check_same_thread=False)
cur = conn.cursor()
cur.execute("""
CREATE TABLE IF NOT EXISTS users(
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

def join_keyboard():
    rows = []
    for ch in REQUIRED_CHANNELS:
        rows.append([InlineKeyboardButton(f"📢 Join {ch}", url=f"https://t.me/{ch.replace('@','')}")])
    rows.append([InlineKeyboardButton("🔍 Continue / Verify Join", callback_data="verify_join")])
    return InlineKeyboardMarkup(rows)

def referral_link(user_id: int) -> str:
    return f"https://t.me/{BOT_USERNAME}?start={user_id}"

async def is_joined_all(app, user_id: int) -> bool:
    # Verify join works only if bot is ADMIN in those channels
    for ch in REQUIRED_CHANNELS:
        try:
            m = await app.bot.get_chat_member(chat_id=ch, user_id=user_id)
            if m.status in ("left", "kicked"):
                return False
        except Exception:
            return False
    return True

def ensure_user(user_id: int):
    cur.execute("SELECT user_id FROM users WHERE user_id=?", (user_id,))
    if not cur.fetchone():
        cur.execute("INSERT INTO users(user_id) VALUES(?)", (user_id,))
        conn.commit()

def add_bonus(user_id: int, amount: int):
    cur.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (amount, user_id))
    conn.commit()

def add_referral(referrer_id: int):
    # increase ref count and bonus
    cur.execute("SELECT user_id FROM users WHERE user_id=?", (referrer_id,))
    if cur.fetchone():
        cur.execute("UPDATE users SET referrals = referrals + 1 WHERE user_id=?", (referrer_id,))
        cur.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (REFER_BONUS, referrer_id))
        conn.commit()

def get_user(user_id: int):
    ensure_user(user_id)
    cur.execute("SELECT referrals, balance, wallet FROM users WHERE user_id=?", (user_id,))
    return cur.fetchone()  # (refs, bal, wallet)

# ---------- Handlers ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    ensure_user(user_id)

    # referral param
    ref_by = None
    if context.args:
        try:
            ref_by = int(context.args[0])
        except:
            ref_by = None

    # Gate first
    joined = await is_joined_all(context.application, user_id)
    if not joined:
        await update.message.reply_text(
            "🚫 Must join all channels first ✅\n\n"
            "1) Join both channels\n"
            "2) Tap 🔍 Continue / Verify Join",
            reply_markup=join_keyboard()
        )
        return

    # First-time join bonus (only once)
    # We'll store bonus by checking if balance is 0 and referrals 0 and wallet empty (simple)
    refs, bal, wallet = get_user(user_id)
    if bal == 0 and refs == 0 and wallet == "":
        add_bonus(user_id, JOIN_BONUS)
        # give referral reward if ref_by exists and not self
        if ref_by and ref_by != user_id:
            ensure_user(ref_by)
            add_referral(ref_by)

    await update.message.reply_text(
        f"🎉 Welcome to {COIN_NAME} Airdrop!\n"
        f"✅ Joining Bonus: {JOIN_BONUS} {COIN_NAME}\n"
        f"🎁 Per Refer: {REFER_BONUS} {COIN_NAME}\n\n"
        "Use the menu below 👇",
        reply_markup=MAIN_MENU
    )

async def verify_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user_id = q.from_user.id

    joined = await is_joined_all(context.application, user_id)
    if not joined:
        await q.edit_message_text(
            "❌ You still haven’t joined all required channels.\n"
            "Join them and tap 🔍 Continue / Verify Join again.",
            reply_markup=join_keyboard()
        )
        return

    await q.edit_message_text("✅ Verified! Now you can use the bot.")
    await context.application.bot.send_message(
        chat_id=user_id,
        text="🎉 Access granted! Use the menu 👇",
        reply_markup=MAIN_MENU
    )

# Wallet input state (simple in-memory)
WAITING_WALLET = set()

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = (update.message.text or "").strip()

    # Gate check
    if not await is_joined_all(context.application, user_id):
        await update.message.reply_text(
            "🚫 Must join all channels first ✅\n\n"
            "Join both channels then tap Verify.",
            reply_markup=join_keyboard()
        )
        return

    ensure_user(user_id)
    refs, bal, wallet = get_user(user_id)

    if user_id in WAITING_WALLET:
        # user is sending wallet address
        addr = text
        if len(addr) < 10:
            await update.message.reply_text("❌ Wallet address seems too short. Try again or send /start")
            return
        cur.execute("UPDATE users SET wallet=? WHERE user_id=?", (addr, user_id))
        conn.commit()
        WAITING_WALLET.discard(user_id)
        await update.message.reply_text("✅ Wallet saved successfully!", reply_markup=MAIN_MENU)
        return

    if text == "💰 Balance":
        await update.message.reply_text(
            f"👤 ID: {user_id}\n"
            f"💎 Available: {bal} {COIN_NAME}\n"
            f"👥 Total Invites: {refs}"
        )

    elif text == "🤝 Invite":
        link = referral_link(user_id)
        await update.message.reply_text(
            f"🤝 Affiliate Program\n\n"
            f"🎁 Reward per Invite: {REFER_BONUS} {COIN_NAME}\n"
            f"👥 Total Invites: {refs}\n\n"
            f"🔗 Your Link:\n{link}"
        )

    elif text == "👛 Wallet":
        show = wallet if wallet else "None"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("Change Wallet Address", callback_data="change_wallet")]
        ])
        await update.message.reply_text(
            f"👛 Your wallet address:\n{show}\n\n"
            "Use button below to change 👇",
            reply_markup=kb
        )

    elif text == "💸 Withdraw":
        if bal < MIN_WITHDRAW:
            await update.message.reply_text(
                f"⚠️ You need at least {MIN_WITHDRAW} {COIN_NAME} to Withdraw.\n"
                f"📊 Current Status: {bal}/{MIN_WITHDRAW} {COIN_NAME}"
            )
            return
        if not wallet:
            await update.message.reply_text("❌ Set your wallet first from 👛 Wallet")
            return

        # demo withdraw request (real payout not implemented)
        await update.message.reply_text(
            "✅ Withdraw request submitted (demo).\n"
            "Admin will review & process."
        )

    elif text == "ℹ️ Information":
        await update.message.reply_text(
            f"ℹ️ {COIN_NAME} Airdrop Bot\n\n"
            f"✅ Join bonus: {JOIN_BONUS}\n"
            f"🎁 Refer bonus: {REFER_BONUS}\n"
            f"💸 Min withdraw: {MIN_WITHDRAW}\n"
        )
    else:
        await update.message.reply_text("Use the menu buttons 👇", reply_markup=MAIN_MENU)

async def change_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user_id = q.from_user.id

    WAITING_WALLET.add(user_id)
    await q.message.reply_text(
        "👇 Enter your wallet address now (BSC / MetaMask / TrustWallet):\n\n"
        "Send the address as a message.\n"
        "To cancel, send: /start"
    )

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(verify_join, pattern="^verify_join$"))
    app.add_handler(CallbackQueryHandler(change_wallet, pattern="^change_wallet$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, menu))
    app.run_polling()

if __name__ == "__main__":
    main()
