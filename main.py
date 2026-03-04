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
                            BotCommand, CallbackQuery, ChatJoinRequest)

# --- SERVER ДЛЯ RENDER ---
app = Flask('')
@app.route('/')
def home(): return "Бот работает на новом токене!"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- CONFIG ---
TOKEN = "8344752199:AAEoFYozZQAj0Vk1EZLDUkh09jF_o9WPQwI"
ADMIN_ID = 8294726083
CHAT_ID = -1003393441169 
CHAT_LINK = "https://t.me/+yai_7_Z-7_45MDky"
DB_PATH = "database.db"

bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- СТРУКТУРА ДАННЫХ ---
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

# --- РАБОТА С БАЗОЙ ---
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""CREATE TABLE IF NOT EXISTS approved_users 
                   (user_id INTEGER PRIMARY KEY, role TEXT, username TEXT, violations INTEGER DEFAULT 0)""")
    cursor.execute("CREATE TABLE IF NOT EXISTS all_users (user_id INTEGER PRIMARY KEY, name TEXT)")
    conn.commit(); conn.close()

def get_uid_by_role(role_name):
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM approved_users WHERE LOWER(role) = LOWER(?)", (role_name,))
    res = cursor.fetchone(); conn.close()
    return res[0] if res else None

# --- МЕНЮ ---
@dp.message(Command("start"))
async def cmd_start(m: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Вступить", callback_data="reg")],
        [InlineKeyboardButton(text="🚨 Жалоба", callback_data="complaint"),
         InlineKeyboardButton(text="📩 Анонимный отзыв", callback_data="feedback")]
    ])
    await m.answer("Меню управления участниками:", reply_markup=kb)

# --- АНОНИМНЫЕ ОТЗЫВЫ ---
@dp.callback_query(F.data == "feedback")
async def start_fb(call: CallbackQuery, state: FSMContext):
    await call.message.answer("Напишите ваш анонимный отзыв:")
    await state.set_state(FeedbackForm.text); await call.answer()

@dp.message(FeedbackForm.text)
async def process_fb(m: types.Message, state: FSMContext):
    await bot.send_message(ADMIN_ID, f"<b>📥 АНОНИМНЫЙ ОТЗЫВ</b>\n\n{m.text}", parse_mode="HTML")
    await m.answer("Отправлено анонимно."); await state.clear()

# --- РЕГИСТРАЦИЯ ---
@dp.callback_query(F.data == "reg")
async def start_reg(call: CallbackQuery, state: FSMContext):
    await call.message.answer("Укажите вашу роль:")
    await state.set_state(RegForm.role); await call.answer()

@dp.message(RegForm.role)
async def p_role(m: types.Message, state: FSMContext):
    await state.update_data(role=m.text)
    await m.answer("Укажите ваш юз:")
    await state.set_state(RegForm.username)

@dp.message(RegForm.username)
async def p_user(m: types.Message, state: FSMContext):
    data = await state.get_data(); uid = m.from_user.id
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Принять ✅", callback_data=f"adm_ok_{uid}"), 
         InlineKeyboardButton(text="Отклонить ❌", callback_data=f"adm_no_{uid}")]
    ])
    await bot.send_message(ADMIN_ID, f"<b>АНКЕТА</b>\nЮЗ: {m.text}\nID: {uid}\nРОЛЬ: {data['role']}", reply_markup=kb, parse_mode="HTML")
    await m.answer("Заявка отправлена."); await state.clear()

# --- ЖАЛОБЫ ---
@dp.callback_query(F.data == "complaint")
async def start_comp(call: CallbackQuery, state: FSMContext):
    await call.message.answer("Назовите ВАШУ роль:")
    await state.set_state(ComplaintForm.my_role); await call.answer()

@dp.message(ComplaintForm.my_role)
async def comp_my_role(m: types.Message, state: FSMContext):
    if not get_uid_by_role(m.text):
        await m.answer("Такой роли не существует. Проверьте правильность:"); return
    await state.update_data(my_role=m.text)
    await m.answer("Суть жалобы:")
    await state.set_state(ComplaintForm.text)

@dp.message(ComplaintForm.text)
async def comp_text(m: types.Message, state: FSMContext):
    await state.update_data(text=m.text)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Отправить без файлов ➡️", callback_data="skip_file")]])
    await m.answer("Прикрепите доказательства или нажмите кнопку:", reply_markup=kb)
    await state.set_state(ComplaintForm.evidence)

@dp.callback_query(F.data == "skip_file", ComplaintForm.evidence)
@dp.message(ComplaintForm.evidence)
async def comp_target_role(msg: types.Message | CallbackQuery, state: FSMContext):
    if isinstance(msg, types.Message):
        file_id = msg.photo[-1].file_id if msg.photo else (msg.document.file_id if msg.document else None)
        await state.update_data(file=file_id)
        await msg.answer("Укажите роль НАРУШИТЕЛЯ:")
    else:
        await msg.message.answer("Укажите роль НАРУШИТЕЛЯ:")
        await msg.answer()
    await state.set_state(ComplaintForm.target_role)

@dp.message(ComplaintForm.target_role)
async def comp_final(m: types.Message, state: FSMContext):
    target_uid = get_uid_by_role(m.text)
    if not target_uid:
        await m.answer("Роль нарушителя не найдена. Попробуйте снова:"); return
    
    data = await state.get_data()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Одобрить ✅", callback_data=f"warn_ok_{target_uid}"),
         InlineKeyboardButton(text="Отклонить ❌", callback_data=f"warn_no")]
    ])
    cap = f"<b>🚨 ЖАЛОБА</b>\nОт: {data['my_role']}\nНа: {m.text}\nСуть: {data['text']}"
    if data.get('file'): await bot.send_photo(ADMIN_ID, data['file'], caption=cap, reply_markup=kb, parse_mode="HTML")
    else: await bot.send_message(ADMIN_ID, cap, reply_markup=kb, parse_mode="HTML")
    await m.answer("Жалоба ушла админу."); await state.clear()

# --- ОБРАБОТКА ВАРНОВ ---
@dp.callback_query(F.data.startswith("warn_"))
async def handle_warn(call: CallbackQuery):
    if "no" in call.data:
        await call.message.edit_text(call.message.text + "\n\n❌ Отклонено"); return
    
    target_uid = int(call.data.split("_")[2])
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute("UPDATE approved_users SET violations = violations + 1 WHERE user_id = ?", (target_uid,))
    cursor.execute("SELECT violations FROM approved_users WHERE user_id = ?", (target_uid,))
    v_count = cursor.fetchone()[0]
    
    if v_count >= 3:
        try: await bot.ban_chat_member(CHAT_ID, target_uid)
        except: pass
        cursor.execute("DELETE FROM approved_users WHERE user_id = ?", (target_uid,))
        await bot.send_message(target_uid, "Вы удалены за 3/3 нарушений.")
        await call.message.edit_text(call.message.text + "\n\n🔥 БАН (3/3)")
    else:
        await bot.send_message(target_uid, f"За вами замечено {v_count}/3 нарушений. Будьте внимательнее.")
        await call.message.edit_text(call.message.text + f"\n\n✅ Варн {v_count}/3")
    conn.commit(); conn.close()

# --- КНОПКИ ПРИНЯТИЯ В ЧАТ ---
@dp.callback_query(F.data.startswith("adm_"))
async def admin_reg_confirm(call: CallbackQuery):
    action, uid = call.data.split("_")[1], int(call.data.split("_")[2])
    if action == "ok":
        # Роль берем из текста сообщения
        role = call.message.text.split("РОЛЬ: ")[1]
        conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO approved_users (user_id, role) VALUES (?, ?)", (uid, role))
        conn.commit(); conn.close()
        await bot.send_message(uid, f"Вы приняты! Роль: {role}\nВступайте: {CHAT_LINK}")
        await call.message.edit_text(call.message.text + "\n\n✅ ОДОБРЕНО")
    else:
        await bot.send_message(uid, "Заявка отклонена.")
        await call.message.edit_text(call.message.text + "\n\n❌ ОТКЛОНЕНО")

# --- АВТО-ПРИНЯТИЕ И ПЛАШКА (Member Tag) ---
@dp.chat_join_request()
async def auto_approve_logic(req: ChatJoinRequest):
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute("SELECT role FROM approved_users WHERE user_id = ?", (req.from_user.id,))
    res = cursor.fetchone(); conn.close()
    if res:
        await req.approve()
        await asyncio.sleep(1)
        try:
            # Новый метод Telegram для установки плашки участнику (БЕЗ админки)
            await bot.make_request("setChatMemberTag", {"chat_id": CHAT_ID, "user_id": req.from_user.id, "tag": res[0]})
        except Exception as e:
            logging.error(f"Ошибка тега: {e}")

# --- ЗАПУСК ---
async def main():
    init_db()
    Thread(target=run, daemon=True).start()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot, allowed_updates=["message", "callback_query", "chat_join_request"])

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
