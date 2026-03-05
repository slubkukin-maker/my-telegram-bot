import asyncio
import sqlite3
import logging
from flask import Flask
from threading import Thread
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (InlineKeyboardButton, InlineKeyboardMarkup, BotCommand, 
                           CallbackQuery, ChatMemberUpdated, ChatJoinRequest)

# --- 24/7 SERVER ---
app = Flask('')
@app.route('/')
def home(): return "Bot is Online"
def run(): app.run(host='0.0.0.0', port=8080)
def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()

# --- CONFIG ---
TOKEN = "8344752199:AAGDB6PqgYxnGVK-o-PjTxZf71gec_mZ_Pw"
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

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS approved_users (user_id INTEGER PRIMARY KEY, role TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS all_users (user_id INTEGER PRIMARY KEY, name TEXT)")
    conn.commit()
    conn.close()

# --- СИСТЕМА ТЕГОВ (ПЛАШЕК) ---
async def set_user_tag(user_id, tag):
    try:
        # Назначаем админом с ПУСТЫМИ правами (только ради плашки)
        await bot.promote_chat_member(
            chat_id=CHAT_ID, 
            user_id=user_id, 
            can_manage_chat=False,
            can_delete_messages=False,
            can_restrict_members=False,
            can_promote_members=False,
            can_change_info=False,
            can_invite_users=False,
            can_pin_messages=False,
            can_manage_video_chats=False,
            is_anonymous=False
        )
        await bot.set_chat_member_custom_title(chat_id=CHAT_ID, user_id=user_id, custom_title=tag)
    except Exception as e:
        logging.error(f"Ошибка плашки для {user_id}: {e}")

# --- COMMANDS ---

@dp.message(Command("start"))
async def cmd_start(m: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Вступить", callback_data="start_reg")]])
    await m.answer(f"Ваш ID: <code>{m.from_user.id}</code>\nДля вступления нажмите кнопку ниже.", reply_markup=kb, parse_mode="HTML")

@dp.message(Command("del"))
async def cmd_delete(m: types.Message):
    if m.from_user.id != ADMIN_ID: return
    try:
        target_id = int(m.text.split()[1])
        conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
        cursor.execute("DELETE FROM all_users WHERE user_id = ?", (target_id,))
        cursor.execute("DELETE FROM approved_users WHERE user_id = ?", (target_id,))
        conn.commit(); conn.close()
        await m.answer(f"Пользователь {target_id} удален из базы.")
    except: await m.answer("Использование: /del ID")

@dp.message(Command("list"))
async def cmd_list(m: types.Message):
    if m.from_user.id != ADMIN_ID: return
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute("SELECT user_id, name FROM all_users"); rows = cursor.fetchall(); conn.close()
    if not rows:
        await m.answer("База пуста.")
        return
    text = "<b>СПИСОК УЧАСТНИКОВ:</b>\n"
    for r in rows: text += f"<code>{r[0]}</code> | {r[1]}\n"
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

# --- АНКЕТА ---

@dp.callback_query(F.data == "start_reg")
async def start_reg(call: CallbackQuery, state: FSMContext):
    await call.message.answer("Укажите вашу роль (она будет на плашке):")
    await state.set_state(Form.role); await call.answer()

@dp.message(Form.role)
async def p_role(m: types.Message, state: FSMContext):
    await state.update_data(role=m.text)
    await m.answer("Укажите ваш ник/имя для базы:")
    await state.set_state(Form.user)

@dp.message(Form.user)
async def p_user(m: types.Message, state: FSMContext):
    data = await state.get_data(); role = data.get('role'); uid = m.from_user.id
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Принять ✅", callback_data=f"adm_ok_{uid}"), 
         InlineKeyboardButton(text="Отклонить ❌", callback_data=f"adm_no_{uid}")]
    ])
    await bot.send_message(ADMIN_ID, f"📝 <b>НОВАЯ АНКЕТА</b>\nИмя: {m.text}\nID: {uid}\nРОЛЬ: {role}", reply_markup=kb, parse_mode="HTML")
    await m.answer("Заявка отправлена администратору. Ожидайте уведомления."); await state.clear()

@dp.callback_query(F.data.startswith("adm_"))
async def admin_btns(call: CallbackQuery):
    action = call.data.split("_")[1]; target_uid = int(call.data.split("_")[2])
    if action == "ok":
        # Извлекаем роль из текста сообщения админа
        role = call.message.text.split("РОЛЬ: ")[1] if "РОЛЬ: " in call.message.text else "Member"
        conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO approved_users (user_id, role) VALUES (?, ?)", (target_uid, role))
        conn.commit(); conn.close()
        
        await bot.send_message(target_uid, f"Ваша заявка одобрена! Ваша роль: {role}\nТеперь вы можете вступить в группу:\n{CHAT_LINK}")
        await call.message.edit_text(call.message.text + "\n\n✅ ОДОБРЕНО")
    elif action == "no":
        await bot.send_message(target_uid, "К сожалению, ваша заявка отклонена.")
        await call.message.edit_text(call.message.text + "\n\n❌ ОТКЛОНЕНО")
    await call.answer()

# --- ОБРАБОТКА ЗАЯВОК И ВСТУПЛЕНИЯ ---

@dp.chat_join_request()
async def handle_join_request(request: ChatJoinRequest):
    uid = request.from_user.id
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute("SELECT role FROM approved_users WHERE user_id = ?", (uid,))
    row = cursor.fetchone(); conn.close()
    
    if row:
        await request.approve() # Авто-принятие, если в базе одобренных
    else:
        # Если его нет в базе — не принимаем (или можно отклонить)
        await bot.send_message(uid, "Чтобы вступить, сначала заполните анкету в боте через /start")

@dp.chat_member()
async def on_chat_member_update(update: ChatMemberUpdated):
    if update.chat.id == CHAT_ID:
        uid = update.new_chat_member.user.id
        # Если пользователь вошел (статус member)
        if update.new_chat_member.status == "member":
            conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
            cursor.execute("SELECT role FROM approved_users WHERE user_id = ?", (uid,))
            row = cursor.fetchone(); conn.close()
            
            name = f"@{update.new_chat_member.user.username}" if update.new_chat_member.user.username else update.new_chat_member.user.first_name
            
            # Обновляем базу сбора
            conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
            cursor.execute("INSERT OR REPLACE INTO all_users (user_id, name) VALUES (?, ?)", (uid, name))
            conn.commit(); conn.close()

            if row:
                await set_user_tag(uid, row[0]) # Ставим плашку
                await bot.send_message(CHAT_ID, f"Приветствуем нового участника {name}! Твоя роль: {row[0]}")
        
        # Если пользователь вышел/выгнали
        elif update.new_chat_member.status in ["left", "kicked"]:
            conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
            cursor.execute("DELETE FROM all_users WHERE user_id = ?", (uid,))
            cursor.execute("DELETE FROM approved_users WHERE user_id = ?", (uid,))
            conn.commit(); conn.close()

# Захват сообщений в группе (обновление имен)
@dp.message(F.chat.id == CHAT_ID)
async def collect_msg(m: types.Message):
    if m.from_user.is_bot: return
    name = f"@{m.from_user.username}" if m.from_user.username else m.from_user.first_name
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO all_users (user_id, name) VALUES (?, ?)", (m.from_user.id, name))
    conn.commit(); conn.close()

async def main():
    init_db(); keep_alive()
    await bot.set_my_commands([
        BotCommand(command="start", description="Меню/Анкета"),
        BotCommand(command="all", description="Общий сбор"),
        BotCommand(command="list", description="Список базы"),
        BotCommand(command="del", description="Удалить по ID")
    ])
    await bot.delete_webhook(drop_pending_updates=True)
    # Важно добавить chat_join_request в allowed_updates
    await dp.start_polling(bot, allowed_updates=["message", "callback_query", "chat_member", "chat_join_request"])

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
