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

# --- SERVER ДЛЯ RENDER ---
app = Flask('')
@app.route('/')
def home(): return "Бот Harmony активен и готов к работе!"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- КОНФИГУРАЦИЯ (НОВЫЙ ТОКЕН) ---
TOKEN = "8344752199:AAEiWZnI-0RrUB8Pl8YsBw6Jw7Sc3wBFkjo"
ADMIN_ID = 8294726083
CHAT_ID = -1003393441169 
CHAT_LINK = "https://t.me/+yai_7_Z-7_45MDky"
DB_PATH = "database.db"

bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- СОСТОЯНИЯ ---
class RegForm(StatesGroup):
    role = State()
    username = State()

# --- БАЗА ДАННЫХ ---
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

# --- НОВАЯ МЕХАНИКА ТЕГОВ (MEMBER TAGS) ---
async def set_member_tag(uid, tag_text):
    try:
        # Прямой вызов API метода setChatMemberTag (Telegram 12.5+)
        await bot.make_request("setChatMemberTag", {
            "chat_id": CHAT_ID,
            "user_id": uid,
            "tag": tag_text
        })
        logging.info(f"Тег '{tag_text}' установлен для {uid}")
    except Exception as e:
        logging.error(f"Ошибка установки тега: {e}")

# --- ЛОГИКА СОЗЫВА ---
async def global_call(new_role):
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM all_users"); rows = cursor.fetchall(); conn.close()
    
    try:
        count = await bot.get_chat_member_count(CHAT_ID)
        total_humans = count - 1 
    except:
        total_humans = len(rows)

    # Скрытые теги (точки) для уведомления всех в базе
    mentions = [f"<a href='tg://user?id={r[0]}'>.</a>" for r in rows]
    text = (f"📣 <b>СОЗЫВ: новый участник</b>\n"
            f"Роль: <b>{new_role}</b>\n\n"
            f"👥 Созвано: <b>{len(rows)}/{total_humans}</b>")
    
    # Отправляем пачками по 10, чтобы избежать лимитов
    for i in range(0, len(mentions), 10):
        chunk = "".join(mentions[i:i+10])
        await bot.send_message(CHAT_ID, text + chunk, parse_mode="HTML")

# --- СБОР ЮЗЕРОВ ДЛЯ СОЗЫВА ---
@dp.message(F.chat.id == CHAT_ID)
async def collector(m: types.Message):
    if m.from_user.is_bot: return
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO all_users (user_id, name) VALUES (?, ?)", 
                   (m.from_user.id, m.from_user.first_name))
    conn.commit(); conn.close()

# --- МЕНЮ (REPLY-КЛАВИАТУРА) ---
def get_main_kb(uid):
    btns = []
    if not is_approved(uid):
        btns.append([KeyboardButton(text="📝 Вступить")])
    btns.append([KeyboardButton(text="🚨 Подать жалобу"), KeyboardButton(text="📩 Оставить отзыв")])
    if is_approved(uid):
        btns.append([KeyboardButton(text="🛡 Апелляция")])
    return ReplyKeyboardMarkup(keyboard=btns, resize_keyboard=True)

@dp.message(Command("start"))
async def cmd_start(m: types.Message):
    await m.answer("Панель управления активирована.", reply_markup=get_main_kb(m.from_user.id))

# --- АДМИН КОМАНДЫ (ADD / DEL / LIST) ---

@dp.message(Command("list"))
async def cmd_list(m: types.Message):
    if m.from_user.id != ADMIN_ID: return
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute("SELECT user_id, role FROM approved_users"); rows = cursor.fetchall(); conn.close()
    if not rows:
        await m.answer("База участников пуста."); return
    res = "📂 <b>БАЗА УЧАСТНИКОВ:</b>\n\n" + "\n".join([f"ID: <code>{r[0]}</code> | Роль: {r[1]}" for r in rows])
    await m.answer(res, parse_mode="HTML")

@dp.message(Command("add"))
async def cmd_add(m: types.Message):
    if m.from_user.id != ADMIN_ID: return
    try:
        parts = m.text.split(maxsplit=2)
        uid = int(parts[1])
        role = parts[2]
        conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO approved_users (user_id, role) VALUES (?, ?)", (uid, role))
        conn.commit(); conn.close()
        # Ставим плашку в чате
        await set_member_tag(uid, role)
        await m.answer(f"✅ Пользователь <code>{uid}</code> добавлен как <b>{role}</b>", parse_mode="HTML")
    except:
        await m.answer("Используй: `/add ID РОЛЬ`", parse_mode="Markdown")

@dp.message(Command("del"))
async def cmd_delete(m: types.Message):
    if m.from_user.id != ADMIN_ID: return
    try:
        target_id = int(m.text.split()[1])
        conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
        cursor.execute("DELETE FROM approved_users WHERE user_id = ?", (target_id,))
        conn.commit(); conn.close()
        # Удаляем плашку (ставим пустой тег)
        await set_member_tag(target_id, "")
        await m.answer(f"✅ Пользователь <code>{target_id}</code> удален из базы и лишен тега.")
    except:
        await m.answer("Используй: `/del ID`", parse_mode="Markdown")

# --- РЕГИСТРАЦИЯ И ОДОБРЕНИЕ ---

@dp.message(F.text == "📝 Вступить")
async def start_reg(m: types.Message, state: FSMContext):
    if is_approved(m.from_user.id): return
    await m.answer("Укажите вашу роль в системе:"); await state.set_state(RegForm.role)

@dp.message(RegForm.role)
async def p_role(m: types.Message, state: FSMContext):
    await state.update_data(role=m.text); await m.answer("Укажите ваш юзернейм:"); await state.set_state(RegForm.username)

@dp.message(RegForm.username)
async def p_user(m: types.Message, state: FSMContext):
    data = await state.get_data()
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Принять ✅", callback_data=f"adm_ok_{m.from_user.id}")]])
    await bot.send_message(ADMIN_ID, f"<b>АНКЕТА</b>\nЮЗ: {m.text}\nID: {m.from_user.id}\nРОЛЬ: {data['role']}", reply_markup=kb, parse_mode="HTML")
    await m.answer("Ваша заявка отправлена на рассмотрение."); await state.clear()

@dp.callback_query(F.data.startswith("adm_ok_"))
async def approve_user(call: CallbackQuery):
    uid = int(call.data.split("_")[2])
    role = call.message.text.split("РОЛЬ: ")[1].split("\n")[0].strip()
    
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO approved_users (user_id, role) VALUES (?, ?)", (uid, role))
    conn.commit(); conn.close()
    
    await bot.send_message(uid, f"Вас приняли! Роль: {role}\n{CHAT_LINK}", reply_markup=get_main_kb(uid))
    await call.message.edit_text(call.message.text + "\n\n✅ ОДОБРЕНО")
    
    # ПРИМЕНЯЕМ ПЛАШКУ (Member Tag)
    await set_member_tag(uid, role)
    # СОЗЫВ
    await global_call(role)

# --- ЗАПУСК ---
async def main():
    init_db()
    Thread(target=run, daemon=True).start()
    await bot.delete_webhook(drop_pending_updates=True)
    await bot.set_my_commands([
        BotCommand(command="start", description="Обновить меню"),
        BotCommand(command="list", description="Список базы"),
        BotCommand(command="add", description="Добавить ID РОЛЬ"),
        BotCommand(command="del", description="Удалить ID")
    ])
    logging.info("Бот Harmony успешно запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
