import asyncio
import logging
import sqlite3
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

import os
from dotenv import load_dotenv

load_dotenv()  # .env faylni o‘qiydi

TOKEN = os.getenv("TOKEN")

if not TOKEN:
    raise ValueError("BOT_TOKEN .env faylda topilmadi!")


# ================== SOZLAMALAR ==================

ADMIN_ID = 1787857253

logging.basicConfig(level=logging.INFO)

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ================== SQLITE ==================
conn = sqlite3.connect("bot.db")
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS movies (
    code TEXT PRIMARY KEY,
    file_id TEXT
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS channels (
    username TEXT PRIMARY KEY
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY
)
""")

conn.commit()

# ================== STATE'LAR ==================
class AddMovie(StatesGroup):
    video = State()
    code = State()

class DeleteMovie(StatesGroup):
    code = State()

class ChannelManage(StatesGroup):
    add = State()
    remove = State()

class Broadcast(StatesGroup):
    message = State()

# ================== YORDAMCHI FUNKSIYALAR ==================
async def check_subscription(user_id):
    cur.execute("SELECT username FROM channels")
    channels = cur.fetchall()

    for (username,) in channels:
        try:
            member = await bot.get_chat_member(username, user_id)
            if member.status not in ("member", "administrator", "creator"):
                return False
        except:
            return False
    return True

def sub_keyboard():
    cur.execute("SELECT username FROM channels")
    kb = []
    for (u,) in cur.fetchall():
        kb.append([InlineKeyboardButton(text="📢 Kanal", url=f"https://t.me/{u.replace('@','')}")])
    kb.append([InlineKeyboardButton(text="✅ Obuna bo‘ldim", callback_data="check_sub")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def admin_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎬 Kino qo‘shish", callback_data="add_movie")],
        [InlineKeyboardButton(text="❌ Kino o‘chirish", callback_data="del_movie")],
        [InlineKeyboardButton(text="📊 Statistika", callback_data="stats")],
        [InlineKeyboardButton(text="📢 Kanal qo‘shish", callback_data="add_channel")],
        [InlineKeyboardButton(text="🗑 Kanal olib tashlash", callback_data="del_channel")],
        [InlineKeyboardButton(text="📨 Barchaga xabar", callback_data="broadcast")]
    ])

# ================== /START ==================
@dp.message(Command("start"))
async def start(message: types.Message):
    cur.execute("INSERT OR IGNORE INTO users VALUES (?)", (message.from_user.id,))
    conn.commit()

    if message.from_user.id == ADMIN_ID:
        await message.answer("👑 ADMIN PANEL", reply_markup=admin_menu())
        return

    if not await check_subscription(message.from_user.id):
        await message.answer(
            "❗ Botdan foydalanish uchun kanallarga obuna bo‘ling:",
            reply_markup=sub_keyboard()
        )
        return

    await message.answer("🎬 Kino kodini yuboring")

# ================== OBUNA TEKSHIRISH ==================
@dp.callback_query(lambda c: c.data == "check_sub")
async def check_sub(call: types.CallbackQuery):
    if await check_subscription(call.from_user.id):
        await call.message.delete()
        await call.message.answer("✅ Endi kino kodini yuboring")
    else:
        await call.answer("⛔ Hali obuna emas!", show_alert=True)

# ================== ADMIN: KINO QO‘SHISH ==================
@dp.callback_query(lambda c: c.data == "add_movie")
async def add_movie(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(AddMovie.video)
    await call.message.answer("🎥 Kinoni yuboring")

@dp.message(AddMovie.video)
async def save_video(message: types.Message, state: FSMContext):
    await state.update_data(file_id=message.video.file_id)
    await state.set_state(AddMovie.code)
    await message.answer("🔢 Kino kodi:")

@dp.message(AddMovie.code)
async def save_code(message: types.Message, state: FSMContext):
    cur.execute(
        "INSERT OR REPLACE INTO movies VALUES (?, ?)",
        (message.text.strip(), (await state.get_data())["file_id"])
    )
    conn.commit()
    await state.clear()
    await message.answer("✅ Kino saqlandi", reply_markup=admin_menu())

# ================== ADMIN: KINO O‘CHIRISH ==================
@dp.callback_query(lambda c: c.data == "del_movie")
async def del_movie(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(DeleteMovie.code)
    await call.message.answer("❌ Kino kodi:")

@dp.message(DeleteMovie.code)
async def delete_movie(message: types.Message, state: FSMContext):
    cur.execute("DELETE FROM movies WHERE code=?", (message.text.strip(),))
    conn.commit()
    await state.clear()
    await message.answer("🗑 Kino o‘chirildi", reply_markup=admin_menu())

# ================== ADMIN: STATISTIKA ==================
@dp.callback_query(lambda c: c.data == "stats")
async def stats(call: types.CallbackQuery):
    cur.execute("SELECT COUNT(*) FROM users")
    users = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM movies")
    movies = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM channels")
    channels = cur.fetchone()[0]

    await call.message.answer(
        f"📊 STATISTIKA\n\n"
        f"👥 Foydalanuvchilar: {users}\n"
        f"🎬 Kinolar: {movies}\n"
        f"📢 Kanallar: {channels}"
    )

# ================== ADMIN: KANAL ==================
@dp.callback_query(lambda c: c.data == "add_channel")
async def add_ch(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(ChannelManage.add)
    await call.message.answer("➕ Kanal @username:")

@dp.message(ChannelManage.add)
async def save_ch(message: types.Message, state: FSMContext):
    cur.execute("INSERT OR IGNORE INTO channels VALUES (?)", (message.text.strip(),))
    conn.commit()
    await state.clear()
    await message.answer("✅ Kanal qo‘shildi", reply_markup=admin_menu())

@dp.callback_query(lambda c: c.data == "del_channel")
async def del_ch(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(ChannelManage.remove)
    await call.message.answer("🗑 Kanal @username:")

@dp.message(ChannelManage.remove)
async def remove_ch(message: types.Message, state: FSMContext):
    cur.execute("DELETE FROM channels WHERE username=?", (message.text.strip(),))
    conn.commit()
    await state.clear()
    await message.answer("❌ Kanal olib tashlandi", reply_markup=admin_menu())

# ================== ADMIN: BARCHAGA XABAR ==================
@dp.callback_query(lambda c: c.data == "broadcast")
async def broadcast_start(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(Broadcast.message)
    await call.message.answer("📨 Xabar matni:")

@dp.message(Broadcast.message)
async def send_broadcast(message: types.Message, state: FSMContext):
    cur.execute("SELECT user_id FROM users")
    users = cur.fetchall()

    for (uid,) in users:
        try:
            await bot.send_message(uid, message.text)
            await asyncio.sleep(0.03)
        except:
            pass

    await state.clear()
    await message.answer("✅ Xabar yuborildi", reply_markup=admin_menu())

# ================== USER: KINO OLISH ==================
@dp.message()
async def get_movie(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        return

    if not await check_subscription(message.from_user.id):
        await message.answer("❗ Avval obuna bo‘ling", reply_markup=sub_keyboard())
        return

    cur.execute("SELECT file_id FROM movies WHERE code=?", (message.text.strip(),))
    movie = cur.fetchone()

    if movie:
        await message.answer_video(movie[0], caption="🎬 Yoqimli tomosha!")
    else:
        await message.answer("❌ Bunday kodli kino yo‘q")

# ================== RUN ==================
async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
