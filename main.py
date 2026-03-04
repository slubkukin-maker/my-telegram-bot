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
                            InputMediaPhoto, InputMediaDocument, ReplyKeyboardRemove, BotCommand, ChatMemberUpdated)

# --- SERVER FOR RENDER ---
app = Flask('')
@app.route('/')
def home(): return "Harmony Bot Active"
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
    check_my_role = State()
    report_target_role = State()
    report_text = State()
    report_files = State()
    admin_reply = State()

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS approved_users (user_id INTEGER PRIMARY KEY, role TEXT, warns INTEGER DEFAULT 0)")
    cursor.execute("CREATE TABLE IF NOT EXISTS all_users (user_id INTEGER PRIMARY KEY, name TEXT)")
    conn.commit(); conn.close()

# --- КЛАВИАТУРЫ ---
def get_main_reply_kb(user_id):
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM approved_users WHERE user_id = ?", (user_id,))
    is_joined = cursor.fetchone(); conn.close()
    kb = []
    if not is_joined: kb.append([KeyboardButton(text="📝 Вступить")])
    kb.append([KeyboardButton(text="⚖️ Апелляция"), KeyboardButton(text="🚫 Жалоба")])
    kb.append([KeyboardButton(text="⭐ Отзыв")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

# --- КОМАНДЫ АДМИНА ---

@dp.message(Command("all"))
async def cmd_all(m: types.Message):
    if m.from_user.id != ADMIN_ID: return
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute("SELECT user_id, name FROM all_users"); rows = cursor.fetchall(); conn.close()
    if not rows: await m.answer("База пуста."); return
    mentions = [f"<a href='tg://user?id={r[0]}'>{r[1]}</a>" for r in rows]
    for i in range(0, len(mentions), 5): # По 5 человек в сообщении
        await m.answer(f"📣 <b>ОБЩИЙ СБОР:</b>\n{', '.join(mentions[i:i+5])}", parse_mode="HTML")

@dp.message(Command("add"))
async def cmd_add(m: types.Message):
    if m.from_user.id != ADMIN_ID: return
    try:
        p = m.text.split(maxsplit=2)
        uid, role = int(p[1]), p[2]
        conn = sqlite3.connect(DB_PATH); cur = conn.cursor()
        cur.execute("INSERT OR REPLACE INTO approved_users (user_id, role, warns) VALUES (?, ?, 0)", (uid, role))
        cur.execute("INSERT OR REPLACE INTO all_users (user_id, name) VALUES (?, ?)", (uid, role))
        conn.commit(); conn.close()
        await m.answer(f"✅ Добавлен вручную: {uid} как {role}")
    except: await m.answer("Пример: /add 12345678 Ризли")

@dp.message(Command("list"))
async def cmd_list(m: types.Message):
    if m.from_user.id != ADMIN_ID: return
    conn = sqlite3.connect(DB_PATH); cur = conn.cursor()
    cur.execute("SELECT user_id, role, warns FROM approved_users"); rows = cur.fetchall(); conn.close()
    if not rows: await m.answer("Пусто."); return
    res = "📋 <b>БАЗА УЧАСТНИКОВ (ТЕГИ):</b>\n" + "\n".join([f"<code>{r[0]}</code> | {r[1]} | {r[2]}/3" for r in rows])
    await m.answer(res, parse_mode="HTML")

# --- ЛОГИКА АВТО-ОБРАБОТКИ ---

# Следим за выходом из чата
@dp.chat_member()
async def on_chat_member_update(update: ChatMemberUpdated):
    if update.chat.id == CHAT_ID:
        if update.new_chat_member.status in ["left", "kicked"]:
            uid = update.old_chat_member.user.id
            conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
            cursor.execute("DELETE FROM all_users WHERE user_id = ?", (uid,))
            cursor.execute("DELETE FROM approved_users WHERE user_id = ?", (uid,))
            conn.commit(); conn.close()

# Захват имен в чате (для /all)
@dp.message(F.chat.id == CHAT_ID)
async def collect_msg(m: types.Message):
    if m.from_user.is_bot: return
    name = f"@{m.from_user.username}" if m.from_user.username else m.from_user.first_name
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO all_users (user_id, name) VALUES (?, ?)", (m.from_user.id, name))
    conn.commit(); conn.close()

# --- СТАНДАРТНАЯ ЛОГИКА (ВСТУПЛЕНИЕ / ЖАЛОБЫ) ---

@dp.message(Command("start"))
async def cmd_start(m: types.Message):
    await m.answer("👋 Привет! Используй меню:", reply_markup=get_main_reply_kb(m.from_user.id))

@dp.message(F.text == "📝 Вступить")
async def btn_reg(m: types.Message, state: FSMContext):
    await m.answer("Твоя роль (для тега):", reply_markup=ReplyKeyboardRemove())
    await state.set_state(Form.role)

@dp.message(Form.role)
async def p_role(m: types.Message, state: FSMContext):
    await state.update_data(role=m.text); await m.answer("Твой юз:"); await state.set_state(Form.user)

@dp.message(Form.user)
async def p_user(m: types.Message, state: FSMContext):
    data = await state.get_data(); role = data.get('role'); uid = m.from_user.id
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Принять", callback_data=f"adm_ok_{uid}_{role[:15]}"), 
         InlineKeyboardButton(text="Отклонить", callback_data=f"adm_no_{uid}")]
    ])
    await bot.send_message(ADMIN_ID, f"🆕 <b>АНКЕТА</b>\nЮз: {m.text}\nID: {uid}\nРоль: {role}", reply_markup=kb, parse_mode="HTML")
    await m.answer("Отправлено!", reply_markup=get_main_reply_kb(uid)); await state.clear()

@dp.callback_query(F.data.startswith("adm_ok_"))
async def adm_approve(call: CallbackQuery):
    p = call.data.split("_"); uid, role = int(p[2]), p[3]
    conn = sqlite3.connect(DB_PATH); cur = conn.cursor()
    cur.execute("INSERT OR REPLACE INTO approved_users (user_id, role, warns) VALUES (?, ?, 0)", (uid, role))
    cur.execute("INSERT OR REPLACE INTO all_users (user_id, name) VALUES (?, ?)", (uid, role))
    conn.commit(); conn.close()
    try: await bot.send_message(uid, f"Принято! Твой тег: {role}\n{CHAT_LINK}")
    except: pass
    await call.message.edit_text(call.message.text + "\n✅ ПРИНЯТ")

# --- ОСТАЛЬНЫЕ ФУНКЦИИ (Жалобы, Апелляции и т.д. - аналогично прошлому коду) ---

# [Здесь можно добавить блоки жалоб из прошлого сообщения, если нужно]

async def main():
    init_db(); Thread(target=run, daemon=True).start()
    await bot.set_my_commands([
        BotCommand(command="start", description="Меню"),
        BotCommand(command="all", description="Вызвать всех"),
        BotCommand(command="list", description="Список тегов"),
        BotCommand(command="add", description="Добавить юзера")
    ])
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot, allowed_updates=["message", "callback_query", "chat_member"])

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO); asyncio.run(main())
