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
                           CallbackQuery, ChatJoinRequest)

# --- SERVER ---
app = Flask('')
@app.route('/')
def home(): return "Harmony: Плашки и Созыв"

def run():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# --- КОНФИГ (АКТУАЛЬНЫЙ ТОКЕН) ---
TOKEN = "8344752199:AAFt6L6id83M-eQZMkXKXRLhle2oP9Um98A"
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

def get_all_users():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM approved_users")
    users = [row[0] for row in cursor.fetchall()]
    conn.close()
    return users

# --- УЛУЧШЕННАЯ ФУНКЦИЯ ПЛАШЕК ---
async def set_member_tag(uid, tag_text):
    try:
        # Проверяем статус в чате для обновления кеша Telegram
        try:
            await bot.get_chat_member(CHAT_ID, uid)
        except Exception as e:
            logging.warning(f"Ошибка проверки членства: {e}")

        url = f"https://api.telegram.org/bot{TOKEN}/setChatMemberTag"
        payload = {
            "chat_id": int(CHAT_ID),
            "user_id": int(uid),
            "tag": str(tag_text)
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as response:
                result = await response.json()
                if result.get("ok"):
                    return True, "OK"
                
                # Если ошибка, ждем еще 3 секунды и пробуем финальный раз
                await asyncio.sleep(3)
                async with session.post(url, json=payload) as retry_res:
                    retry_result = await retry_res.json()
                    return retry_result.get("ok"), retry_result.get("description", "Error")
    except Exception as e:
        logging.error(f"Критическая ошибка Member Tag: {e}")
        return False, str(e)

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

# --- АВТО-ПРИЕМ ---
@dp.chat_join_request()
async def auto_approve(request: ChatJoinRequest):
    try:
        await request.approve()
        await bot.send_message(
            request.from_user.id, 
            "<b>Добро пожаловать!</b> ✅ Заявка одобрена.\n\nЖми <b>📝 Вступить</b>, чтобы заполнить анкету и получить плашку.",
            reply_markup=get_main_kb(), parse_mode="HTML"
        )
    except: pass

def get_main_kb():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="📝 Вступить")]], resize_keyboard=True)

# --- ОБРАБОТКА АНКЕТЫ ---
@dp.callback_query(F.data.startswith("adm_ok_"))
async def approve(call: CallbackQuery):
    uid = int(call.data.split("_")[2])
    role = "Участник"
    if "РОЛЬ: " in call.message.text:
        role = call.message.text.split("РОЛЬ: ")[1].split("\n")[0].strip()

    # Сохраняем в БД
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO approved_users (user_id, role) VALUES (?, ?)", (uid, role))
    conn.commit()
    conn.close()
    
    original_text = call.message.text
    await call.message.edit_text(original_text + "\n⏳ Синхронизация с чатом (5 сек)...")
    
    # Даем Telegram время «принять» участника в списки
    await asyncio.sleep(5)
    
    # Пытаемся поставить плашку
    success, error_msg = await set_member_tag(uid, role)
    
    if success:
        status_text = f"\n✅ ПРИНЯТ. ПЛАШКА '{role}' ВЫДАНА."
    else:
        status_text = f"\n⚠️ ПРИНЯТ, НО ПЛАШКА НЕ ВЫШЛА: {error_msg}"
    
    try:
        await bot.send_message(uid, f"Твоя роль <b>{role}</b> подтверждена!\nВступай: {CHAT_LINK}", parse_mode="HTML")
    except: pass

    await call.message.edit_text(original_text + status_text)
    
    # Созыв
    await internal_call(role)

@dp.callback_query(F.data.startswith("adm_no_"))
async def reject(call: CallbackQuery):
    uid = int(call.data.split("_")[2])
    await bot.send_message(uid, "Заявка отклонена.")
    await call.message.edit_text(call.message.text + "\n❌ ОТКЛОНЕНО")

# --- ЧАТ С АДМИНОМ ---
@dp.callback_query(F.data.startswith("chat_with_"))
async def start_reply(call: CallbackQuery, state: FSMContext):
    target_id = int(call.data.split("_")[2])
    await state.update_data(reply_to=target_id)
    await state.set_state(AdminChat.waiting_for_reply)
    await call.message.answer(f"Напиши сообщение для {target_id}:")
    await call.answer()

@dp.message(AdminChat.waiting_for_reply)
async def send_reply(m: types.Message, state: FSMContext):
    if m.from_user.id != ADMIN_ID: return
    data = await state.get_data()
    target_id = data.get("reply_to")
    try:
        await bot.send_message(target_id, f"✉️ <b>Сообщение от администрации:</b>\n\n{m.text}", parse_mode="HTML")
        await m.answer("Отправлено!")
    except: await m.answer("Ошибка отправки.")
    await state.clear()

# --- РЕГИСТРАЦИЯ ---
@dp.message(F.text == "📝 Вступить")
async def start_reg(m: types.Message, state: FSMContext):
    await m.answer("Напиши свою роль:")
    await state.set_state(RegForm.role)

@dp.message(RegForm.role)
async def p_role(m: types.Message, state: FSMContext):
    await state.update_data(role=m.text)
    await m.answer("Напиши свой @username:")
    await state.set_state(RegForm.username)

@dp.message(RegForm.username)
async def p_user(m: types.Message, state: FSMContext):
    data = await state.get_data()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Принять ✅", callback_data=f"adm_ok_{m.from_user.id}")],
        [InlineKeyboardButton(text="Отклонить ❌", callback_data=f"adm_no_{m.from_user.id}")],
        [InlineKeyboardButton(text="Написать 💬", callback_data=f"chat_with_{m.from_user.id}")]
    ])
    await bot.send_message(ADMIN_ID, f"<b>АНКЕТА</b>\nЮЗ: {m.text}\nID: {m.from_user.id}\nРОЛЬ: {data['role']}", reply_markup=kb, parse_mode="HTML")
    await m.answer("Заявка ушла!")
    await state.clear()

async def main():
    init_db()
    Thread(target=run, daemon=True).start()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot, allowed_updates=["message", "callback_query", "chat_join_request"])

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
