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
def home(): return "Бот Harmony активен"

def run():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# --- CONFIG ---
TOKEN = "8344752199:AAFvfamddKvG6KYPJRC-aYa4uWRunQ7nH2s"
ADMIN_ID = 8294726083
CHAT_ID = -1003393441169 
CHAT_LINK = "https://t.me/+yai_7_Z-7_45MDky"
DB_PATH = "database.db"

bot = Bot(token=TOKEN)
dp = Dispatcher()

class RegForm(StatesGroup):
    role = State()
    username = State()

class AdminChat(StatesGroup):
    waiting_for_reply = State()

# --- DATABASE ---
def init_db():
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS approved_users (user_id INTEGER PRIMARY KEY, role TEXT)")
    conn.commit(); conn.close()

def is_approved(uid):
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM approved_users WHERE user_id = ?", (uid,))
    res = cursor.fetchone(); conn.close()
    return bool(res)

# --- MEMBER TAGS ---
async def set_member_tag(uid, tag_text):
    try:
        await bot.make_request("setChatMemberTag", {"chat_id": CHAT_ID, "user_id": uid, "tag": tag_text})
    except Exception as e: logging.error(f"Tag error: {e}")

# --- АВТО-ПРИЕМ ЗАЯВОК ---
@dp.chat_join_request()
async def auto_approve(request: ChatJoinRequest):
    try:
        await request.approve()
        await bot.send_message(
            request.from_user.id, 
            f"✅ Твоя заявка одобрена!\nЧтобы получить роль и плашку в чате, нажми <b>📝 Вступить</b>",
            reply_markup=get_main_kb(), parse_mode="HTML"
        )
    except Exception as e: logging.error(f"Join error: {e}")

# --- КЛАВИАТУРА ---
def get_main_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📝 Вступить")],
        [KeyboardButton(text="🚨 Подать жалобу"), KeyboardButton(text="📩 Оставить отзыв")]
    ], resize_keyboard=True)

@dp.message(Command("start"))
async def cmd_start(m: types.Message):
    await m.answer("Панель Harmony активирована.", reply_markup=get_main_kb())

# --- КОМАНДЫ ADD / DEL ---
@dp.message(Command("add"))
async def cmd_add(m: types.Message):
    if m.from_user.id != ADMIN_ID: return
    try:
        parts = m.text.split(maxsplit=2)
        uid, role = int(parts[1]), parts[2]
        conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO approved_users (user_id, role) VALUES (?, ?)", (uid, role))
        conn.commit(); conn.close()
        await set_member_tag(uid, role)
        await m.answer(f"✅ Добавлен {uid} как {role}")
    except: await m.answer("Формат: /add ID РОЛЬ")

@dp.message(Command("del"))
async def cmd_del(m: types.Message):
    if m.from_user.id != ADMIN_ID: return
    try:
        uid = int(m.text.split()[1])
        conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
        cursor.execute("DELETE FROM approved_users WHERE user_id = ?", (uid,))
        conn.commit(); conn.close()
        await set_member_tag(uid, "")
        await m.answer(f"❌ Удален {uid}, тег снят.")
    except: await m.answer("Формат: /del ID")

# --- ОБРАБОТКА АНКЕТЫ ---
@dp.callback_query(F.data.startswith("adm_ok_"))
async def approve(call: CallbackQuery):
    uid = int(call.data.split("_")[2])
    role = "Участник"
    if "РОЛЬ: " in call.message.text:
        role = call.message.text.split("РОЛЬ: ")[1].split("\n")[0].strip()

    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO approved_users (user_id, role) VALUES (?, ?)", (uid, role))
    conn.commit(); conn.close()
    
    await set_member_tag(uid, role)
    # ТЕПЕРЬ ОТПРАВЛЯЕТ ССЫЛКУ НА ЧАТ
    await bot.send_message(uid, f"Твоя роль <b>{role}</b> подтверждена!\nВступай в чат: {CHAT_LINK}", parse_mode="HTML")
    await call.message.edit_text(call.message.text + "\n✅ ПОДТВЕРЖДЕНО")
    
    # ТРИГГЕР ЗАЗЫВАЛЫ
    await bot.send_message(CHAT_ID, f"Калл пришел новый участник с ролью: {role}")

@dp.callback_query(F.data.startswith("chat_with_"))
async def start_reply(call: CallbackQuery, state: FSMContext):
    target_id = int(call.data.split("_")[2])
    await state.update_data(reply_to=target_id)
    await state.set_state(AdminChat.waiting_for_reply)
    await call.message.answer(f"Введите ответ для пользователя {target_id}:")
    await call.answer()

@dp.message(AdminChat.waiting_for_reply)
async def send_reply(m: types.Message, state: FSMContext):
    if m.from_user.id != ADMIN_ID: return
    data = await state.get_data(); target_id = data.get("reply_to")
    try:
        await bot.send_message(target_id, f"✉️ <b>Сообщение от администрации:</b>\n\n{m.text}", parse_mode="HTML")
        await m.answer("Отправлено!")
    except: await m.answer("Ошибка отправки.")
    await state.clear()

# --- РЕГИСТРАЦИЯ ---
@dp.message(F.text == "📝 Вступить")
async def start_reg(m: types.Message, state: FSMContext):
    await m.answer("Напиши свою роль:"); await state.set_state(RegForm.role)

@dp.message(RegForm.role)
async def p_role(m: types.Message, state: FSMContext):
    await state.update_data(role=m.text)
    await m.answer("Напиши свой @username:"); await state.set_state(RegForm.username)

@dp.message(RegForm.username)
async def p_user(m: types.Message, state: FSMContext):
    data = await state.get_data()
    # КНОПКИ ПРИНЯТЬ И НАПИСАТЬ
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Принять ✅", callback_data=f"adm_ok_{m.from_user.id}")],
        [InlineKeyboardButton(text="Написать 💬", callback_data=f"chat_with_{m.from_user.id}")]
    ])
    await bot.send_message(ADMIN_ID, f"<b>АНКЕТА</b>\nЮЗ: {m.text}\nID: {m.from_user.id}\nРОЛЬ: {data['role']}", reply_markup=kb, parse_mode="HTML")
    await m.answer("Заявка отправлена админу."); await state.clear()

# --- ЗАПУСК ---
async def main():
    init_db()
    Thread(target=run, daemon=True).start()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot, allowed_updates=["message", "callback_query", "chat_join_request"])

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
