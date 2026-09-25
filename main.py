import telebot
from flask import Flask
import threading
import io
import traceback
import contextlib

BOT_TOKEN = "8860453971:AAGijyQe5MPwlIPhm084LQD2-t149h8z1C4"

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

def run_python(code):
    output = io.StringIO()
    try:
        with contextlib.redirect_stdout(output):
            with contextlib.redirect_stderr(output):
                exec(code, {})
        result = output.getvalue()
        if not result:
            result = "تم التنفيذ بنجاح ✅ (ما في مخرجات print)"
        return result[:4000]
    except Exception:
        return f"خطأ ❌:\n{traceback.format_exc()[:4000]}"

@bot.message_handler(content_types=['document'])
def handle_file(message):
    try:
        file_info = bot.get_file(message.document.file_id)
        downloaded = bot.download_file(file_info.file_path)
        code = downloaded.decode('utf-8')
        bot.reply_to(message, "جاري تشغيل الملف...")
        result = run_python(code)
        bot.reply_to(message, f"النتيجة:\n\n{result}")
    except Exception as e:
        bot.reply_to(message, f"ما قدرت اقرأ الملف: {e}")

@bot.message_handler(func=lambda m: True)
def handle_text(message):
    code = message.text
    if code == "/start":
        bot.reply_to(message, "ارسل لي كود بايثون او ملف .py واشغله لك فورا 🚀")
        return
    result = run_python(code)
    bot.reply_to(message, f"النتيجة:\n\n{result}")

@app.route('/')
def home():
    return "Bot is running!"

def run_bot():
    bot.infinity_polling()

if __name__ == "__main__":
    threading.Thread(target=run_bot).start()
    app.run(host="0.0.0.0", port=10000)
