import os
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

TOKEN = os.environ.get("tele_api")

# ── Fun content ───────────────────────────────────────────────────────────────
JOKES = [
    "Dasturchi nima yeydi? — Spam! 🍖",
    "Bug nima? — Feature ning noto'g'ri ismi! 😄",
    "Nega dasturchilar ko'zoynak takadi? — C# ko'rolmaydi! 🤓",
    "Git push qildim, hammasi yondi. Normal kun. 🔥",
    "99 ta bug fix qildim, 127 tasi chiqdi. 😭",
    "Kompyuter sekin ishlayapti. Restart? — Yo'q, umid qilaman. 🙏",
    "Hello World yozib dasturchi bo'laman deb o'ylardim... 😂",
]

FACTS = [
    "🌍 Dunyoda 700+ dasturlash tili bor!",
    "🐛 'Bug' so'zi 1947 yilda real chivindan kelib chiqqan!",
    "💻 Birinchi kompyuter 1945 yilda yaratilgan va 27 ton og'ir edi!",
    "🐍 Python 1991 yilda yaratilgan — 30 yildan oshdi!",
    "📱 Smartfonlar NASAning Apollo 11 kompyuteridan million marta kuchliroq!",
    "🌐 Internet 1983 yilda rasman ishga tushgan!",
    "⌨️ QWERTY klaviatura 1873 yilda yaratilgan!",
]

MOTIVATIONS = [
    "💪 Har bir expert bir vaqtlar beginner bo'lgan!",
    "🚀 Katta safar ham bitta qadamdan boshlanadi!",
    "🔥 Muvaffaqiyat — sabr + mehnat + vaqt!",
    "⭐ Bugun o'rgangan narsa ertangi qurolting!",
    "🎯 Kod yozish — muammo yechish san'ati!",
    "🌱 Har kuni 1% yaxshilansang, 1 yilda 37x kuchliroq bo'lasan!",
]

RIDDLES = [
    ("Boshida 0, oxirida 1, o'rtasida hamma narsa — bu nima? 🤔", "Ikkilik sistema (Binary)!"),
    ("Har kuni ishlaydi, lekin hech qachon charchamaydi — bu nima? 🤔", "Server!"),
    ("Ko'rinmaydi, lekin hamma joyda bor — bu nima? 🤔", "Internet!"),
    ("Yozasan lekin o'qimaysan, o'qiysan lekin yozmaysan — bu nima? 🤔", "Parol!"),
]

user_riddles = {}

# ── Handlers ──────────────────────────────────────────────────────────────────
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("😂 Hazil", callback_data="joke"),
         InlineKeyboardButton("🧠 Fakt", callback_data="fact")],
        [InlineKeyboardButton("💪 Motivatsiya", callback_data="motivation"),
         InlineKeyboardButton("🎯 Topishmoq", callback_data="riddle")],
        [InlineKeyboardButton("🎲 Tasodifiy raqam", callback_data="random"),
         InlineKeyboardButton("🪙 Tanga tashlash", callback_data="coin")],
    ]
    markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"👋 Salom, {update.effective_user.first_name}!\n\n"
        "Men ko'ngilochar botman! Nima qilamiz? 👇",
        reply_markup=markup
    )

async def button(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id

    keyboard = [[InlineKeyboardButton("🔙 Orqaga", callback_data="back")]]
    markup = InlineKeyboardMarkup(keyboard)

    if query.data == "joke":
        text = f"😂 *Hazil:*\n\n{random.choice(JOKES)}"
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=markup)

    elif query.data == "fact":
        text = f"🧠 *Qiziqarli fakt:*\n\n{random.choice(FACTS)}"
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=markup)

    elif query.data == "motivation":
        text = f"💪 *Motivatsiya:*\n\n{random.choice(MOTIVATIONS)}"
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=markup)

    elif query.data == "riddle":
        riddle, answer = random.choice(RIDDLES)
        user_riddles[uid] = answer
        keyboard = [
            [InlineKeyboardButton("💡 Javobni ko'rish", callback_data="answer")],
            [InlineKeyboardButton("🔙 Orqaga", callback_data="back")]
        ]
        await query.edit_message_text(
            f"🎯 *Topishmoq:*\n\n{riddle}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif query.data == "answer":
        answer = user_riddles.get(uid, "Avval topishmoq tanlang!")
        await query.edit_message_text(
            f"💡 *Javob:*\n\n{answer}",
            parse_mode="Markdown",
            reply_markup=markup
        )

    elif query.data == "random":
        num = random.randint(1, 1000)
        text = f"🎲 *Tasodifiy raqam:*\n\n`{num}`"
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=markup)

    elif query.data == "coin":
        result = random.choice(["👑 Bosh (Heads)", "🦅 Dump (Tails)"])
        text = f"🪙 *Tanga tashlandi:*\n\n{result}!"
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=markup)

    elif query.data == "back":
        keyboard = [
            [InlineKeyboardButton("😂 Hazil", callback_data="joke"),
             InlineKeyboardButton("🧠 Fakt", callback_data="fact")],
            [InlineKeyboardButton("💪 Motivatsiya", callback_data="motivation"),
             InlineKeyboardButton("🎯 Topishmoq", callback_data="riddle")],
            [InlineKeyboardButton("🎲 Tasodifiy raqam", callback_data="random"),
             InlineKeyboardButton("🪙 Tanga tashlash", callback_data="coin")],
        ]
        await query.edit_message_text(
            "Nima qilamiz? 👇",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def echo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    if "salom" in text or "hello" in text:
        await update.message.reply_text(f"👋 Salom! /start buyrug'ini bosing!")
    else:
        await update.message.reply_text("😅 Tushunmadim. /start bosing!")

# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import asyncio
    asyncio.set_event_loop(asyncio.new_event_loop())
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))
    print("Bot ishlamoqda... 🚀")
    app.run_polling(drop_pending_updates=True)
