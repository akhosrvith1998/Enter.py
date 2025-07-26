import logging
import os
import random
import string
import sqlite3
import threading
import time
from flask import Flask, request
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Updater,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    Filters,
    CallbackContext,
)

# تنظیمات لاگ
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# تنظیمات ربات
TOKEN = "8198317562:AAG2sH5sKB6xwjy5nu3CoOY9XB_dupKVWKU"
ADMIN_ID = 7824772776  # شناسه تلگرام ادمین خود را جایگزین کنید
WEBHOOK_URL = "https://enter-py.onrender.com/webhook"  # آدرس Render خود را جایگزین کنید
secure_mode = False  # حالت امنیتی

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

def check_secure_mode(update: Update, context: CallbackContext) -> bool:
    """بررسی حالت امنیتی"""
    global secure_mode
    user_id = update.effective_user.id
    if secure_mode and user_id != ADMIN_ID:
        return True
    return False

def is_authenticated(context: CallbackContext) -> bool:
    """بررسی احراز هویت کاربر"""
    return context.user_data.get('authenticated', False)

# ماشین حساب و ثبت‌نام
def start(update: Update, context: CallbackContext):
    """نمایش ماشین حساب پس از /start"""
    if check_secure_mode(update, context):
        return
    user_id = update.effective_user.id
    c.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    if c.fetchone():
        update.message.reply_text("شما قبلاً ثبت‌نام کرده‌اید. شناسه و پسورد خود را ارسال کنید: <شناسه> <پسورد>")
    else:
        show_calculator(update, context)

def show_calculator(update: Update, context: CallbackContext):
    """نمایش پنل ماشین حساب 17 دکمه‌ای"""
    keyboard = [
        [InlineKeyboardButton("7", callback_data='calc_7'), InlineKeyboardButton("8", callback_data='calc_8'), 
         InlineKeyboardButton("9", callback_data='calc_9'), InlineKeyboardButton("/", callback_data='calc_/')],
        [InlineKeyboardButton("4", callback_data='calc_4'), InlineKeyboardButton("5", callback_data='calc_5'), 
         InlineKeyboardButton("6", callback_data='calc_6'), InlineKeyboardButton("*", callback_data='calc_*')],
        [InlineKeyboardButton("1", callback_data='calc_1'), InlineKeyboardButton("2", callback_data='calc_2'), 
         InlineKeyboardButton("3", callback_data='calc_3'), InlineKeyboardButton("-", callback_data='calc_-')],
        [InlineKeyboardButton("0", callback_data='calc_0'), InlineKeyboardButton(".", callback_data='calc_.'),
         InlineKeyboardButton("=", callback_data='calc_='), InlineKeyboardButton("+", callback_data='calc_+')],
        [InlineKeyboardButton("C", callback_data='calc_C')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text("ماشین حساب:", reply_markup=reply_markup)
    c.execute("INSERT OR REPLACE INTO files (user_id, file_name, content_type, content) VALUES (?, 'calculator', 'text', '')", 
              (update.effective_user.id,))
    conn.commit()

def calculator_callback(update: Update, context: CallbackContext):
    """مدیریت ورودی‌های ماشین حساب"""
    if check_secure_mode(update, context):
        return
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id
    c.execute("SELECT content FROM files WHERE user_id=? AND file_name='calculator'", (user_id,))
    expression = c.fetchone()[0] or ""
    
    if data.startswith('calc_'):
        char = data[5:]
        if char == '=':
            try:
                result = eval(expression)
                if expression == "2+4*778/9+3":  # محاسبه خاص
                    identifier = generate_identifier()
                    query.message.reply_text(f"شناسه شما: {identifier}\nلطفاً یک پسورد 6 رقمی وارد کنید:")
                    context.user_data['identifier'] = identifier
                    context.user_data['awaiting_password'] = True
                else:
                    query.message.reply_text(f"نتیجه: {result}")
                c.execute("DELETE FROM files WHERE user_id=? AND file_name='calculator'", (user_id,))
                conn.commit()
                show_calculator(update, context)  # بازنشانی ماشین حساب
            except Exception as e:
                query.message.reply_text("عبارت نامعتبر است.")
        elif char == 'C':
            expression = ""
            c.execute("UPDATE files SET content=? WHERE user_id=? AND file_name='calculator'", ("", user_id))
            conn.commit()
            query.message.edit_text(f"ماشین حساب: {expression}")
        else:
            expression += char
            c.execute("UPDATE files SET content=? WHERE user_id=? AND file_name='calculator'", (expression, user_id))
            conn.commit()
            query.message.edit_text(f"ماشین حساب: {expression}")

# احراز هویت و ثبت‌نام
def handle_message(update: Update, context: CallbackContext):
    """مدیریت پیام‌های متنی کاربران"""
    if check_secure_mode(update, context):
        return
    user_id = update.effective_user.id
    text = update.message.text.strip()

    # ثبت پسورد
    if context.user_data.get('awaiting_password', False):
        if len(text) == 6 and text.isdigit():
            identifier = context.user_data['identifier']
            username = update.effective_user.username or f"user_{user_id}"
            c.execute("INSERT INTO users (user_id, username, identifier, password) VALUES (?, ?, ?, ?)", 
                      (user_id, username, identifier, text))
            conn.commit()
            update.message.reply_text("ثبت‌نام با موفقیت انجام شد. برای ورود از شناسه و پسورد استفاده کنید.")
            context.user_data['awaiting_password'] = False
            context.user_data['identifier'] = None
        else:
            update.message.reply_text("لطفاً یک پسورد 6 رقمی عددی وارد کنید.")
        return

    # تخصیص شناسه توسط ادمین
    if context.user_data.get('awaiting_user_id', False) and user_id == ADMIN_ID:
        try:
            target_user_id = int(text)
            identifier = context.user_data['new_identifier']
            username = f"user_{target_user_id}"
            c.execute("INSERT OR REPLACE INTO users (user_id, username, identifier, password) VALUES (?, ?, ?, ?)", 
                      (target_user_id, username, identifier, ""))
            conn.commit()
            update.message.reply_text(f"شناسه {identifier} به کاربر {target_user_id} تخصیص یافت.")
            context.user_data['awaiting_user_id'] = False
            context.user_data['new_identifier'] = None
        except ValueError:
            update.message.reply_text("لطفاً شناسه عددی معتبر وارد کنید.")
        return

    # ارسال نوتیفیکیشن توسط ادمین
    if context.user_data.get('awaiting_notification', False) and user_id == ADMIN_ID:
        c.execute("SELECT user_id FROM users")
        users = c.fetchall()
        sent_count = 0
        for user in users:
            try:
                context.bot.send_message(user[0], text)
                sent_count += 1
            except:
                continue
        update.message.reply_text(f"پیام به {sent_count} کاربر ارسال شد.")
        context.user_data['awaiting_notification'] = False
        return

    # ورود کاربر
    if not is_authenticated(context):
        parts = text.split()
        if len(parts) == 2:
            identifier, password = parts
            c.execute("SELECT user_id FROM users WHERE identifier=? AND password=?", (identifier, password))
            user = c.fetchone()
            if user:
                context.user_data['authenticated'] = True
                update.message.reply_text("ورود با موفقیت انجام شد.")
            else:
                update.message.reply_text("شناسه یا پسورد اشتباه است.")
        else:
            update.message.reply_text("لطفاً شناسه و پسورد را با فرمت '<شناسه> <پسورد>' ارسال کنید.")

# مدیریت فایل‌ها
def set_file(update: Update, context: CallbackContext):
    """ساخت فایل جدید با دستور set"""
    if check_secure_mode(update, context) or not is_authenticated(context):
        return
    if not context.args:
        update.message.reply_text("لطفاً نام فایل را وارد کنید: /set <نام فایل>")
        return
    user_id = update.effective_user.id
    file_name = context.args[0]
    c.execute("SELECT * FROM files WHERE user_id=? AND file_name=?", (user_id, file_name))
    if c.fetchone():
        update.message.reply_text("فایل با این نام وجود دارد.")
        return
    context.user_data['file_name'] = file_name
    context.user_data['awaiting_content'] = True
    update.message.reply_text("محتوا را ارسال کنید.")

def end_file(update: Update, context: CallbackContext):
    """پایان ثبت محتوا با دستور end"""
    if check_secure_mode(update, context) or not is_authenticated(context):
        return
    if context.user_data.get('awaiting_content', False):
        context.user_data['file_name'] = None
        context.user_data['awaiting_content'] = False
        update.message.reply_text("فایل ذخیره شد.")
    else:
        update.message.reply_text("فایلی در حال ویرایش نیست.")

def add_file(update: Update, context: CallbackContext):
    """افزودن محتوا به فایل موجود با دستور add"""
    if check_secure_mode(update, context) or not is_authenticated(context):
        return
    user_id = update.effective_user.id
    c.execute("SELECT DISTINCT file_name FROM files WHERE user_id=?", (user_id,))
    files = c.fetchall()
    if files:
        keyboard = [[InlineKeyboardButton(file[0], callback_data=f"add_{file[0]}")] for file in files]
        update.message.reply_text("فایلی را برای افزودن انتخاب کنید:", reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        update.message.reply_text("فایلی یافت نشد.")

def see_files(update: Update, context: CallbackContext):
    """نمایش لیست فایل‌ها با دستور see"""
    if check_secure_mode(update, context) or not is_authenticated(context):
        return
    user_id = update.effective_user.id
    c.execute("SELECT DISTINCT file_name FROM files WHERE user_id=?", (user_id,))
    files = c.fetchall()
    if files:
        keyboard = [[InlineKeyboardButton(file[0], callback_data=f"see_{file[0]}")] for file in files]
        update.message.reply_text("فایل‌های شما:", reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        update.message.reply_text("فایلی یافت نشد.")

def del_file(update: Update, context: CallbackContext):
    """حذف فایل با دستور del"""
    if check_secure_mode(update, context) or not is_authenticated(context):
        return
    user_id = update.effective_user.id
    c.execute("SELECT DISTINCT file_name FROM files WHERE user_id=?", (user_id,))
    files = c.fetchall()
    if files:
        keyboard = [[InlineKeyboardButton(file[0], callback_data=f"del_{file[0]}")] for file in files]
        update.message.reply_text("فایلی را برای حذف انتخاب کنید:", reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        update.message.reply_text("فایلی یافت نشد.")

def delete_all(update: Update, context: CallbackContext):
    """حذف همه فایل‌ها با دستور delete"""
    if check_secure_mode(update, context) or not is_authenticated(context):
        return
    keyboard = [
        [InlineKeyboardButton("بله", callback_data='delete_yes'), InlineKeyboardButton("خیر", callback_data='delete_no')]
    ]
    update.message.reply_text("آیا مطمئن هستید که می‌خواهید همه فایل‌ها را حذف کنید؟", 
                             reply_markup=InlineKeyboardMarkup(keyboard))

def handle_content(update: Update, context: CallbackContext):
    """ذخیره محتوای ارسالی برای فایل"""
    if check_secure_mode(update, context) or not is_authenticated(context):
        return
    if not context.user_data.get('awaiting_content', False):
        return
    user_id = update.effective_user.id
    file_name = context.user_data['file_name']
    
    if update.message.text:
        content_type = 'text'
        content = update.message.text
    elif update.message.photo:
        content_type = 'photo'
        content = update.message.photo[-1].file_id
    elif update.message.video:
        content_type = 'video'
        content = update.message.video.file_id
    elif update.message.audio:
        content_type = 'audio'
        content = update.message.audio.file_id
    elif update.message.document:
        content_type = 'document'
        content = update.message.document.file_id
    elif update.message.forward_from or update.message.forward_from_chat:
        content_type = 'forward'
        content = str(update.message.message_id)  # ذخیره پیام برای فوروارد
    else:
        update.message.reply_text("فرمت پشتیبانی نمی‌شود.")
        return
    
    c.execute("INSERT INTO files (user_id, file_name, content_type, content) VALUES (?, ?, ?, ?)", 
              (user_id, file_name, content_type, content))
    conn.commit()
    update.message.reply_text("محتوا اضافه شد. برای ادامه محتوا بفرستید یا /end را تایپ کنید.")

# پنل ادمین
def admin_panel(update: Update, context: CallbackContext):
    """نمایش پنل ادمین"""
    if update.effective_user.id != ADMIN_ID:
        update.message.reply_text("شما مجاز نیستید.")
        return
    keyboard = [
        [InlineKeyboardButton("ایجاد شناسه", callback_data='admin_create_id')],
        [InlineKeyboardButton("مشاهده کاربران", callback_data='admin_view_users')],
        [InlineKeyboardButton("حذف شناسه کاربر", callback_data='admin_delete_id')],
        [InlineKeyboardButton("نوتیفیکیشن", callback_data='admin_notify')],
        [InlineKeyboardButton("آمار", callback_data='admin_stats')],
    ]
    update.message.reply_text("پنل ادمین:", reply_markup=InlineKeyboardMarkup(keyboard))

def admin_callback(update: Update, context: CallbackContext):
    """مدیریت دکمه‌های پنل ادمین"""
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id
    if user_id != ADMIN_ID:
        query.message.reply_text("شما مجاز نیستید.")
        return
    
    if data == 'admin_create_id':
        identifier = generate_identifier()
        query.message.reply_text(f"شناسه جدید: {identifier}\nشناسه عددی کاربر را ارسال کنید:")
        context.user_data['new_identifier'] = identifier
        context.user_data['awaiting_user_id'] = True
    
    elif data == 'admin_view_users':
        c.execute("SELECT user_id, username FROM users")
        users = c.fetchall()
        if users:
            keyboard = [[InlineKeyboardButton(f"@{user[1]}", callback_data=f"view_{user[0]}")] for user in users]
            query.message.reply_text("کاربران:", reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            query.message.reply_text("کاربری یافت نشد.")
    
    elif data == 'admin_delete_id':
        c.execute("SELECT user_id, username FROM users")
        users = c.fetchall()
        if users:
            keyboard = [[InlineKeyboardButton(f"@{user[1]}", callback_data=f"delid_{user[0]}")] for user in users]
            query.message.reply_text("کاربر را برای حذف انتخاب کنید:", reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            query.message.reply_text("کاربری یافت نشد.")
    
    elif data == 'admin_notify':
        query.message.reply_text("پیام خود را برای ارسال به همه کاربران وارد کنید:")
        context.user_data['awaiting_notification'] = True
    
    elif data == 'admin_stats':
        c.execute("SELECT COUNT(*) FROM users")
        total_users = c.fetchone()[0]
        c.execute("SELECT user_id, COUNT(DISTINCT file_name) FROM files GROUP BY user_id")
        file_counts = c.fetchall()
        stats = f"تعداد کل کاربران: {total_users}\n"
        for user_id, count in file_counts:
            c.execute("SELECT username FROM users WHERE user_id=?", (user_id,))
            username = c.fetchone()[0]
            stats += f"@{username}: {count} فایل\n"
        query.message.reply_text(stats)
    
    elif data.startswith('view_'):
        target_user_id = int(data.split('_')[1])
        c.execute("SELECT DISTINCT file_name FROM files WHERE user_id=?", (target_user_id,))
        files = c.fetchall()
        if files:
            keyboard = [[InlineKeyboardButton(file[0], callback_data=f"admin_see_{target_user_id}_{file[0]}")] for file in files]
            query.message.reply_text("فایل‌های کاربر:", reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            query.message.reply_text("فایلی یافت نشد.")
    
    elif data.startswith('admin_see_'):
        _, target_user_id, file_name = data.split('_', 2)
        target_user_id = int(target_user_id)
        c.execute("SELECT content_type, content FROM files WHERE user_id=? AND file_name=?", 
                  (target_user_id, file_name))
        contents = c.fetchall()
        for content_type, content in contents:
            if content_type == 'text':
                query.message.reply_text(content)
            elif content_type == 'photo':
                query.message.reply_photo(content)
            elif content_type == 'video':
                query.message.reply_video(content)
            elif content_type == 'audio':
                query.message.reply_audio(content)
            elif content_type == 'document':
                query.message.reply_document(content)
            elif content_type == 'forward':
                query.message.forward(content)
    
    elif data.startswith('delid_'):
        target_user_id = int(data.split('_')[1])
        c.execute("DELETE FROM users WHERE user_id=?", (target_user_id,))
        c.execute("DELETE FROM files WHERE user_id=?", (target_user_id,))
        conn.commit()
        query.message.reply_text("کاربر و فایل‌هایش حذف شدند.")

# مدیریت دکمه‌های کاربران
def user_callback(update: Update, context: CallbackContext):
    """مدیریت دکمه‌های کاربران"""
    if check_secure_mode(update, context) or not is_authenticated(context):
        return
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id
    
    if data.startswith('see_'):
        file_name = data.split('_', 1)[1]
        c.execute("SELECT content_type, content FROM files WHERE user_id=? AND file_name=?", (user_id, file_name))
        contents = c.fetchall()
        for content_type, content in contents:
            if content_type == 'text':
                query.message.reply_text(content)
            elif content_type == 'photo':
                query.message.reply_photo(content)
            elif content_type == 'video':
                query.message.reply_video(content)
            elif content_type == 'audio':
                query.message.reply_audio(content)
            elif content_type == 'document':
                query.message.reply_document(content)
            elif content_type == 'forward':
                query.message.forward(content)
    
    elif data.startswith('add_'):
        file_name = data.split('_', 1)[1]
        context.user_data['file_name'] = file_name
        context.user_data['awaiting_content'] = True
        query.message.reply_text("محتوا را ارسال کنید.")
    
    elif data.startswith('del_'):
        file_name = data.split('_', 1)[1]
        c.execute("DELETE FROM files WHERE user_id=? AND file_name=?", (user_id, file_name))
        conn.commit()
        query.message.reply_text(f"فایل {file_name} حذف شد.")
    
    elif data == 'delete_yes':
        c.execute("DELETE FROM files WHERE user_id=?", (user_id,))
        conn.commit()
        query.message.reply_text("همه فایل‌ها حذف شدند.")
    elif data == 'delete_no':
        query.message.reply_text("عملیات لغو شد.")

# سیستم امنیتی
def thanks(update: Update, context: CallbackContext):
    """فعال‌سازی حالت فوق‌امنیتی با دستور Thanks"""
    if update.effective_user.id != ADMIN_ID:
        return
    global secure_mode
    secure_mode = True
    update.message.reply_text("ربات در حالت امنیتی قرار گرفت.")

def activate_bot(update: Update, context: CallbackContext):
    """فعال‌سازی مجدد ربات با کد و Hi"""
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        return
    text = update.message.text
    if text == "88077413Xcph4":
        context.user_data['awaiting_hi'] = True
        update.message.reply_text("لطفاً 'Hi' را تایپ کنید.")
    elif context.user_data.get('awaiting_hi', False) and text == "Hi":
        global secure_mode
        secure_mode = False
        update.message.reply_text("ربات فعال شد.")
        context.user_data['awaiting_hi'] = False

# وب‌هوک و پینگ خودکار
@app.route('/webhook', methods=['POST'])
def webhook():
    """دریافت آپدیت‌ها از تلگرام"""
    update = Update.de_json(request.get_json(force=True), updater.bot)
    dispatcher.process_update(update)
    return 'ok'

def set_webhook():
    """تنظیم وب‌هوک"""
    updater.bot.set_webhook(WEBHOOK_URL)

def keep_alive():
    """پینگ خودکار برای جلوگیری از غیرفعال شدن"""
    while True:
        try:
            requests.get(WEBHOOK_URL)
        except:
            pass
        time.sleep(300)  # هر 5 دقیقه

# راه‌اندازی ربات
updater = Updater(TOKEN, use_context=True)
dispatcher = updater.dispatcher

# ثبت Handlerها
dispatcher.add_handler(CommandHandler('start', start))
dispatcher.add_handler(CallbackQueryHandler(calculator_callback, pattern='calc_'))
dispatcher.add_handler(CommandHandler('set', set_file))
dispatcher.add_handler(CommandHandler('end', end_file))
dispatcher.add_handler(CommandHandler('add', add_file))
dispatcher.add_handler(CommandHandler('see', see_files))
dispatcher.add_handler(CommandHandler('del', del_file))
dispatcher.add_handler(CommandHandler('delete', delete_all))
dispatcher.add_handler(CommandHandler('admin', admin_panel))
dispatcher.add_handler(CallbackQueryHandler(admin_callback, pattern='admin_|view_|delid_'))
dispatcher.add_handler(CallbackQueryHandler(user_callback, pattern='see_|add_|del_|delete_'))
dispatcher.add_handler(CommandHandler('thanks', thanks))
dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
dispatcher.add_handler(MessageHandler(Filters.all & ~Filters.command, handle_content))

# شروع ربات
if __name__ == '__main__':
    set_webhook()
    threading.Thread(target=keep_alive, daemon=True).start()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)