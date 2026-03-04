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
                            BotCommand, CallbackQuery, ChatJoinRequest, ContentType)

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

# --- STATES ---
class RegForm(StatesGroup):
    role = State()
    username = State()

class ComplaintForm(StatesGroup):
    my_role = State()
    text = State()
    evidence = State()
    target_role = State()

class AppealForm(StatesGroup):
    my_role = State()
    text = State()
    evidence = State()

class AdminStates(StatesGroup):
    reply = State()

# --- DATABASE ---
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # Таблица одобренных (с тегами и варнами)
    cursor.execute("""CREATE TABLE IF NOT EXISTS approved_users 
                   (user_id INTEGER PRIMARY KEY, role TEXT, username TEXT, violations INTEGER DEFAULT 0)""")
    # Таблица всех для рассылки /all
    cursor.execute("CREATE TABLE IF NOT EXISTS all_users (user_id INTEGER PRIMARY KEY, name TEXT)")
    conn.commit()
    conn.close()

# --- ХЕЛПЕРЫ ---
def check_role_exists(role_name):
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM approved_users WHERE LOWER(role) = LOWER(?)", (role_name,))
    res = cursor.fetchone()
    conn.close()
    return res[0] if res else None

# --- АВТО-ПРИНЯТИЕ И НОВЫЕ ТЕГИ (API 12.5) ---
@dp.chat_join_request()
async def auto_approve(request: ChatJoinRequest):
    uid = request.from_user.id
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute("SELECT role FROM approved_users WHERE user_id = ?", (uid,))
    res = cursor.fetchone(); conn.close()
    
    if res:
        role = res[0]
        await request.approve()
        await asyncio.sleep(1)
        try:
            # Использование нового метода Bot API для тегов участников (без админки)
            # В aiogram 3.x это может быть bot.set_chat_member_tag
            await bot.make_request("setChatMemberTag", {
                "chat_id": CHAT_ID,
                "user_id": uid,
                "tag": role
            })
        except Exception as e:
            logging.error(f"Tag error: {e}")

# --- РЕГИСТРАЦИЯ ---
@dp.message(Command("start"))
async def cmd_start(m: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Вступить", callback_data="reg")],
        [InlineKeyboardButton(text="🚨 Жалоба", callback_data="complaint"),
         InlineKeyboardButton(text="🛡 Апелляция", callback_data="appeal")]
    ])
    await m.answer(f"Привет! Твой ID: <code>{m.from_user.id}</code>\nВыбери действие:", reply_markup=kb, parse_mode="HTML")

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
    data = await state.get_data(); role = data.get('role'); uid = m.from_user.id
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Принять ✅", callback_data=f"adm_ok_{uid}"), 
         InlineKeyboardButton(text="Отклонить ❌", callback_data=f"adm_no_{uid}")]
    ])
    await bot.send_message(ADMIN_ID, f"<b>НОВАЯ АНКЕТА</b>\nЮЗ: {m.text}\nID: <code>{uid}</code>\nРОЛЬ: {role}", reply_markup=kb, parse_mode="HTML")
    await m.answer("Заявка отправлена."); await state.clear()

# --- СИСТЕМА ЖАЛОБ ---
@dp.callback_query(F.data == "complaint")
async def start_complaint(call: CallbackQuery, state: FSMContext):
    await call.message.answer("Назовите ВАШУ роль:")
    await state.set_state(ComplaintForm.my_role); await call.answer()

@dp.message(ComplaintForm.my_role)
async def comp_my_role(m: types.Message, state: FSMContext):
    if not check_role_exists(m.text):
        await m.answer("Такой роли нет. Проверьте правильность написания и попробуйте снова:")
        return
    await state.update_data(my_role=m.text)
    await m.answer("Опишите суть жалобы:")
    await state.set_state(ComplaintForm.text)

@dp.message(ComplaintForm.text)
async def comp_text(m: types.Message, state: FSMContext):
    await state.update_data(text=m.text)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Отправить без файлов ➡️", callback_data="no_files")]])
    await m.answer("Прикрепите доказательства (скриншот/файл) или нажмите кнопку ниже:", reply_markup=kb)
    await state.set_state(ComplaintForm.evidence)

@dp.callback_query(F.data == "no_files", ComplaintForm.evidence)
async def comp_no_files(call: CallbackQuery, state: FSMContext):
    await call.message.answer("Укажите роль того, на кого идет жалоба:")
    await state.set_state(ComplaintForm.target_role); await call.answer()

@dp.message(ComplaintForm.evidence)
async def comp_files(m: types.Message, state: FSMContext):
    file_id = m.photo[-1].file_id if m.photo else (m.document.file_id if m.document else None)
    await state.update_data(file=file_id)
    await m.answer("Укажите роль того, на кого идет жалоба:")
    await state.set_state(ComplaintForm.target_role)

@dp.message(ComplaintForm.target_role)
async def comp_target(m: types.Message, state: FSMContext):
    target_uid = check_role_exists(m.text)
    if not target_uid:
        await m.answer("Роль нарушителя не найдена. Проверьте еще раз:")
        return
    
    data = await state.get_data()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Одобрить (Варн) ✅", callback_data=f"comp_ok_{target_uid}"),
         InlineKeyboardButton(text="Отклонить ❌", callback_data=f"comp_no_{target_uid}")]
    ])
    
    msg = f"<b>🚨 ЖАЛОБА</b>\nОт: {data['my_role']}\nНа: {m.text} (ID: {target_uid})\nСуть: {data['text']}"
    if data.get('file'):
        await bot.send_photo(ADMIN_ID, data['file'], caption=msg, reply_markup=kb, parse_mode="HTML")
    else:
        await bot.send_message(ADMIN_ID, msg, reply_markup=kb, parse_mode="HTML")
    
    await m.answer("Жалоба отправлена на рассмотрение."); await state.clear()

# --- ОБРАБОТКА ЖАЛОБ АДМИНОМ ---
@dp.callback_query(F.data.startswith("comp_"))
async def handle_complaint_admin(call: CallbackQuery):
    action, target_uid = call.data.split("_")[1], int(call.data.split("_")[2])
    
    if action == "ok":
        conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
        cursor.execute("UPDATE approved_users SET violations = violations + 1 WHERE user_id = ?", (target_uid,))
        cursor.execute("SELECT violations, role FROM approved_users WHERE user_id = ?", (target_uid,))
        res = cursor.fetchone()
        
        if res:
            v_count, role = res
            if v_count >= 3:
                # КИК ИЗ ЧАТА И БАЗЫ
                await bot.ban_chat_member(CHAT_ID, target_uid)
                cursor.execute("DELETE FROM approved_users WHERE user_id = ?", (target_uid,))
                cursor.execute("DELETE FROM all_users WHERE user_id = ?", (target_uid,))
                await bot.send_message(target_uid, "Вы были удалены из чата за достижение 3/3 нарушений.")
                await call.message.edit_text(call.message.text + f"\n\n🔥 ИГРОК ЗАБАНЕН (3/3)")
            else:
                await bot.send_message(target_uid, f"⚠️ За вами замечено {v_count}/3 нарушений, будьте внимательнее.")
                await call.message.edit_text(call.message.text + f"\n\n✅ ВАРН ВЫДАН ({v_count}/3)")
        conn.commit(); conn.close()
    else:
        await call.message.edit_text(call.message.text + "\n\n❌ ЖАЛОБА ОТКЛОНЕНА")
    await call.answer()

# --- АППЕЛЯЦИИ ---
@dp.callback_query(F.data == "appeal")
async def start_appeal(call: CallbackQuery, state: FSMContext):
    await call.message.answer("Назовите вашу роль:")
    await state.set_state(AppealForm.my_role); await call.answer()

@dp.message(AppealForm.my_role)
async def appeal_role(m: types.Message, state: FSMContext):
    if not check_role_exists(m.text):
        await m.answer("Роль не найдена."); return
    await state.update_data(my_role=m.text)
    await m.answer("Текст апелляции:")
    await state.set_state(AppealForm.text)

@dp.message(AppealForm.text)
async def appeal_sent(m: types.Message, state: FSMContext):
    data = await state.get_data()
    await bot.send_message(ADMIN_ID, f"<b>🛡 АПЕЛЛЯЦИЯ</b>\nОт: {data['my_role']}\nТекст: {m.text}\nID: {m.from_user.id}", parse_mode="HTML")
    await m.answer("Апелляция отправлена."); await state.clear()

# --- СТАРЫЕ ФУНКЦИИ (ВОЗВРАЩЕНЫ) ---

@dp.message(Command("list"))
async def cmd_list(m: types.Message):
    if m.from_user.id != ADMIN_ID: return
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute("SELECT user_id, role, violations FROM approved_users"); rows = cursor.fetchall(); conn.close()
    if not rows: await m.answer("База пуста."); return
    text = "📂 <b>СПИСОК (ID | РОЛЬ | ВАРНЫ):</b>\n"
    for r in rows: text += f"<code>{r[0]}</code> | {r[1]} | [{r[2]}/3]\n"
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

# --- ЗАПУСК ---
async def main():
    init_db()
    Thread(target=run, daemon=True).start()
    await bot.set_my_commands([
        BotCommand(command="start", description="Меню"),
        BotCommand(command="all", description="Сбор"),
        BotCommand(command="list", description="Список базы")
    ])
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot, allowed_updates=["message", "callback_query", "chat_join_request"])

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
