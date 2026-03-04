import asyncio
import sqlite3
import logging
import os
from flask import Flask
from threading import Thread
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (ReplyKeyboardMarkup, KeyboardButton, 
                            InlineKeyboardButton, InlineKeyboardMarkup, 
                            BotCommand, CallbackQuery, ChatJoinRequest)

# --- SERVER ---
app = Flask('')
@app.route('/')
def home(): return "Бот Harmony активен!"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- CONFIG (НОВЫЙ ТОКЕН ТУТ) ---
TOKEN = "8344752199:AAEiWZnI-0RrUB8Pl8YsBw6Jw7Sc3wBFkjo"
ADMIN_ID = 8294726083
CHAT_ID = -1003393441169 
CHAT_LINK = "https://t.me/+yai_7_Z-7_45MDky"
DB_PATH = "database.db"

bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- STATES ---
class RegForm(StatesGroup):
    role = State()
    username = State()

# --- DATABASE ---
def init_db():
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS approved_users (user_id INTEGER PRIMARY KEY, role TEXT, violations INTEGER DEFAULT 0)")
    cursor.execute("CREATE TABLE IF NOT EXISTS all_users (user_id INTEGER PRIMARY KEY, name TEXT)")
    conn.commit(); conn.close()

def is_approved(uid):
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM approved_users WHERE user_id = ?", (uid,))
    res = cursor.fetchone(); conn.close()
    return bool(res)

# --- НОВАЯ МЕХАНИКА ТЕГОВ (MEMBER TAGS) ---
async def set_member_tag(uid, tag_text):
    try:
        # Прямой вызов метода API для новых плашек (Member Tags)
        await bot.make_request("setChatMemberTag", {
            "chat_id": CHAT_ID,
            "user_id": uid,
            "tag": tag_text
        })
        logging.info(f"Установлен тег '{tag_text}' для {uid}")
    except Exception as e:
        logging.error(f"Ошибка Member Tag: {e}")

# --- ЛОГИКА СОЗЫВА (n/n) ---
async def global_call(new_role):
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM all_users"); rows = cursor.fetchall(); conn.close()
    
    try:
        count = await bot.get_chat_member_count(CHAT_ID)
        total_humans = count - 1 
    except:
        total_humans = len(rows)

    # Тегаем скрыто через точки
    mentions = [f"<a href='tg://user?id={r[0]}'>.</a>" for r in rows]
    text = (f"📣 <b>СОЗЫВ: новый участник</b>\n"
            f"Роль: <b>{new_role}</b>\n\n"
            f"👥 Созвано: <b>{len(rows)}/{total_humans}</b>")
    
    for i in range(0, len(mentions), 10):
        chunk = "".join(mentions[i:i+10])
        await bot.send_message(CHAT_ID, text + chunk, parse_mode="HTML")

# --- СБОР ЮЗЕРОВ ---
@dp.message(F.chat.id == CHAT_ID)
async def collector(m: types.Message):
    if m.from_user.is_bot: return
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO all_users (user_id, name) VALUES (?, ?)", 
                   (m.from_user.id, m.from_user.first_name))
    conn.commit(); conn.close()

# --- МЕНЮ ---
def get_main_kb(uid):
    btns = []
    if not is_approved(uid): btns.append([KeyboardButton(text="📝 Вступить")])
    btns.append([KeyboardButton(text="🚨 Подать жалобу"), KeyboardButton(text="📩 Оставить отзыв")])
    if is_approved(uid): btns.append([KeyboardButton(text="🛡 Апелляция")])
    return ReplyKeyboardMarkup(keyboard=btns, resize_keyboard=True)

@dp.message(Command("start"))
async def cmd_start(m: types.Message):
    await m.answer("Панель управления активирована.", reply_markup=get_main_kb(m.from_user.id))

# --- ОБРАБОТКА АНКЕТЫ ---
@dp.callback_query(F.data.startswith("adm_ok_"))
async def approve_user(call: CallbackQuery):
    uid = int(call.data.split("_")[2])
    # Вытягиваем роль из текста сообщения
    try:
        role = call.message.text.split("РОЛЬ: ")[1].split("\n")[0].strip()
    except:
        role = "Участник"
    
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO approved_users (user_id, role) VALUES (?, ?)", (uid, role))
    conn.commit(); conn.close()
    
    await bot.send_message(uid, f"Принято! Твоя роль: {role}\n{CHAT_LINK}", reply_markup=get_main_kb(uid))
    await call.message.edit_text(call.message.text + "\n\n✅ ОДОБРЕНО")
    
    # 1. СТАВИМ ТЕГ УЧАСТНИКА (НОВАЯ МЕХАНИКА)
    await set_member_tag(uid, role)
    # 2. ДЕЛАЕМ СОЗЫВ
    await global_call(role)

@dp.message(F.text == "📝 Вступить")
async def start_reg(m: types.Message, state: FSMContext):
    if is_approved(m.from_user.id): return
    await m.answer("Укажите вашу роль:"); await state.set_state(RegForm.role)

@dp.message(RegForm.role)
async def p_role(m: types.Message, state: FSMContext):
    await state.update_data(role=m.text); await m.answer("Ваш юзернейм:"); await state.set_state(RegForm.username)

@dp.message(RegForm.username)
async def p_user(m: types.Message, state: FSMContext):
    data = await state.get_data()
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Принять ✅", callback_data=f"adm_ok_{m.from_user.id}")]])
    await bot.send_message(ADMIN_ID, f"<b>АНКЕТА</b>\nЮЗ: {m.text}\nID: {m.from_user.id}\nРОЛЬ: {data['role']}", reply_markup=kb, parse_mode="HTML")
    await m.answer("Заявка отправлена."); await state.clear()

# --- АДМИН КОМАНДЫ ---
@dp.message(Command("list"))
async def cmd_list(m: types.Message):
    if m.from_user.id != ADMIN_ID: return
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute("SELECT user_id, role FROM approved_users"); rows = cursor.fetchall(); conn.close()
    res = "📂 <b>БАЗА:</b>\n" + "\n".join([f"<code>{r[0]}</code> | {r[1]}" for r in rows])
    await m.answer(res if rows else "База пуста", parse_mode="HTML")

# --- ЗАПУСК ---
async def main():
    init_db()
    Thread(target=run, daemon=True).start()
    await asyncio.sleep(1) # Короткая пауза для стабильности
    await bot.delete_webhook(drop_pending_updates=True)
    await bot.set_my_commands([
        BotCommand(command="start", description="Меню"),
        BotCommand(command="list", description="База (Админ)"),
        BotCommand(command="add", description="Добавить вручную"),
        BotCommand(command="del", description="Удалить")
    ])
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
