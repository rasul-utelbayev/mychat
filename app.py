import os
import random
import threading
import asyncio
from datetime import datetime
from flask import Flask, render_template_string
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

TOKEN = os.environ.get("tele_api")

# ── Statistika ────────────────────────────────────────────────────────────────
stats = {
    "users": {},
    "total_messages": 0,
    "started": datetime.now().strftime("%Y-%m-%d %H:%M")
}

def add_user(user):
    uid = str(user.id)
    if uid not in stats["users"]:
        stats["users"][uid] = {
            "name": user.full_name,
            "username": f"@{user.username}" if user.username else "yo'q",
            "joined": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "messages": 0
        }

def count_message(user):
    uid = str(user.id)
    if uid in stats["users"]:
        stats["users"][uid]["messages"] += 1
    stats["total_messages"] += 1

# ── Kontent ───────────────────────────────────────────────────────────────────
JOKES = [
    "Dasturchi nima yeydi? — Spam! 🍖",
    "Bug nima? — Feature ning noto'g'ri ismi! 😄",
    "99 ta bug fix qildim, 127 tasi chiqdi. 😭",
    "Git push qildim, hammasi yondi. Normal kun. 🔥",
    "Hello World yozib dasturchi bo'laman deb o'ylardim... 😂",
]

FACTS = [
    "🌍 Dunyoda 700+ dasturlash tili bor!",
    "🐛 'Bug' so'zi 1947 yilda real chivindan kelib chiqqan!",
    "💻 Birinchi kompyuter 27 ton og'ir edi!",
    "🐍 Python 1991 yilda yaratilgan!",
    "📱 Smartfonlar Apollo 11 kompyuteridan million marta kuchliroq!",
]

MOTIVATIONS = [
    "💪 Har bir expert bir vaqtlar beginner bo'lgan!",
    "🚀 Katta safar ham bitta qadamdan boshlanadi!",
    "🔥 Muvaffaqiyat — sabr + mehnat + vaqt!",
    "⭐ Bugun o'rgangan narsa ertangi qurolting!",
    "🌱 Har kuni 1% yaxshilansang, 1 yilda 37x kuchliroq bo'lasan!",
]

RIDDLES = [
    ("Boshida 0, oxirida 1, o'rtasida hamma narsa — bu nima? 🤔", "Ikkilik sistema (Binary)!"),
    ("Har kuni ishlaydi, lekin hech qachon charchamaydi — bu nima? 🤔", "Server!"),
    ("Ko'rinmaydi, lekin hamma joyda bor — bu nima? 🤔", "Internet!"),
    ("Yozasan lekin o'qimaysan, o'qiysan lekin yozmaysan — bu nima? 🤔", "Parol!"),
]

user_riddles = {}

# ── Bot handlers ──────────────────────────────────────────────────────────────
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    add_user(update.effective_user)
    count_message(update.effective_user)
    keyboard = [
        [InlineKeyboardButton("😂 Hazil", callback_data="joke"),
         InlineKeyboardButton("🧠 Fakt", callback_data="fact")],
        [InlineKeyboardButton("💪 Motivatsiya", callback_data="motivation"),
         InlineKeyboardButton("🎯 Topishmoq", callback_data="riddle")],
        [InlineKeyboardButton("🎲 Tasodifiy raqam", callback_data="random"),
         InlineKeyboardButton("🪙 Tanga tashlash", callback_data="coin")],
    ]
    await update.message.reply_text(
        f"👋 Salom, {update.effective_user.first_name}!\n\nNima qilamiz? 👇",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def button(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    count_message(query.from_user)
    back = [[InlineKeyboardButton("🔙 Orqaga", callback_data="back")]]

    if query.data == "joke":
        await query.edit_message_text(f"😂 *Hazil:*\n\n{random.choice(JOKES)}", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(back))
    elif query.data == "fact":
        await query.edit_message_text(f"🧠 *Fakt:*\n\n{random.choice(FACTS)}", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(back))
    elif query.data == "motivation":
        await query.edit_message_text(f"💪 *Motivatsiya:*\n\n{random.choice(MOTIVATIONS)}", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(back))
    elif query.data == "riddle":
        riddle, answer = random.choice(RIDDLES)
        user_riddles[uid] = answer
        keyboard = [
            [InlineKeyboardButton("💡 Javobni ko'rish", callback_data="answer")],
            [InlineKeyboardButton("🔙 Orqaga", callback_data="back")]
        ]
        await query.edit_message_text(f"🎯 *Topishmoq:*\n\n{riddle}", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    elif query.data == "answer":
        answer = user_riddles.get(uid, "Avval topishmoq tanlang!")
        await query.edit_message_text(f"💡 *Javob:*\n\n{answer}", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(back))
    elif query.data == "random":
        await query.edit_message_text(f"🎲 *Tasodifiy raqam:*\n\n`{random.randint(1, 1000)}`", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(back))
    elif query.data == "coin":
        result = random.choice(["👑 Bosh (Heads)", "🦅 Dumba (Tails)"])
        await query.edit_message_text(f"🪙 *Tanga:*\n\n{result}!", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(back))
    elif query.data == "back":
        keyboard = [
            [InlineKeyboardButton("😂 Hazil", callback_data="joke"),
             InlineKeyboardButton("🧠 Fakt", callback_data="fact")],
            [InlineKeyboardButton("💪 Motivatsiya", callback_data="motivation"),
             InlineKeyboardButton("🎯 Topishmoq", callback_data="riddle")],
            [InlineKeyboardButton("🎲 Tasodifiy raqam", callback_data="random"),
             InlineKeyboardButton("🪙 Tanga tashlash", callback_data="coin")],
        ]
        await query.edit_message_text("Nima qilamiz? 👇", reply_markup=InlineKeyboardMarkup(keyboard))

async def echo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    add_user(update.effective_user)
    count_message(update.effective_user)
    await update.message.reply_text("😅 Tushunmadim. /start bosing!")

# ── Admin panel ───────────────────────────────────────────────────────────────
ADMIN_HTML = """
<!DOCTYPE html>
<html lang="uz">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Bot Admin Panel</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { background: #0d0d1a; color: #fff; font-family: 'Segoe UI', sans-serif; padding: 20px; }
        h1 { color: #e94560; margin-bottom: 20px; font-size: 24px; }
        .cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 15px; margin-bottom: 30px; }
        .card { background: #16213e; border-radius: 12px; padding: 20px; border-left: 4px solid #e94560; }
        .card h3 { color: #a0a0b0; font-size: 13px; margin-bottom: 8px; }
        .card p { font-size: 32px; font-weight: 700; color: #e94560; }
        .card .small { font-size: 16px; margin-top: 8px; }
        table { width: 100%; border-collapse: collapse; background: #16213e; border-radius: 12px; overflow: hidden; }
        th { background: #0f3460; padding: 12px; text-align: left; font-size: 13px; color: #a0a0b0; }
        td { padding: 12px; border-bottom: 1px solid #0f3460; font-size: 14px; }
        tr:last-child td { border-bottom: none; }
        tr:hover td { background: #1f2d50; }
        .badge { background: #e94560; color: #fff; padding: 2px 8px; border-radius: 10px; font-size: 12px; }
        h2 { margin-bottom: 15px; color: #a0a0b0; font-size: 16px; }
        .btn { background: #e94560; border: none; color: #fff; padding: 8px 16px; border-radius: 8px; cursor: pointer; margin-bottom: 20px; font-size: 14px; }
        .empty { text-align: center; padding: 40px; color: #a0a0b0; }
    </style>
    <script>setTimeout(() => location.reload(), 30000)</script>
</head>
<body>
    <h1>🤖 Bot Admin Panel</h1>
    <button class="btn" onclick="location.reload()">🔄 Yangilash</button>

    <div class="cards">
        <div class="card">
            <h3>👥 Foydalanuvchilar</h3>
            <p>{{ total_users }}</p>
        </div>
        <div class="card">
            <h3>💬 Jami xabarlar</h3>
            <p>{{ total_messages }}</p>
        </div>
        <div class="card">
            <h3>🕐 Ishga tushgan</h3>
            <p class="small">{{ started }}</p>
        </div>
    </div>

    <h2>📋 Foydalanuvchilar</h2>
    {% if users %}
    <table>
        <tr>
            <th>#</th>
            <th>Ism</th>
            <th>Username</th>
            <th>Qo'shilgan</th>
            <th>Xabarlar</th>
        </tr>
        {% for i, user in users %}
        <tr>
            <td>{{ i }}</td>
            <td>{{ user.name }}</td>
            <td>{{ user.username }}</td>
            <td>{{ user.joined }}</td>
            <td><span class="badge">{{ user.messages }}</span></td>
        </tr>
        {% endfor %}
    </table>
    {% else %}
    <div class="empty">😴 Hali hech kim botni ishlatmagan</div>
    {% endif %}
</body>
</html>
"""

# ── Flask ─────────────────────────────────────────────────────────────────────
flask_app = Flask(__name__)

@flask_app.route("/")
def admin():
    users = [(i+1, u) for i, u in enumerate(stats["users"].values())]
    return render_template_string(
        ADMIN_HTML,
        total_users=len(stats["users"]),
        total_messages=stats["total_messages"],
        started=stats["started"],
        users=users
    )

@flask_app.route("/health")
def health():
    return "OK", 200

# ── Bot thread ────────────────────────────────────────────────────────────────
def run_bot():
    async def main():
        bot_app = ApplicationBuilder().token(TOKEN).build()
        bot_app.add_handler(CommandHandler("start", start))
        bot_app.add_handler(CallbackQueryHandler(button))
        bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))
        print("Bot ishlamoqda... 🚀")
        await bot_app.initialize()
        await bot_app.start()
        await bot_app.updater.start_polling(drop_pending_updates=True)
        while True:
            await asyncio.sleep(1)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(main())

# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    threading.Thread(target=run_bot, daemon=True).start()
    port = int(os.environ.get("PORT", 5000))
    flask_app.run(host="0.0.0.0", port=port)
