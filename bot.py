import os
import json
import random
import string
from http.server import BaseHTTPRequestHandler, HTTPServer
import urllib.request
import urllib.parse
import threading

BOT_TOKEN = "8794573324:AAGpHeonpM12PJGt7FGVhs33-YfPJzOvn6k"
ADMIN_ID = 8992713726
DB_FILE = "keys.json"

# === БАЗА КЛЮЧЕЙ ===
def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            return json.load(f)
    return {}

def save_db(db):
    with open(DB_FILE, "w") as f:
        json.dump(db, f, indent=2)

def gen_key():
    part = lambda: "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"QWECKT-{part()}-{part()}"

# === ОТПРАВКА В TELEGRAM ===
def send_message(chat_id, text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": chat_id, "text": text}).encode()
    try:
        urllib.request.urlopen(url, data=data, timeout=10)
    except Exception as e:
        print("send error:", e)

def get_updates(offset=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
    if offset:
        url += f"?offset={offset}"
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        print("updates error:", e)
        return {"ok": False}

# === ЛОГИКА БОТА ===
def handle_command(chat_id, text):
    db = load_db()

    if chat_id != ADMIN_ID:
        if text.startswith("/start"):
            send_message(chat_id, "Привет! Ключи выдаёт только администратор.\nОбратись к нему для получения доступа.")
        elif text.startswith("/getkey"):
            send_message(chat_id, "Ключи выдаёт только администратор.")
        return

    if text.startswith("/start"):
        send_message(chat_id, "Админ-панель qweckt visual:\n/newkey — создать ключ\n/listkeys — список ключей\n/delkey КЛЮЧ — удалить ключ")

    elif text.startswith("/newkey"):
        key = gen_key()
        db[key] = {"used": False, "device": None}
        save_db(db)
        send_message(chat_id, f"Новый ключ:\n{key}")

    elif text.startswith("/listkeys"):
        if not db:
            send_message(chat_id, "Список пуст.")
            return
        lines = []
        for k, v in db.items():
            status = "❌ занят" if v.get("used") else "✅ свободен"
            lines.append(f"{k} — {status}")
        send_message(chat_id, "\n".join(lines))

    elif text.startswith("/delkey"):
        parts = text.split()
        if len(parts) < 2:
            send_message(chat_id, "Использование: /delkey QWECKT-XXXX-XXXX")
            return
        key = parts[1].strip().upper()
        if key in db:
            del db[key]
            save_db(db)
            send_message(chat_id, f"Ключ удалён: {key}")
        else:
            send_message(chat_id, "Такого ключа нет.")

def poll_bot():
    print("Bot polling started")
    offset = None
    while True:
        data = get_updates(offset)
        if data.get("ok"):
            for upd in data["result"]:
                offset = upd["update_id"] + 1
                msg = upd.get("message")
                if not msg:
                    continue
                chat_id = msg["chat"]["id"]
                text = msg.get("text", "")
                if text:
                    try:
                        handle_command(chat_id, text)
                    except Exception as e:
                        print("handler error:", e)

# === HTTP СЕРВЕР (API ДЛЯ ПРИЛОЖЕНИЯ) ===
class Handler(BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_GET(self):
        if self.path.startswith("/check"):
            # /check?key=QWECKT-XXXX-XXXX&device=abc123
            q = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(q)
            key = params.get("key", [""])[0].strip().upper()
            device = params.get("device", [""])[0].strip()

            db = load_db()
            result = {"ok": False, "reason": "invalid"}

            if key in db:
                entry = db[key]
                if not entry.get("used"):
                    entry["used"] = True
                    entry["device"] = device
                    save_db(db)
                    result = {"ok": True}
                elif entry.get("device") == device:
                    result = {"ok": True, "note": "same_device"}
                else:
                    result = {"ok": False, "reason": "used"}

            body = json.dumps(result).encode()
            self.send_response(200)
            self._cors()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(200)
            self._cors()
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"qweckt visual server is running")

    def log_message(self, format, *args):
        pass

def run_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), Handler)
    print(f"Server started on port {port}")
    server.serve_forever()

# === ЗАПУСК ===
if __name__ == "__main__":
    t = threading.Thread(target=poll_bot, daemon=True)
    t.start()
    run_server()
