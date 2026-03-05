import asyncio
import sqlite3
import logging
import os
import aiohttp
from flask import Flask
from threading import Thread
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (ReplyKeyboardMarkup, KeyboardButton, 
                           InlineKeyboardButton, InlineKeyboardMarkup, 
                           BotCommand, CallbackQuery, ChatMemberUpdated, ChatJoinRequest)

# --- CONFIG ---
TOKEN = "8344752199:AAFwouRQZYV2ztyDwC44qCu8uTxq2lgWtoc"
ADMIN_ID = 8294726083
CHAT_ID = -1003393441169 
CHAT_LINK = "https://t.me/+yai_7_Z-7_45MDky"
DB_PATH = "database.db"

# --- WEB SERVER (RENDER FIX) ---
app = Flask(__name__)

@app.route('/')
def health():
    return "Bot is alive", 200

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    # Биндим на 0.0.0.0 — это критично для Render
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

# --- BOT LOGIC ---
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

async def apply_tag(uid, tag):
    url = f"https://api.telegram.org/bot{TOKEN}/setChatMemberTag"
    payload = {"chat_id": CHAT_ID, "user_id": int(uid), "tag": str(tag)}
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, json=payload) as resp:
                return await resp.json()
        except Exception as e:
            logging.error(f"Tag error: {e}")

# --- COMMANDS ---

@dp.message(Command("start"))
async def cmd_start(m: types.Message):
    kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="📝 Вступить")]], resize_keyboard=True)
    await m.answer(f"🤖 <b>Система активна</b>\nТвой ID: <code>{m.from_user.id}</code>\nИспользуй кнопку ниже.", 
                   reply_markup=kb, parse_mode="HTML")

@dp.message(Command("all"))
async def cmd_all(m: types.Message):
    if m.from_user.id != ADMIN_ID: return
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM all_users"); rows = cursor.fetchall(); conn.close()
    if not rows: return
    await m.answer("📢 <b>ОБЩИЙ СБОР!</b>")
    users = [r[0] for r in rows]
    for i in range(0, len(users), 5):
        chunk = users[i:i+5]
        mentions = "".join([f'<a href="tg://user?id={uid}">\u200b</a>' for uid in chunk])
        await m.answer(f"⚡️ {mentions}", parse_mode="HTML")

@dp.message(F.text == "📝 Вступить")
async def start_reg_text(m: types.Message, state: FSMContext):
    await m.answer("💎 Напиши свою роль:")
    await state.set_state(Form.role)

@dp.message(Form.role)
async def p_role(m: types.Message, state: FSMContext):
    await state.update_data(role=m.text)
    await m.answer("👤 Напиши свой ЮЗ:")
    await state.set_state(Form.user)

@dp.message(Form.user)
async def p_user(m: types.Message, state: FSMContext):
    data = await state.get_data(); role = data.get('role'); uid = m.from_user.id
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Принять ✅", callback_data=f"adm_ok_{uid}"), 
         InlineKeyboardButton(text="Отклонить ❌", callback_data=f"adm_no_{uid}")]
    ])
    await bot.send_message(ADMIN_ID, f"📩 <b>АНКЕТА</b>\nЮЗ: {m.text}\nID: {uid}\nРОЛЬ: {role}", reply_markup=kb, parse_mode="HTML")
    await m.answer("📨 Заявка отправлена администрации.")
    await state.clear()

@dp.callback_query(F.data.startswith("adm_"))
async def admin_btns(call: CallbackQuery):
    action, target_uid = call.data.split("_")[1], int(call.data.split("_")[2])
    if action == "ok":
        role = call.message.text.split("РОЛЬ: ")[1] if "РОЛЬ: " in call.message.text else "Member"
        conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO approved_users (user_id, role) VALUES (?, ?)", (target_uid, role))
        conn.commit(); conn.close()
        await bot.send_message(target_uid, f"✅ Принято! Роль <b>{role}</b> применится при входе.\n{CHAT_LINK}", parse_mode="HTML")
        await call.message.edit_text(call.message.text + "\n\n🟢 <b>ОДОБРЕНО</b>")
    elif action == "no":
        await bot.send_message(target_uid, "❌ Твоя заявка отклонена.")
        await call.message.edit_text(call.message.text + "\n\n🔴 <b>ОТКЛОНЕНО</b>")
    await call.answer()

@dp.chat_member()
async def on_chat_member_update(update: ChatMemberUpdated):
    if update.chat.id == CHAT_ID:
        uid = update.new_chat_member.user.id
        if update.new_chat_member.status == "member":
            conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
            cursor.execute("SELECT role FROM approved_users WHERE user_id = ?", (uid,))
            row = cursor.fetchone(); conn.close()
            if row:
                await asyncio.sleep(2)
                await apply_tag(uid, row[0])
                name = f"@{update.new_chat_member.user.username}" if update.new_chat_member.user.username else update.new_chat_member.user.first_name
                conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
                cursor.execute("INSERT OR REPLACE INTO all_users (user_id, name) VALUES (?, ?)", (uid, name))
                conn.commit(); conn.close()

# --- MAIN ---
async def main():
    init_db()
    # Запуск веб-сервера в потоке
    server_thread = Thread(target=run_flask)
    server_thread.daemon = True
    server_thread.start()
    
    # Даем серверу 2 секунды, чтобы Render его задетектил
    await asyncio.sleep(2)
    
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot, allowed_updates=["message", "callback_query", "chat_member", "chat_join_request"])

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped")
