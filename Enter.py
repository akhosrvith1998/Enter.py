import os
import threading
from flask import Flask, jsonify
import requests
import json
import random
import string
import time
import math
from datetime import datetime
import sqlite3
import logging
from logging.handlers import RotatingFileHandler
import atexit

# ================== تنظیمات پایه ==================
TOKEN = os.getenv("TOKEN", "8198317562:AAG2sH5sKB6xwjy5nu3CoOY9XB_dupKVWKU")
BASE_URL = f"https://api.telegram.org/bot{TOKEN}"
DATABASE_FILE = "bot_data.db"

# ================== ساختار دیتابیس ==================
def init_db():
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    
    # جدول کاربران
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id TEXT PRIMARY KEY,
        created_at TEXT NOT NULL,
        owner_chat_id INTEGER
    )
    ''')
    
    # جدول فایل‌ها
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS files (
        file_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        filename TEXT NOT NULL,
        content TEXT NOT NULL,
        UNIQUE(user_id, filename),
        FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
    )
    ''')
    
    # جدول سشن‌ها
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS sessions (
        session_id TEXT PRIMARY KEY,
        user_id TEXT,
        auth_expiry REAL,
        mode TEXT,
        calculator_state TEXT,
        last_message_id INTEGER,
        FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE SET NULL
    )
    ''')
    
    conn.commit()
    conn.close()

# ================== توابع دیتابیس ==================
def db_execute(query, params=(), fetchone=False, fetchall=False, commit=False):
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    cursor.execute(query, params)
    
    result = None
    if fetchone:
        result = cursor.fetchone()
    elif fetchall:
        result = cursor.fetchall()
    
    if commit:
        conn.commit()
    
    conn.close()
    return result

def db_commit():
    conn = sqlite3.connect(DATABASE_FILE)
    conn.commit()
    conn.close()

# ================== تنظیمات لاگ‌گیری ==================
log_handler = RotatingFileHandler(
    'bot.log',
    maxBytes=5*1024*1024,  # 5 MB
    backupCount=3
)
log_handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(levelname)s - %(message)s'
))
logger = logging.getLogger()
logger.addHandler(log_handler)
logger.setLevel(logging.INFO)

# ================== ساختار ماشین حساب ==================
CALC_KEYBOARDS = [
    # سطح 0: عملیات پایه
    [
        ["7", "8", "9", "/"],
        ["4", "5", "6", "*"],
        ["1", "2", "3", "-"],
        ["0", ".", "=", "+"],
        ["Clear", "Back", "up"]
    ],
    
    # سطح 1: پیشرفته
    [
        ["√", "x²", "x^y", "x!"],
        ["1/x", "%", "π", "e"],
        ["7", "8", "9", "/"],
        ["4", "5", "6", "*"],
        ["1", "2", "3", "-"],
        ["0", ".", "=", "+"],
        ["Clear", "Back", "up"]
    ],
    
    # سطح 2: مثلثاتی
    [
        ["sin", "cos", "tan"],
        ["sin⁻¹", "cos⁻¹", "tan⁻¹"],
        ["DEG", "RAD", "hyp"],
        ["7", "8", "9", "/"],
        ["4", "5", "6", "*"],
        ["1", "2", "3", "-"],
        ["0", ".", "=", "+"],
        ["Clear", "Back", "up"]
    ],
    
    # سطح 3: لگاریتمی
    [
        ["log", "ln", "10^x", "e^x"],
        ["7", "8", "9", "/"],
        ["4", "5", "6", "*"],
        ["1", "2", "3", "-"],
        ["0", ".", "=", "+"],
        ["Clear", "Back", "up"]
    ],
    
    # سطح 4: پرانتز و اولویت
    [
        ["(", ")", "Ans", "Exp"],
        ["7", "8", "9", "/"],
        ["4", "5", "6", "*"],
        ["1", "2", "3", "-"],
        ["0", ".", "=", "+"],
        ["Clear", "Back", "up"]
    ],
    
    # سطح 5: پایه‌های عددی
    [
        ["DEC", "HEX", "BIN", "OCT"],
        ["A", "B", "C", "D"],
        ["E", "F", "7", "8"],
        ["9", "/", "4", "5"],
        ["6", "*", "1", "2"],
        ["3", "-", "0", "."],
        ["=", "+", "Clear", "Back"],
        ["up"]
    ],
    
    # سطح 6: حافظه
    [
        ["M+", "M-", "MR", "MC"],
        ["7", "8", "9", "/"],
        ["4", "5", "6", "*"],
        ["1", "2", "3", "-"],
        ["0", ".", "=", "+"],
        ["Clear", "Back", "up"]
    ],
    
    # سطح 7: آماری
    [
        ["Σ", "nCr", "nPr"],
        ["STAT", "7", "8", "9"],
        ["/", "4", "5", "6"],
        ["*", "1", "2", "3"],
        ["-", "0", ".", "="],
        ["+", "Clear", "Back", "up"]
    ],
    
    # سطح 8: حالت‌ها
    [
        ["MODE", "SHIFT", "ALPHA"],
        ["DEL", "INS", "7", "8"],
        ["9", "/", "4", "5"],
        ["6", "*", "1", "2"],
        ["3", "-", "0", "."],
        ["=", "+", "Clear", "Back"],
        ["up"]
    ],
    
    # سطح 9: سایر
    [
        ["Ran#", "→", "d/c"],
        ["7", "8", "9", "/"],
        ["4", "5", "6", "*"],
        ["1", "2", "3", "-"],
        ["0", ".", "=", "+"],
        ["Clear", "Back"]
    ]
]

# ================== برنامه Flask ==================
app = Flask(__name__)

@app.route('/')
def home():
    return "ربات تلگرام فعال است! (نسخه پایدار)"

@app.route('/health')
def health_check():
    return jsonify({
        "status": "active",
        "time": datetime.now().isoformat(),
        "bot": "Telegram File Storage & Calculator",
        "stats": {
            "users": db_execute("SELECT COUNT(*) FROM users", fetchone=True)[0],
            "files": db_execute("SELECT COUNT(*) FROM files", fetchone=True)[0],
            "sessions": db_execute("SELECT COUNT(*) FROM sessions", fetchone=True)[0]
        }
    })

# ================== توابع کمکی ==================
def generate_user_id():
    """ایجاد شناسه کاربری 18 کاراکتری منحصر به فرد"""
    uppercase = ''.join(random.choices(string.ascii_uppercase, k=6))
    lowercase = ''.join(random.choices(string.ascii_lowercase, k=4))
    digits = ''.join(random.choices(string.digits, k=4))
    emojis = ''.join(random.choices(['🌟', '🔑', '💎', '🔒', '📁', '💾', '🔐', '💻', '📱', '💰'], k=4))
    return uppercase + lowercase + digits + emojis

def send_message(chat_id, text, reply_markup=None):
    url = f"{BASE_URL}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    
    try:
        response = requests.post(url, json=payload, timeout=15)
        return response.json()
    except Exception as e:
        logger.error(f"خطا در ارسال پیام: {e}")
        return None

def forward_message(chat_id, from_chat_id, message_id):
    url = f"{BASE_URL}/forwardMessage"
    payload = {
        "chat_id": chat_id,
        "from_chat_id": from_chat_id,
        "message_id": message_id
    }
        
    try:
        response = requests.post(url, json=payload, timeout=20)
        return response.json()
    except Exception as e:
        logger.error(f"خطا در فوروارد پیام: {e}")
        return None

def send_media(chat_id, media_type, file_id, caption=None):
    method = None
    if media_type == "photo":
        method = "sendPhoto"
    elif media_type == "video":
        method = "sendVideo"
    elif media_type == "audio":
        method = "sendAudio"
    elif media_type == "voice":
        method = "sendVoice"
    elif media_type == "document":
        method = "sendDocument"
    elif media_type == "animation":
        method = "sendAnimation"
    elif media_type == "sticker":
        method = "sendSticker"
    
    if not method:
        return send_message(chat_id, "⚠️ نوع رسانه پشتیبانی نمی‌شود")
    
    url = f"{BASE_URL}/{method}"
    payload = {
        "chat_id": chat_id,
        media_type: file_id
    }
    if caption:
        payload["caption"] = caption
        
    try:
        response = requests.post(url, json=payload, timeout=20)
        return response.json()
    except Exception as e:
        logger.error(f"خطا در ارسال رسانه: {e}")
        return None

def is_user_authenticated(chat_id):
    """بررسی احراز هویت کاربر"""
    session = db_execute(
        "SELECT * FROM sessions WHERE session_id = ?",
        (str(chat_id),),
        fetchone=True
    )
    
    if not session:
        return False
    
    if time.time() > session[2]:  # auth_expiry
        return False
    
    return True

def show_calculator(chat_id, level=0, expression="", last_message_id=None):
    if level < 0 or level >= len(CALC_KEYBOARDS):
        level = 0
    
    keyboard = []
    for row in CALC_KEYBOARDS[level]:
        keyboard.append([{"text": btn, "callback_data": f"calc:{btn}"} for btn in row])
    
    if last_message_id:
        try:
            requests.post(f"{BASE_URL}/deleteMessage", json={
                "chat_id": chat_id,
                "message_id": last_message_id
            }, timeout=5)
        except:
            pass
    
    result = send_message(
        chat_id,
        f"<b>🧮 ماشین حساب (سطح {level+1})</b>\n\n<code>{expression or '0'}</code>",
        {"inline_keyboard": keyboard}
    )
    
    if result and result.get("result"):
        return result["result"]["message_id"]
    return None

def calculate_expression(expression):
    try:
        expression = expression.replace("π", "math.pi")
        expression = expression.replace("e", "math.e")
        expression = expression.replace("^", "**")
        expression = expression.replace("√", "math.sqrt")
        expression = expression.replace("sin⁻¹", "math.asin")
        expression = expression.replace("cos⁻¹", "math.acos")
        expression = expression.replace("tan⁻¹", "math.atan")
        expression = expression.replace("sin", "math.sin")
        expression = expression.replace("cos", "math.cos")
        expression = expression.replace("tan", "math.tan")
        expression = expression.replace("hyp", "math.hypot")
        expression = expression.replace("log", "math.log10")
        expression = expression.replace("ln", "math.log")
        expression = expression.replace("x²", "**2")
        expression = expression.replace("x!", "math.factorial")
        expression = expression.replace("1/x", "1/")
        expression = expression.replace("%", "/100")
        expression = expression.replace("Σ", "sum")
        
        safe_dict = {k: getattr(math, k) for k in dir(math) if not k.startswith('_')}
        safe_dict.update({"__builtins__": None})
        
        result = str(eval(expression, {"__builtins__": None}, safe_dict))
        
        if '.' in result:
            integer_part, decimal_part = result.split('.')
            if len(decimal_part) > 10:
                result = f"{integer_part}.{decimal_part[:10]}"
        
        return result
    except Exception as e:
        return f"خطا: {str(e)}"

# ================== مدیریت دستورات ==================
def handle_command(message):
    chat_id = message["chat"]["id"]
    text = message.get("text", "").strip()
    user_id = str(chat_id)
    
    # دستورات ادمین
    admin_chat_id = db_execute(
        "SELECT value FROM settings WHERE key = 'admin'",
        fetchone=True
    )
    
    if admin_chat_id:
        admin_chat_id = admin_chat_id[0]
    
    if text == "88077413Xcph4":
        db_execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            ("admin", str(chat_id)),
            commit=True
        )
        send_message(chat_id, "<b>✅ شما ادمین ربات شدید!</b>\nدستورات مدیریتی:\n/panel - پنل مدیریت")
        return
    
    is_admin = str(chat_id) == admin_chat_id if admin_chat_id else False
    
    if is_admin:
        if text.lower() == "/generate":
            new_user_id = generate_user_id()
            db_execute(
                "INSERT INTO users (user_id, created_at) VALUES (?, ?)",
                (new_user_id, datetime.now().isoformat()),
                commit=True
            )
            send_message(
                chat_id, 
                f"<b>🔑 شناسه کاربری جدید ایجاد شد!</b>\n\n"
                f"شناسه: <code>{new_user_id}</code>\n\n"
                "✅ این شناسه را به کاربر مورد نظر تحویل دهید."
            )
            return
        
        if text.lower() == "/panel":
            show_admin_panel(chat_id)
            return
        
        if text.lower() == "/users":
            users = db_execute("SELECT user_id FROM users", fetchall=True)
            keyboard = {"inline_keyboard": []}
            for uid in users:
                keyboard["inline_keyboard"].append([{
                    "text": f"🔑 {uid[0]}",
                    "callback_data": f"user_detail:{uid[0]}"
                }])
            send_message(chat_id, f"<b>👥 لیست کاربران ({len(users)}):</b>", keyboard)
            return
        
        if text.lower().startswith("/files "):
            parts = text.split()
            if len(parts) >= 2:
                user_id_to_view = parts[1]
                user_files = db_execute(
                    "SELECT filename FROM files WHERE user_id = ?",
                    (user_id_to_view,),
                    fetchall=True
                )
                if not user_files:
                    send_message(chat_id, "⚠️ هیچ فایلی برای این کاربر یافت نشد")
                    return
                files_list = "\n".join([f"📁 {name[0]}" for name in user_files])
                send_message(
                    chat_id,
                    f"<b>🗂 فایل‌های کاربر {user_id_to_view[:12]}...:</b>\n\n{files_list}\n\n"
                    f"برای مشاهده محتوای یک فایل:\n<code>/view {user_id_to_view} نام_فایل</code>"
                )
            return
        
        if text.lower().startswith("/view "):
            parts = text.split(maxsplit=2)
            if len(parts) >= 3:
                user_id_to_view = parts[1]
                filename = parts[2]
                file_content = db_execute(
                    "SELECT content FROM files WHERE user_id = ? AND filename = ?",
                    (user_id_to_view, filename),
                    fetchone=True
                )
                if not file_content:
                    send_message(chat_id, "⚠️ فایل مورد نظر یافت نشد")
                    return
                content = json.loads(file_content[0])
                send_message(chat_id, f"<b>📦 محتوای فایل {filename}:</b>\n")
                for item in content:
                    if item.get("is_forwarded"):
                        forward_result = forward_message(
                            chat_id,
                            item["forward_info"]["chat_id"],
                            item["forward_info"]["message_id"]
                        )
                        if not forward_result or not forward_result.get("ok"):
                            if "text" in item:
                                send_message(chat_id, item["text"])
                            else:
                                send_media(
                                    chat_id,
                                    item["type"],
                                    item["file_id"],
                                    item.get("caption", "")
                                )
                    else:
                        if item["type"] == "text":
                            send_message(chat_id, item["content"])
                        elif item["type"] != "unsupported":
                            send_media(
                                chat_id,
                                item["type"],
                                item["file_id"],
                                item.get("caption", "")
                            )
                return
        
        if text.lower().startswith("/delete_user "):
            parts = text.split(maxsplit=1)
            if len(parts) >= 2:
                user_id_to_delete = parts[1]
                if db_execute("SELECT 1 FROM users WHERE user_id = ?", (user_id_to_delete,), fetchone=True):
                    db_execute("DELETE FROM users WHERE user_id = ?", (user_id_to_delete,), commit=True)
                    send_message(chat_id, f"✅ شناسه کاربری <code>{user_id_to_delete}</code> با موفقیت حذف شد!")
                else:
                    send_message(chat_id, "⚠️ شناسه کاربری یافت نشد")
            return
    
    # احراز هویت کاربران عادی
    if len(text) == 18:
        if db_execute("SELECT 1 FROM users WHERE user_id = ?", (text,), fetchone=True):
            owner = db_execute(
                "SELECT owner_chat_id FROM users WHERE user_id = ?",
                (text,),
                fetchone=True
            )
            if owner and owner[0] and int(owner[0]) != chat_id:
                send_message(chat_id, "⚠️ این شناسه قبلاً توسط کاربر دیگری فعال شده است")
                return
            
            db_execute(
                "UPDATE users SET owner_chat_id = ? WHERE user_id = ?",
                (chat_id, text),
                commit=True
            )
            
            db_execute(
                "INSERT OR REPLACE INTO sessions (session_id, user_id, auth_expiry) VALUES (?, ?, ?)",
                (user_id, text, time.time() + 24 * 3600),
                commit=True
            )
            
            send_message(
                chat_id,
                "🔓 احراز هویت موفق!\n"
                "دستوری شما برای 24 ساعت فعال شد.\n\n"
                "دستورات قابل استفاده:\n"
                "/set - شروع ذخیره‌سازی\n"
                "/end - پایان ذخیره‌سازی\n"
                "/del - حذف فایل"
            )
            return
    
    # دستورات کاربران احراز شده
    if not is_user_authenticated(chat_id):
        return
    
    session = db_execute(
        "SELECT * FROM sessions WHERE session_id = ?",
        (user_id,),
        fetchone=True
    )
    user_id_key = session[1]  # user_id in session
    
    if text.lower() == "/set":
        db_execute(
            "UPDATE sessions SET mode = 'collecting', content = '[]' WHERE session_id = ?",
            (user_id,),
            commit=True
        )
        send_message(chat_id, "📥 حالت ذخیره‌سازی فعال شد!\nهمه پیام‌های شما ذخیره می‌شوند.\nبرای پایان /end ارسال کنید.")
        return
    
    if text.lower() == "/end" and session[3] == "collecting":  # mode
        db_execute(
            "UPDATE sessions SET mode = 'naming' WHERE session_id = ?",
            (user_id,),
            commit=True
        )
        send_message(chat_id, "ذخیره‌سازی پایان یافت. لطفاً نام فایل را وارد کنید:")
        return
    
    if text.lower() == "/del":
        user_files = db_execute(
            "SELECT filename FROM files WHERE user_id = ?",
            (user_id_key,),
            fetchall=True
        )
        if not user_files:
            send_message(chat_id, "⚠️ شما هیچ فایلی ندارید")
            return
        files_list = "\n".join([f"📁 {name[0]}" for name in user_files])
        send_message(
            chat_id,
            f"<b>فایل‌های شما:</b>\n\n{files_list}\n\n"
            "لطفاً نام فایلی را که می‌خواهید حذف کنید وارد نمایید:"
        )
        db_execute(
            "UPDATE sessions SET mode = 'deleting' WHERE session_id = ?",
            (user_id,),
            commit=True
        )
        return
    
    if session[3] == "collecting":  # mode
        content_item = {}
        if "forward_from" in message or "forward_from_chat" in message:
            content_item["is_forwarded"] = True
            content_item["forward_info"] = {
                "chat_id": message["chat"]["id"],
                "message_id": message["message_id"]
            }
        else:
            content_item["is_forwarded"] = False
        
        if "text" in message:
            content_item["type"] = "text"
            content_item["content"] = message["text"]
        elif "photo" in message:
            content_item["type"] = "photo"
            content_item["file_id"] = message["photo"][-1]["file_id"]
            content_item["caption"] = message.get("caption", "")
        elif "video" in message:
            content_item["type"] = "video"
            content_item["file_id"] = message["video"]["file_id"]
            content_item["caption"] = message.get("caption", "")
        elif "audio" in message:
            content_item["type"] = "audio"
            content_item["file_id"] = message["audio"]["file_id"]
            content_item["caption"] = message.get("caption", "")
        elif "voice" in message:
            content_item["type"] = "voice"
            content_item["file_id"] = message["voice"]["file_id"]
        elif "document" in message:
            content_item["type"] = "document"
            content_item["file_id"] = message["document"]["file_id"]
            content_item["caption"] = message.get("caption", "")
        elif "animation" in message:
            content_item["type"] = "animation"
            content_item["file_id"] = message["animation"]["file_id"]
            content_item["caption"] = message.get("caption", "")
        elif "sticker" in message:
            content_item["type"] = "sticker"
            content_item["file_id"] = message["sticker"]["file_id"]
        else:
            content_item["type"] = "unsupported"
        
        # به‌روزرسانی محتوا در دیتابیس
        current_content = db_execute(
            "SELECT content FROM sessions WHERE session_id = ?",
            (user_id,),
            fetchone=True
        )[0]
        content_list = json.loads(current_content)
        content_list.append(content_item)
        
        db_execute(
            "UPDATE sessions SET content = ? WHERE session_id = ?",
            (json.dumps(content_list), user_id),
            commit=True
        )
        return
    
    if session[3] == "naming":  # mode
        filename = text
        content = db_execute(
            "SELECT content FROM sessions WHERE session_id = ?",
            (user_id,),
            fetchone=True
        )[0]
        
        db_execute(
            "INSERT INTO files (user_id, filename, content) VALUES (?, ?, ?)",
            (user_id_key, filename, content),
            commit=True
        )
        
        db_execute(
            "UPDATE sessions SET mode = NULL, content = NULL WHERE session_id = ?",
            (user_id,),
            commit=True
        )
        
        send_message(chat_id, f"✅ فایل با نام <code>{filename}</code> ذخیره شد!")
        return
    
    if session[3] == "deleting":  # mode
        db_execute(
            "DELETE FROM files WHERE user_id = ? AND filename = ?",
            (user_id_key, text),
            commit=True
        )
        
        if db_execute("SELECT changes()", fetchone=True)[0] > 0:
            send_message(chat_id, f"✅ فایل <code>{text}</code> با موفقیت حذف شد!")
        else:
            send_message(chat_id, "⚠️ فایل مورد نظر یافت نشد")
        
        db_execute(
            "UPDATE sessions SET mode = NULL WHERE session_id = ?",
            (user_id,),
            commit=True
        )
        return
    
    # نمایش محتوای فایل
    file_content = db_execute(
        "SELECT content FROM files WHERE user_id = ? AND filename = ?",
        (user_id_key, text),
        fetchone=True
    )
    if file_content:
        content = json.loads(file_content[0])
        send_message(chat_id, f"📦 محتوای فایل <b>{text}</b>:\n")
        for item in content:
            if item.get("is_forwarded"):
                forward_result = forward_message(
                    chat_id,
                    item["forward_info"]["chat_id"],
                    item["forward_info"]["message_id"]
                )
                if not forward_result or not forward_result.get("ok"):
                    if "text" in item:
                        send_message(chat_id, item["text"])
                    else:
                        send_media(
                            chat_id,
                            item["type"],
                            item["file_id"],
                            item.get("caption", "")
                        )
            else:
                if item["type"] == "text":
                    send_message(chat_id, item["content"])
                elif item["type"] != "unsupported":
                    send_media(
                        chat_id,
                        item["type"],
                        item["file_id"],
                        item.get("caption", "")
                    )
        return

# ================== مدیریت رابط کاربری ==================
def show_admin_panel(chat_id):
    keyboard = {
        "inline_keyboard": [
            [{"text": "🔑 ایجاد شناسه جدید", "callback_data": "generate"}],
            [{"text": "👥 مشاهده کاربران", "callback_data": "users"}],
            [{"text": "📊 آمار سیستم", "callback_data": "stats"}]
        ]
    }
    send_message(chat_id, "<b>پنل مدیریت ربات</b>\nلطفاً گزینه مورد نظر را انتخاب کنید:", keyboard)

def handle_calculator_callback(query):
    chat_id = query["message"]["chat"]["id"]
    message_id = query["message"]["message_id"]
    callback_data = query["data"].split(":", 1)[1]
    user_id = str(chat_id)
    
    session = db_execute(
        "SELECT * FROM sessions WHERE session_id = ?",
        (user_id,),
        fetchone=True
    )
    
    calculator_state = json.loads(session[4]) if session and session[4] else {}
    expression = calculator_state.get("expression", "")
    level = calculator_state.get("level", 0)
    
    if callback_data == "Clear":
        expression = ""
    elif callback_data == "Back":
        if len(expression) > 0:
            expression = expression[:-1]
    elif callback_data == "up":
        if level < len(CALC_KEYBOARDS) - 1:
            level += 1
    elif callback_data == "=":
        if expression:
            expression = calculate_expression(expression)
    else:
        expression += callback_data
    
    new_calculator_state = json.dumps({
        "expression": expression,
        "level": level,
        "last_message_id": message_id
    })
    
    db_execute(
        "UPDATE sessions SET calculator_state = ? WHERE session_id = ?",
        (new_calculator_state, user_id),
        commit=True
    )
    
    new_message_id = show_calculator(chat_id, level, expression, message_id)
    
    if new_message_id:
        new_calculator_state = json.dumps({
            "expression": expression,
            "level": level,
            "last_message_id": new_message_id
        })
        db_execute(
            "UPDATE sessions SET calculator_state = ? WHERE session_id = ?",
            (new_calculator_state, user_id),
            commit=True
        )

def process_update(update):
    try:
        if "message" in update:
            if update["message"].get("text") == "/start":
                chat_id = update["message"]["chat"]["id"]
                user_id = str(chat_id)
                
                # ایجاد سشن اولیه برای ماشین حساب
                db_execute(
                    "INSERT OR REPLACE INTO sessions (session_id, calculator_state) VALUES (?, ?)",
                    (user_id, json.dumps({
                        "expression": "",
                        "level": 0,
                        "last_message_id": None
                    })),
                    commit=True
                )
                
                message_id = show_calculator(chat_id)
                if message_id:
                    db_execute(
                        "UPDATE sessions SET calculator_state = ? WHERE session_id = ?",
                        (json.dumps({
                            "expression": "",
                            "level": 0,
                            "last_message_id": message_id
                        }), user_id),
                        commit=True
                    )
                return
            
            handle_command(update["message"])
        
        elif "callback_query" in update:
            query = update["callback_query"]
            chat_id = query["message"]["chat"]["id"]
            callback_data = query["data"]
            
            if callback_data.startswith("calc:"):
                handle_calculator_callback(query)
                return
            
            # مدیریت سایر callback‌ها
            if callback_data == "generate":
                new_user_id = generate_user_id()
                db_execute(
                    "INSERT INTO users (user_id, created_at) VALUES (?, ?)",
                    (new_user_id, datetime.now().isoformat()),
                    commit=True
                )
                send_message(
                    chat_id, 
                    f"<b>🔑 شناسه کاربری جدید ایجاد شد!</b>\n\n"
                    f"شناسه: <code>{new_user_id}</code>\n\n"
                    "✅ این شناسه را به کاربر مورد نظر تحویل دهید."
                )
            
            elif callback_data == "users":
                users = db_execute("SELECT user_id FROM users", fetchall=True)
                keyboard = {"inline_keyboard": []}
                for uid in users:
                    keyboard["inline_keyboard"].append([{
                        "text": f"🔑 {uid[0]}",
                        "callback_data": f"user_detail:{uid[0]}"
                    }])
                send_message(chat_id, f"<b>👥 لیست کاربران ({len(users)}):</b>", keyboard)
            
            elif callback_data == "stats":
                stats = f"""
<b>📊 آمار سیستم:</b>
👤 کاربران ثبت‌شده: {db_execute("SELECT COUNT(*) FROM users", fetchone=True)[0]}
🗂 فایل‌های ذخیره شده: {db_execute("SELECT COUNT(*) FROM files", fetchone=True)[0]}
🔓 جلسات فعال: {db_execute("SELECT COUNT(*) FROM sessions", fetchone=True)[0]}
"""
                send_message(chat_id, stats)
            
            elif callback_data.startswith("user_detail:"):
                user_id = callback_data.split(":", 1)[1]
                keyboard = {
                    "inline_keyboard": [
                        [
                            {"text": "🗑️ حذف شناسه", "callback_data": f"delete_user:{user_id}"},
                            {"text": "📂 نمایش فایل‌ها", "callback_data": f"list_files:{user_id}"}
                        ]
                    ]
                }
                send_message(chat_id, f"<b>🔍 مدیریت کاربر</b>\nشناسه: <code>{user_id}</code>", keyboard)
            
            elif callback_data.startswith("delete_user:"):
                user_id_to_delete = callback_data.split(":", 1)[1]
                if db_execute("SELECT 1 FROM users WHERE user_id = ?", (user_id_to_delete,), fetchone=True):
                    db_execute("DELETE FROM users WHERE user_id = ?", (user_id_to_delete,), commit=True)
                    send_message(chat_id, f"✅ شناسه کاربری <code>{user_id_to_delete}</code> با موفقیت حذف شد!")
                else:
                    send_message(chat_id, "⚠️ شناسه کاربری یافت نشد")
            
            elif callback_data.startswith("list_files:"):
                user_id_to_view = callback_data.split(":", 1)[1]
                user_files = db_execute(
                    "SELECT filename FROM files WHERE user_id = ?",
                    (user_id_to_view,),
                    fetchall=True
                )
                if not user_files:
                    send_message(chat_id, "⚠️ هیچ فایلی برای این کاربر یافت نشد")
                    return
                keyboard = {"inline_keyboard": []}
                for filename in user_files:
                    keyboard["inline_keyboard"].append([{
                        "text": f"📁 {filename[0]}",
                        "callback_data": f"view_file:{user_id_to_view}:{filename[0]}"
                    }])
                send_message(chat_id, f"<b>🗂 فایل‌های کاربر {user_id_to_view[:12]}...:</b>", keyboard)
            
            elif callback_data.startswith("view_file:"):
                parts = callback_data.split(":", 2)
                if len(parts) >= 3:
                    user_id_to_view = parts[1]
                    filename = parts[2]
                    file_content = db_execute(
                        "SELECT content FROM files WHERE user_id = ? AND filename = ?",
                        (user_id_to_view, filename),
                        fetchone=True
                    )
                    if not file_content:
                        send_message(chat_id, "⚠️ فایل مورد نظر یافت نشد")
                        return
                    content = json.loads(file_content[0])
                    send_message(chat_id, f"<b>📦 محتوای فایل {filename}:</b>\n")
                    for item in content:
                        if item.get("is_forwarded"):
                            forward_result = forward_message(
                                chat_id,
                                item["forward_info"]["chat_id"],
                                item["forward_info"]["message_id"]
                            )
                            if not forward_result or not forward_result.get("ok"):
                                if "text" in item:
                                    send_message(chat_id, item["text"])
                                else:
                                    send_media(
                                        chat_id,
                                        item["type"],
                                        item["file_id"],
                                        item.get("caption", "")
                                    )
                        else:
                            if item["type"] == "text":
                                send_message(chat_id, item["content"])
                            elif item["type"] != "unsupported":
                                send_media(
                                    chat_id,
                                    item["type"],
                                    item["file_id"],
                                    item.get("caption", "")
                                )
                
    except Exception as e:
        logger.error(f"خطا در پردازش آپدیت: {e}\n{update}")

# ================== سیستم همیشه فعال ==================
def run_bot():
    logger.info("ربات تلگرام شروع به کار کرد...")
    offset = 0
    while True:
        try:
            response = requests.get(
                f"{BASE_URL}/getUpdates",
                params={"offset": offset, "timeout": 60},
                timeout=65
            )
            
            if response.status_code == 200:
                updates = response.json().get("result", [])
                for update in updates:
                    offset = update["update_id"] + 1
                    threading.Thread(target=process_update, args=(update,)).start()
            else:
                logger.warning(f"خطای API: {response.status_code}")
                time.sleep(5)
        except requests.exceptions.Timeout:
            logger.info("Timeout, restarting polling...")
        except requests.exceptions.ConnectionError:
            logger.warning("Connection error, retrying in 10s...")
            time.sleep(10)
        except Exception as e:
            logger.error(f"خطای غیرمنتظره: {e}")
            time.sleep(5)

def keep_alive():
    while True:
        try:
            # فعال نگه داشتن روی Render
            if 'RENDER' in os.environ:
                requests.get('https://your-bot-name.onrender.com/health', timeout=10)
            
            # فعال نگه داشتن اتصال به تلگرام
            requests.get(f"{BASE_URL}/getMe", timeout=10)
            
            logger.info(f"Keep-alive ping at {datetime.now()}")
            time.sleep(45)  # هر 45 ثانیه
        except Exception as e:
            logger.error(f"Keep-alive error: {e}")
            time.sleep(10)

# ================== تنظیمات اولیه ==================
def setup():
    # ایجاد جداول مورد نیاز
    db_execute(
        "CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)",
        commit=True
    )
    
    # ایجاد جدول کاربران
    db_execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id TEXT PRIMARY KEY,
        created_at TEXT NOT NULL,
        owner_chat_id INTEGER
    )
    ''', commit=True)
    
    # ایجاد جدول فایل‌ها
    db_execute('''
    CREATE TABLE IF NOT EXISTS files (
        file_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        filename TEXT NOT NULL,
        content TEXT NOT NULL,
        UNIQUE(user_id, filename),
        FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
    )
    ''', commit=True)
    
    # ایجاد جدول سشن‌ها
    db_execute('''
    CREATE TABLE IF NOT EXISTS sessions (
        session_id TEXT PRIMARY KEY,
        user_id TEXT,
        auth_expiry REAL,
        mode TEXT,
        content TEXT,
        calculator_state TEXT,
        last_message_id INTEGER,
        FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE SET NULL
    )
    ''', commit=True)
    
    logger.info("پیکربندی پایگاه داده انجام شد")

# ================== اجرای برنامه ==================
if __name__ == "__main__":
    # تنظیمات اولیه
    setup()
    
    # تابع تمیزکاری هنگام خروج
    atexit.register(db_commit)
    
    # شروع سیستم‌های پس‌زمینه
    threading.Thread(target=run_bot, daemon=True).start()
    threading.Thread(target=keep_alive, daemon=True).start()
    
    # اجرای سرور Flask
    app.run(
        host='0.0.0.0',
        port=int(os.environ.get('PORT', 10000)),
        threaded=True,
        debug=False,
        use_reloader=False
    )