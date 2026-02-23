import os
import random
import threading
import asyncio
from datetime import datetime
from flask import Flask, render_template_string
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

TOKEN = os.environ.get("tele_api")
ADMIN_USERNAME = "Rasul_utelbayev"
CHANNEL_ID = os.environ.get("CHANNEL_ID", "")

# ── Ma'lumotlar ───────────────────────────────────────────────────────────────
movies = {}
stats = {"users": {}, "total_requests": 0, "started": datetime.now().strftime("%Y-%m-%d %H:%M")}
waiting_movie = {}

def add_user(user):
    uid = str(user.id)
    if uid not in stats["users"]:
        stats["users"][uid] = {
            "name": user.full_name,
            "username": f"@{user.username}" if user.username else "yo'q",
            "joined": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "requests": 0
        }

def gen_code():
    while True:
        code = str(random.randint(1000, 9999))
        if code not in movies:
            return code

async def check_sub(bot, user_id):
    if not CHANNEL_ID:
        return True
    try:
        member = await bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status in ["member", "administrator", "creator"]
    except:
        return False

# ── Handlers ──────────────────────────────────────────────────────────────────
async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text.strip() if update.message.text else ""
    add_user(user)

    # Obuna tekshirish
    if not await check_sub(ctx.bot, user.id):
        keyboard = [[InlineKeyboardButton("📢 Obuna bo'lish", url=f"https://t.me/{CHANNEL_ID.replace('@', '')}")]]
        await update.message.reply_text(
            "⚠️ Botdan foydalanish uchun kanalga obuna bo'ling!",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    # Admin: "kino" desa kutish rejimi
    if user.username == ADMIN_USERNAME and text.lower() == "kino":
        waiting_movie[user.id] = True
        await update.message.reply_text("📤 Kinoni yuboring (caption = nomi):")
        return

    # Foydalanuvchi: faqat kod yozadi
    if text.isdigit() and len(text) == 4:
        if text in movies:
            stats["total_requests"] += 1
            stats["users"][str(user.id)]["requests"] += 1
            movie = movies[text]
            await update.message.reply_video(
                video=movie["file_id"],
                caption=f"🎬 *{movie['name']}*",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text("❌ Bunday kod topilmadi!")
        return

    # Boshqa xabar
    await update.message.reply_text("🎬 Kino olish uchun 4 xonali kod yuboring.\nMasalan: `2738`", parse_mode="Markdown")

async def handle_video(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.username != ADMIN_USERNAME:
        return
    if user.id not in waiting_movie:
        return

    video = update.message.video or update.message.document
    if not video:
        return

    name = update.message.caption or "Nomsiz"
    code = gen_code()
    movies[code] = {"file_id": video.file_id, "name": name, "date": datetime.now().strftime("%Y-%m-%d %H:%M")}
    del waiting_movie[user.id]

    await update.message.reply_text(
        f"✅ Saqlandi!\n\n🎬 *{name}*\n📌 Kod: `{code}`",
        parse_mode="Markdown"
    )

# ── Admin panel ───────────────────────────────────────────────────────────────
ADMIN_HTML = """
<!DOCTYPE html>
<html><head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Kino Bot Admin</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { background: #0d0d1a; color: #fff; font-family: 'Segoe UI', sans-serif; padding: 20px; }
        h1 { color: #e94560; margin-bottom: 20px; }
        h2 { color: #a0a0b0; font-size: 15px; margin: 20px 0 12px; }
        .cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 15px; margin-bottom: 20px; }
        .card { background: #16213e; border-radius: 12px; padding: 18px; border-left: 4px solid #e94560; }
        .card h3 { color: #a0a0b0; font-size: 12px; margin-bottom: 6px; }
        .card p { font-size: 26px; font-weight: 700; color: #e94560; }
        table { width: 100%; border-collapse: collapse; background: #16213e; border-radius: 12px; overflow: hidden; margin-bottom: 20px; }
        th { background: #0f3460; padding: 10px 12px; text-align: left; font-size: 12px; color: #a0a0b0; }
        td { padding: 10px 12px; border-bottom: 1px solid #0f3460; font-size: 13px; }
        tr:last-child td { border-bottom: none; }
        .badge { background: #e94560; color: #fff; padding: 2px 8px; border-radius: 10px; font-size: 11px; }
        .code { background: #0f3460; color: #4fc3f7; padding: 2px 8px; border-radius: 6px; font-family: monospace; }
        .btn { background: #e94560; border: none; color: #fff; padding: 8px 16px; border-radius: 8px; cursor: pointer; margin-bottom: 20px; }
        .empty { text-align: center; padding: 30px; color: #a0a0b0; }
    </style>
    <script>setTimeout(() => location.reload(), 30000)</script>
</head><body>
    <h1>🎬 Kino Bot Admin</h1>
    <button class="btn" onclick="location.reload()">🔄 Yangilash</button>
    <div class="cards">
        <div class="card"><h3>🎬 Kinolar</h3><p>{{ total_movies }}</p></div>
        <div class="card"><h3>👥 Foydalanuvchilar</h3><p>{{ total_users }}</p></div>
        <div class="card"><h3>📥 So'rovlar</h3><p>{{ total_requests }}</p></div>
    </div>

    <h2>🎬 Kinolar</h2>
    {% if movies %}
    <table>
        <tr><th>Kod</th><th>Nomi</th><th>Sana</th></tr>
        {% for code, m in movies %}
        <tr><td><span class="code">{{ code }}</span></td><td>{{ m.name }}</td><td>{{ m.date }}</td></tr>
        {% endfor %}
    </table>
    {% else %}<div class="empty">😴 Hali kino yo'q</div>{% endif %}

    <h2>👥 Foydalanuvchilar</h2>
    {% if users %}
    <table>
        <tr><th>#</th><th>Ism</th><th>Username</th><th>Qo'shilgan</th><th>So'rovlar</th></tr>
        {% for i, u in users %}
        <tr><td>{{ i }}</td><td>{{ u.name }}</td><td>{{ u.username }}</td><td>{{ u.joined }}</td><td><span class="badge">{{ u.requests }}</span></td></tr>
        {% endfor %}
    </table>
    {% else %}<div class="empty">😴 Hali hech kim yo'q</div>{% endif %}
</body></html>
"""

flask_app = Flask(__name__)

@flask_app.route("/")
def admin():
    return render_template_string(
        ADMIN_HTML,
        total_movies=len(movies),
        total_users=len(stats["users"]),
        total_requests=stats["total_requests"],
        movies=list(movies.items()),
        users=[(i+1, u) for i, u in enumerate(stats["users"].values())]
    )

@flask_app.route("/health")
def health():
    return "OK", 200

# ── Bot thread ────────────────────────────────────────────────────────────────
def run_bot():
    async def main():
        bot_app = ApplicationBuilder().token(TOKEN).build()
        bot_app.add_handler(MessageHandler(filters.VIDEO | filters.Document.VIDEO, handle_video))
        bot_app.add_handler(MessageHandler(filters.TEXT, handle_message))
        print("Kino bot ishlamoqda... 🎬")
        await bot_app.initialize()
        await bot_app.start()
        await bot_app.updater.start_polling(drop_pending_updates=True)
        while True:
            await asyncio.sleep(1)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(main())

if __name__ == "__main__":
    threading.Thread(target=run_bot, daemon=True).start()
    port = int(os.environ.get("PORT", 5000))
    flask_app.run(host="0.0.0.0", port=port)
