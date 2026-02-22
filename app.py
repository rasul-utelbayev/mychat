from flask import Flask, request, jsonify, render_template_string, session
import os, base64, json, hashlib
from groq import Groq

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
app = Flask(__name__)
app.secret_key = "termux_ai_secret_2024"

USERS_FILE = os.path.expanduser("~/users.json")
CHATS_DIR = os.path.expanduser("~/chats")
os.makedirs(CHATS_DIR, exist_ok=True)

HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>AI Chat</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { background: #1a1a2e; color: #fff; font-family: Arial; }
        #chat { height: calc(100vh - 120px); overflow-y: auto; padding: 10px; }
        .user { background: #16213e; padding: 10px; margin: 5px; border-radius: 10px; text-align: right; }
        .ai { background: #0f3460; padding: 10px; margin: 5px; border-radius: 10px; }
        .user img { max-width: 200px; border-radius: 8px; display: block; margin-left: auto; }
        #input-area { position: fixed; bottom: 0; width: 100%; background: #1a1a2e; padding: 10px; display: flex; flex-wrap: wrap; gap: 5px; }
        #msg { flex: 1; min-width: 150px; padding: 10px; border-radius: 10px; border: none; background: #16213e; color: #fff; font-size: 16px; }
        button { padding: 10px; background: #e94560; border: none; border-radius: 10px; color: #fff; font-size: 14px; cursor: pointer; }
        #icons { display: flex; gap: 5px; }
        #status { color: #aaa; font-size: 12px; padding: 2px 10px; width: 100%; }
    </style>
</head>
<body>
    <div id="chat"></div>
    <div id="input-area">
        <input id="msg" type="text" placeholder="Xabar yozing...">
        <div id="icons">
            <button onclick="document.getElementById('img-input').click()">🖼</button>
            <button onclick="recordAudio()">🎤</button>
            <button onclick="send()">➤</button>
        </div>
        <input id="img-input" type="file" accept="image/*" style="display:none" onchange="sendImage(this)">
        <div id="status"></div>
    </div>
    <script>
        let recording = false;

        function addMsg(text, type, imgSrc) {
            const chat = document.getElementById('chat');
            const div = document.createElement('div');
            div.className = type;
            if (imgSrc) div.innerHTML = `<img src="${imgSrc}"><br>${text}`;
            else div.textContent = text;
            chat.appendChild(div);
            chat.scrollTop = 999999;
        }

        function status(msg) {
            document.getElementById('status').textContent = msg;
        }

        async function send() {
            const msg = document.getElementById('msg').value.trim();
            if (!msg) return;
            document.getElementById('msg').value = '';
            addMsg(msg, 'user');
            status('AI javob yozmoqda...');
            const r = await fetch('/chat', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({msg})});
            const d = await r.json();
            addMsg(d.reply, 'ai');
            status('');
        }

        async function sendImage(input) {
            const file = input.files[0];
            if (!file) return;
            const reader = new FileReader();
            reader.onload = async function(e) {
                const base64 = e.target.result;
                addMsg('Rasm yuborildi', 'user', base64);
                status('Rasm tahlil qilinmoqda...');
                const r = await fetch('/image', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({image: base64})});
                const d = await r.json();
                addMsg(d.reply, 'ai');
                status('');
            };
            reader.readAsDataURL(file);
        }

        async function recordAudio() {
            if (!recording) {
                recording = true;
                status('Yozilmoqda... tugash uchun qayta bosing 🔴');
                await fetch('/record_start');
            } else {
                recording = false;
                status('Ovoz tahlil qilinmoqda...');
                await fetch('/record_stop');
                const r = await fetch('/transcribe');
                const d = await r.json();
                if (d.text) {
                    document.getElementById('msg').value = d.text;
                    status('✅ ' + d.text);
                }
            }
        }

        document.getElementById('msg').addEventListener('keypress', e => { if(e.key === 'Enter') send(); });
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML)

@app.route('/chat', methods=['POST'])
def chat():
    msg = request.json['msg']
    history.append({"role": "user", "content": msg})
    r = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=history
    )
    reply = r.choices[0].message.content
    history.append({"role": "assistant", "content": reply})
    return jsonify({"reply": reply})

@app.route('/image', methods=['POST'])
def image():
    img_data = request.json['image']
    base64_data = img_data.split(',')[1]
    r = client.chat.completions.create(
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        messages=[{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_data}"}},
            {"type": "text", "text": "Bu rasmda nima bor? O'zbek tilida ayt."}
        ]}]
    )
    return jsonify({"reply": r.choices[0].message.content})

@app.route('/record_start')
def record_start():
    os.system("termux-microphone-record -f /data/data/com.termux/files/home/ovoz.mp3 &")
    return jsonify({"ok": True})

@app.route('/record_stop')
def record_stop():
    os.system("termux-microphone-record -q")
    return jsonify({"ok": True})

@app.route('/transcribe')
def transcribe():
    try:
        with open(os.path.expanduser("~/ovoz.mp3"), "rb") as f:
            result = client.audio.transcriptions.create(
                file=f, model="whisper-large-v3", language="uz"
            )
        return jsonify({"text": result.text})
    except:
        return jsonify({"text": ""})

app.run(host='0.0.0.0', port=5000)
