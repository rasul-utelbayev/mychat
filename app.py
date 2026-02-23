import os
import random
import threading
import asyncio
from datetime import datetime, timedelta
from flask import Flask, render_template_string, request, session
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, MessageHandler, CallbackQueryHandler, filters, ContextTypes

TOKEN = os.environ.get("tele_api")
ADMIN_USERNAME = "Rasul_utelbayev"
WEB_PASSWORD = "rAsuto2008"

# Ijtimoiy tarmoq linklari (keyinroq o'zgartirasiz)
SOCIAL_LINKS = {
    "telegram": "https://t.me/rasuto",
    "tiktok": "https://tiktok.com/@rasuto",
    "instagram": "https://instagram.com/rasuto",
    "youtube": "https://youtube.com/@rasuto"
}

# ── Ma'lumotlar ───────────────────────────────────────────────────────────────
movies = {}
serials = {}
# channel: {link, is_admin, subscribers, limit_type, limit_value}
# limit_type: "none" | "time" | "subscribers"
# limit_value: sana (time uchun) yoki son (subscribers uchun)
channels = {}
stats = {"users": {}, "total_requests": 0, "started": datetime.now().strftime("%Y-%m-%d %H:%M")}
waiting_movie = {}
waiting_serial = {}
waiting_broadcast = {}
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

def is_channel_active(ch):
    lt = ch.get("limit_type", "none")
    if lt == "none":
        return True
    elif lt == "time":
        end = ch.get("limit_value")
        if end:
            return datetime.now() < datetime.fromisoformat(end)
        return True
    elif lt == "subscribers":
        needed = int(ch.get("limit_value", 0))
        return ch.get("subscribers", 0) < needed
    return True

async def check_sub(bot, user_id):
    if not channels:
        return True, []
    not_subbed = []
    for ch_id, ch in channels.items():
        if not is_channel_active(ch):
            continue
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
async def handle_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    global bot_instance
    bot_instance = ctx.bot
    user = update.effective_user
    add_user(user)
    await update.message.reply_text(
        f"Assalomu alaykum, *{user.first_name}*! 👋\n"
        f"🎬 *RasuFilmBot* ga xush kelibsiz!\n\n"
        f"Bu bot orqali siz:\n"
        f"🎞 Kino kod orqali film topishingiz\n"
        f"📺 Serial kod orqali serial ko'rishingiz\n"
        f"📌 Kodlarni ijtimoiy tarmoqlarimizdan topishingiz mumkin\n\n"
        f"▶️ Boshlash uchun kino kodini yuboring!",
        parse_mode="Markdown"
    )

async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    global bot_instance
    bot_instance = ctx.bot
    user = update.effective_user
    text = update.message.text.strip() if update.message.text else ""
    add_user(user)

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

    if is_admin and user.id in waiting_serial:
        ws = waiting_serial[user.id]
        if ws["step"] == "name":
            ws["name"] = text
            ws["step"] = "episodes"
            await update.message.reply_text(f"✅ Nom: *{text}*\n\nEndi 1-qismni yuboring:", parse_mode="Markdown")
            return

    if is_admin:
        if text.lower() == "kino":
            waiting_movie[user.id] = True
            await update.message.reply_text("📤 Kinoni yuboring (caption = nomi):")
            return
        if text.lower() == "seryal":
            waiting_serial[user.id] = {"name": None, "episodes": [], "step": "name"}
            await update.message.reply_text("📺 Serial nomini yozing:")
            return
        if text.lower() == "yoz":
            waiting_broadcast[user.id] = True
            await update.message.reply_text("📣 Xabar matnini yuboring — hammaga yuboriladi:")
            return
        if user.id in waiting_broadcast:
            del waiting_broadcast[user.id]
            sent = 0
            failed = 0
            for uid in stats["users"]:
                try:
                    await ctx.bot.send_message(chat_id=int(uid), text=text)
                    sent += 1
                except:
                    failed += 1
            await update.message.reply_text(f"✅ Xabar yuborildi!\n\n📤 Yuborildi: {sent}\n❌ Xato: {failed}")
            return
        if text.lower() == "tugatish" and user.id in waiting_serial:
            ws = waiting_serial[user.id]
            if ws["episodes"]:
                code = gen_code()
                serials[code] = {"name": ws["name"] or "Nomsiz", "episodes": ws["episodes"], "date": datetime.now().strftime("%Y-%m-%d %H:%M")}
                del waiting_serial[user.id]
                await update.message.reply_text(f"✅ *{serials[code]['name']}* saqlandi!\n📺 {len(ws['episodes'])} ta qism\n📌 Kod: `{code}`", parse_mode="Markdown")
            else:
                del waiting_serial[user.id]
                await update.message.reply_text("❌ Bekor qilindi.")
            return

    if text.isdigit() and len(text) == 4:
        stats["total_requests"] += 1
        stats["users"][str(user.id)]["requests"] += 1
        if text in movies:
            movie = movies[text]
            await update.message.reply_video(video=movie["file_id"], caption=f"🎬 *{movie['name']}*", parse_mode="Markdown")
        elif text in serials:
            serial = serials[text]
            await update.message.reply_text(f"📺 *{serial['name']}*\n{len(serial['episodes'])} ta qism yuklanmoqda...", parse_mode="Markdown")
            for ep in serial["episodes"]:
                await update.message.reply_video(video=ep["file_id"], caption=f"📺 *{serial['name']}* — {ep['ep']}", parse_mode="Markdown")
        else:
            await update.message.reply_text("❌ Bunday kod topilmadi!")
        return

    # Yo'riqnoma xabari
    tg = SOCIAL_LINKS["telegram"]
    tt = SOCIAL_LINKS["tiktok"]
    ig = SOCIAL_LINKS["instagram"]
    yt = SOCIAL_LINKS["youtube"]
    await update.message.reply_text(
        "🎬 *Kino/serial olish uchun 4 xonali kod yuboring.*\n\n"
        "📌 Kodlarni qayerdan topasiz?\n\n"
        f"📱 [Telegram]({tg})\n"
        f"🎵 [TikTok]({tt})\n"
        f"📸 [Instagram]({ig})\n"
        f"▶️ [YouTube]({yt})\n\n"
        "Profilimizga kiring va kino kodlarini toping! 🍿",
        parse_mode="Markdown",
        disable_web_page_preview=True
    )

async def handle_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    add_user(user)

    if query.data == "check_sub":
        ok, not_subbed = await check_sub(ctx.bot, user.id)
        if ok:
            await query.edit_message_text("✅ Obuna tasdiqlandi! Endi kino kodini yuboring.")
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
    if user.id in waiting_movie:
        name = update.message.caption or "Nomsiz"
        code = gen_code()
        movies[code] = {"file_id": video.file_id, "name": name, "date": datetime.now().strftime("%Y-%m-%d %H:%M")}
        del waiting_movie[user.id]
        await update.message.reply_text(f"✅ Kino saqlandi!\n🎬 *{name}*\n📌 Kod: `{code}`", parse_mode="Markdown")
        return
    if user.id in waiting_serial and waiting_serial[user.id]["step"] == "episodes":
        ws = waiting_serial[user.id]
        ep_num = len(ws["episodes"]) + 1
        ws["episodes"].append({"file_id": video.file_id, "ep": f"Qism {ep_num}"})
        await update.message.reply_text(
            f"✅ *Qism {ep_num}* saqlandi!\n\nDavom etasizmi? Keyingi qismni yuboring.\nTugatish: `tugatish`",
            parse_mode="Markdown"
        )

# ── Admin panel ───────────────────────────────────────────────────────────────
LOGIN_HTML = """<!DOCTYPE html><html><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Admin</title>
<style>*{box-sizing:border-box;margin:0;padding:0}body{background:#0d0d1a;color:#fff;font-family:'Segoe UI',sans-serif;display:flex;justify-content:center;align-items:center;height:100vh}.box{background:#16213e;padding:40px 30px;border-radius:20px;width:100%;max-width:360px}h2{color:#e94560;text-align:center;margin-bottom:25px}input{width:100%;padding:12px;margin:8px 0;border-radius:10px;border:1px solid #0f3460;background:#0d0d1a;color:#fff;font-size:15px;outline:none}input:focus{border-color:#e94560}button{width:100%;padding:13px;margin-top:10px;border-radius:10px;border:none;background:#e94560;color:#fff;font-size:15px;font-weight:600;cursor:pointer}.err{color:#ff6b6b;text-align:center;margin-top:10px;font-size:14px}</style></head><body>
<div class="box"><h2>🤖 Admin Panel</h2>
<input type="password" id="p" placeholder="Parol" onkeydown="if(event.key==='Enter')login()">
<button onclick="login()">Kirish</button><div class="err" id="err"></div></div>
<script>function login(){fetch('/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({password:document.getElementById('p').value})}).then(r=>r.json()).then(d=>{if(d.ok)location.reload();else document.getElementById('err').innerText="Parol noto'g'ri!"})}</script>
</body></html>"""

ADMIN_HTML = """<!DOCTYPE html><html><head>
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
.ok{color:#4caf50;font-weight:600}.no{color:#ff6b6b;font-weight:600}.warn{color:#ff9800;font-weight:600}
.btn{background:#e94560;border:none;color:#fff;padding:8px 14px;border-radius:8px;cursor:pointer;font-size:13px;margin-right:6px;margin-bottom:8px}
.btn-del{background:#333}.btn-green{background:#2e7d32}
.row{display:flex;gap:8px;margin-bottom:10px;flex-wrap:wrap}
.row input,.row select{flex:1;min-width:120px;padding:10px;border-radius:8px;border:1px solid #0f3460;background:#0d0d1a;color:#fff;font-size:13px;outline:none}
.row input:focus,.row select:focus{border-color:#e94560}
.empty{text-align:center;padding:30px;color:#a0a0b0}
.logout{float:right;background:transparent;border:1px solid #e94560;color:#e94560;padding:6px 12px;border-radius:8px;cursor:pointer;font-size:13px}
.section{background:#16213e;border-radius:12px;padding:15px;margin-bottom:15px}
input[type=text],input[type=datetime-local],input[type=number]{background:#0d0d1a;border:1px solid #0f3460;color:#fff;border-radius:8px;padding:8px;font-size:13px;outline:none}
input:focus{border-color:#e94560}
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

<!-- Ijtimoiy tarmoqlar -->
<h2>📱 Ijtimoiy Tarmoq Linklari</h2>
<div class="section">
<div class="row"><span style="color:#a0a0b0;min-width:90px;line-height:36px">📱 Telegram</span><input type="text" id="tg_link" value="{{ social.telegram }}"><button class="btn btn-green" onclick="saveLink('telegram','tg_link')">Saqlash</button></div>
<div class="row"><span style="color:#a0a0b0;min-width:90px;line-height:36px">🎵 TikTok</span><input type="text" id="tt_link" value="{{ social.tiktok }}"><button class="btn btn-green" onclick="saveLink('tiktok','tt_link')">Saqlash</button></div>
<div class="row"><span style="color:#a0a0b0;min-width:90px;line-height:36px">📸 Instagram</span><input type="text" id="ig_link" value="{{ social.instagram }}"><button class="btn btn-green" onclick="saveLink('instagram','ig_link')">Saqlash</button></div>
<div class="row"><span style="color:#a0a0b0;min-width:90px;line-height:36px">▶️ YouTube</span><input type="text" id="yt_link" value="{{ social.youtube }}"><button class="btn btn-green" onclick="saveLink('youtube','yt_link')">Saqlash</button></div>
</div>

<!-- Kanallar -->
<h2>📢 Majburiy Obuna Kanallar</h2>
<div class="section">
<div class="row">
<input type="text" id="ch_id" placeholder="Kanal ID (-1001234567890)">
<input type="text" id="ch_link" placeholder="https://t.me/kanal">
</div>
<div class="row">
<select id="ch_limit" onchange="toggleLimit()">
<option value="none">♾️ Limitsiz</option>
<option value="time">⏰ Vaqtli</option>
<option value="subscribers">👥 Obuna sonli</option>
</select>
<input type="datetime-local" id="ch_time" style="display:none">
<input type="number" id="ch_subs" placeholder="Necha obunagacha" style="display:none">
<button class="btn" onclick="addChannel()">➕ Qo'shish</button>
</div>
</div>

{% if channels %}
<table>
<tr><th>Kanal ID</th><th>Link</th><th>Bot</th><th>Limit</th><th>Holat</th><th></th></tr>
{% for ch_id, ch in channels %}
<tr>
<td><span class="code">{{ ch_id }}</span></td>
<td><a href="{{ ch.link }}" style="color:#4fc3f7" target="_blank">{{ ch.link }}</a></td>
<td>{% if ch.is_admin %}<span class="ok">✅</span>{% else %}<span class="no">❌</span>{% endif %}</td>
<td>
{% if ch.limit_type == 'none' %}♾️ Limitsiz
{% elif ch.limit_type == 'time' %}⏰ {{ ch.limit_value }}
{% elif ch.limit_type == 'subscribers' %}👥 {{ ch.limit_value }} ta
{% endif %}
</td>
<td>{% if ch.active %}<span class="ok">✅ Faol</span>{% else %}<span class="warn">⏸ Tugagan</span>{% endif %}</td>
<td><button class="btn btn-del" onclick="delChannel('{{ ch_id }}')">🗑</button></td>
</tr>
{% endfor %}
</table>
{% else %}<div class="empty">😴 Kanal qo'shilmagan</div>{% endif %}

<!-- Kinolar -->
<h2>🎬 Kinolar</h2>
{% if movies %}
<table>
<tr><th>Kod</th><th>Nomi</th><th>Sana</th><th></th></tr>
{% for code, m in movies %}
<tr>
<td><span class="code">{{ code }}</span></td>
<td><input type="text" value="{{ m.name }}" id="mv_{{ code }}" style="background:transparent;border:none;color:#fff;width:150px"></td>
<td>{{ m.date }}</td>
<td>
<button class="btn btn-green" onclick="renameMovie('{{ code }}')">✏️</button>
<button class="btn btn-del" onclick="delMovie('{{ code }}')">🗑</button>
</td>
</tr>
{% endfor %}
</table>
{% else %}<div class="empty">😴 Hali kino yo'q</div>{% endif %}

<!-- Seryallar -->
<h2>📺 Seryallar</h2>
{% if serials %}
<table>
<tr><th>Kod</th><th>Nomi</th><th>Qismlar</th><th>Sana</th><th></th></tr>
{% for code, s in serials %}
<tr>
<td><span class="code">{{ code }}</span></td>
<td><input type="text" value="{{ s.name }}" id="sr_{{ code }}" style="background:transparent;border:none;color:#fff;width:140px"></td>
<td><span class="badge">{{ s.episodes|length }}</span></td>
<td>{{ s.date }}</td>
<td>
<button class="btn btn-green" onclick="renameSerial('{{ code }}')">✏️</button>
<button class="btn btn-del" onclick="delSerial('{{ code }}')">🗑</button>
</td>
</tr>
{% endfor %}
</table>
{% else %}<div class="empty">😴 Hali serial yo'q</div>{% endif %}

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
function toggleLimit(){
const v=document.getElementById('ch_limit').value;
document.getElementById('ch_time').style.display=v==='time'?'block':'none';
document.getElementById('ch_subs').style.display=v==='subscribers'?'block':'none';
}
function addChannel(){
const id=document.getElementById('ch_id').value.trim();
const link=document.getElementById('ch_link').value.trim();
const lt=document.getElementById('ch_limit').value;
let lv='';
if(lt==='time')lv=document.getElementById('ch_time').value;
if(lt==='subscribers')lv=document.getElementById('ch_subs').value;
if(!id||!link)return alert('ID va linkni kiriting!');
fetch('/add_channel',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id,link,limit_type:lt,limit_value:lv})})
.then(r=>r.json()).then(d=>{if(d.ok)location.reload();else alert('Xato!')})
}
function delChannel(id){if(!confirm('Ochirasizmi?'))return;fetch('/del_channel',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id})}).then(r=>r.json()).then(d=>{if(d.ok)location.reload()})}
function delMovie(code){if(!confirm('Kinoni ochirasizmi?'))return;fetch('/del_movie',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({code})}).then(r=>r.json()).then(d=>{if(d.ok)location.reload()})}
function delSerial(code){if(!confirm('Serialni ochirasizmi?'))return;fetch('/del_serial',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({code})}).then(r=>r.json()).then(d=>{if(d.ok)location.reload()})}
function renameMovie(code){const name=document.getElementById('mv_'+code).value;fetch('/rename_movie',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({code,name})}).then(r=>r.json()).then(d=>{if(d.ok)alert('✅ Saqlandi!')})}
function renameSerial(code){const name=document.getElementById('sr_'+code).value;fetch('/rename_serial',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({code,name})}).then(r=>r.json()).then(d=>{if(d.ok)alert('✅ Saqlandi!')})}
function saveLink(platform,inputId){const url=document.getElementById(inputId).value;fetch('/save_link',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({platform,url})}).then(r=>r.json()).then(d=>{if(d.ok)alert('✅ Saqlandi!')})}
function logout(){fetch('/logout').then(()=>location.reload())}
</script>
</body></html>"""

# ── Flask ─────────────────────────────────────────────────────────────────────
flask_app = Flask(__name__)
flask_app.secret_key = "rasuto_secret_2026"

@flask_app.route("/")
def index():
    if not session.get("admin"):
        return render_template_string(LOGIN_HTML)
    ch_list = []
    for ch_id, ch in channels.items():
        ch_copy = dict(ch)
        ch_copy["active"] = is_channel_active(ch)
        ch_list.append((ch_id, ch_copy))
    return render_template_string(
        ADMIN_HTML,
        total_movies=len(movies), total_serials=len(serials),
        total_users=len(stats["users"]), total_requests=stats["total_requests"],
        total_channels=len(channels), channels=ch_list,
        movies=list(movies.items()), serials=list(serials.items()),
        users=[(i+1, u) for i, u in enumerate(stats["users"].values())],
        social=SOCIAL_LINKS
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
    if not session.get("admin"): return {"ok": False}
    data = request.json
    ch_id = data.get("id")
    channels[ch_id] = {
        "link": data.get("link"),
        "is_admin": False,
        "subscribers": 0,
        "limit_type": data.get("limit_type", "none"),
        "limit_value": data.get("limit_value", "")
    }
    if bot_instance and bot_loop:
        async def check():
            channels[ch_id]["is_admin"] = await check_admin(bot_instance, ch_id)
        asyncio.run_coroutine_threadsafe(check(), bot_loop)
    return {"ok": True}

@flask_app.route("/del_channel", methods=["POST"])
def del_channel():
    if not session.get("admin"): return {"ok": False}
    channels.pop(request.json.get("id"), None)
    return {"ok": True}

@flask_app.route("/del_movie", methods=["POST"])
def del_movie():
    if not session.get("admin"): return {"ok": False}
    movies.pop(request.json.get("code"), None)
    return {"ok": True}

@flask_app.route("/del_serial", methods=["POST"])
def del_serial():
    if not session.get("admin"): return {"ok": False}
    serials.pop(request.json.get("code"), None)
    return {"ok": True}

@flask_app.route("/rename_movie", methods=["POST"])
def rename_movie():
    if not session.get("admin"): return {"ok": False}
    data = request.json
    if data["code"] in movies:
        movies[data["code"]]["name"] = data["name"]
    return {"ok": True}

@flask_app.route("/rename_serial", methods=["POST"])
def rename_serial():
    if not session.get("admin"): return {"ok": False}
    data = request.json
    if data["code"] in serials:
        serials[data["code"]]["name"] = data["name"]
    return {"ok": True}

@flask_app.route("/save_link", methods=["POST"])
def save_link():
    if not session.get("admin"): return {"ok": False}
    data = request.json
    if data["platform"] in SOCIAL_LINKS:
        SOCIAL_LINKS[data["platform"]] = data["url"]
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
        from telegram.ext import CommandHandler
        bot_app.add_handler(CommandHandler("start", handle_start))
        bot_app.add_handler(MessageHandler(filters.VIDEO | filters.Document.VIDEO, handle_video))
        bot_app.add_handler(MessageHandler(filters.TEXT, handle_message))
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
