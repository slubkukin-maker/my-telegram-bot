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
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand, CallbackQuery, ChatMemberUpdated

# --- 24/7 SERVER ---
app = Flask('')
@app.route('/')
def home(): return "Bot is Online"
def run():
    # Исправлено для Render (порт через os.environ)
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()

# --- CONFIG ---
TOKEN = "8344752199:AAFwouRQZYV2ztyDwC44qCu8uTxq2lgWtoc"
ADMIN_ID = 8294726083
CHAT_ID = -1003393441169 
CHAT_LINK = "https://t.me/+yai_7_Z-7_45MDky"
DB_PATH = "database.db"

bot = Bot(token=TOKEN)
dp = Dispatcher()

class Form(StatesGroup):
    role = State()
    user = State()
    admin_reply = State()

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
    # Кнопка "Вступить" внизу на клавиатуре
    kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="📝 Вступить")]], resize_keyboard=True)
    await m.answer(f"ID: <code>{m.from_user.id}</code>", reply_markup=kb, parse_mode="HTML")

@dp.message(Command("add"))
async def cmd_add(m: types.Message):
    if m.from_user.id != ADMIN_ID: return
    try:
        parts = m.text.split(maxsplit=2)
        target_id, role = int(parts[1]), parts[2]
        conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO approved_users (user_id, role) VALUES (?, ?)", (target_id, role))
        conn.commit(); conn.close()
        await m.answer(f"✅ Добавлен ID {target_id} с ролью {role}")
    except: await m.answer("Формат: /add ID РОЛЬ")

@dp.message(Command("del"))
async def cmd_delete(m: types.Message):
    if m.from_user.id != ADMIN_ID: return
    try:
        target_id = int(m.text.split()[1])
        conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
        cursor.execute("DELETE FROM all_users WHERE user_id = ?", (target_id,))
        cursor.execute("DELETE FROM approved_users WHERE user_id = ?", (target_id,))
        conn.commit(); conn.close()
        await m.answer(f"Пользователь {target_id} удален.")
    except: await m.answer("Формат: /del ID")

@dp.message(Command("list"))
async def cmd_list(m: types.Message):
    if m.from_user.id != ADMIN_ID: return
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute("SELECT user_id, name FROM all_users"); rows = cursor.fetchall(); conn.close()
    if not rows:
        await m.answer("EMPTY")
        return
    text = "LIST (ID | NAME):\n"
    for r in rows: text += f"<code>{r[0]}</code> | {r[1]}\n"
    await m.answer(text, parse_mode="HTML")

@dp.message(Command("all"))
async def cmd_all(m: types.Message):
    if m.from_user.id != ADMIN_ID: return
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM all_users"); rows = cursor.fetchall(); conn.close()
    if not rows: return
    await m.answer("🔊 <b>ОБЩИЙ СБОР!</b>", parse_mode="HTML")
    users = [r[0] for r in rows]
    # Скрытый сбор (упоминание через невидимый символ)
    for i in range(0, len(users), 5):
        chunk = users[i:i+5]
        mentions = "".join([f'<a href="tg://user?id={uid}">\u200b</a>' for uid in chunk])
        await m.answer(f"⚡️ {mentions}", parse_mode="HTML")

# --- АНКЕТА ---

@dp.message(F.text == "📝 Вступить")
async def start_reg_text(m: types.Message, state: FSMContext):
    await m.answer("Напиши свою роль:")
    await state.set_state(Form.role)

@dp.message(Form.role)
async def p_role(m: types.Message, state: FSMContext):
    await state.update_data(role=m.text)
    await m.answer("Напиши свой ЮЗ:")
    await state.set_state(Form.user)

@dp.message(Form.user)
async def p_user(m: types.Message, state: FSMContext):
    data = await state.get_data(); role = data.get('role'); uid = m.from_user.id
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Принять ✅", callback_data=f"adm_ok_{uid}"), 
         InlineKeyboardButton(text="Отклонить ❌", callback_data=f"adm_no_{uid}")]
    ])
    await bot.send_message(ADMIN_ID, f"ANKETA\nЮЗ: {m.text}\nID: {uid}\nРОЛЬ: {role}", reply_markup=kb)
    await m.answer("Заявка отправлена."); await state.clear()

@dp.callback_query(F.data.startswith("adm_"))
async def admin_btns(call: CallbackQuery):
    action, target_uid = call.data.split("_")[1], int(call.data.split("_")[2])
    if action == "ok":
        role = call.message.text.split("РОЛЬ: ")[1] if "РОЛЬ: " in call.message.text else "Member"
        conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO approved_users (user_id, role) VALUES (?, ?)", (target_uid, role))
        conn.commit(); conn.close()
        await bot.send_message(target_uid, f"Принято. Роль: {role}\n{CHAT_LINK}")
        await call.message.edit_text(call.message.text + "\nSTATUS: OK")
    elif action == "no":
        await bot.send_message(target_uid, "Отклонено.")
        await call.message.edit_text(call.message.text + "\nSTATUS: NO")
    await call.answer()

# --- ВХОД / ВЫХОД (ТВОЯ СТРУКТУРА) ---

@dp.chat_member()
async def on_chat_member_update(update: ChatMemberUpdated):
    if update.chat.id == CHAT_ID:
        uid = update.new_chat_member.user.id
        # Если юзер зашел
        if update.new_chat_member.status == "member":
            conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
            cursor.execute("SELECT role FROM approved_users WHERE user_id = ?", (uid,))
            row = cursor.fetchone(); conn.close()
            if row:
                name = f"@{update.new_chat_member.user.username}" if update.new_chat_member.user.username else update.new_chat_member.user.first_name
                conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
                cursor.execute("INSERT OR REPLACE INTO all_users (user_id, name) VALUES (?, ?)", (uid, name))
                conn.commit(); conn.close()
        # Если юзер вышел
        elif update.new_chat_member.status in ["left", "kicked"]:
            conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
            cursor.execute("DELETE FROM all_users WHERE user_id = ?", (uid,))
            cursor.execute("DELETE FROM approved_users WHERE user_id = ?", (uid,))
            conn.commit(); conn.close()

async def main():
    init_db(); keep_alive()
    await bot.set_my_commands([
        BotCommand(command="start", description="Меню"),
        BotCommand(command="all", description="Сбор"),
        BotCommand(command="list", description="База"),
        BotCommand(command="del", description="Удалить"),
        BotCommand(command="add", description="Добавить")
    ])
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot, allowed_updates=["message", "callback_query", "chat_member"])

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
