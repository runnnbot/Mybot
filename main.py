import os
import sys
import subprocess
import threading
import tempfile
import shutil
import ast
import builtins
import re
import time

import telebot
from flask import Flask


# =========================================================
# الإعدادات
# =========================================================

TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise RuntimeError("BOT_TOKEN غير موجود في Environment Variables")

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)


# =========================================================
# الجلسات
# =========================================================

sessions = {}
sessions_lock = threading.Lock()


# =========================================================
# المكتبات الأساسية الموجودة في requirements.txt
# =========================================================

BASE_PACKAGES = {
    "telebot": "pyTelegramBotAPI",
    "flask": "Flask",
    "requests": "requests",
    "bs4": "beautifulsoup4",
    "lxml": "lxml",
    "PIL": "pillow",
    "qrcode": "qrcode",
    "pytube": "pytube",
    "yt_dlp": "yt-dlp",
    "openpyxl": "openpyxl",
    "PyPDF2": "PyPDF2",
    "docx": "python-docx",
    "barcode": "python-barcode",
    "faker": "faker",
    "user_agent": "user_agent",
    "fake_useragent": "fake_useragent",
    "httpx": "httpx",
}


# =========================================================
# مكتبات Python القياسية
# =========================================================

STDLIB = set(getattr(sys, "stdlib_module_names", set()))

STDLIB.update({
    "os",
    "sys",
    "time",
    "json",
    "re",
    "math",
    "random",
    "datetime",
    "calendar",
    "string",
    "collections",
    "itertools",
    "functools",
    "typing",
    "pathlib",
    "subprocess",
    "threading",
    "asyncio",
    "socket",
    "ssl",
    "urllib",
    "http",
    "email",
    "hashlib",
    "base64",
    "binascii",
    "csv",
    "sqlite3",
    "logging",
    "traceback",
    "tempfile",
    "shutil",
    "glob",
    "io",
    "platform",
    "uuid",
    "secrets",
    "statistics",
    "decimal",
    "fractions",
    "dataclasses",
    "enum",
    "abc",
    "copy",
    "pickle",
    "struct",
    "textwrap",
    "warnings",
    "inspect",
    "contextlib",
    "functools",
    "operator",
    "types",
})


# =========================================================
# تحويل اسم import إلى اسم pip
# =========================================================

def package_name(module_name):
    root = module_name.split(".")[0]

    if root in BASE_PACKAGES:
        return BASE_PACKAGES[root]

    # أسماء شائعة يكون اسم pip فيها مختلفًا
    known = {
        "cv2": "opencv-python",
        "yaml": "PyYAML",
        "Crypto": "pycryptodome",
        "bs4": "beautifulsoup4",
        "PIL": "pillow",
        "sklearn": "scikit-learn",
        "dateutil": "python-dateutil",
        "dotenv": "python-dotenv",
        "jwt": "PyJWT",
        "selenium": "selenium",
        "numpy": "numpy",
        "pandas": "pandas",
        "matplotlib": "matplotlib",
    }

    return known.get(root, root)


# =========================================================
# استخراج الـ imports من الكود
# =========================================================

def find_imports(code):
    found = set()

    try:
        tree = ast.parse(code)
    except Exception:
        return found

    for node in ast.walk(tree):

        if isinstance(node, ast.Import):

            for alias in node.names:
                found.add(alias.name.split(".")[0])

        elif isinstance(node, ast.ImportFrom):

            if node.module:
                found.add(node.module.split(".")[0])

    return found


# =========================================================
# التحقق هل المكتبة مثبتة
# =========================================================

def is_module_available(module_name, extra_path=None):

    env = os.environ.copy()

    if extra_path:
        old = env.get("PYTHONPATH", "")

        if old:
            env["PYTHONPATH"] = extra_path + os.pathsep + old
        else:
            env["PYTHONPATH"] = extra_path

    try:

        result = subprocess.run(
            [
                sys.executable,
                "-c",
                f"import {module_name}"
            ],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=20
        )

        return result.returncode == 0

    except Exception:
        return False


# =========================================================
# تثبيت مكتبة في المجلد المؤقت
# =========================================================

def install_package(package, target_dir):

    try:

        os.makedirs(target_dir, exist_ok=True)

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "--no-input",
                "--target",
                target_dir,
                package
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=300
        )

        return result.returncode == 0, result.stdout

    except subprocess.TimeoutExpired:

        return False, "انتهى وقت تثبيت المكتبة."

    except Exception as e:

        return False, str(e)


# =========================================================
# تجهيز المكتبات الناقصة دفعة واحدة
# =========================================================

def prepare_libraries(code, temp_lib):

    imports = find_imports(code)

    missing = []

    for module in sorted(imports):

        # مكتبات Python الأساسية
        if module in STDLIB:
            continue

        # المكتبات الموجودة أساسًا في Render
        if module in BASE_PACKAGES:
            if is_module_available(module):
                continue

        # إذا لم تكن موجودة
        if not is_module_available(
            module,
            extra_path=temp_lib
        ):
            missing.append(module)

    if not missing:
        return True, []

    packages = []

    for module in missing:
        package = package_name(module)

        if package not in packages:
            packages.append(package)

    failed = []

    for package in packages:

        success, output = install_package(
            package,
            temp_lib
        )

        if not success:
            failed.append({
                "package": package,
                "output": output
            })

    return len(failed) == 0, failed


# =========================================================
# bootstrap
#
# هذا الكود يشغل الأداة ويعترض input()
# =========================================================

BOOTSTRAP_CODE = r'''
import builtins
import sys
import runpy
import traceback

tool_file = sys.argv[1]


def runner_input(prompt=""):

    prompt = str(prompt).replace("\n", "\\n")

    print(
        "__RUNNER_INPUT__" + prompt,
        flush=True
    )

    answer = sys.stdin.readline()

    if answer == "":
        raise EOFError("تم إغلاق الإدخال")

    return answer.rstrip("\r\n")


builtins.input = runner_input


try:

    runpy.run_path(
        tool_file,
        run_name="__main__"
    )

except SystemExit as e:

    code = e.code if isinstance(e.code, int) else 0
    sys.exit(code)

except Exception:

    traceback.print_exc()
    sys.exit(1)
'''


# =========================================================
# استخراج المكتبة من ModuleNotFoundError
# =========================================================

def extract_missing_module(text):

    patterns = [
        r"No module named ['\"]([^'\"]+)['\"]",
        r"ModuleNotFoundError: No module named ['\"]([^'\"]+)['\"]",
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text
        )

        if match:
            return match.group(1).split(".")[0]

    return None


# =========================================================
# تشغيل الأداة
# =========================================================

def run_python_code(user_id, code, filename="tool.py"):

    workspace = tempfile.mkdtemp(
        prefix=f"runner_{user_id}_"
    )

    temp_lib = os.path.join(
        workspace,
        "libraries"
    )

    tool_path = os.path.join(
        workspace,
        filename
    )

    try:

        # -----------------------------------------
        # حفظ الأداة
        # -----------------------------------------

        with open(
            tool_path,
            "w",
            encoding="utf-8"
        ) as f:

            f.write(code)

        # -----------------------------------------
        # تجهيز المكتبات
        # -----------------------------------------

        bot.send_message(
            user_id,
            "🔍 أفحص مكتبات الأداة..."
        )

        success, failed = prepare_libraries(
            code,
            temp_lib
        )

        if not success:

            text = "❌ فشل تثبيت بعض المكتبات:\n\n"

            for item in failed:
                text += (
                    f"• {item['package']}\n"
                )

            bot.send_message(
                user_id,
                text
            )

            return

        # -----------------------------------------
        # تشغيل الأداة
        # -----------------------------------------

        attempts = 0
        max_attempts = 10

        while attempts < max_attempts:

            attempts += 1

            env = os.environ.copy()

            old_pythonpath = env.get(
                "PYTHONPATH",
                ""
            )

            if old_pythonpath:

                env["PYTHONPATH"] = (
                    temp_lib
                    + os.pathsep
                    + workspace
                    + os.pathsep
                    + old_pythonpath
                )

            else:

                env["PYTHONPATH"] = (
                    temp_lib
                    + os.pathsep
                    + workspace
                )

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
                bufsize=1,
                env=env
            )

            session = {
                "process": process,
                "workspace": workspace,
                "waiting": False,
                "output": []
            }

            with sessions_lock:
                sessions[user_id] = session

            missing_during_run = None

            # -----------------------------------------
            # قراءة إخراج الأداة
            # -----------------------------------------

            while True:

                line = process.stdout.readline()

                if line == "":
                    break

                line = line.rstrip(
                    "\r\n"
                )

                # input()
                if line.startswith(
                    "__RUNNER_INPUT__"
                ):

                    prompt = line[
                        len("__RUNNER_INPUT__"):
                    ]

                    prompt = prompt.replace(
                        "\\n",
                        "\n"
                    )

                    with sessions_lock:

                        if user_id not in sessions:
                            break

                        sessions[user_id][
                            "waiting"
                        ] = True

                    if prompt.strip():

                        bot.send_message(
                            user_id,
                            f"⌨️ {prompt}"
                        )

                    else:

                        bot.send_message(
                            user_id,
                            "⌨️ الأداة تنتظر إدخالًا:"
                        )

                    continue

                # -----------------------------------------
                # اكتشاف مكتبة ناقصة
                # -----------------------------------------

                if "ModuleNotFoundError" in line:

                    missing_during_run = (
                        extract_missing_module(
                            line
                        )
                    )

                if line:

                    session["output"].append(
                        line
                    )

                    if len(
                        session["output"]
                    ) >= 20:

                        text = "\n".join(
                            session["output"][-20:]
                        )

                        try:

                            bot.send_message(
                                user_id,
                                f"📤 الناتج:\n{text}"
                            )

                        except Exception:
                            pass

                        session[
                            "output"
                        ].clear()

            process.wait()

            # -----------------------------------------
            # المكتبة الناقصة ظهرت أثناء التشغيل
            # -----------------------------------------

            if missing_during_run:

                package = package_name(
                    missing_during_run
                )

                bot.send_message(
                    user_id,
                    f"📦 اكتشفت مكتبة ناقصة: "
                    f"{package}\n"
                    f"⏳ جاري تثبيتها مؤقتًا..."
                )

                success, output = install_package(
                    package,
                    temp_lib
                )

                if success:

                    bot.send_message(
                        user_id,
                        f"✅ تم تجهيز {package}\n"
                        "▶️ سأعيد تشغيل الأداة تلقائيًا..."
                    )

                    with sessions_lock:
                        sessions.pop(
                            user_id,
                            None
                        )

                    continue

                else:

                    bot.send_message(
                        user_id,
                        f"❌ لم أستطع تثبيت {package}."
                    )

                    break

            # -----------------------------------------
            # إخراج متبقي
            # -----------------------------------------

            if session["output"]:

                text = "\n".join(
                    session["output"]
                )

                if text.strip():

                    bot.send_message(
                        user_id,
                        f"📤 الناتج:\n{text}"
                    )

            # -----------------------------------------
            # النتيجة
            # -----------------------------------------

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

            break

    except Exception as e:

        bot.send_message(
            user_id,
            f"❌ حدث خطأ في التشغيل:\n{e}"
        )

    finally:

        with sessions_lock:
            sessions.pop(
                user_id,
                None
            )

        # -----------------------------------------
        # حذف البيئة المؤقتة
        # -----------------------------------------

        try:

            shutil.rmtree(
                workspace,
                ignore_errors=True
            )

        except Exception:
            pass


# =========================================================
# /start
# =========================================================

@bot.message_handler(
    commands=["start"]
)
def start(message):

    bot.send_message(
        message.chat.id,
        "✅ البوت شغال\n\n"
        "📁 أرسل ملف Python بصيغة .py\n"
        "أو أرسل الكود داخل ```python ... ```\n\n"
        "المكتبات الناقصة يتم تجهيزها تلقائيًا."
    )


# =========================================================
# /stop
# =========================================================

@bot.message_handler(
    commands=["stop"]
)
def stop(message):

    user_id = message.chat.id

    with sessions_lock:
        session = sessions.get(
            user_id
        )

    if not session:

        bot.send_message(
            user_id,
            "ما فيه أداة تعمل حاليًا."
        )

        return

    process = session.get(
        "process"
    )

    try:

        if process and process.poll() is None:
            process.kill()

    except Exception:
        pass

    with sessions_lock:
        sessions.pop(
            user_id,
            None
        )

    bot.send_message(
        user_id,
        "🛑 تم إيقاف الأداة."
    )


# =========================================================
# استقبال ملف Python
# =========================================================

@bot.message_handler(
    content_types=["document"]
)
def handle_file(message):

    filename = (
        message.document.file_name
    )

    if not filename.lower().endswith(
        ".py"
    ):

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
        "🔍 جاري تجهيز الأداة..."
    )

    try:

        file_info = bot.get_file(
            message.document.file_id
        )

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
        args=(
            user_id,
            code,
            filename
        ),
        daemon=True
    ).start()


# =========================================================
# استخراج كود النص
# =========================================================

def extract_code(text):

    text = text.strip()

    if text.startswith("```"):

        lines = text.splitlines()

        if lines:
            lines = lines[1:]

        if (
            lines
            and lines[-1].strip() == "```"
        ):
            lines = lines[:-1]

        return "\n".join(lines)

    return None


# =========================================================
# استقبال كود Python كنص
# =========================================================

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

                process = session.get(
                    "process"
                )

                try:

                    process.stdin.write(
                        message.text + "\n"
                    )

                    process.stdin.flush()

                    session[
                        "waiting"
                    ] = False

                except Exception:

                    bot.send_message(
                        user_id,
                        "❌ تعذر إرسال الإدخال للأداة."
                    )

            else:

                bot.send_message(
                    user_id,
                    "⚠️ الأداة تعمل حاليًا، "
                    "لكنها لا تنتظر إدخالًا."
                )

            return

    code = extract_code(
        message.text
    )

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
        args=(
            user_id,
            code,
            "text_tool.py"
        ),
        daemon=True
    ).start()


# =========================================================
# استقبال input من الأداة
# =========================================================

@bot.message_handler(
    func=lambda message: (
        message.text is not None
        and not message.text.startswith("/")
    )
)
def handle_input(message):

    user_id = message.chat.id

    with sessions_lock:
        session = sessions.get(
            user_id
        )

    if not session:
        return

    if not session.get("waiting"):
        return

    process = session.get(
        "process"
    )

    try:

        process.stdin.write(
            message.text + "\n"
        )

        process.stdin.flush()

        with sessions_lock:

            if user_id in sessions:

                sessions[user_id][
                    "waiting"
                ] = False

    except Exception as e:

        bot.send_message(
            user_id,
            f"❌ تعذر إرسال الإدخال:\n{e}"
        )


# =========================================================
# Flask / Render
# =========================================================

@app.route("/")
def home():
    return "Bot is Live!"


@app.route("/health")
def health():
    return "OK"


def run_flask():

    port = int(
        os.getenv(
            "PORT",
            "10000"
        )
    )

    app.run(
        host="0.0.0.0",
        port=port
    )


# =========================================================
# تشغيل البوت
# =========================================================

if __name__ == "__main__":

    threading.Thread(
        target=run_flask,
        daemon=True
    ).start()

    bot.infinity_polling()
