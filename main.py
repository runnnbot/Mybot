import os, sys, io, threading, traceback, contextlib
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = os.environ.get("BOT_TOKEN")
flask_app = Flask(__name__)
USER_GLOBALS = {}

# ====== اعدادات الحماية - جاهزة لك ======
MY_ID = 2073104643
PASSWORD = "yfyfyf12345678"
authorized = set()
AUTH_FILE = "auth.txt"

if os.path.exists(AUTH_FILE):
    try:
        with open(AUTH_FILE, "r") as f:
            authorized.add(int(f.read().strip()))
    except:
        pass

@flask_app.route('/')
def home(): return "Super Runner is live!"

def run_flask():
    flask_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid!= MY_ID:
        await update.message.reply_text("🔒 هذا البوت خاص\nارسل رمز التفعيل:")
        return
    if uid not in authorized:
        await update.message.reply_text("🔒 اهلا ياسر! ارسل رمز التفعيل اولاً لتفعيل البوت:")
        return
    await update.message.reply_text(
        "🔥 هلا ياسر! بوت تشغيل كل أدوات بايثون جاهز\n\n"
        "ارسل أي كود، مثال:\n"
        "`print('هلا')`\n"
        "تقدر ترسل الكود عادي أو داخل ```python```\n\n"
        "لايقاف الجلسة: /stop"
    )

async def stop_tool(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid!= MY_ID:
        return
    if uid in USER_GLOBALS:
        USER_GLOBALS.pop(uid, None)
    await update.message.reply_text("🛑 تم ايقاف الاداة ومسح الجلسة، البوت لا يزال شغال ✅\nتقدر ترسل كود جديد في اي وقت.")

async def runner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text.strip()

    # --- تفعيل بالرمز ---
    if text == PASSWORD:
        if uid!= MY_ID:
            await update.message.reply_text("❌ انت لست صاحب البوت")
            return
        authorized.add(uid)
        try:
            with open(AUTH_FILE, "w") as f:
                f.write(str(uid))
        except:
            pass
        await update.message.reply_text("✅ تم التفعيل بنجاح ياسر! الحين ارسل اي كود تبي تشغله")
        return

    # --- حماية ---
    if uid!= MY_ID or uid not in authorized:
        await update.message.reply_text("🔒 ارسل رمز التفعيل اولاً:\n`yfyfyf12345678`", parse_mode='Markdown')
        return

    code = text
    if "```" in code:
        parts = code.split("```")
        code = parts[1] if len(parts) > 1 else parts[0]
        if code.strip().startswith("python"):
            code = code.strip()[6:].strip()

    if uid not in USER_GLOBALS: USER_GLOBALS[uid] = {}

    f = io.StringIO()
    try:
        with contextlib.redirect_stdout(f), contextlib.redirect_stderr(f):
            exec(code, USER_GLOBALS[uid])
        out = f.getvalue() or "✅ تم التنفيذ بدون مخرجات"
        if len(out) > 3500: out = out[:3500] + "\n... تم القص"
        await update.message.reply_text(f"📤 النتيجة:\n```\n{out}\n```", parse_mode='Markdown')
    except Exception:
        await update.message.reply_text(f"❌ خطأ:\n```\n{traceback.format_exc()[-3500:]}\n```", parse_mode='Markdown')

def main():
    threading.Thread(target=run_flask, daemon=True).start()
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop_tool))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, runner))
    print("Bot started...")
    app.run_polling()

if __name__ == "__main__":
    main()
