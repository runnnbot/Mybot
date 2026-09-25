import os, sys, io, threading, traceback, contextlib
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = os.environ.get("BOT_TOKEN")
flask_app = Flask(__name__)
USER_GLOBALS = {}

@flask_app.route('/')
def home(): return "Super Runner is live!"

def run_flask():
    flask_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔥 هلا ياسر! بوت تشغيل كل أدوات بايثون جاهز\n\n"
        "ارسل أي كود، مثال:\n"
        "`print('هلا')`\n"
        "`import requests; print(requests.get('https://api.ipify.org').text)`\n\n"
        "تقدر ترسل الكود عادي أو داخل ```python```"
    )

async def runner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = update.message.text
    if "```" in code:
        parts = code.split("```")
        code = parts[1] if len(parts) > 1 else parts[0]
        if code.strip().startswith("python"):
            code = code.strip()[6:].strip()

    uid = update.effective_user.id
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
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, runner))
    print("Bot started...")
    app.run_polling()

if __name__ == "__main__":
    main()
