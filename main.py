import telebot, sys, io, traceback, os

BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(BOT_TOKEN)

PASSWORD = "yfyfyf12345678"
MY_ID = 2073104643  # انت ياسر
authorized = set()
authorized.add(MY_ID) # انت تدخل مباشرة بدون باسورد حتى لو نسيته

def run_code(code):
    old_out = sys.stdout
    sys.stdout = io.StringIO()
    try:
        exec(code, {})
        return sys.stdout.getvalue() or "✅ تم التشغيل"
    except Exception:
        return traceback.format_exc()
    finally:
        sys.stdout = old_out

@bot.message_handler(commands=['start'])
def start(m):
    if m.chat.id == MY_ID:
        bot.reply_to(m, f"هلا ياسر انت صاحب البوت 👋\nانت داخل تلقائي بدون باسورد\nالرمز حقك هو: {PASSWORD}\nارسل كود او ملف الحين")
        authorized.add(m.chat.id)
    else:
        bot.reply_to(m, "🔒 مرحبا! هذا بوت خاص\nارسل رمز التفعيل:")

@bot.message_handler(content_types=['text','document'])
def all_handle(m):
    chat_id = m.chat.id

    # انت صاحب البوت - تدخل تلقائي
    if chat_id == MY_ID:
        authorized.add(chat_id)

    if chat_id not in authorized:
        if m.content_type == 'text' and m.text == PASSWORD:
            authorized.add(chat_id)
            bot.reply_to(m, "✅ تم التفعيل بنجاح!")
        else:
            # اي شخص غريب - ما نعطيه الرمز ابدا
            bot.reply_to(m, "🔒 رمز خاطئ - ارسل رمز التفعيل الصحيح")
        return

    # اذا انت نسيت الباسورد اكتب /pass
    if m.content_type == 'text' and m.text == "/pass":
        if chat_id == MY_ID:
            bot.reply_to(m, f"رمزك ياسر هو:\n{PASSWORD}")
        else:
            bot.reply_to(m, "🔒 هذا الامر لصاحب البوت فقط")
        return

    if m.content_type == 'document':
        file_info = bot.get_file(m.document.file_id)
        code = bot.download_file(file_info.file_path).decode('utf-8', errors='ignore')
        res = run_code(code)
        bot.send_message(chat_id, f"📁 نتيجة الملف {m.document.file_name}:\n{res[:4000]}")
        return

    if m.content_type == 'text':
        res = run_code(m.text)
        bot.send_message(chat_id, f"{res[:4000]}")

bot.infinity_polling()
