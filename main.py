import os
import sys
import subprocess
import threading
import tempfile
import shutil
import traceback
import builtins

import telebot
from flask import Flask


# =========================
# إعدادات البوت
# =========================

TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise RuntimeError("BOT_TOKEN غير موجود في Environment Variables")

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)


# =========================
# جلسات تشغيل المستخدمين
# =========================

sessions = {}
sessions_lock = threading.Lock()


# =========================
# تثبيت مكتبة ناقصة
# =========================

def install_lib(lib_name):
    try:
        subprocess.check_call([
            sys.executable,
            "-m",
            "pip",
            "install",
            lib_name
        ])
        return True
    except Exception:
        return False


# =========================
# كود التشغيل الداخلي
# =========================

BOOTSTRAP_CODE = r'''
import builtins
import sys
import runpy
import traceback

tool_file = sys.argv[1]


def runner_input(prompt=""):
    # نرسل إشارة للبوت أن الأداة تنتظر input()
    prompt = str(prompt).replace("\n", "\\n")

    print("__RUNNER_INPUT__" + prompt, flush=True)

    # ننتظر إجابة البوت
    answer = sys.stdin.readline()

    if answer == "":
        raise EOFError("تم إغلاق الإدخال")

    return answer.rstrip("\r\n")


# نستبدل input داخل الأداة فقط
builtins.input = runner_input

try:
    runpy.run_path(tool_file, run_name="__main__")

except SystemExit as e:
    code = e.code if isinstance(e.code, int) else 0
    sys.exit(code)

except Exception:
    traceback.print_exc()
    sys.exit(1)
'''


# =========================
# Flask / Render
# =========================

@app.route("/")
def home():
    return "Bot is Live!"


@app.route("/health")
def health():
    return "OK"


# =========================
# /start
# =========================

@bot.message_handler(commands=["start"])
def start(message):
    bot.send_message(
        message.chat.id,
        "✅ البوت شغال\n\n"
        "📁 أرسل ملف Python بصيغة .py\n"
        "أو أرسل الكود داخل ```python ... ```\n\n"
        "إذا الأداة احتاجت input، بسألك عنه تلقائيًا."
    )


# =========================
# /stop
# =========================

@bot.message_handler(commands=["stop"])
def stop(message):

    user_id = message.chat.id

    with sessions_lock:
        session = sessions.get(user_id)

    if not session:
        bot.send_message(user_id, "ما فيه تشغيل حالي.")
        return

    process = session.get("process")

    try:
        if process and process.poll() is None:
            process.kill()
    except Exception:
        pass

    with sessions_lock:
        sessions.pop(user_id, None)

    bot.send_message(user_id, "🛑 تم إيقاف الأداة.")


# =========================
# تشغيل كود Python
# =========================

def run_python_code(user_id, code, filename="tool.py"):

    workspace = tempfile.mkdtemp(prefix=f"runner_{user_id}_")

    tool_path = os.path.join(workspace, filename)

    try:
        with open(tool_path, "w", encoding="utf-8") as f:
            f.write(code)

        process = subprocess.Popen(
            [
                sys.executable,
                "-u",
                "-c",
                BOOTSTRAP_CODE,
                tool_path
            ],
            cwd=workspace,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )

        session = {
            "process": process,
            "workspace": workspace,
            "waiting": False,
            "output": []
        }

        with sessions_lock:
            sessions[user_id] = session

        # قراءة نتيجة الأداة
        while True:

            line = process.stdout.readline()

            if line == "":
                break

            line = line.rstrip("\r\n")

            # =========================
            # الأداة طلبت input()
            # =========================

            if line.startswith("__RUNNER_INPUT__"):

                prompt = line[len("__RUNNER_INPUT__"):]

                prompt = prompt.replace("\\n", "\n")

                with sessions_lock:
                    if user_id not in sessions:
                        break

                    sessions[user_id]["waiting"] = True

                if prompt.strip():
                    bot.send_message(
                        user_id,
                        f"⌨️ {prompt}"
                    )
                else:
                    bot.send_message(
                        user_id,
                        "⌨️ الأداة تنتظر منك إدخالًا:"
                    )

                continue

            # =========================
            # إخراج الأداة الطبيعي
            # =========================

            if line:
                session["output"].append(line)

                # نرسل الإخراج للمستخدم
                # على دفعات صغيرة
                if len(session["output"]) >= 20:
                    text = "\n".join(session["output"][-20:])

                    try:
                        bot.send_message(
                            user_id,
                            f"📤 الناتج:\n{text}"
                        )
                    except Exception:
                        pass

                    session["output"].clear()

        process.wait()

        # إرسال أي إخراج متبقي
        if session["output"]:
            text = "\n".join(session["output"])

            if text.strip():
                bot.send_message(
                    user_id,
                    f"📤 الناتج:\n{text}"
                )

        # =========================
        # النتيجة النهائية
        # =========================

        if process.returncode == 0:
            bot.send_message(
                user_id,
                "✅ انتهى تشغيل الأداة."
            )

        else:
            bot.send_message(
                user_id,
                f"❌ الأداة انتهت بخطأ.\n"
                f"Exit Code: {process.returncode}"
            )

    except Exception as e:

        bot.send_message(
            user_id,
            f"❌ حدث خطأ في تشغيل الأداة:\n{e}"
        )

    finally:

        with sessions_lock:
            sessions.pop(user_id, None)

        try:
            shutil.rmtree(workspace, ignore_errors=True)
        except Exception:
            pass


# =========================
# استقبال ملفات Python
# =========================

@bot.message_handler(content_types=["document"])
def handle_file(message):

    filename = message.document.file_name

    if not filename.lower().endswith(".py"):
        bot.send_message(
            message.chat.id,
            "❌ أرسل ملف Python بصيغة .py فقط."
        )
        return

    user_id = message.chat.id

    with sessions_lock:
        if user_id in sessions:
            bot.send_message(
                user_id,
                "⚠️ عندك أداة تعمل حاليًا.\n"
                "استخدم /stop أولًا."
            )
            return

    bot.send_message(
        user_id,
        f"📁 استلمت: {filename}\n"
        "▶️ جاري التشغيل..."
    )

    try:
        file_info = bot.get_file(message.document.file_id)

        downloaded = bot.download_file(
            file_info.file_path
        )

        code = downloaded.decode(
            "utf-8",
            errors="ignore"
        )

    except Exception as e:

        bot.send_message(
            user_id,
            f"❌ فشل تحميل الملف:\n{e}"
        )
        return

    threading.Thread(
        target=run_python_code,
        args=(user_id, code, filename),
        daemon=True
    ).start()


# =========================
# استقبال كود Python كنص
# =========================

def extract_code(text):

    text = text.strip()

    # ```python
    # code
    # ```

    if text.startswith("```"):

        lines = text.splitlines()

        if lines:
            lines = lines[1:]

        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        return "\n".join(lines)

    return None


@bot.message_handler(
    func=lambda message: (
        message.text is not None
        and message.text.strip().startswith("```")
    )
)
def handle_text_code(message):

    user_id = message.chat.id

    with sessions_lock:
        if user_id in sessions:
            session = sessions[user_id]

            if session.get("waiting"):

                process = session.get("process")

                try:
                    process.stdin.write(
                        message.text + "\n"
                    )
                    process.stdin.flush()

                    session["waiting"] = False

                except Exception:
                    bot.send_message(
                        user_id,
                        "❌ تعذر إرسال الإدخال للأداة."
                    )

            else:
                bot.send_message(
                    user_id,
                    "⚠️ الأداة تعمل حاليًا، لكنها لا تنتظر إدخالًا."
                )

            return

    code = extract_code(message.text)

    if not code:
        bot.send_message(
            user_id,
            "❌ لم أستطع قراءة الكود."
        )
        return

    bot.send_message(
        user_id,
        "▶️ جاري تشغيل الكود..."
    )

    threading.Thread(
        target=run_python_code,
        args=(user_id, code, "text_tool.py"),
        daemon=True
    ).start()


# =========================
# استقبال input من الأداة
# =========================

@bot.message_handler(
    func=lambda message: (
        message.text is not None
        and not message.text.startswith("/")
    )
)
def handle_input(message):

    user_id = message.chat.id

    with sessions_lock:
        session = sessions.get(user_id)

    if not session:
        return

    if not session.get("waiting"):
        return

    process = session.get("process")

    try:

        # نرسل إجابة المستخدم إلى input()
        process.stdin.write(
            message.text + "\n"
        )

        process.stdin.flush()

        with sessions_lock:
            if user_id in sessions:
                sessions[user_id]["waiting"] = False

    except Exception as e:

        bot.send_message(
            user_id,
            f"❌ تعذر إرسال الإدخال:\n{e}"
        )


# =========================
# تشغيل Flask
# =========================

def run_flask():

    port = int(os.getenv("PORT", "10000"))

    app.run(
        host="0.0.0.0",
        port=port
    )


# =========================
# تشغيل البوت
# =========================

if __name__ == "__main__":

    threading.Thread(
        target=run_flask,
        daemon=True
    ).start()

    bot.infinity_polling()
