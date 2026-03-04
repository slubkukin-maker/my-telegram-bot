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
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, BotCommand, CallbackQuery, ChatMemberUpdated

# --- 24/7 SERVER (RENDER OPTIMIZED) ---
app = Flask('')

@app.route('/')
def home():
    return "Bot is Online and Ready!"

def run():
    # Render использует порт 10000 по умолчанию, если не указано иное
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
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Вступить", callback_data="start_reg")]])
    await m.answer(f"Привет! Твой ID: <code>{m.from_user.id}</code>\nНажми кнопку ниже, чтобы подать заявку.", reply_markup=kb, parse_mode="HTML")

@dp.message(Command("del"))
async def cmd_delete(m: types.Message):
    if m.from_user.id != ADMIN_ID: return
    try:
        target_id = int(m.text.split()[1])
        conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
        cursor.execute("DELETE FROM all_users WHERE user_id = ?", (target_id,))
        cursor.execute("DELETE FROM approved_users WHERE user_id = ?", (target_id,))
        conn.commit(); conn.close()
        await m.answer(f"Пользователь {target_id} удален из базы.")
    except:
        await m.answer("Используй: /del ID")

@dp.message(Command("list"))
async def cmd_list(m: types.Message):
    if m.from_user.id != ADMIN_ID: return
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute("SELECT user_id, name FROM all_users"); rows = cursor.fetchall(); conn.close()
    if not rows:
        await m.answer("База пользователей пуста.")
        return
    text = "📊 Список пользователей (ID | Имя):\n"
    for r in rows:
        text += f"<code>{r[0]}</code> | {r[1]}\n"
    await m.answer(text, parse_mode="HTML")

@dp.message(Command("all"))
async def cmd_all(m: types.Message):
    if m.from_user.id != ADMIN_ID: return
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute("SELECT user_id, name FROM all_users"); rows = cursor.fetchall(); conn.close()
    if not rows: return
    mentions = [f"<a href='tg://user?id={r[0]}'>{r[1]}</a>" for r in rows]
    for i in range(0, len(mentions), 5):
        await m.answer(f"📣 СБОР:\n{', '.join(mentions[i:i+5])}", parse_mode="HTML")

# --- АНКЕТА ---

@dp.callback_query(F.data == "start_reg")
async def start_reg(call: CallbackQuery, state: FSMContext):
    await call.message.answer("Укажите вашу роль в команде:")
    await state.set_state(Form.role); await call.answer()

@dp.message(Form.role)
async def p_role(m: types.Message, state: FSMContext):
    await state.update_data(role=m.text); await m.answer("Укажите ваш ник/имя:"); await state.set_state(Form.user)

@dp.message(Form.user)
async def p_user(m: types.Message, state: FSMContext):
    data = await state.get_data(); role = data.get('role'); uid = m.from_user.id
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Принять", callback_data=f"adm_ok_{uid}"), 
         InlineKeyboardButton(text="❌ Отклонить", callback_data=f"adm_no_{uid}")],
        [InlineKeyboardButton(text="✉️ Написать", callback_data=f"adm_msg_{uid}")]
    ])
    await bot.send_message(ADMIN_ID, f"🆕 НОВАЯ АНКЕТА\nЮзер: {m.text}\nID: {uid}\nРоль: {role}", reply_markup=kb)
    await m.answer("Заявка успешно отправлена администрации."); await state.clear()

@dp.callback_query(F.data.startswith("adm_"))
async def admin_btns(call: CallbackQuery, state: FSMContext):
    action = call.data.split("_")[1]; target_uid = int(call.data.split("_")[2])
    if action == "ok":
        role = call.message.text.split("Роль: ")[1] if "Роль: " in call.message.text else "Member"
        conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO approved_users (user_id, role) VALUES (?, ?)", (target_uid, role))
        cursor.execute("INSERT OR REPLACE INTO all_users (user_id, name) VALUES (?, ?)", (target_uid, role))
        conn.commit(); conn.close()
        await bot.send_message(target_uid, f"Ваша заявка одобрена! Ваша роль: {role}\nВступайте в чат: {CHAT_LINK}")
        await call.message.edit_text(call.message.text + "\n\n✅ СТАТУС: ПРИНЯТ")
    elif action == "no":
        await bot.send_message(target_uid, "К сожалению, ваша заявка отклонена.")
        await call.message.edit_text(call.message.text + "\n\n❌ СТАТУС: ОТКЛОНЕН")
    elif action == "msg":
        await call.message.answer(f"Введите текст сообщения для пользователя {target_uid}:")
        await state.update_data(target_to_msg=target_uid); await state.set_state(Form.admin_reply)
    await call.answer()

@dp.message(Form.admin_reply)
async def admin_reply_send(m: types.Message, state: FSMContext):
    data = await state.get_data(); target = data.get('target_to_msg')
    try:
        await bot.send_message(target, f"📩 Сообщение от администрации:\n\n{m.text}")
        await m.answer("Сообщение доставлено.")
    except: await m.answer("Не удалось отправить сообщение.")
    await state.clear()

# --- АВТО-ОЧИСТКА ---
@dp.chat_member()
async def on_chat_member_update(update: ChatMemberUpdated):
    if update.chat.id == CHAT_ID:
        if update.new_chat_member.status in ["left", "kicked"]:
            uid = update.from_user.id
            conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
            cursor.execute("DELETE FROM all_users WHERE user_id = ?", (uid,))
            cursor.execute("DELETE FROM approved_users WHERE user_id = ?", (uid,))
            conn.commit(); conn.close()

@dp.message(F.chat.id == CHAT_ID)
async def collect_msg(m: types.Message):
    if m.from_user.is_bot: return
    name = f"@{m.from_user.username}" if m.from_user.username else m.from_user.first_name
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO all_users (user_id, name) VALUES (?, ?)", (m.from_user.id, name))
    conn.commit(); conn.close()

async def main():
    init_db()
    keep_alive() # Запуск Flask сервера для UptimeRobot
    await bot.set_my_commands([
        BotCommand(command="start", description="Меню"),
        BotCommand(command="all", description="Сбор всех"),
        BotCommand(command="list", description="Список базы"),
        BotCommand(command="del", description="Удалить по ID")
    ])
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot, allowed_updates=["message", "callback_query", "chat_member"])

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
