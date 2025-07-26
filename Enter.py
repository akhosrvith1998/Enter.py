import json
import logging
import os
import random
import string
import sqlite3
import threading
import time
import requests
from flask import Flask, request

# تنظیمات لاگ
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__) # Fix: Use __name__

# تنظیمات ربات
TOKEN = "8198317562:AAG2sH5sKB6xwjy5nu3CoOY9XB_dupKVWKU" # شناسه توکن ربات خود را جایگزین کنید
ADMIN_ID = 7824772776  # شناسه تلگرام ادمین خود را جایگزین کنید
WEBHOOK_URL = "https://enter-py.onrender.com/webhook"  # آدرس Render خود را جایگزین کنید
API_URL = f"https://api.telegram.org/bot{TOKEN}/"
secure_mode = False  # حالت امنیتی
user_data = {}  # ذخیره موقت داده‌های کاربران (برای حالت‌های انتظار و message_id ماشین حساب)

# راه‌اندازی Flask برای وب‌هوک
app = Flask(__name__) # Fix: Use __name__

# راه‌اندازی دیتابیس
conn = sqlite3.connect('database.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS users
             (id INTEGER PRIMARY KEY, user_id INTEGER UNIQUE, username TEXT, identifier TEXT, password TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS files
             (id INTEGER PRIMARY KEY, user_id INTEGER, file_name TEXT, content_type TEXT, content TEXT)''')
conn.commit()

# توابع کمکی
def generate_identifier():
    """تولید شناسه تصادفی با 6 حرف بزرگ، 5 حرف کوچک و 7 عدد"""
    uppercase = ''.join(random.choices(string.ascii_uppercase, k=6))
    lowercase = ''.join(random.choices(string.ascii_lowercase, k=5))
    digits = ''.join(random.choices(string.digits, k=7))
    all_chars = uppercase + lowercase + digits
    return ''.join(random.sample(all_chars, len(all_chars)))

def send_message(chat_id, text, reply_markup=None):
    """ارسال پیام به کاربر"""
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    }
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    try:
        requests.post(f"{API_URL}sendMessage", json=payload)
    except Exception as e:
        logger.error(f"Error sending message to {chat_id}: {e}")

def edit_message_text(chat_id, message_id, text, reply_markup=None):
    """ویرایش پیام موجود"""
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": "Markdown"
    }
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    try:
        requests.post(f"{API_URL}editMessageText", json=payload)
    except Exception as e:
        logger.error(f"Error editing message {message_id} in {chat_id}: {e}")

def send_photo(chat_id, photo, caption=None):
    """ارسال عکس"""
    payload = {"chat_id": chat_id, "photo": photo}
    if caption:
        payload["caption"] = caption
    try:
        requests.post(f"{API_URL}sendPhoto", json=payload)
    except Exception as e:
        logger.error(f"Error sending photo to {chat_id}: {e}")

def send_video(chat_id, video, caption=None):
    """ارسال ویدیو"""
    payload = {"chat_id": chat_id, "video": video}
    if caption:
        payload["caption"] = caption
    try:
        requests.post(f"{API_URL}sendVideo", json=payload)
    except Exception as e:
        logger.error(f"Error sending video to {chat_id}: {e}")

def send_audio(chat_id, audio, caption=None):
    """ارسال صوت"""
    payload = {"chat_id": chat_id, "audio": audio}
    if caption:
        payload["caption"] = caption
    try:
        requests.post(f"{API_URL}sendAudio", json=payload)
    except Exception as e:
        logger.error(f"Error sending audio to {chat_id}: {e}")

def send_document(chat_id, document, caption=None):
    """ارسال سند"""
    payload = {"chat_id": chat_id, "document": document}
    if caption:
        payload["caption"] = caption
    try:
        requests.post(f"{API_URL}sendDocument", json=payload)
    except Exception as e:
        logger.error(f"Error sending document to {chat_id}: {e}")

def send_sticker(chat_id, sticker):
    """ارسال استیکر"""
    payload = {"chat_id": chat_id, "sticker": sticker}
    try:
        requests.post(f"{API_URL}sendSticker", json=payload)
    except Exception as e:
        logger.error(f"Error sending sticker to {chat_id}: {e}")

def send_voice(chat_id, voice):
    """ارسال پیام صوتی"""
    payload = {"chat_id": chat_id, "voice": voice}
    try:
        requests.post(f"{API_URL}sendVoice", json=payload)
    except Exception as e:
        logger.error(f"Error sending voice to {chat_id}: {e}")

def send_video_note(chat_id, video_note):
    """ارسال پیام ویدیویی دایره‌ای"""
    payload = {"chat_id": chat_id, "video_note": video_note}
    try:
        requests.post(f"{API_URL}sendVideoNote", json=payload)
    except Exception as e:
        logger.error(f"Error sending video note to {chat_id}: {e}")

def send_location(chat_id, latitude, longitude):
    """ارسال موقعیت مکانی"""
    payload = {"chat_id": chat_id, "latitude": latitude, "longitude": longitude}
    try:
        requests.post(f"{API_URL}sendLocation", json=payload)
    except Exception as e:
        logger.error(f"Error sending location to {chat_id}: {e}")

def send_contact(chat_id, phone_number, first_name, last_name=None):
    """ارسال مخاطب"""
    payload = {"chat_id": chat_id, "phone_number": phone_number, "first_name": first_name}
    if last_name:
        payload["last_name"] = last_name
    try:
        requests.post(f"{API_URL}sendContact", json=payload)
    except Exception as e:
        logger.error(f"Error sending contact to {chat_id}: {e}")

def check_secure_mode(user_id):
    """بررسی حالت امنیتی"""
    global secure_mode
    return secure_mode and user_id != ADMIN_ID

def is_authenticated(user_id):
    """بررسی احراز هویت کاربر"""
    return user_data.get(user_id, {}).get('authenticated', False)

# ماشین حساب
def show_calculator(chat_id, user_id, message_id=None):
    """نمایش پنل ماشین حساب 17 دکمه‌ای"""
    keyboard = {
        "inline_keyboard": [
            [{"text": "7", "callback_data": "calc_7"}, {"text": "8", "callback_data": "calc_8"},
             {"text": "9", "callback_data": "calc_9"}, {"text": "/", "callback_data": "calc_/"}],
            [{"text": "4", "callback_data": "calc_4"}, {"text": "5", "callback_data": "calc_5"},
             {"text": "6", "callback_data": "calc_6"}, {"text": "*", "callback_data": "calc_*}"], # Fix: Changed empty to *
            [{"text": "1", "callback_data": "calc_1"}, {"text": "2", "callback_data": "calc_2"},
             {"text": "3", "callback_data": "calc_3"}, {"text": "-", "callback_data": "calc_-"}],
            [{"text": "0", "callback_data": "calc_0"}, {"text": ".", "callback_data": "calc_."},
             {"text": "=", "callback_data": "calc_="}, {"text": "+", "callback_data": "calc_+"}],
            [{"text": "C", "callback_data": "calc_C"}]
        ]
    }
    # اطمینان از وجود ورودی ماشین حساب در دیتابیس
    c.execute("INSERT OR REPLACE INTO files (user_id, file_name, content_type, content) VALUES (?, 'calculator', 'text', '')",
              (user_id,))
    conn.commit()

    # دریافت عبارت فعلی ماشین حساب
    c.execute("SELECT content FROM files WHERE user_id=? AND file_name='calculator'", (user_id,))
    expression = c.fetchone()[0] or ""

    if message_id:
        edit_message_text(chat_id, message_id, f"ماشین حساب: {expression}", keyboard)
    else:
        response = requests.post(f"{API_URL}sendMessage", json={"chat_id": chat_id, "text": f"ماشین حساب: {expression}", "reply_markup": json.dumps(keyboard), "parse_mode": "Markdown"})
        if response.status_code == 200:
            message_id = response.json()['result']['message_id']
            user_data[user_id] = user_data.get(user_id, {})
            user_data[user_id]['calculator_message_id'] = message_id
        else:
            logger.error(f"Error sending initial calculator message: {response.text}")

# پردازش آپدیت‌ها
@app.route('/webhook', methods=['POST'])
def webhook():
    """دریافت و پردازش آپدیت‌ها از تلگرام"""
    update = request.get_json(force=True)

    if 'message' in update:
        message = update['message']
        chat_id = message['chat']['id']
        user_id = message['from']['id']
        username = message['from'].get('username', f"user_{user_id}")

        if check_secure_mode(user_id):
            return 'ok'

        # مدیریت دستورات
        if 'text' in message:
            text = message['text'].strip()

            # دستور /start
            if text == '/start':
                c.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
                if c.fetchone():
                    send_message(chat_id, "شما قبلاً ثبت‌نام کرده‌اید. شناسه و پسورد خود را ارسال کنید: <شناسه> <پسورد>")
                else:
                    show_calculator(chat_id, user_id)
                return 'ok'

            # دستور /calculator (برای کاربران احراز هویت شده)
            if text == '/calculator' and is_authenticated(user_id):
                show_calculator(chat_id, user_id)
                return 'ok'

            # دستور /thanks (ادمین)
            if text == '/thanks' and user_id == ADMIN_ID:
                global secure_mode
                secure_mode = True
                send_message(chat_id, "ربات در حالت امنیتی قرار گرفت.")
                return 'ok'

            # فعال‌سازی مجدد (ادمین)
            if user_id == ADMIN_ID:
                if text == "88077413Xcph4":
                    user_data[user_id] = user_data.get(user_id, {})
                    user_data[user_id]['awaiting_hi'] = True
                    send_message(chat_id, "لطفاً 'Hi' را تایپ کنید.")
                    return 'ok'
                elif user_data.get(user_id, {}).get('awaiting_hi', False) and text == "Hi":
                    global secure_mode
                    secure_mode = False
                    send_message(chat_id, "ربات فعال شد.")
                    user_data[user_id]['awaiting_hi'] = False
                    return 'ok'

            # ثبت پسورد
            if user_data.get(user_id, {}).get('awaiting_password', False):
                if len(text) == 6 and text.isdigit():
                    identifier = user_data[user_id]['identifier']
                    c.execute("INSERT INTO users (user_id, username, identifier, password) VALUES (?, ?, ?, ?)",
                              (user_id, username, identifier, text))
                    conn.commit()
                    send_message(chat_id, "ثبت‌نام با موفقیت انجام شد. برای ورود از شناسه و پسورد استفاده کنید.")
                    user_data[user_id]['awaiting_password'] = False
                    user_data[user_id]['identifier'] = None
                else:
                    send_message(chat_id, "لطفاً یک پسورد 6 رقمی عددی وارد کنید.")
                return 'ok'

            # تخصیص شناسه توسط ادمین
            if user_data.get(user_id, {}).get('awaiting_user_id', False) and user_id == ADMIN_ID:
                try:
                    target_user_id = int(text)
                    identifier = user_data[user_id]['new_identifier']
                    target_username = f"user_{target_user_id}"
                    c.execute("INSERT OR REPLACE INTO users (user_id, username, identifier, password) VALUES (?, ?, ?, ?)",
                              (target_user_id, target_username, identifier, ""))
                    conn.commit()
                    send_message(chat_id, f"شناسه {identifier} به کاربر {target_user_id} تخصیص یافت.")
                    user_data[user_id]['awaiting_user_id'] = False
                    user_data[user_id]['new_identifier'] = None
                except ValueError:
                    send_message(chat_id, "لطفاً شناسه عددی معتبر وارد کنید.")
                return 'ok'

            # ارسال نوتیفیکیشن توسط ادمین
            if user_data.get(user_id, {}).get('awaiting_notification', False) and user_id == ADMIN_ID:
                c.execute("SELECT user_id FROM users")
                users = c.fetchall()
                sent_count = 0
                for user in users:
                    try:
                        send_message(user[0], text)
                        sent_count += 1
                    except Exception as e:
                        logger.error(f"Failed to send notification to user {user[0]}: {e}")
                        continue
                send_message(chat_id, f"پیام به {sent_count} کاربر ارسال شد.")
                user_data[user_id]['awaiting_notification'] = False
                return 'ok'

            # دستورات مدیریت فایل (فقط برای کاربران احراز هویت شده)
            if is_authenticated(user_id):
                if text.startswith('/set '):
                    file_name = text[5:].strip()
                    c.execute("SELECT * FROM files WHERE user_id=? AND file_name=?", (user_id, file_name))
                    if c.fetchone():
                        send_message(chat_id, "فایل با این نام وجود دارد. برای افزودن محتوا به آن از دستور /add استفاده کنید.")
                    else:
                        user_data[user_id] = user_data.get(user_id, {})
                        user_data[user_id]['file_name'] = file_name
                        user_data[user_id]['awaiting_content'] = True
                        send_message(chat_id, "محتوا را ارسال کنید.")
                    return 'ok'

                if text == '/end':
                    if user_data.get(user_id, {}).get('awaiting_content', False):
                        user_data[user_id]['file_name'] = None
                        user_data[user_id]['awaiting_content'] = False
                        send_message(chat_id, "پایان ثبت محتوا.") # Fix: More accurate message
                    else:
                        send_message(chat_id, "فایلی در حال ویرایش نیست.")
                    return 'ok'

                if text == '/add':
                    c.execute("SELECT DISTINCT file_name FROM files WHERE user_id=?", (user_id,))
                    files = c.fetchall()
                    if files:
                        keyboard = {"inline_keyboard": [[{"text": file[0], "callback_data": f"add_{file[0]}"}] for file in files]}
                        send_message(chat_id, "فایلی را برای افزودن محتوا انتخاب کنید:", keyboard)
                    else:
                        send_message(chat_id, "فایلی یافت نشد.")
                    return 'ok'

                if text == '/see':
                    c.execute("SELECT DISTINCT file_name FROM files WHERE user_id=?", (user_id,))
                    files = c.fetchall()
                    if files:
                        keyboard = {"inline_keyboard": [[{"text": file[0], "callback_data": f"see_{file[0]}"}] for file in files]}
                        send_message(chat_id, "فایل‌های شما:", keyboard)
                    else:
                        send_message(chat_id, "فایلی یافت نشد.")
                    return 'ok'

                if text == '/del':
                    c.execute("SELECT DISTINCT file_name FROM files WHERE user_id=?", (user_id,))
                    files = c.fetchall()
                    if files:
                        keyboard = {"inline_keyboard": [[{"text": file[0], "callback_data": f"del_{file[0]}"}] for file in files]}
                        send_message(chat_id, "فایلی را برای حذف انتخاب کنید:", keyboard)
                    else:
                        send_message(chat_id, "فایلی یافت نشد.")
                    return 'ok'

                if text == '/delete':
                    keyboard = {
                        "inline_keyboard": [
                            [{"text": "بله", "callback_data": "delete_yes"}, {"text": "خیر", "callback_data": "delete_no"}]
                        ]
                    }
                    send_message(chat_id, "آیا مطمئن هستید که می‌خواهید همه فایل‌ها را حذف کنید؟", keyboard)
                    return 'ok'

                # ذخیره محتوا (برای حالت awaiting_content)
                if user_data.get(user_id, {}).get('awaiting_content', False):
                    file_name = user_data[user_id]['file_name']
                    content_type = None
                    content = None
                    if 'text' in message:
                        content_type = 'text'
                        content = message['text']
                    elif 'photo' in message:
                        content_type = 'photo'
                        content = message['photo'][-1]['file_id']
                    elif 'video' in message:
                        content_type = 'video'
                        content = message['video']['file_id']
                    elif 'audio' in message:
                        content_type = 'audio'
                        content = message['audio']['file_id']
                    elif 'document' in message:
                        content_type = 'document'
                        content = message['document']['file_id']
                    elif 'sticker' in message: # Added support for sticker
                        content_type = 'sticker'
                        content = message['sticker']['file_id']
                    elif 'voice' in message: # Added support for voice
                        content_type = 'voice'
                        content = message['voice']['file_id']
                    elif 'video_note' in message: # Added support for video_note
                        content_type = 'video_note'
                        content = message['video_note']['file_id']
                    elif 'location' in message: # Added support for location
                        content_type = 'location'
                        content = json.dumps({'latitude': message['location']['latitude'], 'longitude': message['location']['longitude']})
                    elif 'contact' in message: # Added support for contact
                        content_type = 'contact'
                        content = json.dumps({'phone_number': message['contact']['phone_number'], 'first_name': message['contact'].get('first_name'), 'last_name': message['contact'].get('last_name')})
                    elif 'forward_from' in message or 'forward_from_chat' in message:
                        content_type = 'forward'
                        content = str(message['message_id']) # Storing message_id for forwarded messages
                    if content_type:
                        c.execute("INSERT INTO files (user_id, file_name, content_type, content) VALUES (?, ?, ?, ?)",
                                  (user_id, file_name, content_type, content))
                        conn.commit()
                        send_message(chat_id, "محتوا اضافه شد. برای ادامه محتوا بفرستید یا /end را تایپ کنید.")
                    else:
                        send_message(chat_id, "فرمت پشتیبانی نمی‌شود.")
                    return 'ok'

            # احراز هویت (اگر کاربر در حالت انتظار برای پسورد نباشد)
            if not user_data.get(user_id, {}).get('awaiting_password', False):
                parts = text.split()
                if len(parts) == 2:
                    identifier, password = parts
                    c.execute("SELECT user_id FROM users WHERE identifier=? AND password=?", (identifier, password))
                    user = c.fetchone()
                    if user:
                        user_data[user_id] = user_data.get(user_id, {})
                        user_data[user_id]['authenticated'] = True
                        send_message(chat_id, "ورود با موفقیت انجام شد.")
                    else:
                        send_message(chat_id, "شناسه یا پسورد اشتباه است.")
                    return 'ok'

    # مدیریت callback query (دکمه‌ها)
    if 'callback_query' in update:
        callback = update['callback_query']
        chat_id = callback['message']['chat']['id']
        user_id = callback['from']['id']
        data = callback['data']
        callback_message_id = callback['message']['message_id'] # Get message_id of the callback query

        if check_secure_mode(user_id):
            return 'ok'

        # ماشین حساب
        if data.startswith('calc_'):
            c.execute("SELECT content FROM files WHERE user_id=? AND file_name='calculator'", (user_id,))
            expression_data = c.fetchone()
            expression = expression_data[0] if expression_data else ""
            char = data[5:]
            calc_message_id = user_data.get(user_id, {}).get('calculator_message_id')

            if char == '=':
                try:
                    result = eval(expression)
                    if expression == "2+4*778/9+3":  # محاسبه خاص برای فعال‌سازی شناسه
                        identifier = generate_identifier()
                        user_data[user_id] = user_data.get(user_id, {})
                        user_data[user_id]['identifier'] = identifier
                        user_data[user_id]['awaiting_password'] = True
                        send_message(chat_id, f"شناسه شما: {identifier}\nلطفاً یک پسورد 6 رقمی عددی وارد کنید:")
                        # حذف پیام ماشین حساب پس از محاسبه خاص
                        if calc_message_id:
                            requests.post(f"{API_URL}deleteMessage", json={"chat_id": chat_id, "message_id": calc_message_id})
                            user_data[user_id].pop('calculator_message_id', None)
                    else:
                        send_message(chat_id, f"نتیجه: {result}")
                        # ریست کردن ماشین حساب پس از محاسبه عادی
                        c.execute("UPDATE files SET content=? WHERE user_id=? AND file_name='calculator'", ("", user_id))
                        conn.commit()
                        if calc_message_id:
                            show_calculator(chat_id, user_id, calc_message_id) # نمایش مجدد با عبارت خالی
                        else:
                            show_calculator(chat_id, user_id) # ارسال پیام جدید اگر قبلی حذف شده
                except Exception as e:
                    logger.error(f"Calculator error for user {user_id}: {e}")
                    send_message(chat_id, "عبارت نامعتبر است.")
                    # ریست کردن ماشین حساب در صورت خطا
                    c.execute("UPDATE files SET content=? WHERE user_id=? AND file_name='calculator'", ("", user_id))
                    conn.commit()
                    if calc_message_id:
                        show_calculator(chat_id, user_id, calc_message_id)
                    else:
                        show_calculator(chat_id, user_id)
            elif char == 'C':
                expression = ""
                c.execute("UPDATE files SET content=? WHERE user_id=? AND file_name='calculator'", ("", user_id))
                conn.commit()
                if calc_message_id:
                    show_calculator(chat_id, user_id, calc_message_id) # ویرایش پیام موجود
                else:
                    show_calculator(chat_id, user_id) # ارسال پیام جدید اگر قبلی حذف شده
            else:
                expression += char
                c.execute("UPDATE files SET content=? WHERE user_id=? AND file_name='calculator'", (expression, user_id))
                conn.commit()
                if calc_message_id:
                    show_calculator(chat_id, user_id, calc_message_id) # ویرایش پیام موجود
                else:
                    show_calculator(chat_id, user_id) # ارسال پیام جدید اگر قبلی حذف شده
            return 'ok'

        # پنل ادمین
        if data.startswith('admin_') and user_id == ADMIN_ID:
            if data == 'admin_create_id':
                identifier = generate_identifier()
                user_data[user_id] = user_data.get(user_id, {})
                user_data[user_id]['new_identifier'] = identifier
                user_data[user_id]['awaiting_user_id'] = True
                send_message(chat_id, f"شناسه جدید: {identifier}\nشناسه عددی کاربر را ارسال کنید:")
            elif data == 'admin_view_users':
                c.execute("SELECT user_id, username FROM users")
                users = c.fetchall()
                if users:
                    keyboard = {"inline_keyboard": [[{"text": f"@{user[1]} (ID: {user[0]})", "callback_data": f"view_{user[0]}"}] for user in users]}
                    send_message(chat_id, "کاربران:", keyboard)
                else:
                    send_message(chat_id, "کاربری یافت نشد.")
            elif data == 'admin_delete_id':
                c.execute("SELECT user_id, username FROM users")
                users = c.fetchall()
                if users:
                    keyboard = {"inline_keyboard": [[{"text": f"@{user[1]} (ID: {user[0]})", "callback_data": f"delid_{user[0]}"}] for user in users]}
                    send_message(chat_id, "کاربر را برای حذف انتخاب کنید:", keyboard)
                else:
                    send_message(chat_id, "کاربری یافت نشد.")
            elif data == 'admin_notify':
                user_data[user_id] = user_data.get(user_id, {})
                user_data[user_id]['awaiting_notification'] = True
                send_message(chat_id, "پیام خود را برای ارسال به همه کاربران وارد کنید:")
            elif data == 'admin_stats':
                c.execute("SELECT COUNT(*) FROM users")
                total_users = c.fetchone()[0]
                c.execute("SELECT user_id, username FROM users")
                users_with_files = c.fetchall()

                stats = f"تعداد کل کاربران: {total_users}\n"

                for user_id_stats, username in users_with_files:
                    c.execute("SELECT COUNT(DISTINCT file_name) FROM files WHERE user_id=?", (user_id_stats,))
                    unique_files_count = c.fetchone()[0]
                    c.execute("SELECT COUNT(*) FROM files WHERE user_id=?", (user_id_stats,))
                    total_content_parts = c.fetchone()[0]

                    stats += f"@{username} (ID: {user_id_stats}): {unique_files_count} فایل منحصر به فرد, {total_content_parts} محتوا\n"

                send_message(chat_id, stats)
            return 'ok'

        if data.startswith('view_') and user_id == ADMIN_ID:
            target_user_id = int(data.split('_')[1])
            c.execute("SELECT DISTINCT file_name FROM files WHERE user_id=?", (target_user_id,))
            files = c.fetchall()
            if files:
                keyboard = {"inline_keyboard": [[{"text": file[0], "callback_data": f"admin_see_{target_user_id}_{file[0]}"}] for file in files]}
                send_message(chat_id, "فایل‌های کاربر:", keyboard)
            else:
                send_message(chat_id, "فایلی یافت نشد.")
            return 'ok'

        if data.startswith('admin_see_') and user_id == ADMIN_ID:
            _, _, target_user_id, file_name = data.split('_', 3) # Fix: split by 3 to handle file names with underscores
            target_user_id = int(target_user_id)
            c.execute("SELECT content_type, content FROM files WHERE user_id=? AND file_name=?",
                      (target_user_id, file_name))
            contents = c.fetchall()
            if not contents:
                send_message(chat_id, "محتوایی برای این فایل یافت نشد.")
                return 'ok'
            for content_type, content in contents:
                try:
                    if content_type == 'text':
                        send_message(chat_id, content)
                    elif content_type == 'photo':
                        send_photo(chat_id, content)
                    elif content_type == 'video':
                        send_video(chat_id, content)
                    elif content_type == 'audio':
                        send_audio(chat_id, content)
                    elif content_type == 'document':
                        send_document(chat_id, content)
                    elif content_type == 'sticker':
                        send_sticker(chat_id, content)
                    elif content_type == 'voice':
                        send_voice(chat_id, content)
                    elif content_type == 'video_note':
                        send_video_note(chat_id, content)
                    elif content_type == 'location':
                        loc_data = json.loads(content)
                        send_location(chat_id, loc_data['latitude'], loc_data['longitude'])
                    elif content_type == 'contact':
                        contact_data = json.loads(content)
                        send_contact(chat_id, contact_data['phone_number'], contact_data['first_name'], contact_data.get('last_name'))
                    elif content_type == 'forward':
                        send_message(chat_id, f"پیام فوروارد شده (Message ID): {content}")
                    else:
                        send_message(chat_id, f"فرمت محتوا پشتیبانی نمی‌شود: {content_type}")
                except Exception as e:
                    logger.error(f"Error sending content of type {content_type} for file {file_name} to admin {chat_id}: {e}")
                    send_message(chat_id, f"خطا در نمایش محتوای نوع {content_type}.")
            return 'ok'

        if data.startswith('delid_') and user_id == ADMIN_ID:
            target_user_id = int(data.split('_')[1])
            c.execute("DELETE FROM users WHERE user_id=?", (target_user_id,))
            c.execute("DELETE FROM files WHERE user_id=?", (target_user_id,))
            conn.commit()
            send_message(chat_id, "کاربر و فایل‌هایش حذف شدند.")
            return 'ok'

        # دکمه‌های کاربران (فقط برای کاربران احراز هویت شده)
        if is_authenticated(user_id):
            if data.startswith('see_'):
                file_name = data.split('_', 1)[1]
                c.execute("SELECT content_type, content FROM files WHERE user_id=? AND file_name=?", (user_id, file_name))
                contents = c.fetchall()
                if not contents:
                    send_message(chat_id, "محتوایی برای این فایل یافت نشد.")
                    return 'ok'
                for content_type, content in contents:
                    try:
                        if content_type == 'text':
                            send_message(chat_id, content)
                        elif content_type == 'photo':
                            send_photo(chat_id, content)
                        elif content_type == 'video':
                            send_video(chat_id, content)
                        elif content_type == 'audio':
                            send_audio(chat_id, content)
                        elif content_type == 'document':
                            send_document(chat_id, content)
                        elif content_type == 'sticker':
                            send_sticker(chat_id, content)
                        elif content_type == 'voice':
                            send_voice(chat_id, content)
                        elif content_type == 'video_note':
                            send_video_note(chat_id, content)
                        elif content_type == 'location':
                            loc_data = json.loads(content)
                            send_location(chat_id, loc_data['latitude'], loc_data['longitude'])
                        elif content_type == 'contact':
                            contact_data = json.loads(content)
                            send_contact(chat_id, contact_data['phone_number'], contact_data['first_name'], contact_data.get('last_name'))
                        elif content_type == 'forward':
                            send_message(chat_id, f"پیام فوروارد شده (Message ID): {content}")
                        else:
                            send_message(chat_id, f"فرمت محتوا پشتیبانی نمی‌شود: {content_type}")
                    except Exception as e:
                        logger.error(f"Error sending content of type {content_type} for file {file_name} to user {chat_id}: {e}")
                        send_message(chat_id, f"خطا در نمایش محتوای نوع {content_type}.")
                return 'ok'

            if data.startswith('add_'):
                file_name = data.split('_', 1)[1]
                user_data[user_id] = user_data.get(user_id, {})
                user_data[user_id]['file_name'] = file_name
                user_data[user_id]['awaiting_content'] = True
                send_message(chat_id, "محتوا را ارسال کنید.")
                return 'ok'

            if data.startswith('del_'):
                file_name = data.split('_', 1)[1]
                c.execute("DELETE FROM files WHERE user_id=? AND file_name=?", (user_id, file_name))
                conn.commit()
                send_message(chat_id, f"فایل {file_name} حذف شد.")
                return 'ok'

            if data == 'delete_yes':
                c.execute("DELETE FROM files WHERE user_id=?", (user_id,))
                conn.commit()
                send_message(chat_id, "همه فایل‌ها حذف شدند.")
                return 'ok'

            if data == 'delete_no':
                send_message(chat_id, "عملیات لغو شد.")
                return 'ok'

    # پنل ادمین (دستور /admin)
    if 'message' in update and update['message']['text'] == '/admin' and update['message']['from']['id'] == ADMIN_ID:
        keyboard = {
            "inline_keyboard": [
                [{"text": "ایجاد شناسه", "callback_data": "admin_create_id"}],
                [{"text": "مشاهده کاربران", "callback_data": "admin_view_users"}],
                [{"text": "حذف شناسه کاربر", "callback_data": "admin_delete_id"}],
                [{"text": "نوتیفیکیشن", "callback_data": "admin_notify"}],
                [{"text": "آمار", "callback_data": "admin_stats"}]
            ]
        }
        send_message(chat_id, "پنل ادمین:", keyboard)
        return 'ok'

    return 'ok'

# تنظیم وب‌هوک
def set_webhook():
    """تنظیم وب‌هوک برای تلگرام"""
    try:
        requests.post(f"{API_URL}setWebhook", json={"url": WEBHOOK_URL})
        logger.info("Webhook set successfully")
    except Exception as e:
        logger.error(f"Error setting webhook: {e}")

# پینگ خودکار برای جلوگیری از غیرفعال شدن
def keep_alive():
    """پینگ خودکار به سرویس Render"""
    while True:
        try:
            requests.get(WEBHOOK_URL)
            logger.info("Keep-alive ping sent.")
        except Exception as e:
            logger.error(f"Error during keep-alive ping: {e}")
        time.sleep(300)  # هر 5 دقیقه

# راه‌اندازی ربات
if __name__ == '__main__': # Fix: Use __name__
    set_webhook()
    threading.Thread(target=keep_alive, daemon=True).start()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

