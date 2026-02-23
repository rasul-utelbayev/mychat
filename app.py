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
movies = {}       # {kod: {file_id, name, date}}
serials = {}      # {kod: {name, episodes: [{file_id, ep}], date}}
channels = {}     # {ch_id: {link, is_admin, subscribers}}
stats = {"users": {}, "total_requests": 0, "started": datetime.now().strftime("%Y-%m-%d %H:%M")}

waiting_movie = {}   # {user_id: True}
waiting_serial = {}  # {user_id: {name: None, episodes: [], step: "name"|"episodes"}}

bot_loop = None
bot_instance = None

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
        if code not in movies and code not in serials:
            return code

async def check_sub(bot, user_id):
    if not channels:
        return True, []
    not_subbed = []
    for ch_id, ch in channels.items():
        try:
            m = await bot.get_chat_member(ch_id, user_id)
            if m.status not in ["member", "administrator", "creator"]:
                not_subbed.append(ch)
        except:
            not_subbed.append(ch)
    return len(not_subbed) == 0, not_subbed

async def check_admin(bot, ch_id):
    try:
        me = await bot.get_me()
        m = await bot.get_chat_member(ch_id, me.id)
        return m.status in ["administrator", "creator"]
    except:
        return False

# ── Bot handlers ──────────────────────────────────────────────────────────────
async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    global bot_instance
    bot_instance = ctx.bot
    user = update.effective_user
    text = update.message.text.strip() if update.message.text else ""
    add_user(user)

    # Obuna tekshirish
    ok, not_subbed = await check_sub(ctx.bot, user.id)
    if not ok:
        keyboard = [[InlineKeyboardButton(f"📢 Obuna bo'lish", url=ch["link"])] for ch in not_subbed]
        keyboard.append([InlineKeyboardButton("🔄 Obuna bo'ldim — Tekshirish", callback_data="check_sub")])
        await update.message.reply_text(
            "⚠️ Botdan foydalanish uchun kanallarga obuna bo'ling!\n\nObuna bo'lgach 🔄 tugmasini bosing.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    is_admin = user.username == ADMIN_USERNAME

    # Admin: serial nomi kutilmoqda
    if is_admin and user.id in waiting_serial:
        ws = waiting_serial[user.id]
        if ws["step"] == "name":
            ws["name"] = text
            ws["step"] = "episodes"
            await update.message.reply_text(
                f"✅ Nom: *{text}*\n\nEndi 1-qismni yuboring (caption = ixtiyoriy):",
                parse_mode="Markdown"
            )
            return

    # Admin buyruqlar
    if is_admin:
        if text.lower() == "kino":
            waiting_movie[user.id] = True
            await update.message.reply_text("📤 Kinoni yuboring (caption = nomi):")
            return
        if text.lower() == "seryal":
            waiting_serial[user.id] = {"name": None, "episodes": [], "step": "name"}
            await update.message.reply_text("📺 Serial nomini yozing:")
            return
        if text.lower() == "tugatish" and user.id in waiting_serial:
            ws = waiting_serial[user.id]
            if ws["episodes"]:
                code = gen_code()
                serials[code] = {
                    "name": ws["name"] or "Nomsiz serial",
                    "episodes": ws["episodes"],
                    "date": datetime.now().strftime("%Y-%m-%d %H:%M")
                }
                del waiting_serial[user.id]
                await update.message.reply_text(
                    f"✅ *{serials[code]['name']}* saqlandi!\n"
                    f"📺 {len(ws['episodes'])} ta qism\n"
                    f"📌 Kod: `{code}`",
                    parse_mode="Markdown"
                )
            else:
                del waiting_serial[user.id]
                await update.message.reply_text("❌ Qism yuklanmadi, bekor qilindi.")
            return

    # Foydalanuvchi: kod
    if text.isdigit() and len(text) == 4:
        stats["total_requests"] += 1
        stats["users"][str(user.id)]["requests"] += 1

        if text in movies:
            movie = movies[text]
            await update.message.reply_video(
                video=movie["file_id"],
                caption=f"🎬 *{movie['name']}*",
                parse_mode="Markdown"
            )
        elif text in serials:
            serial = serials[text]
            await update.message.reply_text(
                f"📺 *{serial['name']}*\n{len(serial['episodes'])} ta qism yuklanmoqda...",
                parse_mode="Markdown"
            )
            for ep in serial["episodes"]:
                await update.message.reply_video(
                    video=ep["file_id"],
                    caption=f"📺 *{serial['name']}* — {ep['ep']}",
                    parse_mode="Markdown"
                )
        else:
            await update.message.reply_text("❌ Bunday kod topilmadi!")
        return

    await update.message.reply_text(
        "🎬 Kino/serial olish uchun 4 xonali kod yuboring.\nMasalan: `2738`",
        parse_mode="Markdown"
    )

async def handle_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    add_user(user)

    if query.data == "check_sub":
        ok, not_subbed = await check_sub(ctx.bot, user.id)
        if ok:
            await query.edit_message_text("✅ Obuna tasdiqlandi! Endi kod yuboring.")
        else:
            keyboard = [[InlineKeyboardButton("📢 Obuna bo'lish", url=ch["link"])] for ch in not_subbed]
            keyboard.append([InlineKeyboardButton("🔄 Tekshirish", callback_data="check_sub")])
            await query.edit_message_text(
                "❌ Hali obuna bo'lmadingiz!\n\nObuna bo'lgach 🔄 tugmasini bosing.",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

async def handle_video(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    global bot_instance
    bot_instance = ctx.bot
    user = update.effective_user
    if user.username != ADMIN_USERNAME:
        return

    video = update.message.video or update.message.document
    if not video:
        return

    # Kino saqlash
    if user.id in waiting_movie:
        name = update.message.caption or "Nomsiz"
        code = gen_code()
        movies[code] = {"file_id": video.file_id, "name": name, "date": datetime.now().strftime("%Y-%m-%d %H:%M")}
        del waiting_movie[user.id]
        await update.message.reply_text(
            f"✅ Kino saqlandi!\n🎬 *{name}*\n📌 Kod: `{code}`",
            parse_mode="Markdown"
        )
        return

    # Serial qism saqlash
    if user.id in waiting_serial and waiting_serial[user.id]["step"] == "episodes":
        ws = waiting_serial[user.id]
        ep_num = len(ws["episodes"]) + 1
        ws["episodes"].append({"file_id": video.file_id, "ep": f"Qism {ep_num}"})
        await update.message.reply_text(
            f"✅ *Qism {ep_num}* saqlandi!\n\nDavom etasizmi? Keyingi qismni yuboring.\n"
            f"Tugatish uchun: `tugatish`",
            parse_mode="Markdown"
        )
        return

# ── Admin panel HTML ──────────────────────────────────────────────────────────
LOGIN_HTML = """
<!DOCTYPE html><html><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Admin Login</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0d0d1a;color:#fff;font-family:'Segoe UI',sans-serif;display:flex;justify-content:center;align-items:center;height:100vh}
.box{background:#16213e;padding:40px 30px;border-radius:20px;width:100%;max-width:360px}
h2{color:#e94560;text-align:center;margin-bottom:25px}
input{width:100%;padding:12px;margin:8px 0;border-radius:10px;border:1px solid #0f3460;background:#0d0d1a;color:#fff;font-size:15px;outline:none}
input:focus{border-color:#e94560}
button{width:100%;padding:13px;margin-top:10px;border-radius:10px;border:none;background:#e94560;color:#fff;font-size:15px;font-weight:600;cursor:pointer}
.err{color:#ff6b6b;text-align:center;margin-top:10px;font-size:14px}
</style></head><body>
<div class="box">
<h2>🤖 Admin Panel</h2>
<input type="password" id="p" placeholder="Parol" onkeydown="if(event.key==='Enter')login()">
<button onclick="login()">Kirish</button>
<div class="err" id="err"></div>
</div>
<script>
function login(){
fetch('/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({password:document.getElementById('p').value})})
.then(r=>r.json()).then(d=>{if(d.ok)location.reload();else document.getElementById('err').innerText="Parol noto'g'ri!"})
}
</script></body></html>
"""

ADMIN_HTML = """
<!DOCTYPE html><html><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Kino Bot Admin</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0d0d1a;color:#fff;font-family:'Segoe UI',sans-serif;padding:20px}
h1{color:#e94560;margin-bottom:20px}h2{color:#a0a0b0;font-size:15px;margin:25px 0 12px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:15px;margin-bottom:20px}
.card{background:#16213e;border-radius:12px;padding:18px;border-left:4px solid #e94560}
.card h3{color:#a0a0b0;font-size:12px;margin-bottom:6px}.card p{font-size:26px;font-weight:700;color:#e94560}
table{width:100%;border-collapse:collapse;background:#16213e;border-radius:12px;overflow:hidden;margin-bottom:20px}
th{background:#0f3460;padding:10px 12px;text-align:left;font-size:12px;color:#a0a0b0}
td{padding:10px 12px;border-bottom:1px solid #0f3460;font-size:13px}tr:last-child td{border-bottom:none}
tr:hover td{background:#1f2d50}
.badge{background:#e94560;color:#fff;padding:2px 8px;border-radius:10px;font-size:11px}
.code{background:#0f3460;color:#4fc3f7;padding:2px 8px;border-radius:6px;font-family:monospace}
.ok{color:#4caf50;font-weight:600}.no{color:#ff6b6b;font-weight:600}
.btn{background:#e94560;border:none;color:#fff;padding:8px 14px;border-radius:8px;cursor:pointer;font-size:13px;margin-right:8px;margin-bottom:10px}
.btn-del{background:#333}
.row{display:flex;gap:8px;margin-bottom:15px;flex-wrap:wrap}
.row input{flex:1;min-width:150px;padding:10px;border-radius:8px;border:1px solid #0f3460;background:#0d0d1a;color:#fff;font-size:14px;outline:none}
.row input:focus{border-color:#e94560}
.empty{text-align:center;padding:30px;color:#a0a0b0}
.logout{float:right;background:transparent;border:1px solid #e94560;color:#e94560;padding:6px 12px;border-radius:8px;cursor:pointer;font-size:13px}
</style>
<script>setTimeout(()=>location.reload(),30000)</script>
</head><body>
<h1>🎬 Kino Bot Admin <button class="logout" onclick="logout()">Chiqish</button></h1>
<button class="btn" onclick="location.reload()">🔄 Yangilash</button>

<div class="cards">
<div class="card"><h3>🎬 Kinolar</h3><p>{{ total_movies }}</p></div>
<div class="card"><h3>📺 Seryallar</h3><p>{{ total_serials }}</p></div>
<div class="card"><h3>👥 Foydalanuvchilar</h3><p>{{ total_users }}</p></div>
<div class="card"><h3>📥 So'rovlar</h3><p>{{ total_requests }}</p></div>
<div class="card"><h3>📢 Kanallar</h3><p>{{ total_channels }}</p></div>
</div>

<h2>📢 Majburiy Obuna Kanallar</h2>
<div class="row">
<input id="ch_id" placeholder="Kanal ID (-1001234567890)">
<input id="ch_link" placeholder="https://t.me/kanal">
<button class="btn" onclick="addChannel()">➕ Qo'shish</button>
</div>
{% if channels %}
<table>
<tr><th>Kanal ID</th><th>Link</th><th>Bot holati</th><th>Obunalar</th><th></th></tr>
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

<h2>🎬 Kinolar</h2>
{% if movies %}
<table>
<tr><th>Kod</th><th>Nomi</th><th>Sana</th><th></th></tr>
{% for code, m in movies %}
<tr><td><span class="code">{{ code }}</span></td><td>{{ m.name }}</td><td>{{ m.date }}</td><td><button class="btn btn-del" onclick="delMovie('{{ code }}')">🗑</button></td></tr>
{% endfor %}
</table>
{% else %}<div class="empty">😴 Hali kino yo'q</div>{% endif %}

<h2>📺 Seryallar</h2>
{% if serials %}
<table>
<tr><th>Kod</th><th>Nomi</th><th>Qismlar</th><th>Sana</th><th></th></tr>
{% for code, s in serials %}
<tr><td><span class="code">{{ code }}</span></td><td>{{ s.name }}</td><td><span class="badge">{{ s.episodes|length }}</span></td><td>{{ s.date }}</td><td><button class="btn btn-del" onclick="delSerial('{{ code }}')">🗑</button></td></tr>
{% endfor %}
</table>
{% else %}<div class="empty">😴 Hali serial yo'q</div>{% endif %}

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
function addChannel(){
const id=document.getElementById('ch_id').value.trim();
const link=document.getElementById('ch_link').value.trim();
if(!id||!link)return alert('ID va linkni kiriting!');
fetch('/add_channel',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id,link})})
.then(r=>r.json()).then(d=>{if(d.ok)location.reload();else alert('Xato!')})
}
function delChannel(id){
if(!confirm('Ochirasizmi?'))return;
fetch('/del_channel',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id})})
.then(r=>r.json()).then(d=>{if(d.ok)location.reload()})
}
function delMovie(code){
if(!confirm('Kinoni ochirasizmi?'))return;
fetch('/del_movie',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({code})})
.then(r=>r.json()).then(d=>{if(d.ok)location.reload()})
}
function delSerial(code){
if(!confirm('Serialni ochirasizmi?'))return;
fetch('/del_serial',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({code})})
.then(r=>r.json()).then(d=>{if(d.ok)location.reload()})
}
function logout(){fetch('/logout').then(()=>location.reload())}
</script>
</body></html>
"""

# ── Flask routes ──────────────────────────────────────────────────────────────
flask_app = Flask(__name__)
flask_app.secret_key = "rasuto_secret_2026"

@flask_app.route("/")
def index():
    if not session.get("admin"):
        return render_template_string(LOGIN_HTML)
    return render_template_string(
        ADMIN_HTML,
        total_movies=len(movies),
        total_serials=len(serials),
        total_users=len(stats["users"]),
        total_requests=stats["total_requests"],
        total_channels=len(channels),
        channels=list(channels.items()),
        movies=list(movies.items()),
        serials=list(serials.items()),
        users=[(i+1, u) for i, u in enumerate(stats["users"].values())]
    )

@flask_app.route("/login", methods=["POST"])
def login():
    if request.json.get("password") == WEB_PASSWORD:
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
    channels[ch_id] = {"link": data.get("link"), "is_admin": False, "subscribers": 0}
    if bot_instance and bot_loop:
        async def check():
            channels[ch_id]["is_admin"] = await check_admin(bot_instance, ch_id)
        asyncio.run_coroutine_threadsafe(check(), bot_loop)
    return {"ok": True}

@flask_app.route("/del_channel", methods=["POST"])
def del_channel():
    if not session.get("admin"):
        return {"ok": False}
    channels.pop(request.json.get("id"), None)
    return {"ok": True}

@flask_app.route("/del_movie", methods=["POST"])
def del_movie():
    if not session.get("admin"):
        return {"ok": False}
    movies.pop(request.json.get("code"), None)
    return {"ok": True}

@flask_app.route("/del_serial", methods=["POST"])
def del_serial():
    if not session.get("admin"):
        return {"ok": False}
    serials.pop(request.json.get("code"), None)
    return {"ok": True}

@flask_app.route("/health")
def health():
    return "OK", 200

# ── Bot thread ────────────────────────────────────────────────────────────────
def run_bot():
    global bot_loop, bot_instance
    async def main():
        global bot_instance
        bot_app = ApplicationBuilder().token(TOKEN).build()
        bot_instance = bot_app.bot
        bot_app.add_handler(MessageHandler(filters.VIDEO | filters.Document.VIDEO, handle_video))
        bot_app.add_handler(MessageHandler(filters.TEXT, handle_message))
        from telegram.ext import CallbackQueryHandler
        bot_app.add_handler(CallbackQueryHandler(handle_callback))
        print("Bot ishlamoqda... 🎬📺")
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
