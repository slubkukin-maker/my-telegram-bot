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
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, BotCommand, CallbackQuery

# --- SERVER FOR RENDER ---
app = Flask('')
@app.route('/')
def home(): return "Bot Harmony is Live"

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
    admin_reply = State()
    report_text = State()

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # Таблица только для тех, кто реально зарегистрирован (одобрен или добавлен)
    cursor.execute("CREATE TABLE IF NOT EXISTS approved_users (user_id INTEGER PRIMARY KEY, role TEXT)")
    conn.commit()
    conn.close()

# --- АДМИН КОМАНДЫ ---

@dp.message(Command("list"))
async def cmd_list(m: types.Message):
    if m.from_user.id != ADMIN_ID: return
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute("SELECT user_id, role FROM approved_users")
    rows = cursor.fetchall(); conn.close()
    
    if not rows:
        await m.answer("📋 <b>База пуста.</b> Пока никто не зарегистрирован.", parse_mode="HTML")
        return
        
    text = "📋 <b>СПИСОК ЗАРЕГИСТРИРОВАННЫХ:</b>\n\n"
    for r in rows:
        text += f"👤 ID: <code>{r[0]}</code> | Роль: <b>{r[1]}</b>\n"
    await m.answer(text, parse_mode="HTML")

@dp.message(Command("add"))
async def cmd_add(m: types.Message):
    if m.from_user.id != ADMIN_ID: return
    try:
        parts = m.text.split(maxsplit=2)
        target_id = int(parts[1])
        role = parts[2]
        conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO approved_users (user_id, role) VALUES (?, ?)", (target_id, role))
        conn.commit(); conn.close()
        await m.answer(f"✅ Юзер <code>{target_id}</code> успешно внесен в базу как <b>{role}</b>", parse_mode="HTML")
    except:
        await m.answer("Пример: <code>/add 12345678 Админ</code>", parse_mode="HTML")

@dp.message(Command("del"))
async def cmd_delete(m: types.Message):
    if m.from_user.id != ADMIN_ID: return
    try:
        target_id = int(m.text.split()[1])
        conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
        cursor.execute("DELETE FROM approved_users WHERE user_id = ?", (target_id,))
        conn.commit(); conn.close()
        await m.answer(f"🗑 Юзер <code>{target_id}</code> удален из базы.", parse_mode="HTML")
    except:
        await m.answer("Пример: <code>/del 12345678</code>", parse_mode="HTML")

# --- ГЛАВНОЕ МЕНЮ И АНКЕТА ---

@dp.message(Command("start"))
async def cmd_start(m: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Вступить", callback_data="start_reg")],
        [InlineKeyboardButton(text="⚖️ Апелляция", callback_data="type_апелляция"),
         InlineKeyboardButton(text="🚫 Жалоба", callback_data="type_жалоба")],
        [InlineKeyboardButton(text="⭐ Отзыв", callback_data="type_отзыв")]
    ])
    await m.answer("Привет! Выбери нужный раздел:", reply_markup=kb)

@dp.callback_query(F.data == "start_reg")
async def start_reg(call: CallbackQuery, state: FSMContext):
    await call.message.answer("Твоя роль (например: Участник):"); await state.set_state(Form.role); await call.answer()

@dp.message(Form.role)
async def p_role(m: types.Message, state: FSMContext):
    await state.update_data(role=m.text); await m.answer("Твой ник:"); await state.set_state(Form.user)

@dp.message(Form.user)
async def p_user(m: types.Message, state: FSMContext):
    data = await state.get_data(); role = data.get('role'); uid = m.from_user.id
    nick = m.text
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Принять", callback_data=f"adm_ok_{uid}_{nick}"), 
         InlineKeyboardButton(text="Отклонить", callback_data=f"adm_no_{uid}")]
    ])
    await bot.send_message(ADMIN_ID, f"🆕 <b>АНКЕТА</b>\nНик: {nick}\nID: {uid}\nРоль: {role}", reply_markup=kb, parse_mode="HTML")
    await m.answer("Анкета отправлена!"); await state.clear()

@dp.callback_query(F.data.startswith("adm_"))
async def admin_btns(call: CallbackQuery):
    data = call.data.split("_")
    action = data[1]
    target_uid = int(data[2])
    
    if action == "ok":
        # Вытаскиваем ник, если он был передан в callback (чтобы в листе было красиво)
        nick = data[3] if len(data) > 3 else "Member"
        conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO approved_users (user_id, role) VALUES (?, ?)", (target_uid, nick))
        conn.commit(); conn.close()
        
        try:
            await bot.send_message(target_uid, f"Твоя анкета одобрена! ✨\nСсылка: {CHAT_LINK}")
        except: pass
        await call.message.edit_text(call.message.text + f"\n\n✅ ПРИНЯТ ({nick})")
        
    elif action == "no":
        try:
            await bot.send_message(target_uid, "К сожалению, твоя анкета отклонена.")
        except: pass
        await call.message.edit_text(call.message.text + "\n\n❌ ОТКЛОНЕН")
    await call.answer()

# --- ЖАЛОБЫ И ПРОЧЕЕ ---
@dp.callback_query(F.data.startswith("type_"))
async def process_report(call: CallbackQuery, state: FSMContext):
    r_type = call.data.split("_")[1]
    await state.update_data(current_report_type=r_type)
    await call.message.answer(f"Напиши текст для: <b>{r_type.upper()}</b>", parse_mode="HTML")
    await state.set_state(Form.report_text)
    await call.answer()

@dp.message(Form.report_text)
async def send_report(m: types.Message, state: FSMContext):
    data = await state.get_data()
    r_type = data.get("current_report_type", "Сообщение")
    await bot.send_message(ADMIN_ID, f"📩 <b>{r_type.upper()}</b>\nОт: {m.from_user.full_name}\nID: {m.from_user.id}\n\nТекст: {m.text}", parse_mode="HTML")
    await m.answer("Отправлено администратору!"); await state.clear()

async def main():
    init_db()
    Thread(target=run, daemon=True).start()
    await bot.set_my_commands([
        BotCommand(command="start", description="Меню"),
        BotCommand(command="list", description="Список зареганых"),
        BotCommand(command="add", description="Добавить в базу"),
        BotCommand(command="del", description="Удалить из базы")
    ])
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
