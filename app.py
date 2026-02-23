import os
import random
import threading
import asyncio
from datetime import datetime
from flask import Flask, render_template_string, request, redirect, session
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

TOKEN = os.environ.get("tele_api")
ADMIN_USERNAME = "Rasul_utelbayev"
WEB_PASSWORD = "rAsuto2008"

# ── Ma'lumotlar ───────────────────────────────────────────────────────────────
movies = {}
channels = {}  # {channel_id: {"link": ..., "is_admin": bool, "subscribers": int}}
stats = {"users": {}, "total_requests": 0, "started": datetime.now().strftime("%Y-%m-%d %H:%M")}
waiting_movie = {}
bot_instance = None

def add_user(user):
    uid = str(user.id)
    if uid not in stats["users"]:
        stats["users"][uid] = {
            "name": user.full_name,
            "username": f"@{user.username}" if user.username else "yo'q",
            "joined": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "requests": 0,
            "subscribed_via": {}
        }

def gen_code():
    while True:
        code = str(random.randint(1000, 9999))
        if code not in movies:
            return code

async def check_channel_admin(bot, channel_id):
    try:
        me = await bot.get_me()
        member = await bot.get_chat_member(channel_id, me.id)
        return member.status in ["administrator", "creator"]
    except:
        return False

async def check_user_subscriptions(bot, user_id):
    if not channels:
        return True, []
    not_subscribed = []
    for ch_id, ch_info in channels.items():
        try:
            member = await bot.get_chat_member(ch_id, user_id)
            if member.status not in ["member", "administrator", "creator"]:
                not_subscribed.append(ch_info)
        except:
            not_subscribed.append(ch_info)
    return len(not_subscribed) == 0, not_subscribed

# ── Bot handlers ──────────────────────────────────────────────────────────────
async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    global bot_instance
    bot_instance = ctx.bot
    user = update.effective_user
    text = update.message.text.strip() if update.message.text else ""
    add_user(user)

    # Obuna tekshirish
    subscribed, not_subbed = await check_user_subscriptions(ctx.bot, user.id)
    if not subscribed:
        keyboard = [[InlineKeyboardButton(f"📢 {ch.get('link', 'Kanal')}", url=ch["link"])] for ch in not_subbed]
        keyboard.append([InlineKeyboardButton("✅ Tekshirish", callback_data="check_sub")])
        await update.message.reply_text(
            "⚠️ Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling!",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    # Admin: kino yuklash
    if user.username == ADMIN_USERNAME and text.lower() == "kino":
        waiting_movie[user.id] = True
        await update.message.reply_text("📤 Kinoni yuboring (caption = nomi):")
        return

    # Foydalanuvchi: kod
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

    await update.message.reply_text("🎬 Kino olish uchun 4 xonali kod yuboring.\nMasalan: `2738`", parse_mode="Markdown")

async def handle_video(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    global bot_instance
    bot_instance = ctx.bot
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

# ── Flask ─────────────────────────────────────────────────────────────────────
flask_app = Flask(__name__)
flask_app.secret_key = "rasuto_secret_2026"

LOGIN_HTML = """
<!DOCTYPE html>
<html><head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Admin Login</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { background: #0d0d1a; color: #fff; font-family: 'Segoe UI', sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; }
        .box { background: #16213e; padding: 40px 30px; border-radius: 20px; width: 100%; max-width: 360px; }
        h2 { color: #e94560; text-align: center; margin-bottom: 25px; }
        input { width: 100%; padding: 12px; margin: 8px 0; border-radius: 10px; border: 1px solid #0f3460; background: #0d0d1a; color: #fff; font-size: 15px; outline: none; }
        input:focus { border-color: #e94560; }
        button { width: 100%; padding: 13px; margin-top: 10px; border-radius: 10px; border: none; background: #e94560; color: #fff; font-size: 15px; font-weight: 600; cursor: pointer; }
        .err { color: #ff6b6b; text-align: center; margin-top: 10px; font-size: 14px; }
    </style>
</head><body>
    <div class="box">
        <h2>🤖 Admin Panel</h2>
        <input type="password" id="p" placeholder="Parol" onkeydown="if(event.key==='Enter')login()">
        <button onclick="login()">Kirish</button>
        <div class="err" id="err"></div>
    </div>
    <script>
        function login() {
            fetch('/login', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({password: document.getElementById('p').value})})
            .then(r=>r.json()).then(d=>{ if(d.ok) location.reload(); else document.getElementById('err').innerText='Parol noto\'g\'ri!'; })
        }
    </script>
</body></html>
"""

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
        h2 { color: #a0a0b0; font-size: 15px; margin: 25px 0 12px; }
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
        .ok { color: #4caf50; font-weight: 600; }
        .no { color: #ff6b6b; font-weight: 600; }
        .btn { background: #e94560; border: none; color: #fff; padding: 8px 16px; border-radius: 8px; cursor: pointer; margin-bottom: 10px; font-size: 13px; margin-right: 8px; }
        .btn-del { background: #333; }
        .input-row { display: flex; gap: 8px; margin-bottom: 20px; }
        .input-row input { flex: 1; padding: 10px; border-radius: 8px; border: 1px solid #0f3460; background: #0d0d1a; color: #fff; font-size: 14px; outline: none; }
        .input-row input:focus { border-color: #e94560; }
        .empty { text-align: center; padding: 30px; color: #a0a0b0; }
        .logout { float: right; background: transparent; border: 1px solid #e94560; color: #e94560; padding: 6px 12px; border-radius: 8px; cursor: pointer; font-size: 13px; }
    </style>
    <script>setTimeout(() => location.reload(), 30000)</script>
</head><body>
    <h1>🎬 Kino Bot Admin <button class="logout" onclick="logout()">Chiqish</button></h1>
    <button class="btn" onclick="location.reload()">🔄 Yangilash</button>

    <div class="cards">
        <div class="card"><h3>🎬 Kinolar</h3><p>{{ total_movies }}</p></div>
        <div class="card"><h3>👥 Foydalanuvchilar</h3><p>{{ total_users }}</p></div>
        <div class="card"><h3>📥 So'rovlar</h3><p>{{ total_requests }}</p></div>
        <div class="card"><h3>📢 Kanallar</h3><p>{{ total_channels }}</p></div>
    </div>

    <!-- Kanallar -->
    <h2>📢 Majburiy Obuna Kanallar</h2>
    <div class="input-row">
        <input id="ch_id" placeholder="Kanal ID (masalan: -1001234567890)">
        <input id="ch_link" placeholder="Kanal link (masalan: https://t.me/kanal)">
        <button class="btn" onclick="addChannel()">➕ Qo'shish</button>
    </div>
    {% if channels %}
    <table>
        <tr><th>Kanal ID</th><th>Link</th><th>Bot Admin</th><th>Obunalar</th><th></th></tr>
        {% for ch_id, ch in channels %}
        <tr>
            <td><span class="code">{{ ch_id }}</span></td>
            <td><a href="{{ ch.link }}" style="color:#4fc3f7" target="_blank">{{ ch.link }}</a></td>
            <td>{% if ch.is_admin %}<span class="ok">✅ Admin</span>{% else %}<span class="no">❌ Admin emas</span>{% endif %}</td>
            <td><span class="badge">{{ ch.subscribers }}</span></td>
            <td><button class="btn btn-del" onclick="delChannel('{{ ch_id }}')">🗑</button></td>
        </tr>
        {% endfor %}
    </table>
    {% else %}<div class="empty">😴 Kanal qo'shilmagan</div>{% endif %}

    <!-- Kinolar -->
    <h2>🎬 Kinolar</h2>
    {% if movies %}
    <table>
        <tr><th>Kod</th><th>Nomi</th><th>Sana</th></tr>
        {% for code, m in movies %}
        <tr><td><span class="code">{{ code }}</span></td><td>{{ m.name }}</td><td>{{ m.date }}</td></tr>
        {% endfor %}
    </table>
    {% else %}<div class="empty">😴 Hali kino yo'q</div>{% endif %}

    <!-- Foydalanuvchilar -->
    <h2>👥 Foydalanuvchilar</h2>
    {% if users %}
    <table>
        <tr><th>#</th><th>Ism</th><th>Username</th><th>Qo'shilgan</th><th>So'rovlar</th></tr>
        {% for i, u in users %}
        <tr><td>{{ i }}</td><td>{{ u.name }}</td><td>{{ u.username }}</td><td>{{ u.joined }}</td><td><span class="badge">{{ u.requests }}</span></td></tr>
        {% endfor %}
    </table>
    {% else %}<div class="empty">😴 Hali hech kim yo'q</div>{% endif %}

    <script>
        function addChannel() {
            const id = document.getElementById('ch_id').value.trim();
            const link = document.getElementById('ch_link').value.trim();
            if (!id || !link) return alert('Kanal ID va linkni kiriting!');
            fetch('/add_channel', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({id, link})})
            .then(r=>r.json()).then(d=>{ if(d.ok) location.reload(); else alert('Xato!'); })
        }
        function delChannel(id) {
            if (!confirm('Ochirasizmi?')) return;
            fetch('/del_channel', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({id})})
            .then(r=>r.json()).then(d=>{ if(d.ok) location.reload(); })
        }
        function logout() {
            fetch('/logout').then(() => location.reload());
        }
    </script>
</body></html>
"""

@flask_app.route("/")
def index():
    if not session.get("admin"):
        return render_template_string(LOGIN_HTML)

    # Kanal admin statusini yangilash
    ch_data = []
    for ch_id, ch in channels.items():
        ch_data.append((ch_id, ch))

    return render_template_string(
        ADMIN_HTML,
        total_movies=len(movies),
        total_users=len(stats["users"]),
        total_requests=stats["total_requests"],
        total_channels=len(channels),
        channels=ch_data,
        movies=list(movies.items()),
        users=[(i+1, u) for i, u in enumerate(stats["users"].values())]
    )

@flask_app.route("/login", methods=["POST"])
def login():
    data = request.json
    if data.get("password") == WEB_PASSWORD:
        session["admin"] = True
        return {"ok": True}
    return {"ok": False}

@flask_app.route("/logout")
def logout():
    session.pop("admin", None)
    return {"ok": True}

@flask_app.route("/add_channel", methods=["POST"])
def add_channel():
    if not session.get("admin"):
        return {"ok": False}
    data = request.json
    ch_id = data.get("id")
    link = data.get("link")
    channels[ch_id] = {"link": link, "is_admin": False, "subscribers": 0}

    # Bot admin tekshirish
    if bot_instance:
        async def check():
            is_admin = await check_channel_admin(bot_instance, ch_id)
            channels[ch_id]["is_admin"] = is_admin
        asyncio.run_coroutine_threadsafe(check(), bot_loop)

    return {"ok": True}

@flask_app.route("/del_channel", methods=["POST"])
def del_channel():
    if not session.get("admin"):
        return {"ok": False}
    ch_id = request.json.get("id")
    channels.pop(ch_id, None)
    return {"ok": True}

@flask_app.route("/health")
def health():
    return "OK", 200

# ── Bot thread ────────────────────────────────────────────────────────────────
bot_loop = None

def run_bot():
    global bot_loop
    async def main():
        global bot_instance
        bot_app = ApplicationBuilder().token(TOKEN).build()
        bot_instance = bot_app.bot
        bot_app.add_handler(MessageHandler(filters.VIDEO | filters.Document.VIDEO, handle_video))
        bot_app.add_handler(MessageHandler(filters.TEXT, handle_message))
        print("Kino bot ishlamoqda... 🎬")
        await bot_app.initialize()
        await bot_app.start()
        await bot_app.updater.start_polling(drop_pending_updates=True)
        while True:
            await asyncio.sleep(1)

    loop = asyncio.new_event_loop()
    bot_loop = loop
    asyncio.set_event_loop(loop)
    loop.run_until_complete(main())

if __name__ == "__main__":
    threading.Thread(target=run_bot, daemon=True).start()
    port = int(os.environ.get("PORT", 5000))
    flask_app.run(host="0.0.0.0", port=port)
