import os
import asyncio
import aiosqlite
import time
import aiohttp
from aiohttp import web
from telebot.async_telebot import AsyncTeleBot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, Message

# ================= سيرفر وهمي لإبقاء Render شغال =================
async def handle(request):
    return web.Response(text="Bot is running live!")

async def web_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"تم تشغيل سيرفر الويب الجانبي على البورت {port}")

# ================= الاعدادات =================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "8434194552"))

bot = AsyncTeleBot(BOT_TOKEN)
DB_NAME = "bot_database_v9.db"
admin_states = {}

# ================= قاعدة البيانات =================
async def init_db():
    async with aiosqlite.connect(DB_NAME, timeout=60) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                attempts INTEGER DEFAULT 0,
                last_attempt REAL DEFAULT 0,
                unlocked INTEGER DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS content (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id INTEGER,
                media_group_id TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS secret_content (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id INTEGER,
                media_group_id TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        await db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('password', '1234')")
        await db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('secret_password', '5678')")
        await db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('post_message', 'مشاهدة ممتعة. تذكر ان المحتوى بينحذف قريب.')")
        await db.commit()

async def get_setting(key):
    async with aiosqlite.connect(DB_NAME, timeout=60) as db:
        async with db.execute("SELECT value FROM settings WHERE key=?", (key,)) as cursor:
            result = await cursor.fetchone()
            return result[0] if result else ""

async def set_setting(key, value):
    async with aiosqlite.connect(DB_NAME, timeout=60) as db:
        await db.execute("UPDATE settings SET value=? WHERE key=?", (value, key))
        await db.commit()

# ================= لوحة تحكم المدير =================
@bot.message_handler(commands=['start'], func=lambda msg: msg.from_user.id == ADMIN_ID)
async def admin_panel(message: Message):
    admin_states.pop(ADMIN_ID, None)

    async with aiosqlite.connect(DB_NAME, timeout=60) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as cursor:
            total_users = (await cursor.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM users WHERE unlocked=1") as cursor:
            unlocked_users = (await cursor.fetchone())[0]

    current_pass = await get_setting('password')
    secret_pass = await get_setting('secret_password')

    text = (
        "لوحة تحكم المدير\n\n"
        f"عدد المشتركين: {total_users}\n"
        f"اللي فتحوا المحتوى: {unlocked_users}\n"
        f"الباسورد العادي الحالي: {current_pass}\n"
        f"الباسورد السري الحالي: {secret_pass}\n\n"
        "اختر من الازرار تحت:"
    )

    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("تغيير الباسورد العادي", callback_data="change_pass"))
    keyboard.add(InlineKeyboardButton("تغيير الباسورد السري", callback_data="change_secret_pass"))
    keyboard.add(InlineKeyboardButton("تحديث المحتوى العادي", callback_data="update_content"))
    keyboard.add(InlineKeyboardButton("تحديث المحتوى السري", callback_data="update_secret_content"))
    keyboard.add(InlineKeyboardButton("تعديل رسالة النهاية", callback_data="change_post_message"))
    keyboard.add(InlineKeyboardButton("تصفير محاولات المشتركين", callback_data="reset_all"))

    await bot.reply_to(message, text, reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: call.from_user.id == ADMIN_ID)
async def admin_callbacks(call):
    data = call.data

    if data == "change_pass":
        admin_states[ADMIN_ID] = "waiting_for_password"
        await bot.send_message(call.message.chat.id, "اكتب الباسورد العادي الجديد وارسل:")

    elif data == "change_secret_pass":
        admin_states[ADMIN_ID] = "waiting_for_secret_password"
        await bot.send_message(call.message.chat.id, "اكتب الباسورد السري الجديد وارسل:")

    elif data == "update_content":
        admin_states[ADMIN_ID] = "waiting_for_content"
        async with aiosqlite.connect(DB_NAME, timeout=60) as db:
            await db.execute("DELETE FROM content")
            await db.commit()

        await bot.send_message(
            call.message.chat.id,
            "تم مسح المحتوى العادي القديم عشان نبدأ على نظافة.\n\n"
            "ارسل المحتوى العادي الجديد الحين (البومات، صور، فيديوهات، كلام).\n"
            "اذا خلصت ارسل: /done"
        )

    elif data == "update_secret_content":
        admin_states[ADMIN_ID] = "waiting_for_secret_content"
        async with aiosqlite.connect(DB_NAME, timeout=60) as db:
            await db.execute("DELETE FROM secret_content")
            await db.commit()

        await bot.send_message(
            call.message.chat.id,
            "تم مسح المحتوى السري القديم عشان نبدأ على نظافة.\n\n"
            "ارسل المحتوى السري الجديد الحين (البومات، صور، فيديوهات، كلام).\n"
            "اذا خلصت ارسل: /done"
        )

    elif data == "change_post_message":
        admin_states[ADMIN_ID] = "waiting_for_post_message"
        current_msg = await get_setting('post_message')
        await bot.send_message(
            call.message.chat.id,
            f"الرسالة الحالية هي:\n\n{current_msg}\n\nارسل الرسالة الجديدة الحين:"
        )

    elif data == "reset_all":
        async with aiosqlite.connect(DB_NAME, timeout=60) as db:
            await db.execute("UPDATE users SET attempts=0, last_attempt=0, unlocked=0")
            await db.commit()
        await bot.answer_callback_query(call.id, "تم التصفير.")
        await bot.send_message(call.message.chat.id, "تم تصفير كل المحاولات، يقدرون يدخلون من جديد.")

    await bot.answer_callback_query(call.id)

@bot.message_handler(commands=['done'], func=lambda msg: msg.from_user.id == ADMIN_ID)
async def done_adding_content(message: Message):
    state = admin_states.get(ADMIN_ID)
    if state in ["waiting_for_content", "waiting_for_secret_content"]:
        admin_states.pop(ADMIN_ID, None)
        await bot.reply_to(message, "تم حفظ المحتوى بنجاح.")

# ================= التقاط مدخلات المدير =================
@bot.message_handler(content_types=['text', 'photo', 'video', 'document', 'audio', 'voice', 'animation', 'location', 'contact'],
                     func=lambda msg: msg.from_user.id == ADMIN_ID)
async def handle_admin_inputs(message: Message):
    if message.text and message.text.startswith('/'):
        return

    state = admin_states.get(ADMIN_ID)

    if state == "waiting_for_password":
        if message.content_type == 'text':
            await set_setting('password', message.text)
            admin_states.pop(ADMIN_ID, None)
            await bot.reply_to(message, f"تم اعتماد الباسورد العادي الجديد: {message.text}")
        else:
            await bot.reply_to(message, "الباسورد لازم يكون نص.")

    elif state == "waiting_for_secret_password":
        if message.content_type == 'text':
            await set_setting('secret_password', message.text)
            admin_states.pop(ADMIN_ID, None)
            await bot.reply_to(message, f"تم اعتماد الباسورد السري الجديد: {message.text}")
        else:
            await bot.reply_to(message, "الباسورد لازم يكون نص.")

    elif state == "waiting_for_post_message":
        if message.content_type == 'text':
            await set_setting('post_message', message.text)
            admin_states.pop(ADMIN_ID, None)
            await bot.reply_to(message, "تم حفظ رسالة النهاية.")
        else:
            await bot.reply_to(message, "رسالة النهاية لازم تكون نص.")

    elif state == "waiting_for_content":
        media_group_id = message.media_group_id if hasattr(message, 'media_group_id') else None
        async with aiosqlite.connect(DB_NAME, timeout=60) as db:
            await db.execute("INSERT INTO content (message_id, media_group_id) VALUES (?, ?)",
                             (message.message_id, media_group_id))
            await db.commit()

    elif state == "waiting_for_secret_content":
        media_group_id = message.media_group_id if hasattr(message, 'media_group_id') else None
        async with aiosqlite.connect(DB_NAME, timeout=60) as db:
            await db.execute("INSERT INTO secret_content (message_id, media_group_id) VALUES (?, ?)",
                             (message.message_id, media_group_id))
            await db.commit()

# ================= نظام المشتركين =================
@bot.message_handler(commands=['start'], func=lambda msg: msg.from_user.id != ADMIN_ID)
async def user_start(message: Message):
    user_id = message.from_user.id
    async with aiosqlite.connect(DB_NAME, timeout=60) as db:
        await db.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
        await db.commit()

    await bot.reply_to(message, "هلا بك. عشان تشوف المحتوى ياليت ترسل الباسورد:")

@bot.message_handler(func=lambda msg: msg.from_user.id != ADMIN_ID)
async def handle_user_password(message: Message):
    user_id = message.from_user.id
    current_time = time.time()

    async with aiosqlite.connect(DB_NAME, timeout=60) as db:
        async with db.execute("SELECT attempts, last_attempt FROM users WHERE user_id=?", (user_id,)) as cursor:
            row = await cursor.fetchone()

        if not row:
            return

        attempts, last_attempt = row
        real_password = await get_setting('password')
        secret_password = await get_setting('secret_password')
        user_input = message.text.strip()

        is_secret = False

        if user_input == real_password:
            is_secret = False
        elif user_input == secret_password:
            is_secret = True
        else:
            await bot.reply_to(message, "الباسورد غلط، تاكد منه.")
            return

        if attempts >= 2:
            await bot.reply_to(message, "استهلكت كل محاولاتك، ما تقدر تفتح المحتوى الحين.")
            return

        if attempts == 1 and (current_time - last_attempt) < 1800:
            remaining_time = int((1800 - (current_time - last_attempt)) / 60)
            await bot.reply_to(message, f"لازم تنتظر {remaining_time} دقيقة قبل تجرب مرة ثانية.")
            return

        await db.execute("UPDATE users SET attempts=?, last_attempt=?, unlocked=1 WHERE user_id=?",
                       (attempts + 1, current_time, user_id))
        await db.commit()

    await bot.reply_to(message, "الباسورد صح. ثواني والمحتوى بيكون عندك.")

    asyncio.create_task(send_and_delete_content(user_id, is_secret))

# ================= محرك التحويل المباشر =================
async def send_and_delete_content(user_id: int, is_secret: bool):
    table_name = "secret_content" if is_secret else "content"

    async with aiosqlite.connect(DB_NAME, timeout=60) as db:
        async with db.execute(f"SELECT message_id, media_group_id FROM {table_name} ORDER BY message_id ASC") as cursor:
            content_messages = await cursor.fetchall()

    if not content_messages:
        await bot.send_message(user_id, "المعذرة، المحتوى مو متوفر حاليا.")
        return

    sent_message_ids = []
    actions = []
    current_group_id = None
    current_group_ids = []

    for msg_id, media_group_id in content_messages:
        if media_group_id:
            if media_group_id == current_group_id:
                current_group_ids.append(msg_id)
            else:
                if current_group_ids:
                    current_group_ids.sort()
                    actions.append({"type": "group", "ids": current_group_ids})
                current_group_id = media_group_id
                current_group_ids = [msg_id]
        else:
            if current_group_ids:
                current_group_ids.sort()
                actions.append({"type": "group", "ids": current_group_ids})
                current_group_ids = []
                current_group_id = None
            actions.append({"type": "single", "id": msg_id})

    if current_group_ids:
        current_group_ids.sort()
        actions.append({"type": "group", "ids": current_group_ids})

    url_copy = f"https://api.telegram.org/bot{BOT_TOKEN}/copyMessages"

    for action in actions:
        if action["type"] == "single":
            try:
                sent_msg = await bot.copy_message(chat_id=user_id, from_chat_id=ADMIN_ID, message_id=action["id"])
                sent_message_ids.append(sent_msg.message_id)
            except:
                pass
            await asyncio.sleep(0.5)

        elif action["type"] == "group":
            payload = {
                "chat_id": user_id,
                "from_chat_id": ADMIN_ID,
                "message_ids": action["ids"]
            }
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(url_copy, json=payload) as resp:
                        res = await resp.json()
                        if res.get("ok"):
                            for msg_obj in res.get("result", []):
                                new_msg_id = msg_obj.get("message_id")
                                if new_msg_id:
                                    sent_message_ids.append(new_msg_id)
            except:
                pass
            await asyncio.sleep(1)

    post_message_text = await get_setting('post_message')
    if post_message_text:
        try:
            post_msg = await bot.send_message(user_id, post_message_text)
            sent_message_ids.append(post_msg.message_id)
        except:
            pass

    try:
        timer_msg = await bot.send_message(user_id, "باقي على حذف المحتوى: 10 دقايق")
        sent_message_ids.append(timer_msg.message_id)

        for remaining_mins in range(9, 0, -1):
            await asyncio.sleep(60)
            try:
                await bot.edit_message_text(
                    f"باقي على حذف المحتوى: {remaining_mins} دقايق",
                    chat_id=user_id,
                    message_id=timer_msg.message_id
                )
            except:
                pass

        await asyncio.sleep(60)
    except:
        await asyncio.sleep(600)

    url_delete = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteMessages"
    for i in range(0, len(sent_message_ids), 100):
        chunk = sent_message_ids[i:i+100]
        if not chunk: continue
        payload = {
            "chat_id": user_id,
            "message_ids": chunk
        }
        try:
            async with aiohttp.ClientSession() as session:
                await session.post(url_delete, json=payload)
        except:
            pass

    try:
        await bot.send_message(user_id, "انتهى الوقت، وانحذف المحتوى.")
    except:
        pass

# ================= تشغيل البوت =================
async def main():
    print("جاري تشغيل قاعدة البيانات...")
    await init_db()
    
    print("تشغيل سيرفر الويب الجانبي (aiohttp)...")
    await web_server()
    
    print("تنظيف الاتصالات المعلقة (لحماية البوت من التعارض)...")
    await bot.delete_webhook(drop_pending_updates=True)
    
    print("البوت شغال الحين وينتظر الرسايل...")
    await bot.polling(non_stop=True)

if __name__ == "__main__":
    asyncio.run(main())
