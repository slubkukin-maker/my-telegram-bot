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
                            CallbackQuery, ChatJoinRequest)

# --- SERVER ДЛЯ RENDER ---
app = Flask('')
@app.route('/')
def home(): return "Harmony Bot: Плашки и Созыв активны!"

def run():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# --- КОНФИГ (ТВОЙ НОВЫЙ ТОКЕН) ---
TOKEN = "8344752199:AAGzVYnAgUFW72XG1lnR26QrZPFFj12WbiE"
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

# --- БАЗА ДАННЫХ ---
def init_db():
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS approved_users (user_id INTEGER PRIMARY KEY, role TEXT)")
    conn.commit(); conn.close()

def get_all_users():
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM approved_users")
    users = [row[0] for row in cursor.fetchall()]; conn.close()
    return users

# --- НОВАЯ ФУНКЦИЯ: УСТАНОВКА ПЛАШКИ (MEMBER TAG) ---
async def set_member_tag(uid, tag_text):
    try:
        # Официальный метод Telegram для установки тега (плашки) участника
        await bot.make_request("setChatMemberTag", {
            "chat_id": CHAT_ID,
            "user_id": uid,
            "tag": tag_text
        })
        logging.info(f"Плашка '{tag_text}' установлена для {uid}")
    except Exception as e:
        logging.error(f"Ошибка установки плашки: {e}")

# --- УМНЫЙ СОЗЫВ (ПАЧКАМИ ПО 5) ---
async def internal_call(new_member_role):
    users = get_all_users()
    if not users: return
    
    # Главное сообщение
    await bot.send_message(CHAT_ID, f"📢 <b>Общий сбор!</b>\nПришел новый участник с ролью: <b>{new_member_role}</b>", parse_mode="HTML")

    # Скрытые теги по 5 штук для пуш-уведомлений
    chunk_size = 5
    for i in range(0, len(users), chunk_size):
        chunk = users[i:i + chunk_size]
        mentions = "".join([f'<a href="tg://user?id={uid}">\u200b</a>' for uid in chunk])
        try:
            await bot.send_message(CHAT_ID, f"⚡️{mentions}", parse_mode="HTML")
            await asyncio.sleep(0.6)
        except: pass

# --- АВТО-ПРИЕМ ЗАЯВОК ---
@dp.chat_join_request()
async def auto_approve(request: ChatJoinRequest):
    try:
        await request.approve()
        await bot.send_message(
            request.from_user.id, 
            "<b>Добро пожаловать!</b> ✅ Заявка одобрена.\n\nНажми <b>📝 Вступить</b>, чтобы заполнить анкету и получить роль/плашку.",
            reply_markup=get_main_kb(), parse_mode="HTML"
        )
    except: pass

# --- КЛАВИАТУРА ---
def get_main_kb():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="📝 Вступить")]], resize_keyboard=True)

@dp.message(Command("start"))
async def cmd_start(m: types.Message):
    await m.answer("Бот Harmony запущен и готов выдавать плашки.", reply_markup=get_main_kb())

# --- ОБРАБОТКА АНКЕТЫ (ПРИНЯТИЕ + ПЛАШКА) ---
@dp.callback_query(F.data.startswith("adm_ok_"))
async def approve(call: CallbackQuery):
    uid = int(call.data.split("_")[2])
    # Достаем роль из текста анкеты
    role = call.message.text.split("РОЛЬ: ")[1].split("\n")[0].strip() if "РОЛЬ: " in call.message.text else "Участник"
    
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO approved_users (user_id, role) VALUES (?, ?)", (uid, role))
    conn.commit(); conn.close()
    
    # !!! ТУТ БОТ АВТОМАТИЧЕСКИ ПОДПИСЫВАЕТ ТЕГ (ПЛАШКУ) !!!
    await set_member_tag(uid, role)
    
    await bot.send_message(uid, f"Твоя роль <b>{role}</b> подтверждена!\nВступай в чат: {CHAT_LINK}", parse_mode="HTML")
    await call.message.edit_text(call.message.text + f"\n✅ ПРИНЯТ. ПЛАШКА '{role}' ВЫДАНА.")
    
    # Запуск созыва
    await internal_call(role)

@dp.callback_query(F.data.startswith("adm_no_"))
async def reject(call: CallbackQuery):
    uid = int(call.data.split("_")[2])
    await bot.send_message(uid, "Заявка отклонена администрацией.")
    await call.message.edit_text(call.message.text + "\n❌ ОТКЛОНЕНО")

# --- ЧАТ С ПОЛЬЗОВАТЕЛЕМ ---
@dp.callback_query(F.data.startswith("chat_with_"))
async def start_reply(call: CallbackQuery, state: FSMContext):
    target_id = int(call.data.split("_")[2])
    await state.update_data(reply_to=target_id)
    await state.set_state(AdminChat.waiting_for_reply)
    await call.message.answer(f"Напиши сообщение для пользователя {target_id}:")
    await call.answer()

@dp.message(AdminChat.waiting_for_reply)
async def send_reply(m: types.Message, state: FSMContext):
    if m.from_user.id != ADMIN_ID: return
    data = await state.get_data(); target_id = data.get("reply_to")
    try:
        await bot.send_message(target_id, f"✉️ <b>Сообщение от администрации:</b>\n\n{m.text}", parse_mode="HTML")
        await m.answer("Отправлено!")
    except: await m.answer("Ошибка.")
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
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Принять ✅", callback_data=f"adm_ok_{m.from_user.id}")],
        [InlineKeyboardButton(text="Отклонить ❌", callback_data=f"adm_no_{m.from_user.id}")],
        [InlineKeyboardButton(text="Написать 💬", callback_data=f"chat_with_{m.from_user.id}")]
    ])
    await bot.send_message(ADMIN_ID, f"<b>АНКЕТА</b>\nЮЗ: {m.text}\nID: {m.from_user.id}\nРОЛЬ: {data['role']}", reply_markup=kb, parse_mode="HTML")
    await m.answer("Заявка ушла. Жди решения!"); await state.clear()

# --- ЗАПУСК ---
async def main():
    init_db()
    Thread(target=run, daemon=True).start()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot, allowed_updates=["message", "callback_query", "chat_join_request"])

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO); asyncio.run(main())
