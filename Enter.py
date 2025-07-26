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
logger = logging.getLogger(__name__)

# تنظیمات ربات
TOKEN = "8198317562:AAG2sH5sKB6xwjy5nu3CoOY9XB_dupKVWKU"
ADMIN_ID = 7824772776  # شناسه تلگرام ادمین خود را جایگزین کنید
WEBHOOK_URL = "https://enter-py.onrender.com/webhook"  # آدرس Render خود را جایگزین کنید
API_URL = f"https://api.telegram.org/bot{TOKEN}/"
secure_mode = False  # حالت امنیتی
user_data = {}  # ذخیره موقت داده‌های کاربران

# راه‌اندازی Flask برای وب‌هوک
app = Flask(__name__)

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
        logger.error(f"Error sending message: {e}")

def send_photo(chat_id, photo, caption=None):
    """ارسال عکس"""
    payload = {"chat_id": chat_id, "photo": photo}
    if caption:
        payload["caption"] = caption
    try:
        requests.post(f"{API_URL}sendPhoto", json=payload)
    except Exception as e:
        logger.error(f"Error sending photo: {e}")

def send_video(chat_id, video, caption=None):
    """ارسال ویدیو"""
    payload = {"chat_id": chat_id, "video": video}
    if caption:
        payload["caption"] = caption
    try:
        requests.post(f"{API_URL}sendVideo", json=payload)
    except Exception as e:
        logger.error(f"Error sending video: {e}")

def send_audio(chat_id, audio, caption=None):
    """ارسال صوت"""
    payload = {"chat_id": chat_id, "audio": audio}
    if caption:
        payload["caption"] = caption
    try:
        requests.post(f"{API_URL}sendAudio", json=payload)
    except Exception as e:
        logger.error(f"Error sending audio: {e}")

def send_document(chat_id, document, caption=None):
    """ارسال سند"""
    payload = {"chat_id": chat_id, "document": document}
    if caption:
        payload["caption"] = caption
    try:
        requests.post(f"{API_URL}sendDocument", json=payload)
    except Exception as e:
        logger.error(f"Error sending document: {e}")

def check_secure_mode(user_id):
    """بررسی حالت امنیتی"""
    global secure_mode
    return secure_mode and user_id != ADMIN_ID

def is_authenticated(user_id):
    """بررسی احراز هویت کاربر"""
    return user_data.get(user_id, {}).get('authenticated', False)

# ماشین حساب
def show_calculator(chat_id, user_id):
    """نمایش پنل ماشین حساب 17 دکمه‌ای"""
    keyboard = {
        "inline_keyboard": [
            [{"text": "7", "callback_data": "calc_7"}, {"text": "8", "callback_data": "calc_8"}, 
             {"text": "9", "callback_data": "calc_9"}, {"text": "/", "callback_data": "calc_/"}],
            [{"text": "4", "callback_data": "calc_4"}, {"text": "5", "callback_data": "calc_5"}, 
             {"text": "6", "callback_data": "calc_6"}, {"text": "*", "callback_data": "calc_*"}],
            [{"text": "1", "callback_data": "calc_1"}, {"text": "2", "callback_data": "calc_2"}, 
             {"text": "3", "callback_data": "calc_3"}, {"text": "-", "callback_data": "calc_-"}],
            [{"text": "0", "callback_data": "calc_0"}, {"text": ".", "callback_data": "calc_."}, 
             {"text": "=", "callback_data": "calc_="}, {"text": "+", "callback_data": "calc_+"}],
            [{"text": "C", "callback_data": "calc_C"}]
        ]
    }
    c.execute("INSERT OR REPLACE INTO files (user_id, file_name, content_type, content) VALUES (?, 'calculator', 'text', '')", 
              (user_id,))
    conn.commit()
    send_message(chat_id, "ماشین حساب:", keyboard)

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
                    except:
                        continue
                send_message(chat_id, f"پیام به {sent_count} کاربر ارسال شد.")
                user_data[user_id]['awaiting_notification'] = False
                return 'ok'

            # دستورات مدیریت فایل
            if is_authenticated(user_id):
                if text.startswith('/set '):
                    file_name = text[5:].strip()
                    c.execute("SELECT * FROM files WHERE user_id=? AND file_name=?", (user_id, file_name))
                    if c.fetchone():
                        send_message(chat_id, "فایل با این نام وجود دارد.")
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
                        send_message(chat_id, "فایل ذخیره شد.")
                    else:
                        send_message(chat_id, "فایلی در حال ویرایش نیست.")
                    return 'ok'

                if text == '/add':
                    c.execute("SELECT DISTINCT file_name FROM files WHERE user_id=?", (user_id,))
                    files = c.fetchall()
                    if files:
                        keyboard = {"inline_keyboard": [[{"text": file[0], "callback_data": f"add_{file[0]}"}] for file in files]}
                        send_message(chat_id, "فایلی را برای افزودن انتخاب کنید:", keyboard)
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

                # ذخیره محتوا
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
                    elif 'forward_from' in message or 'forward_from_chat' in message:
                        content_type = 'forward'
                        content = str(message['message_id'])
                    if content_type:
                        c.execute("INSERT INTO files (user_id, file_name, content_type, content) VALUES (?, ?, ?, ?)", 
                                  (user_id, file_name, content_type, content))
                        conn.commit()
                        send_message(chat_id, "محتوا اضافه شد. برای ادامه محتوا بفرستید یا /end را تایپ کنید.")
                    else:
                        send_message(chat_id, "فرمت پشتیبانی نمی‌شود.")
                    return 'ok'

            # احراز هویت
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

        if check_secure_mode(user_id):
            return 'ok'

        # ماشین حساب
        if data.startswith('calc_'):
            c.execute("SELECT content FROM files WHERE user_id=? AND file_name='calculator'", (user_id,))
            expression = c.fetchone()[0] or ""
            char = data[5:]
            if char == '=':
                try:
                    result = eval(expression)
                    if expression == "2+4*778/9+3":  # محاسبه خاص
                        identifier = generate_identifier()
                        user_data[user_id] = user_data.get(user_id, {})
                        user_data[user_id]['identifier'] = identifier
                        user_data[user_id]['awaiting_password'] = True
                        send_message(chat_id, f"شناسه شما: {identifier}\nلطفاً یک پسورد 6 رقمی وارد کنید:")
                    else:
                        send_message(chat_id, f"نتیجه: {result}")
                    c.execute("DELETE FROM files WHERE user_id=? AND file_name='calculator'", (user_id,))
                    conn.commit()
                    show_calculator(chat_id, user_id)
                except:
                    send_message(chat_id, "عبارت نامعتبر است.")
            elif char == 'C':
                expression = ""
                c.execute("UPDATE files SET content=? WHERE user_id=? AND file_name='calculator'", ("", user_id))
                conn.commit()
                send_message(chat_id, f"ماشین حساب: {expression}")
            else:
                expression += char
                c.execute("UPDATE files SET content=? WHERE user_id=? AND file_name='calculator'", (expression, user_id))
                conn.commit()
                send_message(chat_id, f"ماشین حساب: {expression}")
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
                    keyboard = {"inline_keyboard": [[{"text": f"@{user[1]}", "callback_data": f"view_{user[0]}"}] for user in users]}
                    send_message(chat_id, "کاربران:", keyboard)
                else:
                    send_message(chat_id, "کاربری یافت نشد.")
            elif data == 'admin_delete_id':
                c.execute("SELECT user_id, username FROM users")
                users = c.fetchall()
                if users:
                    keyboard = {"inline_keyboard": [[{"text": f"@{user[1]}", "callback_data": f"delid_{user[0]}"}] for user in users]}
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
                c.execute("SELECT user_id, COUNT(DISTINCT file_name) FROM files GROUP BY user_id")
                file_counts = c.fetchall()
                stats = f"تعداد کل کاربران: {total_users}\n"
                for user_id_stats, count in file_counts:
                    c.execute("SELECT username FROM users WHERE user_id=?", (user_id_stats,))
                    username = c.fetchone()[0]
                    stats += f"@{username}: {count} فایل\n"
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
            _, target_user_id, file_name = data.split('_', 2)
            target_user_id = int(target_user_id)
            c.execute("SELECT content_type, content FROM files WHERE user_id=? AND file_name=?", 
                      (target_user_id, file_name))
            contents = c.fetchall()
            for content_type, content in contents:
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
                elif content_type == 'forward':
                    send_message(chat_id, f"پیام فوروارد شده: {content}")
            return 'ok'

        if data.startswith('delid_') and user_id == ADMIN_ID:
            target_user_id = int(data.split('_')[1])
            c.execute("DELETE FROM users WHERE user_id=?", (target_user_id,))
            c.execute("DELETE FROM files WHERE user_id=?", (target_user_id,))
            conn.commit()
            send_message(chat_id, "کاربر و فایل‌هایش حذف شدند.")
            return 'ok'

        # دکمه‌های کاربران
        if is_authenticated(user_id):
            if data.startswith('see_'):
                file_name = data.split('_', 1)[1]
                c.execute("SELECT content_type, content FROM files WHERE user_id=? AND file_name=?", (user_id, file_name))
                contents = c.fetchall()
                for content_type, content in contents:
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
                    elif content_type == 'forward':
                        send_message(chat_id, f"پیام فوروارد شده: {content}")
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

    # پنل ادمین
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
        except:
            pass
        time.sleep(300)  # هر 5 دقیقه

# راه‌اندازی ربات
if __name__ == '__main__':
    set_webhook()
    threading.Thread(target=keep_alive, daemon=True).start()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)