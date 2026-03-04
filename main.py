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
def home(): return "Бот в строю!"

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
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""CREATE TABLE IF NOT EXISTS approved_users 
                   (user_id INTEGER PRIMARY KEY, role TEXT, username TEXT, violations INTEGER DEFAULT 0)""")
    cursor.execute("CREATE TABLE IF NOT EXISTS all_users (user_id INTEGER PRIMARY KEY, name TEXT)")
    conn.commit(); conn.close()

def is_user_approved(uid):
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM approved_users WHERE user_id = ?", (uid,))
    res = cursor.fetchone(); conn.close()
    return True if res else False

def get_uid_by_role(role_name):
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM approved_users WHERE LOWER(role) = LOWER(?)", (role_name,))
    res = cursor.fetchone(); conn.close()
    return res[0] if res else None

# --- КЛАВИАТУРА ---
def get_main_reply_kb(uid):
    buttons = []
    if not is_user_approved(uid):
        buttons.append([KeyboardButton(text="📝 Вступить")])
    buttons.append([KeyboardButton(text="🚨 Подать жалобу"), KeyboardButton(text="📩 Оставить отзыв")])
    if is_user_approved(uid):
        buttons.append([KeyboardButton(text="🛡 Апелляция")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

# --- ЛОГИКА СОЗЫВА ---
async def global_call(new_user_role):
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute("SELECT user_id, name FROM all_users"); rows = cursor.fetchall(); conn.close()
    
    # Считаем реальных людей в чате через API
    try:
        total_in_chat = await bot.get_chat_member_count(CHAT_ID)
        total_humans = total_in_chat - 1 # Вычитаем самого бота
    except:
        total_humans = len(rows)

    mentions = [f"<a href='tg://user?id={r[0]}'>\u2063</a>" for r in rows] # Скрытые теги, чтобы не спамить именами
    called_count = len(mentions)
    
    text = (f"📣 <b>СОЗЫВ: новый участник</b>\n"
            f"Роль: <b>{new_user_role}</b>\n\n"
            f"👥 Созвано: <b>{called_count}/{total_humans}</b>")
    
    # Отправляем по 5 тегов в сообщении, чтобы не словить лимит
    for i in range(0, len(mentions), 5):
        chunk = "".join(mentions[i:i+5])
        await bot.send_message(CHAT_ID, f"{text}{chunk}", parse_mode="HTML")

# --- ОБРАБОТЧИКИ ---

@dp.message(Command("start"))
async def cmd_start(m: types.Message):
    await m.answer("Панель управления активирована.", reply_markup=get_main_reply_kb(m.from_user.id))

@dp.message(F.text == "📝 Вступить")
async def btn_reg(m: types.Message, state: FSMContext):
    if is_user_approved(m.from_user.id): return
    await m.answer("Укажите вашу роль:"); await state.set_state(RegForm.role)

@dp.message(F.text == "🚨 Подать жалобу")
async def btn_complaint(m: types.Message, state: FSMContext):
    await m.answer("Назовите ВАШУ роль в системе:"); await state.set_state(ComplaintForm.my_role)

@dp.message(F.text == "📩 Оставить отзыв")
async def btn_feedback(m: types.Message, state: FSMContext):
    await m.answer("Напишите ваш анонимный отзыв:"); await state.set_state(FeedbackForm.text)

@dp.message(F.text == "🛡 Апелляция")
async def btn_appeal(m: types.Message, state: FSMContext):
    if not is_user_approved(m.from_user.id): return
    await m.answer("Опишите причину апелляции:"); await state.set_state(AppealForm.text)

# --- АДМИН КОМАНДЫ ---

@dp.message(Command("list"))
async def cmd_list(m: types.Message):
    if m.from_user.id != ADMIN_ID: return
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute("SELECT user_id, role, violations FROM approved_users"); rows = cursor.fetchall(); conn.close()
    if not rows: await m.answer("База пуста."); return
    res = "📂 <b>БАЗА:</b>\n" + "\n".join([f"<code>{r[0]}</code> | {r[1]} | {r[2]}/3" for r in rows])
    await m.answer(res, parse_mode="HTML")

@dp.message(Command("add"))
async def cmd_add(m: types.Message):
    if m.from_user.id != ADMIN_ID: return
    try:
        p = m.text.split(maxsplit=2)
        uid, role = int(p[1]), p[2]
        conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO approved_users (user_id, role) VALUES (?, ?)", (uid, role))
        conn.commit(); conn.close()
        await m.answer(f"✅ Добавлен: {uid}")
    except: await m.answer("Формат: `/add ID РОЛЬ`", parse_mode="Markdown")

@dp.message(Command("del"))
async def cmd_delete(m: types.Message):
    if m.from_user.id != ADMIN_ID: return
    try:
        tid = int(m.text.split()[1])
        conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
        cursor.execute("DELETE FROM approved_users WHERE user_id = ?", (tid,))
        conn.commit(); conn.close()
        await m.answer(f"✅ {tid} удален.")
    except: await m.answer("Формат: `/del ID`", parse_mode="Markdown")

# --- АНКЕТЫ И ПРИНЯТИЕ ---

@dp.message(RegForm.role)
async def p_role(m: types.Message, state: FSMContext):
    await state.update_data(role=m.text); await m.answer("Укажите ваш юз:"); await state.set_state(RegForm.username)

@dp.message(RegForm.username)
async def p_user(m: types.Message, state: FSMContext):
    data = await state.get_data()
    name = f"@{m.from_user.username}" if m.from_user.username else m.from_user.first_name
    # Сразу сохраняем в общую базу всех (для созыва)
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO all_users (user_id, name) VALUES (?, ?)", (m.from_user.id, name))
    conn.commit(); conn.close()
    
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Принять ✅", callback_data=f"adm_ok_{m.from_user.id}"), InlineKeyboardButton(text="Отклонить ❌", callback_data=f"adm_no_{m.from_user.id}")]])
    await bot.send_message(ADMIN_ID, f"<b>АНКЕТА</b>\nЮЗ: {m.text}\nID: {m.from_user.id}\nРОЛЬ: {data['role']}", reply_markup=kb, parse_mode="HTML")
    await m.answer("Заявка отправлена."); await state.clear()

@dp.callback_query(F.data.startswith("adm_"))
async def admin_reg_confirm(call: CallbackQuery):
    action, uid = call.data.split("_")[1], int(call.data.split("_")[2])
    if action == "ok":
        role = call.message.text.split("РОЛЬ: ")[1]
        conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO approved_users (user_id, role) VALUES (?, ?)", (uid, role))
        conn.commit(); conn.close()
        await bot.send_message(uid, f"Принято! Роль: {role}\n{CHAT_LINK}", reply_markup=get_main_reply_kb(uid))
        await call.message.edit_text(call.message.text + "\n\n✅ ОДОБРЕНО")
        # ВЫЗОВ СОЗЫВА
        await global_call(role)
    else:
        await bot.send_message(uid, "Отклонено."); await call.message.edit_text(call.message.text + "\n\n❌ ОТКЛОНЕНО")

# --- СИСТЕМА ЖАЛОБ И ОТЗЫВОВ ---
@dp.message(ComplaintForm.my_role)
async def comp_my_role(m: types.Message, state: FSMContext):
    if not get_uid_by_role(m.text): await m.answer("Нет такой роли!"); return
    await state.update_data(my_role=m.text); await m.answer("Суть:"); await state.set_state(ComplaintForm.text)

@dp.message(ComplaintForm.text)
async def comp_text(m: types.Message, state: FSMContext):
    await state.update_data(text=m.text); await m.answer("Файлы?", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Пропустить", callback_data="skip_file")]])); await state.set_state(ComplaintForm.evidence)

@dp.callback_query(F.data == "skip_file", ComplaintForm.evidence)
@dp.message(ComplaintForm.evidence)
async def comp_target_role(msg: types.Message | CallbackQuery, state: FSMContext):
    if isinstance(msg, types.Message):
        fid = msg.photo[-1].file_id if msg.photo else (msg.document.file_id if msg.document else None)
        await state.update_data(file=fid); await msg.answer("Роль нарушителя:")
    else: await msg.message.answer("Роль нарушителя:"); await msg.answer()
    await state.set_state(ComplaintForm.target_role)

@dp.message(ComplaintForm.target_role)
async def comp_final(m: types.Message, state: FSMContext):
    target_uid = get_uid_by_role(m.text)
    if not target_uid: await m.answer("Не найден!"); return
    data = await state.get_data()
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Варн ✅", callback_data=f"warn_ok_{target_uid}"), InlineKeyboardButton(text="Отмена ❌", callback_data="warn_no")]])
    cap = f"🚨 <b>ЖАЛОБА</b>\nОт: {data['my_role']}\nНа: {m.text}\nСуть: {data['text']}"
    if data.get('file'): await bot.send_photo(ADMIN_ID, data['file'], caption=cap, reply_markup=kb, parse_mode="HTML")
    else: await bot.send_message(ADMIN_ID, cap, reply_markup=kb, parse_mode="HTML")
    await m.answer("Жалоба ушла."); await state.clear()

@dp.message(FeedbackForm.text)
async def process_fb(m: types.Message, state: FSMContext):
    await bot.send_message(ADMIN_ID, f"📥 <b>ОТЗЫВ</b>\n\n{m.text}", parse_mode="HTML"); await m.answer("Принято!"); await state.clear()

@dp.message(AppealForm.text)
async def process_appeal(m: types.Message, state: FSMContext):
    await bot.send_message(ADMIN_ID, f"🛡 <b>АПЕЛЛЯЦИЯ</b>\nID: {m.from_user.id}\nТекст: {m.text}", parse_mode="HTML"); await m.answer("Ушло."); await state.clear()

# --- ВАРНЫ ---
@dp.callback_query(F.data.startswith("warn_"))
async def handle_warn(call: CallbackQuery):
    if "no" in call.data: await call.message.delete(); return
    tuid = int(call.data.split("_")[2])
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute("UPDATE approved_users SET violations = violations + 1 WHERE user_id = ?", (tuid,))
    cursor.execute("SELECT violations FROM approved_users WHERE user_id = ?", (tuid,))
    v = cursor.fetchone()[0]
    if v >= 3:
        try: await bot.ban_chat_member(CHAT_ID, tuid)
        except: pass
        cursor.execute("DELETE FROM approved_users WHERE user_id = ?", (tuid,))
        await bot.send_message(tuid, "Бан 3/3."); await call.message.edit_text("🔥 Игрок забанен")
    else:
        await bot.send_message(tuid, f"Варн {v}/3."); await call.message.edit_text(f"✅ Выдан варн {v}/3")
    conn.commit(); conn.close()

# --- ПЛАШКИ ---
@dp.chat_join_request()
async def auto_approve_logic(req: ChatJoinRequest):
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute("SELECT role FROM approved_users WHERE user_id = ?", (req.from_user.id,))
    res = cursor.fetchone(); conn.close()
    if res:
        await req.approve(); await asyncio.sleep(1)
        try: await bot.make_request("setChatMemberTag", {"chat_id": CHAT_ID, "user_id": req.from_user.id, "tag": res[0]})
        except: pass

# --- ЗАПУСК ---
async def main():
    init_db()
    Thread(target=run, daemon=True).start()
    await bot.delete_webhook(drop_pending_updates=True)
    # Настройка команд для меню
    await bot.set_my_commands([
        BotCommand(command="start", description="Обновить меню"),
        BotCommand(command="list", description="Список базы"),
        BotCommand(command="add", description="Добавить (ID РОЛЬ)"),
        BotCommand(command="del", description="Удалить (ID)")
    ])
    await dp.start_polling(bot, allowed_updates=["message", "callback_query", "chat_join_request"])

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
