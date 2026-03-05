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

# --- 24/7 SERVER (RENDER COMPATIBLE) ---
app = Flask('')
@app.route('/')
def home(): return "Bot is Online"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

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

# --- DATABASE ---
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS approved_users (user_id INTEGER PRIMARY KEY, role TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS all_users (user_id INTEGER PRIMARY KEY, name TEXT)")
    conn.commit()
    conn.close()

# --- TAG API ---
async def apply_tag(uid, tag):
    url = f"https://api.telegram.org/bot{TOKEN}/setChatMemberTag"
    payload = {"chat_id": CHAT_ID, "user_id": int(uid), "tag": str(tag)}
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as resp:
            return await resp.json()

# --- KEYBOARDS ---
def main_kb():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="📝 Вступить")]], resize_keyboard=True)

# --- COMMANDS ---

@dp.message(Command("start"))
async def cmd_start(m: types.Message):
    await m.answer(f"👋 Привет! Твой ID: <code>{m.from_user.id}</code>\nИспользуй кнопку ниже для подачи анкеты.", 
                   reply_markup=main_kb(), parse_mode="HTML")

@dp.message(Command("add"))
async def cmd_add(m: types.Message):
    if m.from_user.id != ADMIN_ID: return
    try:
        parts = m.text.split(maxsplit=2)
        target_id, role = int(parts[1]), parts[2]
        conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO approved_users (user_id, role) VALUES (?, ?)", (target_id, role))
        conn.commit(); conn.close()
        await m.answer(f"✅ Пользователь {target_id} добавлен в базу с ролью: {role}")
    except:
        await m.answer("⚠️ Формат: /add ID РОЛЬ")

@dp.message(Command("del"))
async def cmd_delete(m: types.Message):
    if m.from_user.id != ADMIN_ID: return
    try:
        target_id = int(m.text.split()[1])
        conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
        cursor.execute("DELETE FROM all_users WHERE user_id = ?", (target_id,))
        cursor.execute("DELETE FROM approved_users WHERE user_id = ?", (target_id,))
        conn.commit(); conn.close()
        await m.answer(f"🗑 Пользователь {target_id} удален.")
    except:
        await m.answer("⚠️ Формат: /del ID")

@dp.message(Command("list"))
async def cmd_list(m: types.Message):
    if m.from_user.id != ADMIN_ID: return
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute("SELECT user_id, name FROM all_users"); rows = cursor.fetchall(); conn.close()
    if not rows:
        await m.answer("📭 База пуста.")
        return
    text = "📋 <b>СПИСОК (ID | ЮЗ):</b>\n"
    for r in rows:
        text += f"<code>{r[0]}</code> | {r[1]}\n"
    await m.answer(text, parse_mode="HTML")

@dp.message(Command("all"))
async def cmd_all(m: types.Message):
    if m.from_user.id != ADMIN_ID: return
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM all_users"); rows = cursor.fetchall(); conn.close()
    if not rows: return
    
    await m.answer("📣 <b>ОБЩИЙ СБОР!</b>")
    
    # Сбор по 5 человек с невидимым упоминанием
    users = [r[0] for r in rows]
    for i in range(0, len(users), 5):
        chunk = users[i:i+5]
        mentions = "".join([f'<a href="tg://user?id={uid}">\u200b</a>' for uid in chunk])
        await m.answer(f"⚡️ {mentions}", parse_mode="HTML")
        await asyncio.sleep(0.5)

# --- АНКЕТА ---

@dp.message(F.text == "📝 Вступить")
async def start_reg_text(m: types.Message, state: FSMContext):
    await m.answer("📝 Напиши свою роль:")
    await state.set_state(Form.role)

@dp.message(Form.role)
async def p_role(m: types.Message, state: FSMContext):
    await state.update_data(role=m.text)
    await m.answer("👤 Напиши свой ЮЗ:")
    await state.set_state(Form.user)

@dp.message(Form.user)
async def p_user(m: types.Message, state: FSMContext):
    data = await state.get_data()
    role = data.get('role')
    uid = m.from_user.id
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Принять ✅", callback_data=f"adm_ok_{uid}"), 
         InlineKeyboardButton(text="Отклонить ❌", callback_data=f"adm_no_{uid}")]
    ])
    await bot.send_message(ADMIN_ID, f"📝 <b>АНКЕТА</b>\nЮЗ: {m.text}\nID: {uid}\nРОЛЬ: {role}", reply_markup=kb, parse_mode="HTML")
    await m.answer("📨 Заявка отправлена.")
    await state.clear()

# --- ADMIN ACTIONS ---

@dp.callback_query(F.data.startswith("adm_"))
async def admin_btns(call: CallbackQuery):
    action = call.data.split("_")[1]
    target_uid = int(call.data.split("_")[2])
    
    if action == "ok":
        role = call.message.text.split("РОЛЬ: ")[1] if "РОЛЬ: " in call.message.text else "Member"
        conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO approved_users (user_id, role) VALUES (?, ?)", (target_uid, role))
        conn.commit(); conn.close()
        await bot.send_message(target_uid, f"✨ Принято! Роль <b>{role}</b> будет выдана автоматически при входе.\n{CHAT_LINK}", parse_mode="HTML")
        await call.message.edit_text(call.message.text + "\n\n✅ <b>СТАТУС: ОДОБРЕНО</b>", parse_mode="HTML")
        
    elif action == "no":
        await bot.send_message(target_uid, "❌ Твоя заявка была отклонена.")
        await call.message.edit_text(call.message.text + "\n\n❌ <b>СТАТУС: ОТКЛОНЕНО</b>", parse_mode="HTML")
    await call.answer()

# --- ЛОГИКА ВСТУПЛЕНИЯ И ПЛАШЕК ---

@dp.chat_join_request()
async def auto_approve(request: ChatJoinRequest):
    try:
        await request.approve()
    except:
        pass

@dp.chat_member()
async def on_chat_member_update(update: ChatMemberUpdated):
    if update.chat.id == CHAT_ID:
        uid = update.new_chat_member.user.id
        
        # ВСТУПЛЕНИЕ
        if update.new_chat_member.status == "member":
            conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
            cursor.execute("SELECT role FROM approved_users WHERE user_id = ?", (uid,))
            row = cursor.fetchone(); conn.close()
            
            if row:
                role = row[0]
                await asyncio.sleep(2)
                await apply_tag(uid, role) # ПОДПИСЬ ТЕГА
                
                # Добавляем в список для сбора
                name = f"@{update.new_chat_member.user.username}" if update.new_chat_member.user.username else update.new_chat_member.user.first_name
                conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
                cursor.execute("INSERT OR REPLACE INTO all_users (user_id, name) VALUES (?, ?)", (uid, name))
                conn.commit(); conn.close()

        # ВЫХОД
        elif update.new_chat_member.status in ["left", "kicked"]:
            conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
            cursor.execute("DELETE FROM all_users WHERE user_id = ?", (uid,))
            cursor.execute("DELETE FROM approved_users WHERE user_id = ?", (uid,))
            conn.commit(); conn.close()

async def main():
    init_db()
    Thread(target=run, daemon=True).start()
    await bot.set_my_commands([
        BotCommand(command="start", description="Меню"),
        BotCommand(command="all", description="Общий сбор"),
        BotCommand(command="list", description="Список участников"),
        BotCommand(command="del", description="Удалить по ID"),
        BotCommand(command="add", description="Добавить в базу")
    ])
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot, allowed_updates=["message", "callback_query", "chat_member", "chat_join_request"])

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
