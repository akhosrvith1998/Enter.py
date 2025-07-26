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

TOKEN = "8198317562:AAG2sH5sKB6xwjy5nu3CoOY9XB_dupKVWKU"  # Replace with your bot token
ADMIN_ID = 7824772776  # Replace with your Telegram admin ID
WEBHOOK_URL = "https://enter-py.onrender.com/webhook"  # Replace with your Render URL
API_URL = f"https://api.telegram.org/bot{TOKEN}/"

app = Flask(__name__)

# Global state (for temporary user data, consider persisting this in a real app)
secure_mode = False
user_data = {}  # Stores awaiting states and calculator message IDs

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
    """Generic function to send requests to Telegram API."""
    try:
        response = requests.post(f"{API_URL}{method}", json=payload)
        response.raise_for_status()  # Raise an HTTPError for bad responses (4xx or 5xx)
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error during Telegram API request ({method}): {e}")
        return None

def send_message(chat_id, text, reply_markup=None):
    """Sends a text message to the user."""
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    }
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    return _send_telegram_request("sendMessage", payload)

def edit_message_text(chat_id, message_id, text, reply_markup=None):
    """Edits an existing message."""
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
    """Deletes a message."""
    payload = {"chat_id": chat_id, "message_id": message_id}
    return _send_telegram_request("deleteMessage", payload)

def send_photo(chat_id, photo, caption=None):
    """Sends a photo."""
    payload = {"chat_id": chat_id, "photo": photo}
    if caption:
        payload["caption"] = caption
    return _send_telegram_request("sendPhoto", payload)

def send_video(chat_id, video, caption=None):
    """Sends a video."""
    payload = {"chat_id": chat_id, "video": video}
    if caption:
        payload["caption"] = caption
    return _send_telegram_request("sendVideo", payload)

def send_audio(chat_id, audio, caption=None):
    """Sends an audio file."""
    payload = {"chat_id": chat_id, "audio": audio}
    if caption:
        payload["caption"] = caption
    return _send_telegram_request("sendAudio", payload)

def send_document(chat_id, document, caption=None):
    """Sends a document."""
    payload = {"chat_id": chat_id, "document": document}
    if caption:
        payload["caption"] = caption
    return _send_telegram_request("sendDocument", payload)

def send_sticker(chat_id, sticker):
    """Sends a sticker."""
    payload = {"chat_id": chat_id, "sticker": sticker}
    return _send_telegram_request("sendSticker", payload)

def send_voice(chat_id, voice):
    """Sends a voice message."""
    payload = {"chat_id": chat_id, "voice": voice}
    return _send_telegram_request("sendVoice", payload)

def send_video_note(chat_id, video_note):
    """Sends a video note (circular video)."""
    payload = {"chat_id": chat_id, "video_note": video_note}
    return _send_telegram_request("sendVideoNote", payload)

def send_location(chat_id, latitude, longitude):
    """Sends a location."""
    payload = {"chat_id": chat_id, "latitude": latitude, "longitude": longitude}
    return _send_telegram_request("sendLocation", payload)

def send_contact(chat_id, phone_number, first_name, last_name=None):
    """Sends a contact."""
    payload = {"chat_id": chat_id, "phone_number": phone_number, "first_name": first_name}
    if last_name:
        payload["last_name"] = last_name
    return _send_telegram_request("sendContact", payload)

def create_inline_keyboard(buttons):
    """Creates an inline keyboard markup."""
    return {"inline_keyboard": buttons}

# --- Helper Functions (Application Logic) ---
def generate_identifier():
    """Generates a random identifier with 6 uppercase, 5 lowercase, and 7 digits."""
    uppercase = ''.join(random.choices(string.ascii_uppercase, k=6))
    lowercase = ''.join(random.choices(string.ascii_lowercase, k=5))
    digits = ''.join(random.choices(string.digits, k=7))
    all_chars = uppercase + lowercase + digits
    return ''.join(random.sample(all_chars, len(all_chars)))

def check_secure_mode(user_id):
    """Checks if secure mode is active and the user is not the admin."""
    global secure_mode
    return secure_mode and user_id != ADMIN_ID

def is_authenticated(user_id):
    """Checks if the user is authenticated."""
    return user_data.get(user_id, {}).get('authenticated', False)

# --- Database Interaction Functions ---
def get_user_by_id(user_id):
    """Retrieves a user from the database by user_id."""
    c.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    return c.fetchone()

def get_user_by_credentials(identifier, password):
    """Retrieves a user from the database by identifier and password."""
    c.execute("SELECT user_id FROM users WHERE identifier=? AND password=?", (identifier, password))
    return c.fetchone()

def add_user(user_id, username, identifier, password):
    """Adds a new user to the database."""
    c.execute("INSERT INTO users (user_id, username, identifier, password) VALUES (?, ?, ?, ?)",
              (user_id, username, identifier, password))
    conn.commit()

def delete_user_and_files(user_id):
    """Deletes a user and all their associated files from the database."""
    c.execute("DELETE FROM users WHERE user_id=?", (user_id,))
    c.execute("DELETE FROM files WHERE user_id=?", (user_id,))
    conn.commit()

def get_files_by_user(user_id):
    """Retrieves distinct file names for a given user."""
    c.execute("SELECT DISTINCT file_name FROM files WHERE user_id=?", (user_id,))
    return c.fetchall()

def get_file_content(user_id, file_name):
    """Retrieves all content parts for a specific file of a user."""
    c.execute("SELECT content_type, content FROM files WHERE user_id=? AND file_name=?",
              (user_id, file_name))
    return c.fetchall()

def add_file_content(user_id, file_name, content_type, content):
    """Adds content to a file for a user."""
    c.execute("INSERT INTO files (user_id, file_name, content_type, content) VALUES (?, ?, ?, ?)",
              (user_id, file_name, content_type, content))
    conn.commit()

def delete_file(user_id, file_name):
    """Deletes a specific file for a user."""
    c.execute("DELETE FROM files WHERE user_id=? AND file_name=?", (user_id, file_name))
    conn.commit()

def delete_all_files_for_user(user_id):
    """Deletes all files for a specific user."""
    c.execute("DELETE FROM files WHERE user_id=?", (user_id,))
    conn.commit()

def get_calculator_expression(user_id):
    """Retrieves the current calculator expression for a user."""
    c.execute("SELECT content FROM files WHERE user_id=? AND file_name='calculator'", (user_id,))
    result = c.fetchone()
    return result[0] if result else ""

def update_calculator_expression(user_id, expression):
    """Updates the calculator expression for a user."""
    c.execute("INSERT OR REPLACE INTO files (user_id, file_name, content_type, content) VALUES (?, 'calculator', 'text', ?)",
              (user_id, expression))
    conn.commit()

# --- Calculator Logic ---
def show_calculator(chat_id, user_id, message_id=None):
    """Displays or updates the 17-button calculator panel."""
    keyboard = create_inline_keyboard([
        [{"text": "7", "callback_data": "calc_7"}, {"text": "8", "callback_data": "calc_8"},
         {"text": "9", "callback_data": "calc_9"}, {"text": "/", "callback_data": "calc_/"}],
        [{"text": "4", "callback_data": "calc_4"}, {"text": "5", "callback_data": "calc_5"},
         {"text": "6", "callback_data": "calc_6"}, {"text": "*", "callback_data": "calc_*}"}], # Corrected: calc_*
        [{"text": "1", "callback_data": "calc_1"}, {"text": "2", "callback_data": "calc_2"},
         {"text": "3", "callback_data": "calc_3"}, {"text": "-", "callback_data": "calc_-"}],
        [{"text": "0", "callback_data": "calc_0"}, {"text": ".", "callback_data": "calc_."},
         {"text": "=", "callback_data": "calc_="}, {"text": "+", "callback_data": "calc_+"}],
        [{"text": "C", "callback_data": "calc_C"}]
    ])

    expression = get_calculator_expression(user_id)

    if message_id:
        edit_message_text(chat_id, message_id, f"ماشین حساب: {expression}", keyboard)
    else:
        response = send_message(chat_id, f"ماشین حساب: {expression}", keyboard)
        if response and response.get('ok'):
            message_id = response['result']['message_id']
            user_data.setdefault(user_id, {})['calculator_message_id'] = message_id
        else:
            logger.error(f"Error sending initial calculator message: {response}")

def handle_calculator_callback(chat_id, user_id, data):
    """Handles calculator button presses."""
    expression = get_calculator_expression(user_id)
    char = data[5:]
    calc_message_id = user_data.get(user_id, {}).get('calculator_message_id')

    if char == '=':
        try:
            result = eval(expression)
            if expression == "2+4*778/9+3":
                identifier = generate_identifier()
                user_data.setdefault(user_id, {})['identifier'] = identifier
                user_data[user_id]['awaiting_password'] = True
                send_message(chat_id, f"شناسه شما: {identifier}\nلطفاً یک پسورد 6 رقمی عددی وارد کنید:")
                if calc_message_id:
                    delete_message(chat_id, calc_message_id)
                    user_data[user_id].pop('calculator_message_id', None)
            else:
                send_message(chat_id, f"نتیجه: {result}")
                update_calculator_expression(user_id, "")  # Reset calculator
                if calc_message_id:
                    show_calculator(chat_id, user_id, calc_message_id)
                else:
                    show_calculator(chat_id, user_id)
        except Exception as e:
            logger.error(f"Calculator error for user {user_id}: {e}")
            send_message(chat_id, "عبارت نامعتبر است.")
            update_calculator_expression(user_id, "")  # Reset on error
            if calc_message_id:
                show_calculator(chat_id, user_id, calc_message_id)
            else:
                show_calculator(chat_id, user_id)
    elif char == 'C':
        update_calculator_expression(user_id, "")
        if calc_message_id:
            show_calculator(chat_id, user_id, calc_message_id)
        else:
            show_calculator(chat_id, user_id)
    else:
        expression += char
        update_calculator_expression(user_id, expression)
        if calc_message_id:
            show_calculator(chat_id, user_id, calc_message_id)
        else:
            show_calculator(chat_id, user_id)

# --- Message Handlers ---
def handle_start_command(chat_id, user_id, username):
    """Handles the /start command."""
    if get_user_by_id(user_id):
        send_message(chat_id, "شما قبلاً ثبت‌نام کرده‌اید. شناسه و پسورد خود را ارسال کنید: <شناسه> <پسورد>")
    else:
        show_calculator(chat_id, user_id)

def handle_calculator_command(chat_id, user_id):
    """Handles the /calculator command."""
    if is_authenticated(user_id):
        show_calculator(chat_id, user_id)
    else:
        send_message(chat_id, "لطفاً ابتدا احراز هویت کنید.")

def handle_thanks_command(chat_id, user_id):
    """Handles the /thanks command (admin only)."""
    global secure_mode
    if user_id == ADMIN_ID:
        secure_mode = True
        send_message(chat_id, "ربات در حالت امنیتی قرار گرفت.")

def handle_admin_reactivation(chat_id, user_id, text):
    """Handles admin reactivation sequence."""
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
            return True
    return False

def handle_password_entry(chat_id, user_id, username, text):
    """Handles password entry during registration."""
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
    """Handles admin assigning user ID to a new identifier."""
    if user_data.get(user_id, {}).get('awaiting_user_id', False) and user_id == ADMIN_ID:
        try:
            target_user_id = int(text)
            identifier = user_data[user_id]['new_identifier']
            target_username = f"user_{target_user_id}"
            add_user(target_user_id, target_username, identifier, "") # Password can be empty for admin created IDs
            send_message(chat_id, f"شناسه {identifier} به کاربر {target_user_id} تخصیص یافت.")
            user_data[user_id]['awaiting_user_id'] = False
            user_data[user_id]['new_identifier'] = None
        except ValueError:
            send_message(chat_id, "لطفاً شناسه عددی معتبر وارد کنید.")
        return True
    return False

def handle_admin_notification_text(chat_id, user_id, text):
    """Handles admin sending a notification to all users."""
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
        send_message(chat_id, f"پیام به {sent_count} کاربر ارسال شد.")
        user_data[user_id]['awaiting_notification'] = False
        return True
    return False

def handle_file_set_command(chat_id, user_id, text):
    """Handles the /set command for files."""
    file_name = text[5:].strip()
    if get_file_content(user_id, file_name):
        send_message(chat_id, "فایل با این نام وجود دارد. برای افزودن محتوا به آن از دستور /add استفاده کنید.")
    else:
        user_data.setdefault(user_id, {})['file_name'] = file_name
        user_data[user_id]['awaiting_content'] = True
        send_message(chat_id, "محتوا را ارسال کنید.")

def handle_file_end_command(chat_id, user_id):
    """Handles the /end command for file content input."""
    if user_data.get(user_id, {}).get('awaiting_content', False):
        user_data[user_id]['file_name'] = None
        user_data[user_id]['awaiting_content'] = False
        send_message(chat_id, "پایان ثبت محتوا.")
    else:
        send_message(chat_id, "فایلی در حال ویرایش نیست.")

def handle_file_add_command(chat_id, user_id):
    """Handles the /add command to add content to existing files."""
    files = get_files_by_user(user_id)
    if files:
        keyboard_buttons = [[{"text": file[0], "callback_data": f"add_{file[0]}"}] for file in files]
        send_message(chat_id, "فایلی را برای افزودن محتوا انتخاب کنید:", create_inline_keyboard(keyboard_buttons))
    else:
        send_message(chat_id, "فایلی یافت نشد.")

def handle_file_see_command(chat_id, user_id):
    """Handles the /see command to view file contents."""
    files = get_files_by_user(user_id)
    if files:
        keyboard_buttons = [[{"text": file[0], "callback_data": f"see_{file[0]}"}] for file in files]
        send_message(chat_id, "فایل‌های شما:", create_inline_keyboard(keyboard_buttons))
    else:
        send_message(chat_id, "فایلی یافت نشد.")

def handle_file_del_command(chat_id, user_id):
    """Handles the /del command to delete a specific file."""
    files = get_files_by_user(user_id)
    if files:
        keyboard_buttons = [[{"text": file[0], "callback_data": f"del_{file[0]}"}] for file in files]
        send_message(chat_id, "فایلی را برای حذف انتخاب کنید:", create_inline_keyboard(keyboard_buttons))
    else:
        send_message(chat_id, "فایلی یافت نشد.")

def handle_file_delete_all_command(chat_id):
    """Handles the /delete command to delete all user files."""
    keyboard = create_inline_keyboard([
        [{"text": "بله", "callback_data": "delete_yes"}, {"text": "خیر", "callback_data": "delete_no"}]
    ])
    send_message(chat_id, "آیا مطمئن هستید که می‌خواهید همه فایل‌ها را حذف کنید؟", keyboard)

def handle_awaiting_content_input(chat_id, user_id, message):
    """Handles incoming messages when awaiting file content."""
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
    """Handles user authentication attempts."""
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

# --- Callback Query Handlers ---
def handle_admin_panel_callback(chat_id, user_id, data):
    """Handles admin panel button presses."""
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
    """Handles admin viewing files of a specific user."""
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
    """Handles admin viewing content of a specific file."""
    if user_id == ADMIN_ID:
        # Split by 3 to handle file names with underscores
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
                logger.error(f"Error sending content of type {content_type} for file {file_name} to admin {chat_id}: {e}")
                send_message(chat_id, f"خطا در نمایش محتوای نوع {content_type}.")
        return True
    return False

def handle_admin_delete_user_callback(chat_id, user_id, data):
    """Handles admin deleting a specific user."""
    if user_id == ADMIN_ID:
        target_user_id = int(data.split('_')[1])
        delete_user_and_files(target_user_id)
        send_message(chat_id, "کاربر و فایل‌هایش حذف شدند.")
        return True
    return False

def handle_user_see_file_callback(chat_id, user_id, data):
    """Handles user viewing content of a specific file."""
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
                logger.error(f"Error sending content of type {content_type} for file {file_name} to user {chat_id}: {e}")
                send_message(chat_id, f"خطا در نمایش محتوای نوع {content_type}.")
        return True
    return False

def handle_user_add_file_callback(chat_id, user_id, data):
    """Handles user adding content to a specific file."""
    if is_authenticated(user_id):
        file_name = data.split('_', 1)[1]
        user_data.setdefault(user_id, {})['file_name'] = file_name
        user_data[user_id]['awaiting_content'] = True
        send_message(chat_id, "محتوا را ارسال کنید.")
        return True
    return False

def handle_user_delete_file_callback(chat_id, user_id, data):
    """Handles user deleting a specific file."""
    if is_authenticated(user_id):
        file_name = data.split('_', 1)[1]
        delete_file(user_id, file_name)
        send_message(chat_id, f"فایل {file_name} حذف شد.")
        return True
    return False

def handle_user_delete_all_files_confirmation(chat_id, user_id, data):
    """Handles user confirming or cancelling deletion of all files."""
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
    """Receives and processes updates from Telegram."""
    update = request.get_json(force=True)

    if 'message' in update:
        message = update['message']
        chat_id = message['chat']['id']
        user_id = message['from']['id']
        username = message['from'].get('username', f"user_{user_id}")
        text = message.get('text', '').strip()

        if check_secure_mode(user_id):
            return 'ok'

        # Handle admin panel command separately as it doesn't require authentication
        if text == '/admin' and user_id == ADMIN_ID:
            keyboard = create_inline_keyboard([
                [{"text": "ایجاد شناسه", "callback_data": "admin_create_id"}],
                [{"text": "مشاهده کاربران", "callback_data": "admin_view_users"}],
                [{"text": "حذف شناسه کاربر", "callback_data": "admin_delete_id"}],
                [{"text": "نوتیفیکیشن", "callback_data": "admin_notify"}],
                [{"text": "آمار", "callback_data": "admin_stats"}]
            ])
            send_message(chat_id, "پنل ادمین:", keyboard)
            return 'ok'

        # Handle awaiting states first
        if handle_admin_reactivation(chat_id, user_id, text): return 'ok'
        if handle_password_entry(chat_id, user_id, username, text): return 'ok'
        if handle_admin_user_id_assignment(chat_id, user_id, text): return 'ok'
        if handle_admin_notification_text(chat_id, user_id, text): return 'ok'
        if handle_awaiting_content_input(chat_id, user_id, message): return 'ok'

        # Handle commands
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
            # Attempt authentication if no other command/awaiting state matched
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
    """Sets the webhook for Telegram."""
    try:
        response = requests.post(f"{API_URL}setWebhook", json={"url": WEBHOOK_URL})
        response.raise_for_status()
        logger.info("Webhook set successfully")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error setting webhook: {e}")

def keep_alive():
    """Pings the Render service to prevent idling."""
    while True:
        try:
            requests.get(WEBHOOK_URL)
            logger.info("Keep-alive ping sent.")
        except requests.exceptions.RequestException as e:
            logger.error(f"Error during keep-alive ping: {e}")
        time.sleep(300)  # Every 5 minutes

if __name__ == '__main__':
    set_webhook()
    threading.Thread(target=keep_alive, daemon=True).start()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)