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
                            BotCommand, CallbackQuery, ChatMemberUpdated, ChatJoinRequest)

# --- SERVER ДЛЯ RENDER ---
app = Flask('')
@app.route('/')
def home(): return "Бот работает!"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- CONFIG ---
TOKEN = "8344752199:AAEuPor3OXH890Z9XMKBVLRQWWEx6f9a9Sw"
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

# --- DATABASE ---
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS approved_users (user_id INTEGER PRIMARY KEY, role TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS all_users (user_id INTEGER PRIMARY KEY, name TEXT)")
    conn.commit()
    conn.close()

# --- МЕХАНИКА ТЕГОВ (Member Tags) + АВТО-ПРИНЯТИЕ ---
@dp.chat_join_request()
async def auto_approve_and_tag(request: ChatJoinRequest):
    uid = request.from_user.id
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT role FROM approved_users WHERE user_id = ?", (uid,))
    res = cursor.fetchone()
    conn.close()
    
    if res:
        role = res[0]
        # 1. Одобряем вход
        await request.approve()
        
        # 2. Ставим плашку (Custom Title)
        try:
            await asyncio.sleep(2) # Пауза, чтобы сервер TG успел "увидеть" юзера в чате
            # Даем минимальные права админа (иначе тег не отобразится)
            await bot.promote_chat_member(
                chat_id=CHAT_ID,
                user_id=uid,
                can_invite_users=True 
            )
            # Устанавливаем сам текст плашки
            await bot.set_chat_administrator_custom_title(CHAT_ID, uid, role)
            await bot.send_message(CHAT_ID, f"🎉 В чат вошел: <b>{role}</b>", parse_mode="HTML")
        except Exception as e:
            logging.error(f"Ошибка при выдаче тега: {e}")
    else:
        # Если юзера нет в базе, заявка просто висит (ты можешь принять её вручную)
        pass

# --- КОМАНДЫ АДМИНА ---

@dp.message(Command("del"))
async def cmd_delete(m: types.Message):
    if m.from_user.id != ADMIN_ID: return
    try:
        target_id = int(m.text.split()[1])
        conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
        cursor.execute("DELETE FROM all_users WHERE user_id = ?", (target_id,))
        cursor.execute("DELETE FROM approved_users WHERE user_id = ?", (target_id,))
        conn.commit(); conn.close()
        await m.answer(f"✅ Пользователь {target_id} удален.")
    except:
        await m.answer("Юзай: /del ID")

@dp.message(Command("list"))
async def cmd_list(m: types.Message):
    if m.from_user.id != ADMIN_ID: return
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute("SELECT user_id, name FROM all_users"); rows = cursor.fetchall(); conn.close()
    if not rows:
        await m.answer("База пуста."); return
    text = "📂 <b>БАЗА (ID | NAME):</b>\n"
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
        await m.answer(f"📣 <b>СБОР:</b>\n{', '.join(mentions[i:i+5])}", parse_mode="HTML")

# --- АНКЕТА ---

@dp.message(Command("start"))
async def cmd_start(m: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📝 Вступить", callback_data="start_reg")]])
    await m.answer(f"Твой ID: <code>{m.from_user.id}</code>\nНажми кнопку ниже:", reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data == "start_reg")
async def start_reg(call: CallbackQuery, state: FSMContext):
    await call.message.answer("Укажите вашу роль (будет на плашке):")
    await state.set_state(Form.role); await call.answer()

@dp.message(Form.role)
async def p_role(m: types.Message, state: FSMContext):
    await state.update_data(role=m.text); await m.answer("Укажите ваш ник:"); await state.set_state(Form.user)

@dp.message(Form.user)
async def p_user(m: types.Message, state: FSMContext):
    data = await state.get_data(); role = data.get('role'); uid = m.from_user.id
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Принять ✅", callback_data=f"adm_ok_{uid}"), 
         InlineKeyboardButton(text="Отклонить ❌", callback_data=f"adm_no_{uid}")],
        [InlineKeyboardButton(text="Написать 💬", callback_data=f"adm_msg_{uid}")]
    ])
    await bot.send_message(ADMIN_ID, f"<b>ANKETA</b>\nUSER: {m.text}\nID: <code>{uid}</code>\nROLE: {role}", reply_markup=kb, parse_mode="HTML")
    await m.answer("Заявка отправлена администратору."); await state.clear()

# --- КНОПКИ АДМИНА ---

@dp.callback_query(F.data.startswith("adm_"))
async def admin_btns(call: CallbackQuery, state: FSMContext):
    action = call.data.split("_")[1]; target_uid = int(call.data.split("_")[2])
    
    if action == "ok":
        # Достаем роль из текста анкеты
        role = "Member"
        if "ROLE: " in call.message.text:
            role = call.message.text.split("ROLE: ")[1].split("\n")[0]
            
        conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO approved_users (user_id, role) VALUES (?, ?)", (target_uid, role))
        conn.commit(); conn.close()
        
        await bot.send_message(target_uid, f"Принято! Твоя роль: {role}\nВступай: {CHAT_LINK}")
        await call.message.edit_text(call.message.text + "\n\n✅ ОДОБРЕНО")
        
    elif action == "no":
        await bot.send_message(target_uid, "Отклонено.")
        await call.message.edit_text(call.message.text + "\n\n❌ ОТКЛОНЕНО")
        
    elif action == "msg":
        await call.message.answer(f"Текст для {target_uid}:")
        await state.update_data(target_to_msg=target_uid); await state.set_state(Form.admin_reply)
    await call.answer()

@dp.message(Form.admin_reply)
async def admin_reply_send(m: types.Message, state: FSMContext):
    data = await state.get_data(); target = data.get('target_to_msg')
    try:
        await bot.send_message(target, f"✉️ Сообщение от админа:\n\n{m.text}")
        await m.answer("Отправлено.")
    except: await m.answer("Ошибка.")
    await state.clear()

# --- СБОР ИМЕН В ГРУППЕ ---
@dp.message(F.chat.id == CHAT_ID)
async def collect_msg(m: types.Message):
    if m.from_user.is_bot: return
    name = f"@{m.from_user.username}" if m.from_user.username else m.from_user.first_name
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO all_users (user_id, name) VALUES (?, ?)", (m.from_user.id, name))
    conn.commit(); conn.close()

# --- УДАЛЕНИЕ ПРИ ВЫХОДЕ ---
@dp.chat_member()
async def on_chat_member_update(update: ChatMemberUpdated):
    if update.chat.id == CHAT_ID:
        if update.new_chat_member.status in ["left", "kicked"]:
            uid = update.new_chat_member.user.id
            conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
            cursor.execute("DELETE FROM all_users WHERE user_id = ?", (uid,))
            cursor.execute("DELETE FROM approved_users WHERE user_id = ?", (uid,))
            conn.commit(); conn.close()

# --- ЗАПУСК ---
async def main():
    init_db()
    Thread(target=run, daemon=True).start() # Запуск Flask сервера
    await bot.set_my_commands([
        BotCommand(command="start", description="Регистрация"),
        BotCommand(command="all", description="Сбор"),
        BotCommand(command="list", description="База"),
        BotCommand(command="del", description="Удалить по ID")
    ])
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot, allowed_updates=["message", "callback_query", "chat_member", "chat_join_request"])

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
