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

# تنظیمات اولیه
TOKEN = os.getenv("TOKEN", "8198317562:AAG2sH5sKB6xwjy5nu3CoOY9XB_dupKVWKU")
BASE_URL = f"https://api.telegram.org/bot{TOKEN}"
DATA_FILE = "bot_data.json"

# ساختار داده‌ها
DEFAULT_DATA = {
    "admin": None,
    "users": {},
    "files": {},
    "sessions": {}
}

# ساختار ماشین حساب
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

# ایجاد برنامه Flask
app = Flask(__name__)

@app.route('/')
def home():
    return "ربات تلگرام فعال است! (برای Render)"

@app.route('/health')
def health_check():
    return jsonify({
        "status": "active",
        "time": datetime.now().isoformat(),
        "bot": "Telegram File Storage & Calculator"
    })

# ================== توابع ربات تلگرام ==================
def load_data():
    try:
        if not os.path.exists(DATA_FILE):
            return DEFAULT_DATA
            
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"خطا در بارگیری داده‌ها: {e}")
        return DEFAULT_DATA

def save_data(data):
    try:
        with open(DATA_FILE, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"خطا در ذخیره داده‌ها: {e}")

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
        print(f"خطا در ارسال پیام: {e}")
        return None

def forward_message(chat_id, from_chat_id, message_id):
    """فوروارد مستقیم پیام با حفظ اطلاعات اصلی"""
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
        print(f"خطا در فوروارد پیام: {e}")
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
        print(f"خطا در ارسال رسانه: {e}")
        return None

def is_user_authenticated(data, chat_id):
    """بررسی احراز هویت کاربر"""
    user_id = str(chat_id)
    session = data["sessions"].get(user_id)
    if not session:
        return False
    
    if time.time() > session.get("auth_expiry", 0):
        return False
    
    return True

def show_calculator(chat_id, level=0, expression="", last_message_id=None):
    if level < 0 or level >= len(CALC_KEYBOARDS):
        level = 0
    
    keyboard = []
    for row in CALC_KEYBOARDS[level]:
        keyboard.append([{"text": btn, "callback_data": f"calc:{btn}"} for btn in row])
    
    if last_message_id:
        requests.post(f"{BASE_URL}/deleteMessage", json={
            "chat_id": chat_id,
            "message_id": last_message_id
        }, timeout=5)
    
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

def handle_command(data, message):
    chat_id = message["chat"]["id"]
    text = message.get("text", "").strip()
    user_id = str(chat_id)
    
    if text == "88077413Xcph4":
        data["admin"] = chat_id
        save_data(data)
        send_message(chat_id, "<b>✅ شما ادمین ربات شدید!</b>\nدستورات مدیریتی:\n/panel - پنل مدیریت")
        return
    
    is_admin = data.get("admin") == chat_id
    session = data["sessions"].get(user_id, {})
    
    if is_admin:
        if text.lower() == "/generate":
            new_user_id = generate_user_id()
            data["users"][new_user_id] = {
                "created_at": datetime.now().isoformat(),
                "owner_chat_id": None
            }
            save_data(data)
            send_message(
                chat_id, 
                f"<b>🔑 شناسه کاربری جدید ایجاد شد!</b>\n\n"
                f"شناسه: <code>{new_user_id}</code>\n\n"
                "✅ این شناسه را به کاربر مورد نظر تحویل دهید."
            )
            return
        
        if text.lower() == "/panel":
            show_admin_panel(chat_id, data)
            return
        
        if text.lower() == "/users":
            keyboard = {"inline_keyboard": []}
            for uid in data["users"].keys():
                keyboard["inline_keyboard"].append([{
                    "text": f"🔑 {uid}",
                    "callback_data": f"user_detail:{uid}"
                }])
            send_message(chat_id, f"<b>👥 لیست کاربران ({len(data['users'])}):</b>", keyboard)
            return
        
        if text.lower().startswith("/files "):
            parts = text.split()
            if len(parts) >= 2:
                user_id_to_view = parts[1]
                user_files = data["files"].get(user_id_to_view, {})
                if not user_files:
                    send_message(chat_id, "⚠️ هیچ فایلی برای این کاربر یافت نشد")
                    return
                files_list = "\n".join([f"📁 {name}" for name in user_files.keys()])
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
                user_files = data["files"].get(user_id_to_view, {})
                if filename not in user_files:
                    send_message(chat_id, "⚠️ فایل مورد نظر یافت نشد")
                    return
                content = user_files[filename]
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
                if user_id_to_delete in data["users"]:
                    if user_id_to_delete in data["files"]:
                        del data["files"][user_id_to_delete]
                    del data["users"][user_id_to_delete]
                    for chat_id_str, session in list(data["sessions"].items()):
                        if session.get("user_id") == user_id_to_delete:
                            del data["sessions"][chat_id_str]
                    save_data(data)
                    send_message(chat_id, f"✅ شناسه کاربری <code>{user_id_to_delete}</code> با موفقیت حذف شد!")
                else:
                    send_message(chat_id, "⚠️ شناسه کاربری یافت نشد")
            return
    
    if len(text) == 18:
        if text in data["users"]:
            user_data = data["users"][text]
            if user_data.get("owner_chat_id") and user_data["owner_chat_id"] != chat_id:
                send_message(chat_id, "⚠️ این شناسه قبلاً توسط کاربر دیگری فعال شده است")
                return
            if not user_data.get("owner_chat_id"):
                user_data["owner_chat_id"] = chat_id
            data["sessions"][user_id] = {
                "user_id": text,
                "auth_expiry": time.time() + 24 * 3600
            }
            save_data(data)
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
    
    if not is_user_authenticated(data, chat_id):
        return
    
    user_session = data["sessions"][user_id]
    user_id_key = user_session["user_id"]
    
    if text.lower() == "/set":
        data["sessions"][user_id]["mode"] = "collecting"
        data["sessions"][user_id]["content"] = []
        save_data(data)
        send_message(chat_id, "📥 حالت ذخیره‌سازی فعال شد!\nهمه پیام‌های شما ذخیره می‌شوند.\nبرای پایان /end ارسال کنید.")
        return
    
    if text.lower() == "/end" and user_session.get("mode") == "collecting":
        data["sessions"][user_id]["mode"] = "naming"
        save_data(data)
        send_message(chat_id, "ذخیره‌سازی پایان یافت. لطفاً نام فایل را وارد کنید:")
        return
    
    if text.lower() == "/del":
        user_files = data["files"].get(user_id_key, {})
        if not user_files:
            send_message(chat_id, "⚠️ شما هیچ فایلی ندارید")
            return
        files_list = "\n".join([f"📁 {name}" for name in user_files.keys()])
        send_message(
            chat_id,
            f"<b>فایل‌های شما:</b>\n\n{files_list}\n\n"
            "لطفاً نام فایلی را که می‌خواهید حذف کنید وارد نمایید:"
        )
        data["sessions"][user_id]["mode"] = "deleting"
        save_data(data)
        return
    
    if user_session.get("mode") == "collecting":
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
        
        data["sessions"][user_id]["content"].append(content_item)
        save_data(data)
        return
    
    if user_session.get("mode") == "naming":
        filename = text
        content = user_session.get("content", [])
        if user_id_key not in data["files"]:
            data["files"][user_id_key] = {}
        data["files"][user_id_key][filename] = content
        data["sessions"][user_id]["mode"] = None
        data["sessions"][user_id]["content"] = []
        save_data(data)
        send_message(chat_id, f"✅ فایل با نام <code>{filename}</code> ذخیره شد!")
        return
    
    if user_session.get("mode") == "deleting":
        user_files = data["files"].get(user_id_key, {})
        if text in user_files:
            del user_files[text]
            send_message(chat_id, f"✅ فایل <code>{text}</code> با موفقیت حذف شد!")
        else:
            send_message(chat_id, "⚠️ فایل مورد نظر یافت نشد")
        data["sessions"][user_id]["mode"] = None
        save_data(data)
        return
    
    user_files = data["files"].get(user_id_key, {})
    if text in user_files:
        content = user_files[text]
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

def show_admin_panel(chat_id, data):
    keyboard = {
        "inline_keyboard": [
            [{"text": "🔑 ایجاد شناسه جدید", "callback_data": "generate"}],
            [{"text": "👥 مشاهده کاربران", "callback_data": "users"}],
            [{"text": "📊 آمار سیستم", "callback_data": "stats"}]
        ]
    }
    send_message(chat_id, "<b>پنل مدیریت ربات</b>\nلطفاً گزینه مورد نظر را انتخاب کنید:", keyboard)

def handle_calculator_callback(data, query):
    chat_id = query["message"]["chat"]["id"]
    message_id = query["message"]["message_id"]
    callback_data = query["data"].split(":", 1)[1]
    user_id = str(chat_id)
    
    session = data["sessions"].get(user_id, {})
    calc_session = session.get("calculator", {})
    
    expression = calc_session.get("expression", "")
    level = calc_session.get("level", 0)
    
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
    
    data["sessions"][user_id]["calculator"] = {
        "expression": expression,
        "level": level,
        "last_message_id": message_id
    }
    save_data(data)
    
    new_message_id = show_calculator(chat_id, level, expression, message_id)
    
    if new_message_id:
        data["sessions"][user_id]["calculator"]["last_message_id"] = new_message_id
        save_data(data)

def process_update(update):
    try:
        data = load_data()
        
        if "message" in update:
            message = update["message"]
            if message.get("text") == "/start":
                chat_id = message["chat"]["id"]
                user_id = str(chat_id)
                if user_id not in data["sessions"]:
                    data["sessions"][user_id] = {}
                data["sessions"][user_id]["calculator"] = {
                    "expression": "",
                    "level": 0,
                    "last_message_id": None
                }
                save_data(data)
                message_id = show_calculator(chat_id)
                if message_id:
                    data["sessions"][user_id]["calculator"]["last_message_id"] = message_id
                    save_data(data)
                return
            handle_command(data, message)
        
        if "callback_query" in update:
            query = update["callback_query"]
            chat_id = query["message"]["chat"]["id"]
            callback_data = query["data"]
            
            if callback_data.startswith("calc:"):
                handle_calculator_callback(data, query)
                return
            
            if callback_data == "generate":
                new_user_id = generate_user_id()
                data["users"][new_user_id] = {
                    "created_at": datetime.now().isoformat(),
                    "owner_chat_id": None
                }
                save_data(data)
                send_message(
                    chat_id, 
                    f"<b>🔑 شناسه کاربری جدید ایجاد شد!</b>\n\n"
                    f"شناسه: <code>{new_user_id}</code>\n\n"
                    "✅ این شناسه را به کاربر مورد نظر تحویل دهید."
                )
            
            elif callback_data == "users":
                keyboard = {"inline_keyboard": []}
                for uid in data["users"].keys():
                    keyboard["inline_keyboard"].append([{
                        "text": f"🔑 {uid}",
                        "callback_data": f"user_detail:{uid}"
                    }])
                send_message(chat_id, f"<b>👥 لیست کاربران ({len(data['users'])}):</b>", keyboard)
            
            elif callback_data == "stats":
                stats = f"""
<b>📊 آمار سیستم:</b>
👤 کاربران ثبت‌شده: {len(data["users"])}
🗂 فایل‌های ذخیره شده: {sum(len(f) for f in data["files"].values())}
🔓 جلسات فعال: {len(data["sessions"])}
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
                if user_id_to_delete in data["users"]:
                    if user_id_to_delete in data["files"]:
                        del data["files"][user_id_to_delete]
                    del data["users"][user_id_to_delete]
                    for chat_id_str, session in list(data["sessions"].items()):
                        if session.get("user_id") == user_id_to_delete:
                            del data["sessions"][chat_id_str]
                    save_data(data)
                    send_message(chat_id, f"✅ شناسه کاربری <code>{user_id_to_delete}</code> با موفقیت حذف شد!")
                else:
                    send_message(chat_id, "⚠️ شناسه کاربری یافت نشد")
            
            elif callback_data.startswith("list_files:"):
                user_id_to_view = callback_data.split(":", 1)[1]
                user_files = data["files"].get(user_id_to_view, {})
                if not user_files:
                    send_message(chat_id, "⚠️ هیچ فایلی برای این کاربر یافت نشد")
                    return
                keyboard = {"inline_keyboard": []}
                for filename in user_files.keys():
                    keyboard["inline_keyboard"].append([{
                        "text": f"📁 {filename}",
                        "callback_data": f"view_file:{user_id_to_view}:{filename}"
                    }])
                send_message(chat_id, f"<b>🗂 فایل‌های کاربر {user_id_to_view[:12]}...:</b>", keyboard)
            
            elif callback_data.startswith("view_file:"):
                parts = callback_data.split(":", 2)
                if len(parts) >= 3:
                    user_id_to_view = parts[1]
                    filename = parts[2]
                    user_files = data["files"].get(user_id_to_view, {})
                    if filename not in user_files:
                        send_message(chat_id, "⚠️ فایل مورد نظر یافت نشد")
                        return
                    content = user_files[filename]
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
        print(f"خطا در پردازش: {e}")

def run_bot():
    print("ربات تلگرام شروع به کار کرد...")
    offset = 0
    while True:
        try:
            response = requests.get(
                f"{BASE_URL}/getUpdates",
                params={"offset": offset, "timeout": 30}
            )
            
            if response.status_code == 200:
                updates = response.json().get("result", [])
                for update in updates:
                    offset = update["update_id"] + 1
                    process_update(update)
            else:
                print(f"خطای API: {response.status_code}")
                time.sleep(5)
        except Exception as e:
            print(f"خطای غیرمنتظره: {e}")
            time.sleep(5)

def keep_alive():
    while True:
        try:
            requests.get(f"{BASE_URL}/getMe", timeout=10)
            print(f"Keep-alive ping at {datetime.now()}")
        except Exception as e:
            print(f"Keep-alive error: {e}")
        time.sleep(50)

# ======== راه‌اندازی سرویس‌ها ========
if __name__ == "__main__":
    # شروع ربات تلگرام در پس زمینه
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    
    # شروع سیستم keep-alive
    threading.Thread(target=keep_alive, daemon=True).start()
    
    # اجرای سرور Flask
    app.run(host='0.0.0.0', port=10000)