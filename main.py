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
                            BotCommand, CallbackQuery, ChatMemberUpdated, ChatJoinRequest)

# --- SERVER (для работы 24/7) ---
app = Flask('')
@app.route('/')
def home(): return "Bot is Online and Ready"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()

# --- CONFIG ---
TOKEN = "8344752199:AAFwouRQZYV2ztyDwC44qCu8uTxq2lgWtoc"
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

# --- DATABASE ---
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS approved_users (user_id INTEGER PRIMARY KEY, role TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS all_users (user_id INTEGER PRIMARY KEY, name TEXT)")
    conn.commit()
    conn.close()

# --- МЕХАНИКА АВТО-ПРИНЯТИЯ И ТЕГОВ (Member Tags) ---
@dp.chat_join_request()
async def auto_approve_and_tag(request: ChatJoinRequest):
    uid = request.from_user.id
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT role FROM approved_users WHERE user_id = ?", (uid,))
    res = cursor.fetchone()
    conn.close()
    
    if res:
        role = res[0]
        # 1. Одобряем вход в группу
        await request.approve()
        
        # 2. Выдаем "Тег" (Custom Title)
        # Чтобы тег работал, нужно дать юзеру минимальные права админа
        try:
            await asyncio.sleep(1) # Короткая пауза для синхронизации
            await bot.promote_chat_member(
                chat_id=CHAT_ID,
                user_id=uid,
                can_invite_users=True # Минимальное право, чтобы считаться админом с тегом
            )
            await bot.set_chat_administrator_custom_title(
                chat_id=CHAT_ID,
                user_id=uid,
                custom_title=role
            )
            await bot.send_message(CHAT_ID, f"🎉 В чат вошел одобренный участник: <b>{role}</b>", parse_mode="HTML")
        except Exception as e:
            logging.error(f"Не удалось поставить тег: {e}")
    else:
        # Если пользователя нет в базе одобренных, заявка просто висит (или можно отклонить)
        pass

# --- КОМАНДЫ АДМИНА ---

@dp.message(Command("del"))
async def cmd_delete(m: types.Message):
    if m.from_user.id != ADMIN_ID: return
    try:
        target_id = int(m.text.split()[1])
        conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
        cursor.execute("DELETE FROM all_users WHERE user_id = ?", (target_id,))
        cursor.execute("DELETE FROM approved_users WHERE user_id = ?", (target_id,))
        conn.commit(); conn.close()
        await m.answer(f"✅ Пользователь {target_id} удален из базы.")
    except:
        await m.answer("Формат: /del ID")

@dp.message(Command("list"))
async def cmd_list(m: types.Message):
    if m.from_user.id != ADMIN_ID: return
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute("SELECT user_id, name FROM all_users"); rows = cursor.fetchall(); conn.close()
    if not rows:
        await m.answer("Список пуст.")
        return
    text = "📂 <b>СПИСОК ЮЗЕРОВ (ID | ИМЯ):</b>\n"
    for r in rows:
        text += f"<code>{r[0]}</code> | {r[1]}\n"
    await m.answer(text, parse_mode="HTML")

@dp.message(Command("all"))
async def cmd_all(m: types.Message):
    if m.from_user.id != ADMIN_ID: return
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute("SELECT user_id, name FROM all_users"); rows = cursor.fetchall(); conn.close()
    if not rows: return
    mentions = [f"<a href='tg://user?id={r[0]}'>{r[1]}</a>" for r in rows]
    for i in range(0, len(mentions), 5):
        await m.answer(f"📣 <b>ОБЩИЙ СБОР:</b>\n{', '.join(mentions[i:i+5])}", parse_mode="HTML")

# --- РЕГИСТРАЦИЯ (АНКЕТА) ---

@dp.message(Command("start"))
async def cmd_start(m: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📝 Подать заявку", callback_data="start_reg")]])
    await m.answer(f"Твой ID: <code>{m.from_user.id}</code>\nНажми кнопку, чтобы выбрать роль.", reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data == "start_reg")
async def start_reg(call: CallbackQuery, state: FSMContext):
    await call.message.answer("Введите желаемую роль (она будет на плашке):")
    await state.set_state(Form.role); await call.answer()

@dp.message(Form.role)
async def p_role(m: types.Message, state: FSMContext):
    await state.update_data(role=m.text)
    await m.answer("Введите ваш ник или имя для базы:")
    await state.set_state(Form.user)

@dp.message(Form.user)
async def p_user(m: types.Message, state: FSMContext):
    data = await state.get_data()
    role = data.get('role')
    uid = m.from_user.id
    user_name = m.text
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Принять ✅", callback_data=f"adm_ok_{uid}"), 
         InlineKeyboardButton(text="Отклонить ❌", callback_data=f"adm_no_{uid}")],
        [InlineKeyboardButton(text="Написать 💬", callback_data=f"adm_msg_{uid}")]
    ])
    
    await bot.send_message(ADMIN_ID, f"<b>НОВАЯ АНКЕТА</b>\nИмя: {user_name}\nID: <code>{uid}</code>\nРоль: {role}", reply_markup=kb, parse_mode="HTML")
    
    # Сохраняем имя во временную базу на случай одобрения
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO all_users (user_id, name) VALUES (?, ?)", (uid, user_name))
    conn.commit(); conn.close()
    
    await m.answer("Ваша заявка отправлена. Ожидайте одобрения администратором.")
    await state.clear()

# --- КНОПКИ АДМИНИСТРАТОРА ---

@dp.callback_query(F.data.startswith("adm_"))
async def admin_btns(call: CallbackQuery, state: FSMContext):
    data_parts = call.data.split("_")
    action = data_parts[1]
    target_uid = int(data_parts[2])
    
    if action == "ok":
        # Извлекаем роль из сообщения админу
        role = "Member"
        if "Роль: " in call.message.text:
            role = call.message.text.split("Роль: ")[1].split("\n")[0]
        
        conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO approved_users (user_id, role) VALUES (?, ?)", (target_uid, role))
        conn.commit(); conn.close()
        
        await bot.send_message(target_uid, f"Ваша заявка одобрена! 🎉\nВаша роль: {role}\n\nВступайте в группу по ссылке: {CHAT_LINK}")
        await call.message.edit_text(call.message.text + "\n\n✅ ОДОБРЕНО")
        
    elif action == "no":
        await bot.send_message(target_uid, "К сожалению, ваша заявка была отклонена.")
        await call.message.edit_text(call.message.text + "\n\n❌ ОТКЛОНЕНО")
        
    elif action == "msg":
        await call.message.answer(f"Напишите текст сообщения для <code>{target_uid}</code>:", parse_mode="HTML")
        await state.update_data(target_to_msg=target_uid)
        await state.set_state(Form.admin_reply)
        
    await call.answer()

@dp.message(Form.admin_reply)
async def admin_reply_send(m: types.Message, state: FSMContext):
    data = await state.get_data(); target = data.get('target_to_msg')
    try:
        await bot.send_message(target, f"✉️ <b>Сообщение от администрации:</b>\n\n{m.text}", parse_mode="HTML")
        await m.answer("Сообщение доставлено.")
    except:
        await m.answer("Ошибка отправки (возможно, пользователь заблокировал бота).")
    await state.clear()

# --- АВТО-УДАЛЕНИЕ ПРИ ВЫХОДЕ И СБОР ИМЕН ---

@dp.chat_member()
async def on_chat_member_update(update: ChatMemberUpdated):
    if update.chat.id == CHAT_ID:
        if update.new_chat_member.status in ["left", "kicked"]:
            uid = update.new_chat_member.user.id
            conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
            cursor.execute("DELETE FROM all_users WHERE user_id = ?", (uid,))
            cursor.execute("DELETE FROM approved_users WHERE user_id = ?", (uid,))
            conn.commit(); conn.close()

@dp.message(F.chat.id == CHAT_ID)
async def collect_msg(m: types.Message):
    if m.from_user.is_bot: return
    # Обновляем имя пользователя в базе, когда он пишет
    name = f"@{m.from_user.username}" if m.from_user.username else m.from_user.first_name
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO all_users (user_id, name) VALUES (?, ?)", (m.from_user.id, name))
    conn.commit(); conn.close()

# --- ЗАПУСК ---

async def main():
    init_db()
    keep_alive() # Запуск Flask сервера в потоке
    
    await bot.set_my_commands([
        BotCommand(command="start", description="Регистрация"),
        BotCommand(command="all", description="Вызвать всех"),
        BotCommand(command="list", description="Показать базу"),
        BotCommand(command="del", description="Удалить по ID")
    ])
    
    await bot.delete_webhook(drop_pending_updates=True)
    # Важно добавить chat_join_request в список разрешенных обновлений
    await dp.start_polling(bot, allowed_updates=["message", "callback_query", "chat_member", "chat_join_request"])

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped")
