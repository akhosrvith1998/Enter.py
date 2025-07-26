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
import re

# ================== تنظیمات پایه ==================
TOKEN = os.getenv("TOKEN", "8198317562:AAG2sH5sKB6xwjy5nu3CoOY9XB_dupKVWKU")
BASE_URL = f"https://api.telegram.org/bot{TOKEN}"
DATABASE_FILE = "bot_data.db"

# ================== ساختار دیتابیس ==================
def init_db():
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    
    # جدول تنظیمات
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    ''')
    
    # جدول کاربران
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id TEXT PRIMARY KEY,
        created_at TEXT NOT NULL,
        owner_chat_id INTEGER,
        owner_first_name TEXT,
        owner_last_name TEXT,
        owner_username TEXT
    )
    ''')
    
    # جدول فایل‌ها
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS files (
        file_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        filename TEXT NOT NULL,
        content TEXT NOT NULL,
        created_at TEXT NOT NULL,
        size INTEGER NOT NULL,
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
        target_file TEXT,
        content TEXT,
        calculator_state TEXT,
        last_message_id INTEGER,
        FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE SET NULL
    )
    ''')
    
    # جدول لاگ‌ها
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS logs (
        log_id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        level TEXT NOT NULL,
        message TEXT NOT NULL
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

def log_to_db(level, message):
    db_execute(
        "INSERT INTO logs (timestamp, level, message) VALUES (?, ?, ?)",
        (datetime.now().isoformat(), level, message),
        commit=True
    )

# ================== تنظیمات لاگ‌گیری ==================
log_handler = RotatingFileHandler(
    'bot.log',
    maxBytes=2*1024*1024,  # 2 MB
    backupCount=3
)
log_handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(levelname)s - %(message)s'
))
logger = logging.getLogger()
logger.addHandler(log_handler)
logger.setLevel(logging.INFO)

# ================== ساختار ماشین حساب ساده ==================
CALC_KEYBOARD = [
    [{"text": "7", "callback_data": "calc:7"}, 
     {"text": "8", "callback_data": "calc:8"}, 
     {"text": "9", "callback_data": "calc:9"}, 
     {"text": "÷", "callback_data": "calc:/"}],
     
    [{"text": "4", "callback_data": "calc:4"}, 
     {"text": "5", "callback_data": "calc:5"}, 
     {"text": "6", "callback_data": "calc:6"}, 
     {"text": "×", "callback_data": "calc:*"}],
     
    [{"text": "1", "callback_data": "calc:1"}, 
     {"text": "2", "callback_data": "calc:2"}, 
     {"text": "3", "callback_data": "calc:3"}, 
     {"text": "-", "callback_data": "calc:-"}],
     
    [{"text": "0", "callback_data": "calc:0"}, 
     {"text": ".", "callback_data": "calc:."}, 
     {"text": "=", "callback_data": "calc:="}, 
     {"text": "+", "callback_data": "calc:+"}],
     
    [{"text": "❌ پاک کردن", "callback_data": "calc:Clear"}, 
     {"text": "🔙 بازگشت", "callback_data": "calc:Back"}]
]

# ================== برنامه Flask ==================
app = Flask(__name__)

@app.route('/')
def home():
    return "ربات تلگرام فعال است! (نسخه حرفه‌ای)"

@app.route('/health')
def health_check():
    try:
        users = db_execute("SELECT COUNT(*) FROM users", fetchone=True) or (0,)
        files = db_execute("SELECT COUNT(*) FROM files", fetchone=True) or (0,)
        sessions = db_execute("SELECT COUNT(*) FROM sessions", fetchone=True) or (0,)
        
        stats = {
            "status": "active",
            "time": datetime.now().isoformat(),
            "stats": {
                "users": users[0],
                "files": files[0],
                "sessions": sessions[0]
            }
        }
        return jsonify(stats)
    except Exception as e:
        logger.error(f"خطا در health check: {e}")
        return jsonify({"status": "error", "message": str(e)})

# ================== توابع کمکی ==================
def generate_user_id():
    """ایجاد شناسه کاربری 18 کاراکتری منحصر به فرد"""
    uppercase = ''.join(random.choices(string.ascii_uppercase, k=5))
    lowercase = ''.join(random.choices(string.ascii_lowercase, k=4))
    digits = ''.join(random.choices(string.digits, k=5))
    special_chars = ''.join(random.choices('&%_"\'/×÷^√∆-+><=α@°•⌀©™®|}{][$№§¶¡±‰₿₽€£¥¢№«»≤≥', k=4))
    return f"#{uppercase}{lowercase}{digits}{special_chars}"

def get_user_display_name(user_id):
    """دریافت نام نمایشی کاربر"""
    try:
        user = db_execute(
            "SELECT owner_first_name, owner_last_name, owner_username FROM users WHERE user_id = ?",
            (user_id,),
            fetchone=True
        )
        
        if user:
            first_name = user[0] or ""
            last_name = user[1] or ""
            username = user[2] or ""
            
            if first_name or last_name:
                return f"{first_name} {last_name}".strip()
            elif username:
                return f"@{username}"
    except Exception as e:
        logger.error(f"خطا در دریافت نام کاربر: {e}")
    
    return user_id[:12] + "..."

def send_message(chat_id, text, reply_markup=None, parse_mode="HTML"):
    url = f"{BASE_URL}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True
    }
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    
    try:
        response = requests.post(url, json=payload, timeout=15)
        return response.json()
    except Exception as e:
        logger.error(f"خطا در ارسال پیام: {e}")
        log_to_db("ERROR", f"Failed to send message: {e}")
        return None

def edit_message(chat_id, message_id, text, reply_markup=None):
    url = f"{BASE_URL}/editMessageText"
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": "HTML"
    }
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    
    try:
        response = requests.post(url, json=payload, timeout=15)
        return response.json()
    except Exception as e:
        logger.error(f"خطا در ویرایش پیام: {e}")
        log_to_db("ERROR", f"Failed to edit message: {e}")
        return None

def delete_message(chat_id, message_id):
    try:
        requests.post(
            f"{BASE_URL}/deleteMessage",
            json={"chat_id": chat_id, "message_id": message_id},
            timeout=5
        )
    except:
        pass

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
        log_to_db("ERROR", f"Failed to forward message: {e}")
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
        log_to_db("ERROR", f"Failed to send media: {e}")
        return None

def is_user_authenticated(chat_id):
    """بررسی احراز هویت کاربر"""
    try:
        session = db_execute(
            "SELECT auth_expiry FROM sessions WHERE session_id = ?",
            (str(chat_id),),
            fetchone=True
        )
        
        if not session or session[0] is None:
            return False
        
        if time.time() > session[0]:
            return False
        
        return True
    except Exception as e:
        logger.error(f"خطا در بررسی احراز هویت: {e}")
        return False

def show_calculator(chat_id, expression="", last_message_id=None):
    if last_message_id:
        try:
            delete_message(chat_id, last_message_id)
        except:
            pass
    
    result = send_message(
        chat_id,
        f"<b>🧮 ماشین حساب</b>\n\n<code>{expression or '0'}</code>",
        {"inline_keyboard": CALC_KEYBOARD}
    )
    
    if result and result.get("result"):
        return result["result"]["message_id"]
    return None

def update_calculator(chat_id, message_id, expression):
    try:
        edit_message(
            chat_id,
            message_id,
            f"<b>🧮 ماشین حساب</b>\n\n<code>{expression or '0'}</code>",
            {"inline_keyboard": CALC_KEYBOARD}
        )
        return message_id
    except:
        return show_calculator(chat_id, expression)

def calculate_expression(expression):
    try:
        # جایگزینی نمادها برای محاسبه
        expression = expression.replace("×", "*").replace("÷", "/")
        
        # محاسبه نتیجه
        result = str(eval(expression))
        
        # محدود کردن اعشار
        if '.' in result:
            integer_part, decimal_part = result.split('.')
            if len(decimal_part) > 6:
                result = f"{integer_part}.{decimal_part[:6]}"
        
        return result
    except Exception as e:
        return f"خطا: {str(e)}"

# ================== مدیریت دستورات ==================
def handle_command(message):
    try:
        chat_id = message["chat"]["id"]
        text = message.get("text", "").strip()
        user_id = str(chat_id)
        first_name = message["from"].get("first_name", "")
        last_name = message["from"].get("last_name", "")
        username = message["from"].get("username", "")
        
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
                users = db_execute("SELECT user_id FROM users", fetchall=True) or []
                keyboard = {"inline_keyboard": []}
                for uid in users:
                    display_name = get_user_display_name(uid[0])
                    keyboard["inline_keyboard"].append([{
                        "text": f"👤 {display_name}",
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
                    ) or []
                    if not user_files:
                        send_message(chat_id, "⚠️ هیچ فایلی برای این کاربر یافت نشد")
                        return
                    files_list = "\n".join([f"📁 {name[0]}" for name in user_files])
                    send_message(
                        chat_id,
                        f"<b>🗂 فایل‌های کاربر {get_user_display_name(user_id_to_view)}:</b>\n\n{files_list}\n\n"
                        f"برای مشاهده محتوای یک فایل:\n<code>/view {user_id_to_view} نام_فایل</code>"
                    )
                return
            
            # سایر دستورات ادمین ...
        
        # احراز هویت کاربران عادی
        if len(text) == 18 and text.startswith("#"):
            user_record = db_execute("SELECT * FROM users WHERE user_id = ?", (text,), fetchone=True)
            if user_record:
                owner = user_record[2] if len(user_record) > 2 else None
                
                if owner and int(owner) != chat_id:
                    send_message(chat_id, "⚠️ این شناسه قبلاً توسط کاربر دیگری فعال شده است")
                    return
                
                db_execute(
                    "UPDATE users SET owner_chat_id = ?, owner_first_name = ?, owner_last_name = ?, owner_username = ? WHERE user_id = ?",
                    (chat_id, first_name, last_name, username, text),
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
                    "/set - ذخیره فایل جدید\n"
                    "/rep - افزودن به فایل موجود\n"
                    "/pin - مشاهده فایل‌های شما\n"
                    "/del - حذف فایل"
                )
                return
            else:
                send_message(chat_id, "⚠️ شناسه وارد شده معتبر نیست")
                return
        
        # دستورات کاربران احراز شده
        if not is_user_authenticated(chat_id):
            return
        
        session = db_execute(
            "SELECT * FROM sessions WHERE session_id = ?",
            (user_id,),
            fetchone=True
        )
        
        if not session:
            return
        
        user_id_key = session[1]  # user_id in session
        
        if text.lower() == "/set":
            db_execute(
                "UPDATE sessions SET mode = 'collecting', content = '[]' WHERE session_id = ?",
                (user_id,),
                commit=True
            )
            send_message(chat_id, "📥 حالت ذخیره‌سازی فعال شد!\nهمه پیام‌های شما ذخیره می‌شوند.\nبرای پایان /end ارسال کنید.")
            return
        
        # سایر دستورات کاربران ...
        
    except Exception as e:
        logger.error(f"خطا در مدیریت دستور: {e}")
        log_to_db("ERROR", f"Command handling error: {e}")

# ================== مدیریت رابط کاربری ==================
def show_admin_panel(chat_id):
    try:
        total_users = db_execute("SELECT COUNT(*) FROM users", fetchone=True) or (0,)
        total_files = db_execute("SELECT COUNT(*) FROM files", fetchone=True) or (0,)
        total_size = db_execute("SELECT SUM(size) FROM files", fetchone=True) or (0,)
        
        stats = f"""
<b>📊 آمار سیستم:</b>
👤 کاربران: {total_users[0]}
📁 فایل‌ها: {total_files[0]}
💾 حجم کل: {total_size[0] / 1024 if total_size[0] else 0:.2f} کیلوبایت
    """
        
        keyboard = {
            "inline_keyboard": [
                [{"text": "🔑 ایجاد شناسه کاربری", "callback_data": "generate"}],
                [{"text": "👥 مدیریت کاربران", "callback_data": "users"}],
                [{"text": "📂 مدیریت فایل‌ها", "callback_data": "files"}],
                [{"text": "📊 مشاهده آمار", "callback_data": "stats"}],
                [{"text": "📝 مشاهده لاگ‌ها", "callback_data": "logs"}]
            ]
        }
        
        send_message(chat_id, f"<b>🛠 پنل مدیریت پیشرفته</b>\n{stats}", keyboard)
    except Exception as e:
        logger.error(f"خطا در نمایش پنل ادمین: {e}")

def handle_calculator_callback(query):
    try:
        chat_id = query["message"]["chat"]["id"]
        message_id = query["message"]["message_id"]
        callback_data = query["data"].split(":", 1)[1]
        user_id = str(chat_id)
        
        session = db_execute(
            "SELECT calculator_state FROM sessions WHERE session_id = ?",
            (user_id,),
            fetchone=True
        )
        
        calculator_state = {}
        if session and session[0]:
            try:
                calculator_state = json.loads(session[0])
            except:
                calculator_state = {}
        
        expression = calculator_state.get("expression", "")
        
        if callback_data == "Clear":
            expression = ""
        elif callback_data == "Back":
            if len(expression) > 0:
                expression = expression[:-1]
        elif callback_data == "=":
            if expression:
                expression = calculate_expression(expression)
        else:
            expression += callback_data
        
        # به‌روزرسانی رابط کاربری
        last_msg_id = calculator_state.get("last_message_id")
        new_msg_id = update_calculator(chat_id, last_msg_id, expression)
        
        # ذخیره حالت جدید
        new_calculator_state = json.dumps({
            "expression": expression,
            "last_message_id": new_msg_id
        })
        
        db_execute(
            "UPDATE sessions SET calculator_state = ? WHERE session_id = ?",
            (new_calculator_state, user_id),
            commit=True
        )
    except Exception as e:
        logger.error(f"خطا در مدیریت ماشین حساب: {e}")

def process_update(update):
    try:
        if "message" in update:
            message = update["message"]
            
            # دستور /start برای نمایش ماشین حساب
            if message.get("text") == "/start":
                chat_id = message["chat"]["id"]
                user_id = str(chat_id)
                
                # ایجاد سشن اولیه برای ماشین حساب
                db_execute(
                    "INSERT OR REPLACE INTO sessions (session_id, calculator_state) VALUES (?, ?)",
                    (user_id, json.dumps({
                        "expression": "",
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
                            "last_message_id": message_id
                        }), user_id),
                        commit=True
                    )
                return
            
            handle_command(message)
        
        elif "callback_query" in update:
            query = update["callback_query"]
            chat_id = query["message"]["chat"]["id"]
            callback_data = query["data"]
            message_id = query["message"]["message_id"]
            
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
            
            # سایر callback ها ...
            
    except Exception as e:
        logger.error(f"خطا در پردازش آپدیت: {e}\n{update}")
        log_to_db("ERROR", f"Update processing error: {e}")

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
                requests.get('https://your-bot-name.onrender.com/health', timeout=5)
            
            # فعال نگه داشتن اتصال به تلگرام
            requests.get(f"{BASE_URL}/getMe", timeout=5)
            
            logger.info(f"Keep-alive ping at {datetime.now()}")
            time.sleep(5)  # هر 5 ثانیه
        except Exception as e:
            logger.error(f"Keep-alive error: {e}")
            time.sleep(2)

# ================== تنظیمات اولیه ==================
def setup():
    # ایجاد جداول مورد نیاز
    try:
        db_execute(
            "CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)",
            commit=True
        )
        
        # ایجاد جدول کاربران
        db_execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            owner_chat_id INTEGER,
            owner_first_name TEXT,
            owner_last_name TEXT,
            owner_username TEXT
        )
        ''', commit=True)
        
        # ایجاد جدول فایل‌ها
        db_execute('''
        CREATE TABLE IF NOT EXISTS files (
            file_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            filename TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL,
            size INTEGER NOT NULL,
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
            target_file TEXT,
            content TEXT,
            calculator_state TEXT,
            last_message_id INTEGER,
            FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE SET NULL
        )
        ''', commit=True)
        
        # ایجاد جدول لاگ‌ها
        db_execute('''
        CREATE TABLE IF NOT EXISTS logs (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            level TEXT NOT NULL,
            message TEXT NOT NULL
        )
        ''', commit=True)
        
        logger.info("پیکربندی پایگاه داده انجام شد")
    except Exception as e:
        logger.error(f"خطا در پیکربندی پایگاه داده: {e}")

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