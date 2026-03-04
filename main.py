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
                            InputMediaPhoto, InputMediaDocument, ReplyKeyboardRemove)

# --- SERVER ---
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
    conn.commit(); conn.close()

# --- УМНОЕ ГЛАВНОЕ МЕНЮ (REPLY) ---
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

def get_user_by_role(role_name):
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute("SELECT user_id, warns FROM approved_users WHERE role = ?", (role_name,))
    res = cursor.fetchone(); conn.close()
    return res

# --- КОМАНДЫ ---
@dp.message(Command("start"))
async def cmd_start(m: types.Message):
    await m.answer("👋 Добро пожаловать в Harmony! Воспользуйся меню ниже:", 
                   reply_markup=get_main_reply_kb(m.from_user.id))

# Обработка текстовых кнопок из меню
@dp.message(F.text == "📝 Вступить")
async def btn_reg(m: types.Message, state: FSMContext):
    await m.answer("Твоя роль (например: Ризли • влд):", reply_markup=ReplyKeyboardRemove())
    await state.set_state(Form.role)

@dp.message(F.text == "⚖️ Апелляция")
async def btn_app(m: types.Message, state: FSMContext):
    await state.update_data(r_type="апелляция", files=[])
    await m.answer("Для подтверждения введи <b>свою роль</b>:", parse_mode="HTML", reply_markup=ReplyKeyboardRemove())
    await state.set_state(Form.check_my_role)

@dp.message(F.text == "🚫 Жалоба")
async def btn_rep(m: types.Message, state: FSMContext):
    await state.update_data(r_type="жалоба", files=[])
    await m.answer("Для подтверждения введи <b>свою роль</b>:", parse_mode="HTML", reply_markup=ReplyKeyboardRemove())
    await state.set_state(Form.check_my_role)

@dp.message(F.text == "⭐ Отзыв")
async def btn_fb(m: types.Message, state: FSMContext):
    await state.update_data(r_type="отзыв", files=[])
    await m.answer("Напиши свой отзыв:", reply_markup=ReplyKeyboardRemove())
    await state.set_state(Form.report_text)

# --- ЛОГИКА АНКЕТЫ ---
@dp.message(Form.role)
async def p_role(m: types.Message, state: FSMContext):
    await state.update_data(role=m.text); await m.answer("Твой юз:")
    await state.set_state(Form.user)

@dp.message(Form.user)
async def p_user(m: types.Message, state: FSMContext):
    data = await state.get_data(); role = data.get('role'); uid = m.from_user.id
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Принять", callback_data=f"adm_ok_{uid}_{role[:15]}"), 
         InlineKeyboardButton(text="Отклонить", callback_data=f"adm_no_{uid}")]
    ])
    await bot.send_message(ADMIN_ID, f"🆕 <b>АНКЕТА</b>\nЮз: {m.text}\nID: {uid}\nРоль: {role}", reply_markup=kb, parse_mode="HTML")
    await m.answer("Анкета отправлена! Ожидай ответа.", reply_markup=get_main_reply_kb(uid))
    await state.clear()

# --- ЖАЛОБЫ / АПЕЛЛЯЦИИ ---
@dp.message(Form.check_my_role)
async def check_my_role(m: types.Message, state: FSMContext):
    user_data = get_user_by_role(m.text)
    if not user_data:
        await m.answer("Такой роли нет в базе. Проверь написание:")
        return
    await state.update_data(my_role=m.text)
    data = await state.get_data()
    if data['r_type'] == "жалоба":
        await m.answer("Напиши <b>роль того, на кого</b> жалуешься:")
        await state.set_state(Form.report_target_role)
    else:
        await m.answer("Напиши текст апелляции:")
        await state.set_state(Form.report_text)

@dp.message(Form.report_target_role)
async def check_target_role(m: types.Message, state: FSMContext):
    if not get_user_by_role(m.text):
        await m.answer("Роль нарушителя не найдена. Попробуй еще раз:"); return
    await state.update_data(target_role=m.text)
    await m.answer("Опиши суть:"); await state.set_state(Form.report_text)

@dp.message(Form.report_text)
async def get_report_text(m: types.Message, state: FSMContext):
    await state.update_data(text=m.text)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Отправить без файлов ➡️", callback_data="finish_report")]])
    await m.answer("Прикрепи доказательства (фото/док) или нажми кнопку ниже.", reply_markup=kb)
    await state.set_state(Form.report_files)

@dp.message(Form.report_files, F.photo | F.document)
async def get_files(m: types.Message, state: FSMContext):
    data = await state.get_data(); files = data.get('files', [])
    fid = m.photo[-1].file_id if m.photo else m.document.file_id
    files.append({'type': 'photo' if m.photo else 'doc', 'id': fid})
    await state.update_data(files=files)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Завершить и отправить ✅", callback_data="finish_report")]])
    await m.answer(f"Файлов: {len(files)}. Можно еще.", reply_markup=kb)

@dp.callback_query(F.data == "finish_report")
async def send_to_adm(call: CallbackQuery, state: FSMContext):
    data = await state.get_data(); uid = call.from_user.id; files = data.get('files', [])
    target_info = f"\nНа кого: <b>{data.get('target_role', '-')}</b>" if data['r_type'] == "жалоба" else ""
    msg = f"📩 <b>{data['r_type'].upper()}</b>\nОт: {data['my_role']}{target_info}\n\nТекст: {data['text']}"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Принять", callback_data=f"adm_rep_ok_{uid}_{data['r_type']}")],
        [InlineKeyboardButton(text="❌ Отклонить", callback_data=f"adm_rep_no_{uid}")],
        [InlineKeyboardButton(text="💬 Ответ", callback_data=f"adm_msg_{uid}")]
    ])
    if not files: await bot.send_message(ADMIN_ID, msg, reply_markup=kb, parse_mode="HTML")
    else:
        media = [InputMediaPhoto(media=f['id']) if f['type']=='photo' else InputMediaDocument(media=f['id']) for f in files]
        media[0].caption = msg; media[0].parse_mode = "HTML"
        await bot.send_media_group(ADMIN_ID, media)
        await bot.send_message(ADMIN_ID, "Управление:", reply_markup=kb)
    await call.message.answer("Отправлено! ✅", reply_markup=get_main_reply_kb(uid))
    await state.clear(); await call.answer()

# --- КНОПКИ АДМИНА ---
@dp.callback_query(F.data.startswith("adm_"))
async def admin_actions(call: CallbackQuery, state: FSMContext):
    p = call.data.split("_"); act = p[1]; tid = int(p[2])
    if act == "ok":
        role = p[3]; conn = sqlite3.connect(DB_PATH); cur = conn.cursor()
        cur.execute("INSERT OR REPLACE INTO approved_users (user_id, role, warns) VALUES (?, ?, 0)", (tid, role))
        conn.commit(); conn.close()
        try: await bot.send_message(tid, f"Ты принят! ✨\n{CHAT_LINK}", reply_markup=get_main_reply_kb(tid))
        except: pass
        await call.message.edit_text(call.message.text + "\n✅ ПРИНЯТ")
    elif act == "rep" and p[2] == "ok":
        real_uid = int(p[3]); r_type = p[4]
        if r_type == "жалоба":
            try:
                t_role = call.message.text.split("На кого: ")[1].split("\n")[0]
                t_uid, t_warns = get_user_by_role(t_role)
                new_w = t_warns + 1
                conn = sqlite3.connect(DB_PATH); cur = conn.cursor()
                cur.execute("UPDATE approved_users SET warns = ? WHERE user_id = ?", (new_w, t_uid))
                conn.commit(); conn.close()
                await bot.send_message(t_uid, f"⚠️ Нарушение {new_w}/3!")
                if new_w >= 3:
                    await bot.ban_chat_member(CHAT_ID, t_uid)
                    conn = sqlite3.connect(DB_PATH); cur = conn.cursor()
                    cur.execute("DELETE FROM approved_users WHERE user_id = ?", (t_uid,))
                    conn.commit(); conn.close()
                    await bot.send_message(t_uid, "Исключен за 3/3 варна.", reply_markup=get_main_reply_kb(t_uid))
            except: pass
        await bot.send_message(real_uid, "Рассмотрено! ✅")
        await call.message.edit_text(call.message.text + "\n✅ ОДОБРЕНО")
    elif act == "msg":
        await call.message.answer(f"Ответ для {tid}:")
        await state.update_data(target_to_msg=tid); await state.set_state(Form.admin_reply)
    await call.answer()

@dp.message(Command("list"))
async def cmd_list(m: types.Message):
    if m.from_user.id != ADMIN_ID: return
    conn = sqlite3.connect(DB_PATH); cur = conn.cursor()
    cur.execute("SELECT user_id, role, warns FROM approved_users"); rows = cur.fetchall(); conn.close()
    if not rows: await m.answer("База пуста."); return
    res = "📋 <b>БАЗА:</b>\n" + "\n".join([f"<code>{r[0]}</code> | {r[1]} | {r[2]}/3" for r in rows])
    await m.answer(res, parse_mode="HTML")

@dp.message(Form.admin_reply)
async def admin_reply_send(m: types.Message, state: FSMContext):
    d = await state.get_data(); t = d.get('target_to_msg')
    try: 
        await bot.send_message(t, f"✉️ <b>Ответ администрации:</b>\n\n{m.text}", parse_mode="HTML")
        await m.answer("Отправлено!")
    except: await m.answer("Ошибка")
    await state.clear()

async def main():
    init_db(); Thread(target=run, daemon=True).start()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO); asyncio.run(main())
