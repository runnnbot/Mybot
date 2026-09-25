import telebot, sys, io, traceback, os, subprocess, threading, time
from flask import Flask

BOT_TOKEN = os.getenv("BOT_TOKEN")
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot Alive 24/7 ✅"

def run_flask():
    app.run(host='0.0.0.0', port=10000)

# يشغل موقع وهمي عشان Render ما يطفي
threading.Thread(target=run_flask, daemon=True).start()

bot = telebot.TeleBot(BOT_TOKEN)
PASSWORD = "yfyfyf12345678"
MY_ID = 2073104643
authorized = set([MY_ID])

def run_code(code):
    old = sys.stdout
    sys.stdout = io.StringIO()
    try:
        exec(code, {})
        return True, sys.stdout.getvalue() or "✅ تم تشغيل الاداة"
    except ModuleNotFoundError as e:
        lib = str(e).split("'")[1] if "'" in str(e) else "مكتبة ناقصة"
        return False, f"MISSING:{lib}"
    except Exception:
        return False, traceback.format_exc()
    finally:
        sys.stdout = old

@bot.message_handler(content_types=['text','document'])
def handle(m):
    chat_id = m.chat.id
    if chat_id == MY_ID: authorized.add(chat_id)

    if chat_id not in authorized:
        if m.content_type == 'text' and m.text == PASSWORD:
            authorized.add(chat_id)
            bot.reply_to(m, "✅ تم التفعيل، البوت شغال 24 ساعة")
            return
        else:
            bot.reply_to(m, "🔒 ارسل رمز الدخول")
            return

    txt = m.text if m.content_type == 'text' else ""

    # امر التثبيت المؤقت
    if txt.startswith("ثبت ") or txt.startswith("/install "):
        lib = txt.split()[-1].strip()
        bot.send_message(chat_id, f"⏳ جاري تثبيت {lib} مؤقتا...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", lib])
            bot.send_message(chat_id, f"✅ تم تثبيت {lib}\nالحين ارسل اداتك وتشتغل فورا\n💡 عشان توفر مساحة بتنحذف اذا طفى السيرفر")
        except Exception as e:
            bot.send_message(chat_id, f"❌ فشل التثبيت: {e}")
        return

    code = txt if m.content_type == 'text' else bot.download_file(bot.get_file(m.document.file_id).file_path).decode(errors='ignore')
    if not code: return

    ok, res = run_code(code)
    if not ok and res.startswith("MISSING:"):
        lib = res.split(":")[1]
        bot.send_message(chat_id, f"⚠️ المكتبة ناقصة: {lib}\n\nما ثبتها عشان اوفر مساحة المجاني\nاذا تحتاجها الحين اكتب:\nثبت {lib}")
    else:
        bot.send_message(chat_id, res[:4000])

# تشغيل البوت
print("Bot Started 24/7...")
bot.infinity_polling()
