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
from aiogram.types import (InlineKeyboardButton, InlineKeyboardMarkup, 
                            ReplyKeyboardMarkup, KeyboardButton, CallbackQuery, 
                            ReplyKeyboardRemove, BotCommand, ChatMemberUpdated, ChatJoinRequest)

# --- SERVER ---
app = Flask('')
@app.route('/')
def home(): return "Bot is Online"
def run():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# --- CONFIG ---
TOKEN = "8344752199:AAEU6zgkYOPGyIFHmIxoTPCIuvRclEIczdc"
ADMIN_ID = 8294726083
CHAT_ID = -1003393441169 
CHAT_LINK = "https://t.me/+yai_7_Z-7_45MDky"
DB_PATH = "database.db"

bot = Bot(token=TOKEN)
dp = Dispatcher()

class Form(StatesGroup):
    role = State()
    user = State()

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS approved_users (user_id INTEGER PRIMARY KEY, role TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS all_users (user_id INTEGER PRIMARY KEY, name TEXT)")
    conn.commit(); conn.close()

def get_main_reply_kb(user_id):
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM approved_users WHERE user_id = ?", (user_id,))
    is_joined = cursor.fetchone(); conn.close()
    kb = []
    if not is_joined: kb.append([KeyboardButton(text="📝 Вступить")])
    kb.append([KeyboardButton(text="⚖️ Апелляция"), KeyboardButton(text="🚫 Жалоба")])
    kb.append([KeyboardButton(text="⭐ Отзыв")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

# --- ФУНКЦИЯ УСТАНОВКИ ТЕГА ---
async def apply_member_tag(uid, role):
    try:
        # Устанавливаем кастомный тег (звание) участнику
        # В Telegram API для этого используется set_chat_administrator_custom_title, 
        # даже если у пользователя нет прав (он будет числиться участником с тегом)
        await bot.promote_chat_member(
            chat_id=CHAT_ID,
            user_id=uid,
            can_invite_users=True # Минимальное право для возможности носить тег
        )
        await bot.set_chat_administrator_custom_title(
            chat_id=CHAT_ID,
            user_id=uid,
            custom_title=role
        )
        return True
    except Exception as e:
        logging.error(f"Ошибка тега: {e}")
        return False

# --- АВТОМАТИЧЕСКОЕ ОДОБРЕНИЕ ЗАЯВКИ И ТЕГ ---
@dp.chat_join_request()
async def approve_and_tag(request: ChatJoinRequest):
    uid = request.from_user.id
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute("SELECT role FROM approved_users WHERE user_id = ?", (uid,))
    res = cursor.fetchone(); conn.close()
    
    if res:
        role = res[0]
        await request.approve() # Бот одобряет вход в группу
        await asyncio.sleep(2) # Пауза, чтобы юзер успел "зайти"
        await apply_member_tag(uid, role) # Ставим тот самый тег

# --- СБОР ИМЕН В ЧАТЕ ---
@dp.message(F.chat.id == CHAT_ID)
async def collect_names(m: types.Message):
    if m.from_user.is_bot: return
    name = f"@{m.from_user.username}" if m.from_user.username else m.from_user.first_name
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO all_users (user_id, name) VALUES (?, ?)", (m.from_user.id, name))
    conn.commit(); conn.close()

# --- АНКЕТА ---
@dp.message(F.text == "📝 Вступить")
async def start_reg(m: types.Message, state: FSMContext):
    await m.answer("Укажите роль:", reply_markup=ReplyKeyboardRemove())
    await state.set_state(Form.role)

@dp.message(Form.role)
async def p_role(m: types.Message, state: FSMContext):
    await state.update_data(role=m.text)
    await m.answer("Укажите ник:")
    await state.set_state(Form.user)

@dp.message(Form.user)
async def p_user(m: types.Message, state: FSMContext):
    data = await state.get_data(); role = data['role']; uid = m.from_user.id
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Принять", callback_data=f"adm_ok_{uid}"), 
         InlineKeyboardButton(text="Отклонить", callback_data=f"adm_no_{uid}")]
    ])
    await bot.send_message(ADMIN_ID, f"ANKETA\nUSER: {m.text}\nID: {uid}\nROLE: {role}", reply_markup=kb)
    await m.answer("Отправлено!", reply_markup=get_main_reply_kb(uid))
    await state.clear()

@dp.callback_query(F.data.startswith("adm_ok_"))
async def adm_approve(call: CallbackQuery):
    uid = int(call.data.split("_")[2])
    role = call.message.text.split("ROLE: ")[1] if "ROLE: " in call.message.text else "Участник"
    
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO approved_users (user_id, role) VALUES (?, ?)", (uid, role))
    conn.commit(); conn.close()
    
    await bot.send_message(uid, f"Принято! {role}\n{CHAT_LINK}")
    await call.message.edit_text(call.message.text + "\n✅ ПРИНЯТ")
    await call.answer()

# --- КОМАНДЫ ---
@dp.message(Command("all"))
async def cmd_all(m: types.Message):
    if m.from_user.id != ADMIN_ID: return
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute("SELECT user_id, name FROM all_users"); rows = cursor.fetchall(); conn.close()
    if not rows: return
    mentions = [f"<a href='tg://user?id={r[0]}'>{r[1]}</a>" for r in rows]
    for i in range(0, len(mentions), 5):
        await m.answer(f"СБОР:\n{', '.join(mentions[i:i+5])}", parse_mode="HTML")

async def main():
    init_db(); Thread(target=run, daemon=True).start()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot, allowed_updates=["message", "callback_query", "chat_member", "chat_join_request"])

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO); asyncio.run(main())
