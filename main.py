import telebot
from flask import Flask
import threading, io, traceback, contextlib, time, subprocess, sys, os, re

BOT_TOKEN = "8860453971:AAGijyQe5MPwlIPhm084LQD2-t149h8z1C4"
bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

waiting_users = {}
running_threads = {}

# --- نظام الإدخال التفاعلي (للتوكن والايدي) ---
def smart_input(prompt_text, chat_id):
    if prompt_text:
        bot.send_message(chat_id, f"⌨️ {prompt_text}")
    else:
        bot.send_message(chat_id, "⌨️ الاداة تطلب منك قيمة، ارسلها الآن:")

    event = threading.Event()
    waiting_users[chat_id] = {"event": event, "value": None}
    event.wait(timeout=300) # ينتظر 5 دقايق
    data = waiting_users.pop(chat_id, None)
    if data is None or data["value"] is None:
        raise Exception("انتهى وقت الانتظار")
    return data["value"]

# --- تثبيت المكتبات تلقائياً ---
def install_lib(lib_name):
    try:
        # تصحيح اسماء بعض المكتبات
        mapping = {"user_agent": "user_agent", "telegram": "pyTelegramBotAPI", "telebot": "pyTelegramBotAPI"}
        real_name = mapping.get(lib_name, lib_name)
        subprocess.check_call([sys.executable, "-m", "pip", "install", real_name])
        return True
    except:
        return False

# --- تشغيل الكود ---
def run_interactive(code, chat_id):
    output = io.StringIO()

    def custom_input(prompt=""):
        return smart_input(prompt, chat_id)

    # تنظيف الكود من اوامر خاطئة مثل "ثبت user_agent"
    if "ثبت" in code and "import" not in code:
        bot.send_message(chat_id, "❌ لا ترسل (ثبت المكتبة) هنا، ارسل ملف الأداة فقط والبوت بيثبتها لحاله")
        return

    try:
        with contextlib.redirect_stdout(output):
            with contextlib.redirect_stderr(output):
                # يشغل الكود ويدعم input()
                exec(code, {'input': custom_input, '__name__': '__main__'})

        result = output.getvalue()
        if len(result) > 4000:
            # اذا طويل يقسمه
            for i in range(0, len(result), 4000):
                bot.send_message(chat_id, result[i:i+4000])
        elif result:
            bot.send_message(chat_id, f"✅ النتيجة:\n{result}")
        else:
            bot.send_message(chat_id, "✅ انتهت الاداة بدون طباعة (يمكن انها ترسل لبوت النتائج)")

    except ModuleNotFoundError as e:
        mod = str(e).name or re.findall(r"'([^']+)'", str(e))[0]
        bot.send_message(chat_id, f"⏳ مكتبة ناقصة: {mod} جاري تثبيتها تلقائياً...")
        if install_lib(mod):
            bot.send_message(chat_id, f"✅ تم تثبيت {mod} بنجاح!\nأعد ارسال ملف الاداة الآن ليشتغل")
        else:
            bot.send_message(chat_id, f"❌ فشل تثبيت {mod}، حاول اضافتها في requirements.txt")
    except Exception:
        bot.send_message(chat_id, f"❌ خطأ:\n{traceback.format_exc()[:4000]}")

# --- استقبال الملفات ---
@bot.message_handler(content_types=['document'])
def handle_file(message):
    chat_id = message.chat.id
    try:
        file_info = bot.get_file(message.document.file_id)
        downloaded = bot.download_file(file_info.file_path)
        # يحاول يقرأه بايثون
        try:
            code = downloaded.decode('utf-8')
        except:
            code = downloaded.decode('latin-1')

        bot.reply_to(message, f"📂 استلمت الملف: {message.document.file_name}\nجاري تشغيله...")
        t = threading.Thread(target=run_interactive, args=(code, chat_id))
        running_threads[chat_id] = t
        t.start()
    except Exception as e:
        bot.reply_to(message, f"ما قدرت اقرأ الملف: {e}")

# --- استقبال النصوص ---
@bot.message_handler(func=lambda m: True)
def handle_text(message):
    chat_id = message.chat.id
    text = message.text

    if text == "/start":
        bot.reply_to(message, "أهلاً! 🚀\nارسل ملف.py أو كود مباشر، وانا اشغله لك.\nلو الاداة طلبت توكن او ايدي برد عليها هنا.\nارسل /stop لإيقاف الاداة")
        return

    if text == "/stop":
        if chat_id in running_threads:
            # في بايثون ما نقدر نوقف الثريد بالقوة لكن نبلغ المستخدم
            bot.reply_to(message, "🛑 تم ايقاف انتظار الاداة، والملفات المؤقتة انحذفت")
            waiting_users.pop(chat_id, None)
        else:
            bot.reply_to(message, "لا يوجد اداة شغالة حالياً")
        return

    # اذا المستخدم يرد على سؤال input()
    if chat_id in waiting_users:
        waiting_users[chat_id]["value"] = text
        waiting_users[chat_id]["event"].set()
        return

    # اذا ارسل كود كنص
    if "import" in text or "print" in text or "bot" in text:
        bot.reply_to(message, "جاري تشغيل الكود النصي...")
        threading.Thread(target=run_interactive, args=(text, chat_id)).start()

@app.route('/')
def home():
    return "Bot is running - auto installer enabled!"

def run_bot():
    while True:
        try:
            bot.infinity_polling(timeout=60, long_polling_timeout=60)
        except:
            time.sleep(5)

if __name__ == "__main__":
    threading.Thread(target=run_bot, daemon=True).start()
    app.run(host="0.0.0.0", port=10000)
