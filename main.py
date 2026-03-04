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
                            ReplyKeyboardRemove, ChatJoinRequest)

# --- SERVER FOR RENDER / UPTIME ---
app = Flask('')
@app.route('/')
def home(): return "Harmony Bot is Online"

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

# --- DATABASE ---
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS approved_users (user_id INTEGER PRIMARY KEY, role TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS all_users (user_id INTEGER PRIMARY KEY, name TEXT)")
    conn.commit()
    conn.close()

# --- KEYBOARDS ---
def get_main_reply_kb(user_id):
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM approved_users WHERE user_id = ?", (user_id,))
    is_joined = cursor.fetchone(); conn.close()
    
    kb = []
    if not is_joined:
        kb.append([KeyboardButton(text="📝 Вступить")])
    kb.append([KeyboardButton(text="⚖️ Апелляция"), KeyboardButton(text="🚫 Жалоба")])
    kb.append([KeyboardButton(text="⭐ Отзыв")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

# --- АВТО-ПРИНЯТИЕ + ВЫДАЧА ТЕГА ---
@dp.chat_join_request()
async def approve_and_tag(request: ChatJoinRequest):
    uid = request.from_user.id
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute("SELECT role FROM approved_users WHERE user_id = ?", (uid,))
    res = cursor.fetchone(); conn.close()
    
    if res:
        role = res[0]
        # 1. Принимаем в группу
        await request.approve()
        
        # Уведомление админу
        await bot.send_message(ADMIN_ID, f"🔔 <b>Вход!</b>\nЮзер: {request.from_user.full_name}\nID: <code>{uid}</code>\nРоль: <code>{role}</code>", parse_mode="HTML")
        
        # 2. Пытаемся поставить Member Tag (нужны права админа у бота)
        try:
            await asyncio.sleep(2) # Пауза, чтобы Telegram успел обработать вход
            await bot.promote_chat_member(
                chat_id=CHAT_ID, 
                user_id=uid, 
                can_invite_users=True # Минимальное право для отображения тега
            )
            await bot.set_chat_administrator_custom_title(CHAT_ID, uid, role)
            await bot.send_message(CHAT_ID, f"🎉 Встречаем нового участника: <b>{role}</b>!", parse_mode="HTML")
        except Exception as e:
            logging.error(f"Ошибка при выдаче тега: {e}")

# --- СБОР ДАННЫХ ДЛЯ /ALL ---
@dp.message(F.chat.id == CHAT_ID)
async def collect_names(m: types.Message):
    if m.from_user.is_bot: return
    
    # Имя для упоминания: приоритет username, если нет - имя
    display_name = f"@{m.from_user.username}" if m.from_user.username else m.from_user.first_name
    
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO all_users (user_id, name) VALUES (?, ?)", (m.from_user.id, display_name))
    conn.commit(); conn.close()

# --- АНКЕТА РЕГИСТРАЦИИ ---
@dp.message(Command("start"))
async def cmd_start(m: types.Message):
    await m.answer("Добро пожаловать!", reply_markup=get_main_reply_kb(m.from_user.id))

@dp.message(F.text == "📝 Вступить")
async def start_reg(m: types.Message, state: FSMContext):
    await m.answer("Укажите вашу роль (например: Воин, Маг):", reply_markup=ReplyKeyboardRemove())
    await state.set_state(Form.role)

@dp.message(Form.role)
async def p_role(m: types.Message, state: FSMContext):
    await state.update_data(role=m.text)
    await m.answer("Укажите ваш игровой ник:")
    await state.set_state(Form.user)

@dp.message(Form.user)
async def p_user(m: types.Message, state: FSMContext):
    data = await state.get_data()
    role = data['role']
    uid = m.from_user.id
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Принять ✅", callback_data=f"adm_ok_{uid}"), 
         InlineKeyboardButton(text="Отклонить ❌", callback_data=f"adm_no_{uid}")]
    ])
    
    await bot.send_message(ADMIN_ID, f"🆕 <b>АНКЕТА</b>\nЮЗЕР: {m.text}\nID: <code>{uid}</code>\nROLE: {role}", reply_markup=kb, parse_mode="HTML")
    await m.answer("Ваша заявка отправлена на проверку!", reply_markup=get_main_reply_kb(uid))
    await state.clear()

# --- ОБРАБОТКА РЕШЕНИЯ АДМИНА ---
@dp.callback_query(F.data.startswith("adm_ok_"))
async def adm_approve(call: CallbackQuery):
    uid = int(call.data.split("_")[2])
    # Вытягиваем роль из текста сообщения админа
    try:
        role = call.message.text.split("ROLE: ")[1]
    except:
        role = "Member"
    
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO approved_users (user_id, role) VALUES (?, ?)", (uid, role))
    conn.commit(); conn.close()
    
    await bot.send_message(uid, f"Ваша заявка одобрена! ✅\nРоль: {role}\n\nВступайте в группу по ссылке:\n{CHAT_LINK}")
    await call.message.edit_text(call.message.text + f"\n\n✅ ОДОБРЕНО (Роль: {role})")
    await call.answer("Пользователь одобрен")

@dp.callback_query(F.data.startswith("adm_no_"))
async def adm_decline(call: CallbackQuery):
    uid = int(call.data.split("_")[2])
    await bot.send_message(uid, "К сожалению, ваша заявка отклонена. ❌")
    await call.message.edit_text(call.message.text + "\n\n❌ ОТКЛОНЕНО")
    await call.answer("Отклонено")

# --- КОМАНДА /ALL ---
@dp.message(Command("all"))
async def cmd_all(m: types.Message):
    if m.from_user.id != ADMIN_ID: return
    
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute("SELECT user_id, name FROM all_users"); rows = cursor.fetchall(); conn.close()
    
    if not rows:
        await m.answer("Список пуст.")
        return
        
    mentions = [f"<a href='tg://user?id={r[0]}'>{r[1]}</a>" for r in rows]
    # Разбиваем по 5 человек, чтобы не спамить огромным сообщением
    for i in range(0, len(mentions), 5):
        await m.answer(f"📣 <b>ОБЩИЙ СБОР:</b>\n{', '.join(mentions[i:i+5])}", parse_mode="HTML")

# --- MAIN ---
async def main():
    init_db()
    Thread(target=run, daemon=True).start() # Flask для Render
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot, allowed_updates=["message", "callback_query", "chat_member", "chat_join_request"])

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot stopped")
