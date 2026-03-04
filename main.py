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

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
def get_main_reply_kb(user_id):
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM approved_users WHERE user_id = ?", (user_id,))
    is_joined = cursor.fetchone(); conn.close()
    kb = []
    if not is_joined: kb.append([KeyboardButton(text="📝 Вступить")])
    kb.append([KeyboardButton(text="⚖️ Апелляция"), KeyboardButton(text="🚫 Жалоба")])
    kb.append([KeyboardButton(text="⭐ Отзыв")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_user_by_role(role_name):
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute("SELECT user_id, warns FROM approved_users WHERE role = ?", (role_name,))
    res = cursor.fetchone(); conn.close()
    return res

# --- КОМАНДЫ АДМИНА ---

@dp.message(Command("all"))
async def cmd_all(m: types.Message):
    if m.from_user.id != ADMIN_ID: return
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute("SELECT user_id, name FROM all_users"); rows = cursor.fetchall(); conn.close()
    if not rows: await m.answer("База пуста."); return
    mentions = [f"<a href='tg://user?id={r[0]}'>{r[1]}</a>" for r in rows]
    for i in range(0, len(mentions), 5):
        await m.answer(f"📣 <b>ОБЩИЙ СБОР:</b>\n{', '.join(mentions[i:i+5])}", parse_mode="HTML")

@dp.message(Command("list"))
async def cmd_list(m: types.Message):
    if m.from_user.id != ADMIN_ID: return
    conn = sqlite3.connect(DB_PATH); cur = conn.cursor()
    cur.execute("SELECT user_id, role, warns FROM approved_users"); rows = cur.fetchall(); conn.close()
    if not rows: await m.answer("Пусто."); return
    res = "📋 <b>БАЗА (ТЕГИ):</b>\n" + "\n".join([f"<code>{r[0]}</code> | {r[1]} | {r[2]}/3" for r in rows])
    await m.answer(res, parse_mode="HTML")

@dp.message(Command("del"))
async def cmd_del(m: types.Message):
    if m.from_user.id != ADMIN_ID: return
    try:
        uid = int(m.text.split()[1])
        conn = sqlite3.connect(DB_PATH); cur = conn.cursor()
        cur.execute("DELETE FROM approved_users WHERE user_id = ?", (uid,))
        cur.execute("DELETE FROM all_users WHERE user_id = ?", (uid,))
        conn.commit(); conn.close()
        await m.answer(f"🗑 Удален: {uid}")
    except: await m.answer("Пример: /del ID")

# --- СБОР И ОЧИСТКА ---

@dp.chat_member()
async def on_chat_member_update(update: ChatMemberUpdated):
    if update.chat.id == CHAT_ID:
        if update.new_chat_member.status in ["left", "kicked"]:
            uid = update.old_chat_member.user.id
            conn = sqlite3.connect(DB_PATH); cur = conn.cursor()
            cur.execute("DELETE FROM all_users WHERE user_id = ?", (uid,))
            cur.execute("DELETE FROM approved_users WHERE user_id = ?", (uid,))
            conn.commit(); conn.close()

@dp.message(F.chat.id == CHAT_ID)
async def collect_msg(m: types.Message):
    if m.from_user.is_bot: return
    name = f"@{m.from_user.username}" if m.from_user.username else m.from_user.first_name
    conn = sqlite3.connect(DB_PATH); cur = conn.cursor()
    cur.execute("INSERT OR REPLACE INTO all_users (user_id, name) VALUES (?, ?)", (m.from_user.id, name))
    conn.commit(); conn.close()

# --- ЛОГИКА БОТА ---

@dp.message(Command("start"))
async def cmd_start(m: types.Message):
    await m.answer("👋 Привет! Используй меню ниже:", reply_markup=get_main_reply_kb(m.from_user.id))

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
    
    # АВТО-ТЕГ (Админка без прав)
    try:
        await bot.promote_chat_member(CHAT_ID, uid, can_invite_users=True)
        await bot.set_chat_administrator_custom_title(CHAT_ID, uid, role)
        status = f"\n✅ ПРИНЯТ. Тег установлен."
    except Exception as e: status = f"\n✅ ПРИНЯТ. Тег вручную! (Ошибка: {e})"
    
    try: await bot.send_message(uid, f"Принято! Твой тег: {role}\n{CHAT_LINK}", reply_markup=get_main_reply_kb(uid))
    except: pass
    await call.message.edit_text(call.message.text + status)

# --- ЖАЛОБЫ / АПЕЛЛЯЦИИ ---
@dp.message(F.text.in_(["⚖️ Апелляция", "🚫 Жалоба", "⭐ Отзыв"]))
async def btn_reports(m: types.Message, state: FSMContext):
    r_type = m.text.split()[1].lower()
    await state.update_data(r_type=r_type, files=[])
    if r_type == "отзыв":
        await m.answer("Напиши свой отзыв:", reply_markup=ReplyKeyboardRemove())
        await state.set_state(Form.report_text)
    else:
        await m.answer("Введи <b>свою роль</b> для проверки:", parse_mode="HTML", reply_markup=ReplyKeyboardRemove())
        await state.set_state(Form.check_my_role)

@dp.message(Form.check_my_role)
async def check_my_role(m: types.Message, state: FSMContext):
    if not get_user_by_role(m.text):
        await m.answer("Такой роли нет в базе. Проверь написание:"); return
    await state.update_data(my_role=m.text); data = await state.get_data()
    if data['r_type'] == "жалоба":
        await m.answer("Напиши <b>роль того, на кого</b> жалуешься:"); await state.set_state(Form.report_target_role)
    else:
        await m.answer("Текст апелляции:"); await state.set_state(Form.report_text)

@dp.message(Form.report_target_role)
async def check_target(m: types.Message, state: FSMContext):
    if not get_user_by_role(m.text):
        await m.answer("Нарушитель не найден в базе. Проверь роль:"); return
    await state.update_data(target_role=m.text); await m.answer("Суть жалобы:"); await state.set_state(Form.report_text)

@dp.message(Form.report_text)
async def get_text(m: types.Message, state: FSMContext):
    await state.update_data(text=m.text)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Отправить без файлов ➡️", callback_data="finish_report")]])
    await m.answer("Прикрепи фото/док или нажми кнопку.", reply_markup=kb); await state.set_state(Form.report_files)

@dp.message(Form.report_files, F.photo | F.document)
async def get_files(m: types.Message, state: FSMContext):
    data = await state.get_data(); files = data.get('files', [])
    fid = m.photo[-1].file_id if m.photo else m.document.file_id
    files.append({'type': 'photo' if m.photo else 'doc', 'id': fid})
    await state.update_data(files=files)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Завершить ✅", callback_data="finish_report")]])
    await m.answer(f"Файлов: {len(files)}", reply_markup=kb)

@dp.callback_query(F.data == "finish_report")
async def finish_rep(call: CallbackQuery, state: FSMContext):
    data = await state.get_data(); uid = call.from_user.id; files = data.get('files', [])
    target = f"\nНа кого: <b>{data.get('target_role', '-')}</b>" if data['r_type'] == "жалоба" else ""
    msg = f"📩 <b>{data['r_type'].upper()}</b>\nОт: {data.get('my_role', 'Аноним')}{target}\n\n{data['text']}"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Одобрить", callback_data=f"adm_rep_ok_{uid}_{data['r_type']}")],
        [InlineKeyboardButton(text="❌ Отказать", callback_data=f"adm_rep_no_{uid}")]
    ])
    if not files: await bot.send_message(ADMIN_ID, msg, reply_markup=kb, parse_mode="HTML")
    else:
        media = [InputMediaPhoto(media=f['id']) if f['type']=='photo' else InputMediaDocument(media=f['id']) for f in files]
        media[0].caption = msg; media[0].parse_mode = "HTML"
        await bot.send_media_group(ADMIN_ID, media); await bot.send_message(ADMIN_ID, "Управление:", reply_markup=kb)
    await call.message.answer("Отправлено!", reply_markup=get_main_reply_kb(uid)); await state.clear(); await call.answer()

@dp.callback_query(F.data.startswith("adm_rep_"))
async def adm_rep_actions(call: CallbackQuery):
    p = call.data.split("_"); act, r_uid, r_type = p[2], int(p[3]), p[4] if len(p)>4 else ""
    if act == "ok":
        if r_type == "жалоба":
            try:
                t_role = call.message.text.split("На кого: ")[1].split("\n")[0]
                t_uid, t_warns = get_user_by_role(t_role); new_w = t_warns + 1
                conn = sqlite3.connect(DB_PATH); cur = conn.cursor()
                cur.execute("UPDATE approved_users SET warns = ? WHERE user_id = ?", (new_w, t_uid))
                conn.commit(); conn.close()
                await bot.send_message(t_uid, f"⚠️ Нарушение {new_w}/3!")
                if new_w >= 3:
                    await bot.ban_chat_member(CHAT_ID, t_uid)
                    conn = sqlite3.connect(DB_PATH); cur = conn.cursor()
                    cur.execute("DELETE FROM approved_users WHERE user_id = ?", (t_uid,))
                    conn.commit(); conn.close()
            except: pass
        await bot.send_message(r_uid, "Ваша заявка одобрена! ✅")
        await call.message.edit_text(call.message.text + "\n✅ ОДОБРЕНО")
    else:
        await bot.send_message(r_uid, "В заявке отказано. ❌")
        await call.message.edit_text(call.message.text + "\n❌ ОТКАЗАНО")
    await call.answer()

async def main():
    init_db(); Thread(target=run, daemon=True).start()
    await bot.set_my_commands([
        BotCommand(command="start", description="Меню"),
        BotCommand(command="all", description="Позвать всех"),
        BotCommand(command="list", description="Список базы"),
        BotCommand(command="del", description="Удалить юзера")
    ])
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot, allowed_updates=["message", "callback_query", "chat_member"])

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO); asyncio.run(main())
