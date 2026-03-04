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
from aiogram.types import (ReplyKeyboardMarkup, KeyboardButton, 
                            InlineKeyboardButton, InlineKeyboardMarkup, 
                            BotCommand, CallbackQuery, ChatJoinRequest)

# --- SERVER ---
app = Flask('')
@app.route('/')
def home(): return "Бот Harmony активен!"

def run():
    # Порт 10000 для Render
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# --- CONFIG ---
TOKEN = "8344752199:AAHI7gZKcDAK2Dc7jzJMgjqO50iSy3LbYbY"
ADMIN_ID = 8294726083
CHAT_ID = -1003393441169 
CHAT_LINK = "https://t.me/+yai_7_Z-7_45MDky"
DB_PATH = "database.db"

bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- STATES ---
class RegForm(StatesGroup):
    role = State()
    username = State()

class ComplaintForm(StatesGroup):
    my_role = State()
    text = State()
    evidence = State()
    target_role = State()

class FeedbackForm(StatesGroup):
    text = State()

class AppealForm(StatesGroup):
    text = State()

# --- DATABASE ---
def init_db():
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS approved_users (user_id INTEGER PRIMARY KEY, role TEXT, violations INTEGER DEFAULT 0)")
    cursor.execute("CREATE TABLE IF NOT EXISTS all_users (user_id INTEGER PRIMARY KEY, name TEXT)")
    conn.commit(); conn.close()

def is_approved(uid):
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM approved_users WHERE user_id = ?", (uid,))
    res = cursor.fetchone(); conn.close()
    return bool(res)

def get_uid_by_role(role_name):
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM approved_users WHERE LOWER(role) = LOWER(?)", (role_name,))
    res = cursor.fetchone(); conn.close()
    return res[0] if res else None

# --- МЕХАНИКА ТЕГОВ (MEMBER TAGS) ---
async def set_member_tag(uid, tag_text):
    try:
        await bot.make_request("setChatMemberTag", {
            "chat_id": CHAT_ID,
            "user_id": uid,
            "tag": tag_text
        })
    except Exception as e:
        logging.error(f"Ошибка Member Tag: {e}")

# --- ЛОГИКА СОЗЫВА ---
async def global_call(new_role):
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM all_users"); rows = cursor.fetchall(); conn.close()
    
    try:
        count = await bot.get_chat_member_count(CHAT_ID)
        total_humans = count - 1 
    except:
        total_humans = len(rows)

    mentions = [f"<a href='tg://user?id={r[0]}'>.</a>" for r in rows]
    text = (f"📣 <b>СОЗЫВ: новый участник</b>\n"
            f"Роль: <b>{new_role}</b>\n\n"
            f"👥 Созвано: <b>{len(rows)}/{total_humans}</b>")
    
    for i in range(0, len(mentions), 10):
        chunk = "".join(mentions[i:i+10])
        await bot.send_message(CHAT_ID, text + chunk, parse_mode="HTML")

# --- СБОР ЮЗЕРОВ ---
@dp.message(F.chat.id == CHAT_ID)
async def collector(m: types.Message):
    if m.from_user.is_bot: return
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO all_users (user_id, name) VALUES (?, ?)", 
                   (m.from_user.id, m.from_user.first_name))
    conn.commit(); conn.close()

# --- МЕНЮ ---
def get_main_kb(uid):
    btns = []
    if not is_approved(uid): btns.append([KeyboardButton(text="📝 Вступить")])
    btns.append([KeyboardButton(text="🚨 Подать жалобу"), KeyboardButton(text="📩 Оставить отзыв")])
    if is_approved(uid): btns.append([KeyboardButton(text="🛡 Апелляция")])
    return ReplyKeyboardMarkup(keyboard=btns, resize_keyboard=True)

@dp.message(Command("start"))
async def cmd_start(m: types.Message):
    await m.answer("Панель управления активирована.", reply_markup=get_main_kb(m.from_user.id))

# --- АДМИН КОМАНДЫ ---
@dp.message(Command("add"))
async def cmd_add(m: types.Message):
    if m.from_user.id != ADMIN_ID: return
    try:
        parts = m.text.split(maxsplit=2)
        uid, role = int(parts[1]), parts[2]
        conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO approved_users (user_id, role) VALUES (?, ?)", (uid, role))
        conn.commit(); conn.close()
        await set_member_tag(uid, role)
        await m.answer(f"✅ Добавлен {uid} как {role}")
    except: await m.answer("Формат: `/add ID РОЛЬ`")

@dp.message(Command("del"))
async def cmd_del(m: types.Message):
    if m.from_user.id != ADMIN_ID: return
    try:
        uid = int(m.text.split()[1])
        conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
        cursor.execute("DELETE FROM approved_users WHERE user_id = ?", (uid,))
        conn.commit(); conn.close()
        await set_member_tag(uid, "")
        await m.answer(f"✅ Участник {uid} удален.")
    except: await m.answer("Формат: `/del ID`")

@dp.message(Command("list"))
async def cmd_list(m: types.Message):
    if m.from_user.id != ADMIN_ID: return
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute("SELECT user_id, role FROM approved_users"); rows = cursor.fetchall(); conn.close()
    res = "📂 <b>БАЗА:</b>\n" + "\n".join([f"<code>{r[0]}</code> | {r[1]}" for r in rows])
    await m.answer(res if rows else "База пуста", parse_mode="HTML")

# --- ВСТУПЛЕНИЕ ---
@dp.message(F.text == "📝 Вступить")
async def start_reg(m: types.Message, state: FSMContext):
    if is_approved(m.from_user.id): return
    await m.answer("Укажите вашу роль:"); await state.set_state(RegForm.role)

@dp.message(RegForm.role)
async def p_role(m: types.Message, state: FSMContext):
    await state.update_data(role=m.text); await m.answer("Ваш юзернейм:"); await state.set_state(RegForm.username)

@dp.message(RegForm.username)
async def p_user(m: types.Message, state: FSMContext):
    data = await state.get_data()
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Принять ✅", callback_data=f"adm_ok_{m.from_user.id}")]])
    await bot.send_message(ADMIN_ID, f"<b>АНКЕТА</b>\nЮЗ: {m.text}\nID: {m.from_user.id}\nРОЛЬ: {data['role']}", reply_markup=kb, parse_mode="HTML")
    await m.answer("Заявка отправлена."); await state.clear()

@dp.callback_query(F.data.startswith("adm_ok_"))
async def approve_user(call: CallbackQuery):
    uid = int(call.data.split("_")[2])
    role = call.message.text.split("РОЛЬ: ")[1].split("\n")[0].strip()
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO approved_users (user_id, role) VALUES (?, ?)", (uid, role))
    conn.commit(); conn.close()
    await bot.send_message(uid, f"Принято! Твоя роль: {role}\n{CHAT_LINK}", reply_markup=get_main_kb(uid))
    await call.message.edit_text(call.message.text + "\n\n✅ ОДОБРЕНО")
    await set_member_tag(uid, role)
    await global_call(role)

# --- ЖАЛОБЫ И ОТЗЫВЫ ---
@dp.message(F.text == "📩 Оставить отзыв")
async def btn_feedback(m: types.Message, state: FSMContext):
    await m.answer("Напишите ваш отзыв:"); await state.set_state(FeedbackForm.text)

@dp.message(FeedbackForm.text)
async def process_fb(m: types.Message, state: FSMContext):
    await bot.send_message(ADMIN_ID, f"📥 <b>ОТЗЫВ</b>\n\n{m.text}", parse_mode="HTML")
    await m.answer("Принято!"); await state.clear()

@dp.message(F.text == "🚨 Подать жалобу")
async def btn_complaint(m: types.Message, state: FSMContext):
    await m.answer("Ваша роль:"); await state.set_state(ComplaintForm.my_role)

@dp.message(ComplaintForm.my_role)
async def comp_1(m: types.Message, state: FSMContext):
    await state.update_data(my_role=m.text); await m.answer("Суть жалобы:"); await state.set_state(ComplaintForm.text)

@dp.message(ComplaintForm.text)
async def comp_2(m: types.Message, state: FSMContext):
    await state.update_data(text=m.text); await m.answer("Роль нарушителя:"); await state.set_state(ComplaintForm.target_role)

@dp.message(ComplaintForm.target_role)
async def comp_final(m: types.Message, state: FSMContext):
    data = await state.get_data()
    await bot.send_message(ADMIN_ID, f"🚨 <b>ЖАЛОБА</b>\nОт: {data['my_role']}\nНа: {m.text}\nСуть: {data['text']}", parse_mode="HTML")
    await m.answer("Жалоба отправлена."); await state.clear()

# --- ЗАПУСК ---
async def main():
    init_db()
    Thread(target=run, daemon=True).start()
    await asyncio.sleep(2)
    await bot.delete_webhook(drop_pending_updates=True)
    await bot.set_my_commands([
        BotCommand(command="start", description="Меню"),
        BotCommand(command="list", description="База (Админ)"),
        BotCommand(command="add", description="Добавить ID РОЛЬ"),
        BotCommand(command="del", description="Удалить ID")
    ])
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
