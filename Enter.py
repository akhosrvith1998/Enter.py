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

# --- Configuration ---
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = "8198317562:AAG2sH5sKB6xwjy5nu3CoOY9XB_dupKVWKU"  # توکن ربات خود را اینجا جایگزین کنید
ADMIN_ID = 7824772776  # شناسه تلگرام ادمین خود را اینجا جایگزین کنید
WEBHOOK_URL = "https://enter-py.onrender.com/webhook"  # آدرس Render خود را اینجا جایگزین کنید
API_URL = f"https://api.telegram.org/bot{TOKEN}/"

app = Flask(__name__)

# Global state (for temporary user data, consider persisting this in a real app)
secure_mode = False
# user_data اکنون عبارت ماشین حساب را برای سرعت بیشتر در حافظه ذخیره می‌کند
user_data = {}  # حالت‌های انتظار، شناسه‌های پیام ماشین حساب، و عبارات ماشین حساب را ذخیره می‌کند

# --- Database Setup ---
conn = sqlite3.connect('database.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS users
             (id INTEGER PRIMARY KEY, user_id INTEGER UNIQUE, username TEXT, identifier TEXT, password TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS files
             (id INTEGER PRIMARY KEY, user_id INTEGER, file_name TEXT, content_type TEXT, content TEXT)''')
conn.commit()

# --- Helper Functions (Telegram API Interactions) ---
def _send_telegram_request(method, payload):
    """تابع عمومی برای ارسال درخواست‌ها به API تلگرام."""
    try:
        response = requests.post(f"{API_URL}{method}", json=payload)
        response.raise_for_status()  # برای پاسخ‌های ناموفق (4xx یا 5xx) یک HTTPError ایجاد می‌کند
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"خطا در درخواست API تلگرام ({method}): {e}")
        return None

def send_message(chat_id, text, reply_markup=None):
    """ارسال یک پیام متنی به کاربر."""
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    }
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    return _send_telegram_request("sendMessage", payload)

def edit_message_text(chat_id, message_id, text, reply_markup=None):
    """ویرایش یک پیام موجود."""
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": "Markdown"
    }
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    return _send_telegram_request("editMessageText", payload)

def delete_message(chat_id, message_id):
    """حذف یک پیام."""
    payload = {"chat_id": chat_id, "message_id": message_id}
    return _send_telegram_request("deleteMessage", payload)

def send_photo(chat_id, photo, caption=None):
    """ارسال یک عکس."""
    payload = {"chat_id": chat_id, "photo": photo}
    if caption:
        payload["caption"] = caption
    return _send_telegram_request("sendPhoto", payload)

def send_video(chat_id, video, caption=None):
    """ارسال یک ویدیو."""
    payload = {"chat_id": chat_id, "video": video}
    if caption:
        payload["caption"] = caption
    return _send_telegram_request("sendVideo", payload)

def send_audio(chat_id, audio, caption=None):
    """ارسال یک فایل صوتی."""
    payload = {"chat_id": chat_id, "audio": audio}
    if caption:
        payload["caption"] = caption
    return _send_telegram_request("sendAudio", payload)

def send_document(chat_id, document, caption=None):
    """ارسال یک سند."""
    payload = {"chat_id": chat_id, "document": document}
    if caption:
        payload["caption"] = caption
    return _send_telegram_request("sendDocument", payload)

def send_sticker(chat_id, sticker):
    """ارسال یک استیکر."""
    payload = {"chat_id": chat_id, "sticker": sticker}
    return _send_telegram_request("sendSticker", payload)

def send_voice(chat_id, voice):
    """ارسال یک پیام صوتی."""
    payload = {"chat_id": chat_id, "voice": voice}
    return _send_telegram_request("sendVoice", payload)

def send_video_note(chat_id, video_note):
    """ارسال یک پیام ویدیویی دایره‌ای."""
    payload = {"chat_id": chat_id, "video_note": video_note}
    return _send_telegram_request("sendVideoNote", payload)

def send_location(chat_id, latitude, longitude):
    """ارسال یک موقعیت مکانی."""
    payload = {"chat_id": chat_id, "latitude": latitude, "longitude": longitude}
    return _send_telegram_request("sendLocation", payload)

def send_contact(chat_id, phone_number, first_name, last_name=None):
    """ارسال یک مخاطب."""
    payload = {"chat_id": chat_id, "phone_number": phone_number, "first_name": first_name}
    if last_name:
        payload["last_name"] = last_name
    return _send_telegram_request("sendContact", payload)

def create_inline_keyboard(buttons):
    """یک کیبورد اینلاین ایجاد می‌کند."""
    return {"inline_keyboard": buttons}

# --- Helper Functions (Application Logic) ---
def generate_identifier():
    """یک شناسه تصادفی با 6 حرف بزرگ، 5 حرف کوچک و 7 عدد تولید می‌کند."""
    uppercase = ''.join(random.choices(string.ascii_uppercase, k=6))
    lowercase = ''.join(random.choices(string.ascii_lowercase, k=5))
    digits = ''.join(random.choices(string.digits, k=7))
    all_chars = uppercase + lowercase + digits
    return ''.join(random.sample(all_chars, len(all_chars)))

def check_secure_mode(user_id):
    """بررسی می‌کند که آیا حالت امنیتی فعال است و کاربر ادمین نیست."""
    global secure_mode
    return secure_mode and user_id != ADMIN_ID

def is_authenticated(user_id):
    """بررسی می‌کند که آیا کاربر احراز هویت شده است."""
    return user_data.get(user_id, {}).get('authenticated', False)

# --- Database Interaction Functions ---
def get_user_by_id(user_id):
    """یک کاربر را از دیتابیس بر اساس user_id بازیابی می‌کند."""
    c.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    return c.fetchone()

def get_user_by_credentials(identifier, password):
    """یک کاربر را از دیتابیس بر اساس شناسه و رمز عبور بازیابی می‌کند."""
    c.execute("SELECT user_id FROM users WHERE identifier=? AND password=?", (identifier, password))
    return c.fetchone()

def add_user(user_id, username, identifier, password):
    """یک کاربر جدید به دیتابیس اضافه می‌کند."""
    c.execute("INSERT INTO users (user_id, username, identifier, password) VALUES (?, ?, ?, ?)",
              (user_id, username, identifier, password))
    conn.commit()

def delete_user_and_files(user_id):
    """یک کاربر و تمام فایل‌های مرتبط با او را از دیتابیس حذف می‌کند."""
    c.execute("DELETE FROM users WHERE user_id=?", (user_id,))
    c.execute("DELETE FROM files WHERE user_id=?", (user_id,))
    conn.commit()

def get_files_by_user(user_id):
    """نام‌های فایل‌های منحصر به فرد را برای یک کاربر مشخص بازیابی می‌کند."""
    c.execute("SELECT DISTINCT file_name FROM files WHERE user_id=?", (user_id,))
    return c.fetchall()

def get_file_content(user_id, file_name):
    """تمام بخش‌های محتوا را برای یک فایل خاص از یک کاربر بازیابی می‌کند."""
    c.execute("SELECT content_type, content FROM files WHERE user_id=? AND file_name=?",
              (user_id, file_name))
    return c.fetchall()

def add_file_content(user_id, file_name, content_type, content):
    """محتوا را به یک فایل برای یک کاربر اضافه می‌کند."""
    c.execute("INSERT INTO files (user_id, file_name, content_type, content) VALUES (?, ?, ?, ?)",
              (user_id, file_name, content_type, content))
    conn.commit()

def delete_file(user_id, file_name):
    """یک فایل مشخص را برای یک کاربر حذف می‌کند."""
    c.execute("DELETE FROM files WHERE user_id=? AND file_name=?", (user_id, file_name))
    conn.commit()

def delete_all_files_for_user(user_id):
    """تمام فایل‌ها را برای یک کاربر مشخص حذف می‌کند."""
    c.execute("DELETE FROM files WHERE user_id=?", (user_id,))
    conn.commit()

# --- Calculator Logic ---
def show_calculator(chat_id, user_id, message_id=None):
    """پنل ماشین حساب 17 دکمه‌ای را نمایش یا به‌روزرسانی می‌کند."""
    # تغییر '/' به '÷' برای نمایش، منطق داخلی همچنان '/' است
    keyboard = create_inline_keyboard([
        [{"text": "7", "callback_data": "calc_7"}, {"text": "8", "callback_data": "calc_8"},
         {"text": "9", "callback_data": "calc_9"}, {"text": "÷", "callback_data": "calc_/"}], # تغییر به ÷
        [{"text": "4", "callback_data": "calc_4"}, {"text": "5", "callback_data": "calc_5"},
         {"text": "6", "callback_data": "calc_6"}, {"text": "*", "callback_data": "calc_*}"}],
        [{"text": "1", "callback_data": "calc_1"}, {"text": "2", "callback_data": "calc_2"},
         {"text": "3", "callback_data": "calc_3"}, {"text": "-", "callback_data": "calc_-"}],
        [{"text": "0", "callback_data": "calc_0"}, {"text": ".", "callback_data": "calc_."},
         {"text": "=", "callback_data": "calc_="}, {"text": "+", "callback_data": "calc_+"}],
        [{"text": "C", "callback_data": "calc_C"}]
    ])

    # دریافت عبارت فعلی از user_data در حافظه
    expression = user_data.setdefault(user_id, {}).get('calculator_expression', '')

    if message_id:
        edit_message_text(chat_id, message_id, f"ماشین حساب: {expression}", keyboard)
    else:
        response = send_message(chat_id, f"ماشین حساب: {expression}", keyboard)
        if response and response.get('ok'):
            message_id = response['result']['message_id']
            user_data[user_id]['calculator_message_id'] = message_id
        else:
            logger.error(f"خطا در ارسال پیام اولیه ماشین حساب: {response}")

def handle_calculator_callback(chat_id, user_id, data):
    """کلیک‌های دکمه ماشین حساب را مدیریت می‌کند."""
    # دریافت عبارت فعلی از user_data در حافظه
    expression = user_data.setdefault(user_id, {}).get('calculator_expression', '')
    char = data[5:] # این کاراکتر واقعی است، مثلاً '7', '+', '/'

    calc_message_id = user_data.get(user_id, {}).get('calculator_message_id')

    # اعتبارسنجی اولیه برای عملگرها برای جلوگیری از عملگرهای متوالی (به جز منفی تک‌عضوی)
    operators = ['+', '-', '*', '/']
    if char in operators and expression and expression[-1] in operators and char != '-':
        # اگر کاراکتر فعلی عملگر و کاراکتر قبلی هم عملگر باشد (و منفی تک‌عضوی نباشد)، آن را جایگزین می‌کند
        expression = expression[:-1] + char
    elif char == '.' and '.' in expression.split(operators[-1] if operators[-1] in expression else '+')[::-1][0]:
        # جلوگیری از چندین نقطه در یک عدد
        pass
    else:
        expression += char

    if char == '=':
        try:
            # توالی خاص برای تولید شناسه، ساده شده به '9999='
            if expression.strip() == "9999=": # بررسی کل عبارت شامل '='
                identifier = generate_identifier()
                user_data.setdefault(user_id, {})['identifier'] = identifier
                user_data[user_id]['awaiting_password'] = True
                send_message(chat_id, f"شناسه شما: {identifier}\nلطفاً یک پسورد 6 رقمی عددی وارد کنید:")
                if calc_message_id:
                    delete_message(chat_id, calc_message_id)
                    user_data[user_id].pop('calculator_message_id', None)
                user_data[user_id]['calculator_expression'] = "" # پاک کردن عبارت پس از محاسبه خاص
            else:
                # ارزیابی عبارت، حذف '=' انتهایی
                result = eval(expression.rstrip('='))
                send_message(chat_id, f"نتیجه: {result}")
                user_data[user_id]['calculator_expression'] = ""  # پاک کردن عبارت پس از محاسبه عادی
                if calc_message_id:
                    show_calculator(chat_id, user_id, calc_message_id)
                else:
                    show_calculator(chat_id, user_id)
        except (SyntaxError, ZeroDivisionError, TypeError, NameError) as e:
            logger.error(f"خطای ماشین حساب برای کاربر {user_id}: {e}")
            send_message(chat_id, "عبارت نامعتبر است. لطفاً ورودی را بررسی کنید.")
            user_data[user_id]['calculator_expression'] = ""  # پاک کردن عبارت در صورت خطا
            if calc_message_id:
                show_calculator(chat_id, user_id, calc_message_id)
            else:
                show_calculator(chat_id, user_id)
        except Exception as e:
            logger.error(f"خطای غیرمنتظره ماشین حساب برای کاربر {user_id}: {e}")
            send_message(chat_id, "خطای ناشناخته در ماشین حساب رخ داد.")
            user_data[user_id]['calculator_expression'] = ""  # پاک کردن عبارت در صورت خطا
            if calc_message_id:
                show_calculator(chat_id, user_id, calc_message_id)
            else:
                show_calculator(chat_id, user_id)

    elif char == 'C':
        user_data[user_id]['calculator_expression'] = "" # پاک کردن عبارت
        if calc_message_id:
            show_calculator(chat_id, user_id, calc_message_id)
        else:
            show_calculator(chat_id, user_id)
    else:
        # به‌روزرسانی عبارت در user_data
        user_data[user_id]['calculator_expression'] = expression
        if calc_message_id:
            show_calculator(chat_id, user_id, calc_message_id)
        else:
            show_calculator(chat_id, user_id)

# --- Message Handlers ---
def handle_start_command(chat_id, user_id, username):
    """دستور /start را مدیریت می‌کند."""
    if get_user_by_id(user_id):
        send_message(chat_id, "شما قبلاً ثبت‌نام کرده‌اید. شناسه و پسورد خود را ارسال کنید: <شناسه> <پسورد>")
    else:
        send_message(chat_id, "برای ثبت‌نام، از ماشین حساب استفاده کنید و '9999=' را محاسبه کنید.")
        show_calculator(chat_id, user_id)

def handle_calculator_command(chat_id, user_id):
    """دستور /calculator را مدیریت می‌کند."""
    if is_authenticated(user_id):
        show_calculator(chat_id, user_id)
    else:
        send_message(chat_id, "لطفاً ابتدا احراز هویت کنید.")

def handle_thanks_command(chat_id, user_id):
    """دستور /thanks را مدیریت می‌کند (فقط ادمین)."""
    global secure_mode
    if user_id == ADMIN_ID:
        secure_mode = True
        send_message(chat_id, "ربات در حالت امنیتی قرار گرفت.")

def handle_admin_reactivation(chat_id, user_id, text):
    """توالی فعال‌سازی مجدد ادمین را مدیریت می‌کند."""
    global secure_mode
    if user_id == ADMIN_ID:
        if text == "88077413Xcph4":
            user_data.setdefault(user_id, {})['awaiting_hi'] = True
            send_message(chat_id, "لطفاً 'Hi' را تایپ کنید.")
            return True
        elif user_data.get(user_id, {}).get('awaiting_hi', False) and text == "Hi":
            secure_mode = False
            send_message(chat_id, "ربات فعال شد.")
            user_data[user_id]['awaiting_hi'] = False
            # پنل ادمین را بلافاصله پس از فعال‌سازی نمایش می‌دهد
            show_admin_panel(chat_id)
            return True
    return False

def handle_password_entry(chat_id, user_id, username, text):
    """ورود رمز عبور را در طول ثبت‌نام مدیریت می‌کند."""
    if user_data.get(user_id, {}).get('awaiting_password', False):
        if len(text) == 6 and text.isdigit():
            identifier = user_data[user_id]['identifier']
            add_user(user_id, username, identifier, text)
            send_message(chat_id, "ثبت‌نام با موفقیت انجام شد. برای ورود از شناسه و پسورد استفاده کنید.")
            user_data[user_id]['awaiting_password'] = False
            user_data[user_id]['identifier'] = None
        else:
            send_message(chat_id, "لطفاً یک پسورد 6 رقمی عددی وارد کنید.")
        return True
    return False

def handle_admin_user_id_assignment(chat_id, user_id, text):
    """تخصیص user ID توسط ادمین به یک شناسه جدید را مدیریت می‌کند."""
    if user_data.get(user_id, {}).get('awaiting_user_id', False) and user_id == ADMIN_ID:
        try:
            target_user_id = int(text)
            identifier = user_data[user_id]['new_identifier']
            target_username = f"user_{target_user_id}"
            add_user(target_user_id, target_username, identifier, "") # رمز عبور می‌تواند برای شناسه‌های ایجاد شده توسط ادمین خالی باشد
            send_message(chat_id, f"شناسه {identifier} به کاربر {target_user_id} تخصیص یافت.")
            user_data[user_id]['awaiting_user_id'] = False
            user_data[user_id]['new_identifier'] = None
        except ValueError:
            send_message(chat_id, "لطفاً شناسه عددی معتبر وارد کنید.")
        return True
    return False

def handle_admin_notification_text(chat_id, user_id, text):
    """ارسال پیام نوتیفیکیشن توسط ادمین به همه کاربران را مدیریت می‌کند."""
    if user_data.get(user_id, {}).get('awaiting_notification', False) and user_id == ADMIN_ID:
        c.execute("SELECT user_id FROM users")
        users = c.fetchall()
        sent_count = 0
        for user in users:
            try:
                send_message(user[0], text)
                sent_count += 1
            except Exception as e:
                logger.error(f"خطا در ارسال نوتیفیکیشن به کاربر {user[0]}: {e}")
        send_message(chat_id, f"پیام به {sent_count} کاربر ارسال شد.")
        user_data[user_id]['awaiting_notification'] = False
        return True
    return False

def handle_file_set_command(chat_id, user_id, text):
    """دستور /set را برای فایل‌ها مدیریت می‌کند."""
    file_name = text[5:].strip()
    if get_file_content(user_id, file_name):
        send_message(chat_id, "فایل با این نام وجود دارد. برای افزودن محتوا به آن از دستور /add استفاده کنید.")
    else:
        user_data.setdefault(user_id, {})['file_name'] = file_name
        user_data[user_id]['awaiting_content'] = True
        send_message(chat_id, "محتوا را ارسال کنید.")

def handle_file_end_command(chat_id, user_id):
    """دستور /end را برای ورود محتوای فایل مدیریت می‌کند."""
    if user_data.get(user_id, {}).get('awaiting_content', False):
        user_data[user_id]['file_name'] = None
        user_data[user_id]['awaiting_content'] = False
        send_message(chat_id, "پایان ثبت محتوا.")
    else:
        send_message(chat_id, "فایلی در حال ویرایش نیست.")

def handle_file_add_command(chat_id, user_id):
    """دستور /add را برای افزودن محتوا به فایل‌های موجود مدیریت می‌کند."""
    files = get_files_by_user(user_id)
    if files:
        keyboard_buttons = [[{"text": file[0], "callback_data": f"add_{file[0]}"}] for file in files]
        send_message(chat_id, "فایلی را برای افزودن محتوا انتخاب کنید:", create_inline_keyboard(keyboard_buttons))
    else:
        send_message(chat_id, "فایلی یافت نشد.")

def handle_file_see_command(chat_id, user_id):
    """دستور /see را برای مشاهده محتوای فایل مدیریت می‌کند."""
    files = get_files_by_user(user_id)
    if files:
        keyboard_buttons = [[{"text": file[0], "callback_data": f"see_{file[0]}"}] for file in files]
        send_message(chat_id, "فایل‌های شما:", create_inline_keyboard(keyboard_buttons))
    else:
        send_message(chat_id, "فایلی یافت نشد.")

def handle_file_del_command(chat_id, user_id):
    """دستور /del را برای حذف یک فایل خاص مدیریت می‌کند."""
    files = get_files_by_user(user_id)
    if files:
        keyboard_buttons = [[{"text": file[0], "callback_data": f"del_{file[0]}"}] for file in files]
        send_message(chat_id, "فایلی را برای حذف انتخاب کنید:", create_inline_keyboard(keyboard_buttons))
    else:
        send_message(chat_id, "فایلی یافت نشد.")

def handle_file_delete_all_command(chat_id):
    """دستور /delete را برای حذف تمام فایل‌های کاربر مدیریت می‌کند."""
    keyboard = create_inline_keyboard([
        [{"text": "بله", "callback_data": "delete_yes"}, {"text": "خیر", "callback_data": "delete_no"}]
    ])
    send_message(chat_id, "آیا مطمئن هستید که می‌خواهید همه فایل‌ها را حذف کنید؟", keyboard)

def handle_awaiting_content_input(chat_id, user_id, message):
    """پیام‌های ورودی را هنگام انتظار برای محتوای فایل مدیریت می‌کند."""
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
        elif 'sticker' in message:
            content_type = 'sticker'
            content = message['sticker']['file_id']
        elif 'voice' in message:
            content_type = 'voice'
            content = message['voice']['file_id']
        elif 'video_note' in message:
            content_type = 'video_note'
            content = message['video_note']['file_id']
        elif 'location' in message:
            content_type = 'location'
            content = json.dumps({'latitude': message['location']['latitude'], 'longitude': message['location']['longitude']})
        elif 'contact' in message:
            content_type = 'contact'
            contact_data = message['contact']
            content = json.dumps({
                'phone_number': contact_data['phone_number'],
                'first_name': contact_data.get('first_name'),
                'last_name': contact_data.get('last_name')
            })
        elif 'forward_from' in message or 'forward_from_chat' in message:
            content_type = 'forward'
            content = str(message['message_id'])

        if content_type:
            add_file_content(user_id, file_name, content_type, content)
            send_message(chat_id, "محتوا اضافه شد. برای ادامه محتوا بفرستید یا /end را تایپ کنید.")
        else:
            send_message(chat_id, "فرمت پشتیبانی نمی‌شود.")
        return True
    return False

def handle_authentication_attempt(chat_id, user_id, text):
    """تلاش‌های احراز هویت کاربر را مدیریت می‌کند."""
    if not user_data.get(user_id, {}).get('awaiting_password', False):
        parts = text.split()
        if len(parts) == 2:
            identifier, password = parts
            user = get_user_by_credentials(identifier, password)
            if user:
                user_data.setdefault(user_id, {})['authenticated'] = True
                send_message(chat_id, "ورود با موفقیت انجام شد.")
            else:
                send_message(chat_id, "شناسه یا پسورد اشتباه است.")
            return True
    return False

# --- Admin Panel Display Function ---
def show_admin_panel(chat_id):
    """کیبورد پنل ادمین را نمایش می‌دهد."""
    keyboard = create_inline_keyboard([
        [{"text": "ایجاد شناسه", "callback_data": "admin_create_id"}],
        [{"text": "مشاهده کاربران", "callback_data": "admin_view_users"}],
        [{"text": "حذف شناسه کاربر", "callback_data": "admin_delete_id"}],
        [{"text": "نوتیفیکیشن", "callback_data": "admin_notify"}],
        [{"text": "آمار", "callback_data": "admin_stats"}]
    ])
    send_message(chat_id, "پنل ادمین:", keyboard)

# --- Callback Query Handlers ---
def handle_admin_panel_callback(chat_id, user_id, data):
    """کلیک‌های دکمه پنل ادمین را مدیریت می‌کند."""
    if user_id == ADMIN_ID:
        if data == 'admin_create_id':
            identifier = generate_identifier()
            user_data.setdefault(user_id, {})['new_identifier'] = identifier
            user_data[user_id]['awaiting_user_id'] = True
            send_message(chat_id, f"شناسه جدید: {identifier}\nشناسه عددی کاربر را ارسال کنید:")
        elif data == 'admin_view_users':
            users = c.execute("SELECT user_id, username FROM users").fetchall()
            if users:
                keyboard_buttons = [[{"text": f"@{user[1]} (ID: {user[0]})", "callback_data": f"view_{user[0]}"}] for user in users]
                send_message(chat_id, "کاربران:", create_inline_keyboard(keyboard_buttons))
            else:
                send_message(chat_id, "کاربری یافت نشد.")
        elif data == 'admin_delete_id':
            users = c.execute("SELECT user_id, username FROM users").fetchall()
            if users:
                keyboard_buttons = [[{"text": f"@{user[1]} (ID: {user[0]})", "callback_data": f"delid_{user[0]}"}] for user in users]
                send_message(chat_id, "کاربر را برای حذف انتخاب کنید:", create_inline_keyboard(keyboard_buttons))
            else:
                send_message(chat_id, "کاربری یافت نشد.")
        elif data == 'admin_notify':
            user_data.setdefault(user_id, {})['awaiting_notification'] = True
            send_message(chat_id, "پیام خود را برای ارسال به همه کاربران وارد کنید:")
        elif data == 'admin_stats':
            total_users = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            users_with_files = c.execute("SELECT user_id, username FROM users").fetchall()

            stats = f"تعداد کل کاربران: {total_users}\n"
            for user_id_stats, username in users_with_files:
                unique_files_count = c.execute("SELECT COUNT(DISTINCT file_name) FROM files WHERE user_id=?", (user_id_stats,)).fetchone()[0]
                total_content_parts = c.execute("SELECT COUNT(*) FROM files WHERE user_id=?", (user_id_stats,)).fetchone()[0]
                stats += f"@{username} (ID: {user_id_stats}): {unique_files_count} فایل منحصر به فرد, {total_content_parts} محتوا\n"
            send_message(chat_id, stats)
        return True
    return False

def handle_admin_view_user_files_callback(chat_id, user_id, data):
    """مدیریت مشاهده فایل‌های یک کاربر خاص توسط ادمین."""
    if user_id == ADMIN_ID:
        target_user_id = int(data.split('_')[1])
        files = get_files_by_user(target_user_id)
        if files:
            keyboard_buttons = [[{"text": file[0], "callback_data": f"admin_see_{target_user_id}_{file[0]}"}] for file in files]
            send_message(chat_id, "فایل‌های کاربر:", create_inline_keyboard(keyboard_buttons))
        else:
            send_message(chat_id, "فایلی یافت نشد.")
        return True
    return False

def handle_admin_see_file_content_callback(chat_id, user_id, data):
    """مدیریت مشاهده محتوای یک فایل خاص توسط ادمین."""
    if user_id == ADMIN_ID:
        # برای مدیریت نام فایل‌هایی که شامل underscore هستند، با 3 بار تقسیم می‌شود
        _, _, target_user_id, file_name = data.split('_', 3)
        target_user_id = int(target_user_id)
        contents = get_file_content(target_user_id, file_name)

        if not contents:
            send_message(chat_id, "محتوایی برای این فایل یافت نشد.")
            return True

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
                logger.error(f"خطا در ارسال محتوای نوع {content_type} برای فایل {file_name} به ادمین {chat_id}: {e}")
                send_message(chat_id, f"خطا در نمایش محتوای نوع {content_type}.")
        return True
    return False

def handle_admin_delete_user_callback(chat_id, user_id, data):
    """مدیریت حذف یک کاربر خاص توسط ادمین."""
    if user_id == ADMIN_ID:
        target_user_id = int(data.split('_')[1])
        delete_user_and_files(target_user_id)
        send_message(chat_id, "کاربر و فایل‌هایش حذف شدند.")
        return True
    return False

def handle_user_see_file_callback(chat_id, user_id, data):
    """مدیریت مشاهده محتوای یک فایل خاص توسط کاربر."""
    if is_authenticated(user_id):
        file_name = data.split('_', 1)[1]
        contents = get_file_content(user_id, file_name)
        if not contents:
            send_message(chat_id, "محتوایی برای این فایل یافت نشد.")
            return True

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
                logger.error(f"خطا در ارسال محتوای نوع {content_type} برای فایل {file_name} به کاربر {chat_id}: {e}")
                send_message(chat_id, f"خطا در نمایش محتوای نوع {content_type}.")
        return True
    return False

def handle_user_add_file_callback(chat_id, user_id, data):
    """مدیریت افزودن محتوا به یک فایل خاص توسط کاربر."""
    if is_authenticated(user_id):
        file_name = data.split('_', 1)[1]
        user_data.setdefault(user_id, {})['file_name'] = file_name
        user_data[user_id]['awaiting_content'] = True
        send_message(chat_id, "محتوا را ارسال کنید.")
        return True
    return False

def handle_user_delete_file_callback(chat_id, user_id, data):
    """مدیریت حذف یک فایل خاص توسط کاربر."""
    if is_authenticated(user_id):
        file_name = data.split('_', 1)[1]
        delete_file(user_id, file_name)
        send_message(chat_id, f"فایل {file_name} حذف شد.")
        return True
    return False

def handle_user_delete_all_files_confirmation(chat_id, user_id, data):
    """مدیریت تأیید یا لغو حذف تمام فایل‌ها توسط کاربر."""
    if is_authenticated(user_id):
        if data == 'delete_yes':
            delete_all_files_for_user(user_id)
            send_message(chat_id, "همه فایل‌ها حذف شدند.")
        elif data == 'delete_no':
            send_message(chat_id, "عملیات لغو شد.")
        return True
    return False

# --- Webhook Endpoint ---
@app.route('/webhook', methods=['POST'])
def webhook():
    """به‌روزرسانی‌ها را از تلگرام دریافت و پردازش می‌کند."""
    update = request.get_json(force=True)

    if 'message' in update:
        message = update['message']
        chat_id = message['chat']['id']
        user_id = message['from']['id']
        username = message['from'].get('username', f"user_{user_id}")
        text = message.get('text', '').strip()

        if check_secure_mode(user_id):
            return 'ok'

        # مدیریت دستور پنل ادمین به صورت جداگانه، زیرا نیازی به احراز هویت ندارد
        if text == '/admin' and user_id == ADMIN_ID:
            show_admin_panel(chat_id)
            return 'ok'

        # ابتدا حالت‌های انتظار را مدیریت می‌کند
        if handle_admin_reactivation(chat_id, user_id, text): return 'ok'
        if handle_password_entry(chat_id, user_id, username, text): return 'ok'
        if handle_admin_user_id_assignment(chat_id, user_id, text): return 'ok'
        if handle_admin_notification_text(chat_id, user_id, text): return 'ok'
        if handle_awaiting_content_input(chat_id, user_id, message): return 'ok'

        # مدیریت دستورات
        if text == '/start':
            handle_start_command(chat_id, user_id, username)
        elif text == '/calculator':
            handle_calculator_command(chat_id, user_id)
        elif text == '/thanks':
            handle_thanks_command(chat_id, user_id)
        elif text.startswith('/set '):
            if is_authenticated(user_id):
                handle_file_set_command(chat_id, user_id, text)
            else:
                send_message(chat_id, "لطفاً ابتدا احراز هویت کنید.")
        elif text == '/end':
            if is_authenticated(user_id):
                handle_file_end_command(chat_id, user_id)
            else:
                send_message(chat_id, "لطفاً ابتدا احراز هویت کنید.")
        elif text == '/add':
            if is_authenticated(user_id):
                handle_file_add_command(chat_id, user_id)
            else:
                send_message(chat_id, "لطفاً ابتدا احراز هویت کنید.")
        elif text == '/see':
            if is_authenticated(user_id):
                handle_file_see_command(chat_id, user_id)
            else:
                send_message(chat_id, "لطفاً ابتدا احراز هویت کنید.")
        elif text == '/del':
            if is_authenticated(user_id):
                handle_file_del_command(chat_id, user_id)
            else:
                send_message(chat_id, "لطفاً ابتدا احراز هویت کنید.")
        elif text == '/delete':
            if is_authenticated(user_id):
                handle_file_delete_all_command(chat_id)
            else:
                send_message(chat_id, "لطفاً ابتدا احراز هویت کنید.")
        else:
            # تلاش برای احراز هویت اگر هیچ دستور/حالت انتظاری مطابقت نداشت
            handle_authentication_attempt(chat_id, user_id, text)

    elif 'callback_query' in update:
        callback = update['callback_query']
        chat_id = callback['message']['chat']['id']
        user_id = callback['from']['id']
        data = callback['data']

        if check_secure_mode(user_id):
            return 'ok'

        if data.startswith('calc_'):
            handle_calculator_callback(chat_id, user_id, data)
        elif data.startswith('admin_'):
            handle_admin_panel_callback(chat_id, user_id, data)
        elif data.startswith('view_'):
            handle_admin_view_user_files_callback(chat_id, user_id, data)
        elif data.startswith('admin_see_'):
            handle_admin_see_file_content_callback(chat_id, user_id, data)
        elif data.startswith('delid_'):
            handle_admin_delete_user_callback(chat_id, user_id, data)
        elif data.startswith('see_'):
            handle_user_see_file_callback(chat_id, user_id, data)
        elif data.startswith('add_'):
            handle_user_add_file_callback(chat_id, user_id, data)
        elif data.startswith('del_'):
            handle_user_delete_file_callback(chat_id, user_id, data)
        elif data in ['delete_yes', 'delete_no']:
            handle_user_delete_all_files_confirmation(chat_id, user_id, data)

    return 'ok'

# --- Bot Initialization ---
def set_webhook():
    """وب‌هوک را برای تلگرام تنظیم می‌کند."""
    try:
        response = requests.post(f"{API_URL}setWebhook", json={"url": WEBHOOK_URL})
        response.raise_for_status()
        logger.info("وب‌هوک با موفقیت تنظیم شد")
    except requests.exceptions.RequestException as e:
        logger.error(f"خطا در تنظیم وب‌هوک: {e}")

def keep_alive():
    """سرویس Render را پینگ می‌کند تا از غیرفعال شدن جلوگیری کند."""
    while True:
        try:
            requests.get(WEBHOOK_URL)
            logger.info("پینگ Keep-alive ارسال شد.")
        except requests.exceptions.RequestException as e:
            logger.error(f"خطا در پینگ Keep-alive: {e}")
        time.sleep(300)  # هر 5 دقیقه

if __name__ == '__main__':
    set_webhook()
    threading.Thread(target=keep_alive, daemon=True).start()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

