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
def home(): return "Бот Harmony: Авто-прием заявок активен!"

def run():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# --- КОНФИГ ---
TOKEN = "8344752199:AAFvfamddKvG6KYPJRC-aYa4uWRunQ7nH2s"
ADMIN_ID = 8294726083
CHAT_ID = -1003393441169 
CHAT_LINK = "https://t.me/+yai_7_Z-7_45MDky"
DB_PATH = "database.db"

bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- СОСТОЯНИЯ ---
class RegForm(StatesGroup):
    role = State()
    username = State()

class AdminChat(StatesGroup):
    waiting_for_reply = State()

# --- БАЗА ДАННЫХ ---
def init_db():
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS approved_users (user_id INTEGER PRIMARY KEY, role TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS all_users (user_id INTEGER PRIMARY KEY, name TEXT)")
    conn.commit(); conn.close()

def is_approved(uid):
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM approved_users WHERE user_id = ?", (uid,))
    res = cursor.fetchone(); conn.close()
    return bool(res)

# --- АВТОМАТИЧЕСКИЙ ПРИЕМ ЗАЯВОК ---
@dp.chat_join_request()
async def auto_approve(request: ChatJoinRequest):
    try:
        # Бот одобряет заявку в группу
        await request.approve()
        logging.info(f"Заявка от {request.from_user.id} одобрена автоматически.")
        
        # Сразу пишем пользователю в личку, чтобы он зарегистрировался
        await bot.send_message(
            request.from_user.id, 
            "Добро пожаловать в Harmony! ✅ Ваша заявка одобрена.\n\n"
            "Чтобы получить роль и плашку в чате, нажмите кнопку **📝 Вступить** ниже.",
            reply_markup=get_main_kb(request.from_user.id)
        )
    except Exception as e:
        logging.error(f"Ошибка авто-приема: {e}")

# --- МЕХАНИКА ТЕГОВ ---
async def set_member_tag(uid, tag_text):
    try:
        await bot.make_request("setChatMemberTag", {"chat_id": CHAT_ID, "user_id": uid, "tag": tag_text})
    except Exception as e: logging.error(f"Tag error: {e}")

# --- ЛОГИКА СОЗЫВА ---
async def global_call(new_role):
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM all_users"); rows = cursor.fetchall(); conn.close()
    mentions = [f"<a href='tg://user?id={r[0]}'>.</a>" for r in rows]
    text = f"📣 <b>СОЗЫВ: новый участник</b>\nРоль: <b>{new_role}</b>"
    for i in range(0, len(mentions), 10):
        await bot.send_message(CHAT_ID, text + "".join(mentions[i:i+10]), parse_mode="HTML")

# --- СБОР ID ---
@dp.message(F.chat.id == CHAT_ID)
async def collector(m: types.Message):
    if m.from_user.is_bot: return
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO all_users (user_id, name) VALUES (?, ?)", (m.from_user.id, m.from_user.first_name))
    conn.commit(); conn.close()

# --- КЛАВИАТУРА ---
def get_main_kb(uid):
    btns = [[KeyboardButton(text="📝 Вступить")]]
    btns.append([KeyboardButton(text="🚨 Подать жалобу"), KeyboardButton(text="📩 Оставить отзыв")])
    return ReplyKeyboardMarkup(keyboard=btns, resize_keyboard=True)

@dp.message(Command("start"))
async def cmd_start(m: types.Message):
    await m.answer("Панель управления активирована.", reply_markup=get_main_kb(m.from_user.id))

# --- РЕГИСТРАЦИЯ И АДМИН-КНОПКИ ---
@dp.message(F.text == "📝 Вступить")
async def start_reg(m: types.Message, state: FSMContext):
    await m.answer("Укажите вашу будущую роль:"); await state.set_state(RegForm.role)

@dp.message(RegForm.role)
async def p_role(m: types.Message, state: FSMContext):
    await state.update_data(role=m.text); await m.answer("Ваш юзернейм:"); await state.set_state(RegForm.username)

@dp.message(RegForm.username)
async def p_user(m: types.Message, state: FSMContext):
    data = await state.get_data()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Принять ✅", callback_data=f"adm_ok_{m.from_user.id}")],
        [InlineKeyboardButton(text="Отклонить ❌", callback_data=f"adm_no_{m.from_user.id}")],
        [InlineKeyboardButton(text="Написать 💬", callback_data=f"chat_with_{m.from_user.id}")]
    ])
    await bot.send_message(ADMIN_ID, f"АНКЕТА\nЮЗ: {m.text}\nID: {m.from_user.id}\nРОЛЬ: {data['role']}", reply_markup=kb)
    await m.answer("Анкета отправлена админу на проверку."); await state.clear()

@dp.callback_query(F.data.startswith("adm_ok_"))
async def approve(call: CallbackQuery):
    uid = int(call.data.split("_")[2])
    role = call.message.text.split("РОЛЬ: ")[1].strip()
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO approved_users (user_id, role) VALUES (?, ?)", (uid, role))
    conn.commit(); conn.close()
    await bot.send_message(uid, f"Админ подтвердил вашу роль: {role}! Теперь у вас есть плашка в чате.")
    await call.message.edit_text(call.message.text + "\n✅ ПОДТВЕРЖДЕНО")
    await set_member_tag(uid, role)
    await global_call(role)

# --- ДИАЛОГ С АДМИНОМ ---
@dp.callback_query(F.data.startswith("chat_with_"))
async def start_reply(call: CallbackQuery, state: FSMContext):
    target_id = int(call.data.split("_")[2])
    await state.update_data(reply_to=target_id)
    await state.set_state(AdminChat.waiting_for_reply)
    await call.message.answer(f"Введите ответ для пользователя {target_id}:")
    await call.answer()

@dp.message(AdminChat.waiting_for_reply)
async def send_reply(m: types.Message, state: FSMContext):
    data = await state.get_data(); target_id = data.get("reply_to")
    try:
        await bot.send_message(target_id, f"✉️ <b>Сообщение от администрации:</b>\n\n{m.text}", parse_mode="HTML")
        await m.answer("Отправлено!")
    except: await m.answer("Ошибка.")
    await state.clear()

# --- ЗАПУСК ---
async def main():
    init_db()
    Thread(target=run, daemon=True).start()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot, allowed_updates=["message", "callback_query", "chat_join_request"])

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
