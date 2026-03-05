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
                           CallbackQuery, ChatJoinRequest, ChatMemberUpdated)

# --- SERVER ---
app = Flask('')
@app.route('/')
def home(): return "Harmony: Плашки при вступлении"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- КОНФИГ (ТОКЕН ОБНОВЛЕН) ---
TOKEN = "8344752199:AAFwouRQZYV2ztyDwC44qCu8uTxq2lgWtoc"
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
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS approved_users (user_id INTEGER PRIMARY KEY, role TEXT)")
    conn.commit()
    conn.close()

def get_user_role(uid):
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute("SELECT role FROM approved_users WHERE user_id = ?", (uid,))
    res = cursor.fetchone(); conn.close()
    return res[0] if res else None

def get_all_users():
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM approved_users")
    users = [row[0] for row in cursor.fetchall()]; conn.close()
    return users

# --- ФУНКЦИЯ ПЛАШЕК (ЧЕРЕЗ API) ---
async def set_member_tag(uid, tag_text):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/setChatMemberTag"
        payload = {"chat_id": CHAT_ID, "user_id": int(uid), "tag": str(tag_text)}
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as response:
                return await response.json()
    except Exception as e:
        logging.error(f"Ошибка Member Tag: {e}")
        return None

# --- УМНЫЙ СОЗЫВ ---
async def internal_call(new_member_role):
    users = get_all_users()
    if not users: return
    await bot.send_message(CHAT_ID, f"📢 <b>Общий сбор!</b>\nНовый участник: <b>{new_member_role}</b>", parse_mode="HTML")
    chunk_size = 5
    for i in range(0, len(users), chunk_size):
        chunk = users[i:i + chunk_size]
        mentions = "".join([f'<a href="tg://user?id={uid}">\u200b</a>' for uid in chunk])
        try:
            await bot.send_message(CHAT_ID, f"⚡️{mentions}", parse_mode="HTML")
            await asyncio.sleep(0.6)
        except: pass

# --- ТЕХНИКА: АВТО-ПЛАШКА ПРИ ВСТУПЛЕНИИ ---
@dp.chat_member()
async def on_member_join(update: ChatMemberUpdated):
    # Если юзер только что стал участником (member)
    if update.chat.id == CHAT_ID and update.new_chat_member.status == "member":
        uid = update.new_chat_member.user.id
        role = get_user_role(uid)
        
        if role:
            # Магия: вешаем плашку, как только он зашел
            await asyncio.sleep(1) # Микро-пауза для прогрузки
            res = await set_member_tag(uid, role)
            logging.info(f"Авто-тег для {uid} ({role}): {res}")
            
            # Созыв
            await internal_call(role)

# --- АВТО-ПРИЕМ ЗАЯВОК ---
@dp.chat_join_request()
async def auto_approve(request: ChatJoinRequest):
    try:
        await request.approve()
        await bot.send_message(
            request.from_user.id, 
            "<b>Заявка одобрена!</b> ✅\n\nЧтобы получить роль (плашку), нажми кнопку ниже:",
            reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="📝 Вступить")]], resize_keyboard=True),
            parse_mode="HTML"
        )
    except: pass

# --- ОБРАБОТКА АНКЕТЫ ---
@dp.callback_query(F.data.startswith("adm_ok_"))
async def approve(call: CallbackQuery):
    uid = int(call.data.split("_")[2])
    role = call.message.text.split("РОЛЬ: ")[1].split("\n")[0].strip() if "РОЛЬ: " in call.message.text else "Участник"

    # Сохраняем роль в БД (чтобы выдать её при вступлении)
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO approved_users (user_id, role) VALUES (?, ?)", (uid, role))
    conn.commit(); conn.close()
    
    await bot.send_message(uid, f"Твоя роль <b>{role}</b> утверждена!\nТеперь заходи в чат: {CHAT_LINK}", parse_mode="HTML")
    await call.message.edit_text(call.message.text + f"\n✅ ОДОБРЕНО. Роль {role} выдастся автоматически при входе.")

@dp.callback_query(F.data.startswith("adm_no_"))
async def reject(call: CallbackQuery):
    uid = int(call.data.split("_")[2])
    await bot.send_message(uid, "Заявка отклонена.")
    await call.message.edit_text(call.message.text + "\n❌ ОТКЛОНЕНО")

# --- РЕГИСТРАЦИЯ ---
@dp.message(F.text == "📝 Вступить")
async def start_reg(m: types.Message, state: FSMContext):
    await m.answer("Напиши свою роль (например: Ризли):"); await state.set_state(RegForm.role)

@dp.message(RegForm.role)
async def p_role(m: types.Message, state: FSMContext):
    await state.update_data(role=m.text)
    await m.answer("Напиши свой ник или @username:"); await state.set_state(RegForm.username)

@dp.message(RegForm.username)
async def p_user(m: types.Message, state: FSMContext):
    data = await state.get_data()
    uid = m.from_user.id
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Принять ✅", callback_data=f"adm_ok_{uid}")],
        [InlineKeyboardButton(text="Отклонить ❌", callback_data=f"adm_no_{uid}")],
        [InlineKeyboardButton(text="Написать 💬", callback_data=f"chat_with_{uid}")]
    ])
    await bot.send_message(ADMIN_ID, f"<b>АНКЕТА</b>\nЮЗ: {m.text}\nID: {uid}\nРОЛЬ: {data['role']}", reply_markup=kb, parse_mode="HTML")
    await m.answer("Анкета отправлена на проверку!"); await state.clear()

# --- ЧАТ С АДМИНОМ (ОБРАТНАЯ СВЯЗЬ) ---
@dp.callback_query(F.data.startswith("chat_with_"))
async def start_reply(call: CallbackQuery, state: FSMContext):
    target_id = int(call.data.split("_")[2])
    await state.update_data(reply_to=target_id); await state.set_state(AdminChat.waiting_for_reply)
    await call.message.answer(f"Пиши ответ для {target_id}:"); await call.answer()

@dp.message(AdminChat.waiting_for_reply)
async def send_reply(m: types.Message, state: FSMContext):
    if m.from_user.id != ADMIN_ID: return
    data = await state.get_data(); target_id = data.get("reply_to")
    try:
        await bot.send_message(target_id, f"✉️ <b>Сообщение от админа:</b>\n\n{m.text}", parse_mode="HTML")
        await m.answer("Отправлено!"); await state.clear()
    except: await m.answer("Ошибка.")

async def main():
    init_db()
    Thread(target=run, daemon=True).start()
    await bot.delete_webhook(drop_pending_updates=True)
    # Важно: добавляем chat_member в список разрешенных обновлений
    await dp.start_polling(bot, allowed_updates=["message", "callback_query", "chat_join_request", "chat_member"])

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO); asyncio.run(main())
