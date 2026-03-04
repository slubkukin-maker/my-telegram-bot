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
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, BotCommand, CallbackQuery

# --- SERVER ---
app = Flask('')
@app.route('/')
def home(): return "Бот работает!"

def run():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()

# --- CONFIG ---
TOKEN = "8344752199:AAFwouRQZYV2ztyDwC44qCu8uTxq2lgWtoc"
ADMIN_ID = 8294726083
CHAT_ID = -1003393441169 
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
    conn.commit()
    conn.close()

# --- COMMANDS ---

@dp.message(Command("start"))
async def cmd_start(m: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Вступить", callback_data="start_reg")]])
    await m.answer(f"Твой ID: <code>{m.from_user.id}</code>", reply_markup=kb, parse_mode="HTML")

@dp.message(Command("add"))
async def cmd_add_manual(m: types.Message):
    if m.from_user.id != ADMIN_ID: return
    try:
        parts = m.text.split()
        target_id = int(parts[1])
        role = parts[2] if len(parts) > 2 else "Участник"
        conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO approved_users (user_id, role) VALUES (?, ?)", (target_id, role))
        cursor.execute("INSERT OR REPLACE INTO all_users (user_id, name) VALUES (?, ?)", (target_id, role))
        conn.commit(); conn.close()
        await m.answer(f"✅ Добавлен ID {target_id} как {role}")
    except:
        await m.answer("Ошибка! Пиши так: /add 12345678 Роль")

@dp.message(Command("check"))
async def cmd_check(m: types.Message):
    if m.from_user.id != ADMIN_ID: return
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM approved_users"); approved = [r[0] for r in cursor.fetchall()]
    cursor.execute("SELECT user_id, name FROM all_users"); all_u = cursor.fetchall(); conn.close()
    
    bad = [f"<code>{u[0]}</code> | {u[1]}" for u in all_u if u[0] not in approved]
    if not bad: await m.answer("Все подтверждены! ✅")
    else: await m.answer("<b>Без роли:</b>\n" + "\n".join(bad), parse_mode="HTML")

@dp.message(Command("list"))
async def cmd_list(m: types.Message):
    if m.from_user.id != ADMIN_ID: return
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute("SELECT user_id, name FROM all_users"); rows = cursor.fetchall(); conn.close()
    if not rows: await m.answer("Пусто")
    else: await m.answer("\n".join([f"{r[0]} | {r[1]}" for r in rows]))

@dp.message(Command("all"))
async def cmd_all(m: types.Message):
    if m.from_user.id != ADMIN_ID: return
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute("SELECT user_id, name FROM all_users"); rows = cursor.fetchall(); conn.close()
    mentions = [f"<a href='tg://user?id={r[0]}'>{r[1]}</a>" for r in rows]
    for i in range(0, len(mentions), 5):
        await m.answer(f"📣 СБОР:\n{', '.join(mentions[i:i+5])}", parse_mode="HTML")

# --- ANKETA ---
@dp.callback_query(F.data == "start_reg")
async def reg(call: CallbackQuery, state: FSMContext):
    await call.message.answer("Твоя роль:"); await state.set_state(Form.role); await call.answer()

@dp.message(Form.role)
async def p1(m: types.Message, state: FSMContext):
    await state.update_data(role=m.text); await m.answer("Твой ник:"); await state.set_state(Form.user)

@dp.message(Form.user)
async def p2(m: types.Message, state: FSMContext):
    data = await state.get_data(); role = data.get('role'); uid = m.from_user.id
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅", callback_data=f"ok_{uid}"), InlineKeyboardButton(text="❌", callback_data=f"no_{uid}")]])
    await bot.send_message(ADMIN_ID, f"ID: {uid}\nНик: {m.text}\nРоль: {role}", reply_markup=kb)
    await m.answer("Заявка у админа!"); await state.clear()

@dp.callback_query(F.data.startswith("ok_") | F.data.startswith("no_"))
async def adm_proc(call: CallbackQuery):
    action, uid = call.data.split("_")
    if action == "ok":
        conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO approved_users (user_id, role) VALUES (?, ?)", (int(uid), "Member"))
        conn.commit(); conn.close()
        await bot.send_message(int(uid), "Принят!")
        await call.message.edit_text("✅ Одобрено")
    else:
        await bot.send_message(int(uid), "Отклонено")
        await call.message.edit_text("❌ Отказ")

# --- COLLECT ---
@dp.message(F.chat.id == CHAT_ID)
async def collect(m: types.Message):
    if m.from_user.is_bot: return
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO all_users (user_id, name) VALUES (?, ?)", (m.from_user.id, m.from_user.full_name))
    conn.commit(); conn.close()

async def main():
    init_db(); keep_alive()
    await bot.set_my_commands([
        BotCommand(command="start", description="Старт"),
        BotCommand(command="all", description="Тегнуть всех"),
        BotCommand(command="check", description="Кто без тега"),
        BotCommand(command="add", description="Добавить ID"),
        BotCommand(command="list", description="Список"),
        BotCommand(command="del", description="Удалить")
    ])
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
