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
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, BotCommand, CallbackQuery, ChatMemberUpdated

# --- SERVER ---
app = Flask('')
@app.route('/')
def home(): return "Bot is Online"

def run():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run, daemon=True)
    t.start()

# --- CONFIG ---
TOKEN = "8344752199:AAEM_QXGdVx5t8XkQCMWQlCKubhwBaeMvTo"
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
    report_text = State() # Для жалоб/отзывов

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS approved_users (user_id INTEGER PRIMARY KEY, role TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS all_users (user_id INTEGER PRIMARY KEY, name TEXT)")
    conn.commit()
    conn.close()

# --- КНОПКИ ГЛАВНОГО МЕНЮ ---
def main_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Вступить (Анкета)", callback_data="start_reg")],
        [InlineKeyboardButton(text="🚫 Жалоба", callback_data="type_жалоба"),
         InlineKeyboardButton(text="⚖️ Апелляция", callback_data="type_апелляция")],
        [InlineKeyboardButton(text="⭐ Отзыв", callback_data="type_отзыв")]
    ])

# --- COMMANDS ---

@dp.message(Command("start"))
async def cmd_start(m: types.Message):
    await m.answer(f"Привет! Твой ID: <code>{m.from_user.id}</code>\nВыбери действие:", 
                   reply_markup=main_kb(), parse_mode="HTML")

@dp.message(Command("check"))
async def cmd_check(m: types.Message):
    if m.from_user.id != ADMIN_ID: return
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM approved_users"); approved = [r[0] for r in cursor.fetchall()]
    cursor.execute("SELECT user_id, name FROM all_users"); all_u = cursor.fetchall(); conn.close()
    bad = [f"<code>{u[0]}</code> | {u[1]}" for u in all_u if u[0] not in approved]
    if not bad: await m.answer("Все подтверждены! ✅")
    else: await m.answer("<b>БЕЗ РОЛИ:</b>\n\n" + "\n".join(bad), parse_mode="HTML")

# --- ЛОГИКА ЖАЛОБ / ОТЗЫВОВ ---

@dp.callback_query(F.data.startswith("type_"))
async def process_report_type(call: CallbackQuery, state: FSMContext):
    report_type = call.data.split("_")[1]
    await state.update_data(current_report_type=report_type)
    await call.message.answer(f"Напиши текст для: <b>{report_type.upper()}</b>", parse_mode="HTML")
    await state.set_state(Form.report_text)
    await call.answer()

@dp.message(Form.report_text)
async def send_report_to_admin(m: types.Message, state: FSMContext):
    data = await state.get_data()
    r_type = data.get("current_report_type", "Сообщение")
    uid = m.from_user.id
    username = m.from_user.username or m.from_user.first_name

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Ответить", callback_data=f"adm_msg_{uid}")]
    ])
    
    await bot.send_message(ADMIN_ID, f"📩 <b>НОВАЯ {r_type.upper()}</b>\nОт: @{username} (ID: {uid})\n\nТекст: {m.text}", 
                           reply_markup=kb, parse_mode="HTML")
    await m.answer("Спасибо! Твое сообщение отправлено администрации.")
    await state.clear()

# --- АНКЕТА ---

@dp.callback_query(F.data == "start_reg")
async def start_reg(call: CallbackQuery, state: FSMContext):
    await call.message.answer("Укажите твою роль (например: Владелец, Участник):")
    await state.set_state(Form.role); await call.answer()

@dp.message(Form.role)
async def p_role(m: types.Message, state: FSMContext):
    await state.update_data(role=m.text); await m.answer("Твой ник в игре/чате:"); await state.set_state(Form.user)

@dp.message(Form.user)
async def p_user(m: types.Message, state: FSMContext):
    data = await state.get_data(); role = data.get('role'); uid = m.from_user.id
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Принять", callback_data=f"adm_ok_{uid}"), 
         InlineKeyboardButton(text="Отклонить", callback_data=f"adm_no_{uid}")],
        [InlineKeyboardButton(text="Написать", callback_data=f"adm_msg_{uid}")]
    ])
    await bot.send_message(ADMIN_ID, f"🆕 <b>АНКЕТА</b>\nЮзер: {m.text}\nID: {uid}\nРоль: {role}", reply_markup=kb, parse_mode="HTML")
    await m.answer("Заявка отправлена. Ожидай решения!"); await state.clear()

@dp.callback_query(F.data.startswith("adm_"))
async def admin_btns(call: CallbackQuery, state: FSMContext):
    action = call.data.split("_")[1]; target_uid = int(call.data.split("_")[2])
    if action == "ok":
        role = "Member"
        if "Роль: " in call.message.text: role = call.message.text.split("Роль: ")[1].split("\n")[0]
        conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO approved_users (user_id, role) VALUES (?, ?)", (target_uid, role))
        cursor.execute("INSERT OR REPLACE INTO all_users (user_id, name) VALUES (?, ?)", (target_uid, role))
        conn.commit(); conn.close()
        await bot.send_message(target_uid, f"Твоя анкета одобрена! ✨\nРоль: {role}\nВступай: {CHAT_LINK}")
        await call.message.edit_text(call.message.text + "\n\n✅ СТАТУС: ПРИНЯТ")
    elif action == "no":
        await bot.send_message(target_uid, "К сожалению, твоя анкета отклонена.")
        await call.message.edit_text(call.message.text + "\n\n❌ СТАТУС: ОТКЛОНЕН")
    elif action == "msg":
        await call.message.answer(f"Напиши ответ для пользователя {target_uid}:")
        await state.update_data(target_to_msg=target_uid); await state.set_state(Form.admin_reply)
    await call.answer()

@dp.message(Form.admin_reply)
async def admin_reply_send(m: types.Message, state: FSMContext):
    data = await state.get_data(); target = data.get('target_to_msg')
    try:
        await bot.send_message(target, f"<b>Сообщение от администрации:</b>\n\n{m.text}", parse_mode="HTML")
        await m.answer("Ответ отправлен!")
    except: await m.answer("Не удалось отправить (возможно, бот заблокирован).")
    await state.clear()

# --- СБОР И ДРУГОЕ ---

@dp.message(Command("list"))
async def cmd_list(m: types.Message):
    if m.from_user.id != ADMIN_ID: return
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute("SELECT user_id, name FROM all_users"); rows = cursor.fetchall(); conn.close()
    if not rows: await m.answer("База пуста."); return
    text = "📊 СПИСОК ЮЗЕРОВ:\n" + "\n".join([f"<code>{r[0]}</code> | {r[1]}" for r in rows])
    await m.answer(text, parse_mode="HTML")

@dp.message(F.chat.id == CHAT_ID, ~F.text.startswith("/"))
async def collect_msg(m: types.Message):
    if m.from_user.is_bot: return
    name = m.from_user.full_name
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO all_users (user_id, name) VALUES (?, ?)", (m.from_user.id, name))
    conn.commit(); conn.close()

async def main():
    init_db(); keep_alive()
    await bot.set_my_commands([
        BotCommand(command="start", description="Главное меню"),
        BotCommand(command="check", description="Проверка ролей"),
        BotCommand(command="list", description="Вся база")
    ])
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
