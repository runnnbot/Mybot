import os
import sys
import subprocess
import threading
import telebot
from flask import Flask
import builtins

# ========= الاعدادات =========
TOKEN = os.getenv("BOT_TOKEN") # لازم تحط توكن بوتك في Render -> Environment
bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# عشان نتذكر مين ينتظر ادخال
waiting_users = {}
user_files = {}

def install_lib(lib_name):
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", lib_name])
        return True
    except:
        return False

# هذا هو اللي يصلح مشكلة التعليق
def smart_input(prompt=""):
    user_id = smart_input.current_user
    if prompt:
        bot.send_message(user_id, f"⌨️ {prompt}")

    waiting_users[user_id] = True

    # ننتظر المستخدم يرسل رسالة
    import time
    while waiting_users.get(user_id, False):
        time.sleep(1)

    return smart_input.user_response.get(user_id, "")

smart_input.current_user = None
smart_input.user_response = {}

@app.route('/')
def home():
    return "Bot is Live!"

@bot.message_handler(commands=['start'])
def start(m):
    bot.send_message(m.chat.id, "✅ البوت شغال\nارسل ملف.py وبيشغله لك")

@bot.message_handler(commands=['stop'])
def stop(m):
    if m.chat.id in waiting_users:
        waiting_users[m.chat.id] = False
        bot.send_message(m.chat.id, "🛑 تم ايقاف التشغيل")
    else:
        bot.send_message(m.chat.id, "ما فيه شي شغال")

@bot.message_handler(content_types=['document'])
def handle_file(m):
    if not m.document.file_name.endswith('.py'):
        bot.send_message(m.chat.id, "ارسل ملف.py فقط")
        return

    bot.send_message(m.chat.id, f"📁 استلمت الملف: {m.document.file_name}\nجاري تشغيله...")

    file_info = bot.get_file(m.document.file_id)
    downloaded = bot.download_file(file_info.file_path)
    code = downloaded.decode('utf-8', errors='ignore')

    # شغل الكود في ثريد عشان ما يعلق البوت
    def run_code():
        try:
            # نركب الـ input الذكي
            smart_input.current_user = m.chat.id
            builtins.input = smart_input

            # بيئة التشغيل
            exec_globals = {"__builtins__": builtins}

            exec(code, exec_globals)
            bot.send_message(m.chat.id, "✅ انتهى التشغيل")
        except ModuleNotFoundError as e:
            lib = str(e).split("'")[1]
            bot.send_message(m.chat.id, f"⏳ جاري تثبيت المكتبة الناقصة: {lib}")
            if install_lib(lib):
                bot.send_message(m.chat.id, f"✅ تم تثبيت {lib}\nأعد ارسال الملف مرة ثانية")
            else:
                bot.send_message(m.chat.id, f"❌ فشل تثبيت {lib}")
        except Exception as e:
            bot.send_message(m.chat.id, f"❌ خطأ:\n{e}")
        finally:
            if m.chat.id in waiting_users:
                del waiting_users[m.chat.id]
            smart_input.current_user = None

    threading.Thread(target=run_code).start()

# لو المستخدم يرد وهو في حالة انتظار
@bot.message_handler(func=lambda m: m.chat.id in waiting_users and waiting_users[m.chat.id])
def handle_input(m):
    smart_input.user_response[m.chat.id] = m.text
    waiting_users[m.chat.id] = False

def run_flask():
    app.run(host='0.0.0.0', port=10000)

if __name__ == "__main__":
    threading.Thread(target=run_flask).start()
    bot.infinity_polling()
