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
def home(): return "Harmony Bot Active"

def run():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# --- CONFIG ---
TOKEN = "8344752199:AAFvfamddKvG6KYPJRC-aYa4uWRunQ7nH2s"
ADMIN_ID = 8294726083
CHAT_ID = -1003393441169 
DB_PATH = "database.db"

bot = Bot(token=TOKEN)
dp = Dispatcher()

class RegForm(StatesGroup):
    role = State()
    username = State()

# --- DATABASE ---
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS approved_users (user_id INTEGER PRIMARY KEY, role TEXT)")
    conn.commit()
    conn.close()

# --- МЕХАНИКА ТЕГОВ (MEMBER TAGS) ---
async def set_member_tag(uid, tag_text):
    try:
        # Прямой вызов API для установки плашки (Member Tag)
        await bot.make_request("setChatMemberTag", {
            "chat_id": CHAT_ID,
            "user_id": uid,
            "tag": tag_text
        })
        logging.info(f"Тег {tag_text} установлен для {uid}")
    except Exception as e:
        logging.error(f"Ошибка Member Tag: {e}")

# --- АВТО-ПРИЕМ ЗАЯВОК ---
@dp.chat_join_request()
async def auto_approve(request: ChatJoinRequest):
    try:
        await request.approve() # Бот принимает заявку в группу
        await bot.send_message(
            request.from_user.id, 
            "✅ Твоя заявка в группу одобрена!\nЧтобы получить роль и плашку, нажми <b>📝 Вступить</b>",
            reply_markup=get_main_kb(),
            parse_mode="HTML"
        )
    except Exception as e:
        logging.error(f"Error in auto-approve: {e}")

# --- КЛАВИАТУРА ---
def get_main_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📝 Вступить")],
        [KeyboardButton(text="🚨 Подать жалобу"), KeyboardButton(text="📩 Оставить отзыв")]
    ], resize_keyboard=True)

@dp.message(Command("start"))
async def cmd_start(m: types.Message):
    await m.answer("Панель управления Harmony.", reply_markup=get_main_kb())

# --- ИСПРАВЛЕННЫЕ КОМАНДЫ ADD / DEL ---
@dp.message(Command("add"))
async def cmd_add(m: types.Message):
    if m.from_user.id != ADMIN_ID: return
    try:
        args = m.text.split(maxsplit=2) # /add 1234567 Роль
        uid = int(args[1])
        role = args[2]
        
        conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO approved_users (user_id, role) VALUES (?, ?)", (uid, role))
        conn.commit(); conn.close()
        
        await set_member_tag(uid, role)
        await m.answer(f"✅ Пользователь {uid} добавлен в базу как {role}. Тег установлен.")
    except Exception as e:
        await m.answer("Ошибка! Формат: <code>/add ID РОЛЬ</code>", parse_mode="HTML")

@dp.message(Command("del"))
async def cmd_del(m: types.Message):
    if m.from_user.id != ADMIN_ID: return
    try:
        args = m.text.split()
        uid = int(args[1])
        
        conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
        cursor.execute("DELETE FROM approved_users WHERE user_id = ?", (uid,))
        conn.commit(); conn.close()
        
        await set_member_tag(uid, "") # Снимаем плашку
        await m.answer(f"✅ Пользователь {uid} удален, тег снят.")
    except Exception as e:
        await m.answer("Ошибка! Формат: <code>/del ID</code>", parse_mode="HTML")

# --- ОДОБРЕНИЕ И ТРИГГЕР ЗАЗЫВАЛЫ ---
@dp.callback_query(F.data.startswith("adm_ok_"))
async def approve(call: CallbackQuery):
    uid = int(call.data.split("_")[2])
    # Вытягиваем роль из сообщения анкеты
    role = "Участник"
    if "РОЛЬ: " in call.message.text:
        role = call.message.text.split("РОЛЬ: ")[1].strip()

    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO approved_users (user_id, role) VALUES (?, ?)", (uid, role))
    conn.commit(); conn.close()
    
    await set_member_tag(uid, role)
    await bot.send_message(uid, f"Твоя роль <b>{role}</b> подтверждена!", parse_mode="HTML")
    await call.message.edit_text(call.message.text + "\n✅ ПОДТВЕРЖДЕНО")
    
    # Твой созыв для Зазывалы
    await bot.send_message(CHAT_ID, f"Калл пришел новый участник с ролью: {role}")

# --- РЕГИСТРАЦИЯ ---
@dp.message(F.text == "📝 Вступить")
async def start_reg(m: types.Message, state: FSMContext):
    await m.answer("Напиши свою роль:"); await state.set_state(RegForm.role)

@dp.message(RegForm.role)
async def p_role(m: types.Message, state: FSMContext):
    await state.update_data(role=m.text)
    await m.answer("Напиши свой ник:"); await state.set_state(RegForm.username)

@dp.message(RegForm.username)
async def p_user(m: types.Message, state: FSMContext):
    data = await state.get_data()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Принять ✅", callback_data=f"adm_ok_{m.from_user.id}")],
        [InlineKeyboardButton(text="Отклонить ❌", callback_data=f"adm_no_{m.from_user.id}")]
    ])
    await bot.send_message(ADMIN_ID, f"<b>АНКЕТА</b>\nЮЗ: {m.text}\nID: {m.from_user.id}\nРОЛЬ: {data['role']}", reply_markup=kb, parse_mode="HTML")
    await m.answer("Заявка отправлена админу."); await state.clear()

# --- ЗАПУСК ---
async def main():
    init_db()
    Thread(target=run, daemon=True).start()
    await bot.delete_webhook(drop_pending_updates=True)
    # Обязательно добавляем chat_join_request в allowed_updates
    await dp.start_polling(bot, allowed_updates=["message", "callback_query", "chat_join_request"])

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
