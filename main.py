import asyncio
import sqlite3
import logging
from flask import Flask
from threading import Thread
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, BotCommand, CallbackQuery, ChatMemberUpdated, ChatJoinRequest

app = Flask('')
@app.route('/')
def home(): return "Bot is Online"
def run(): app.run(host='0.0.0.0', port=8080)
def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()

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

@dp.message(Command("start"))
async def cmd_start(m: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Вступить", callback_data="start_reg")]])
    await m.answer(f"ID: <code>{m.from_user.id}</code>", reply_markup=kb, parse_mode="HTML")

@dp.message(Command("add"))
async def cmd_add(m: types.Message):
    if m.from_user.id != ADMIN_ID: return
    try:
        args = m.text.split(maxsplit=2)
        target_id = int(args[1])
        role = args[2] if len(args) > 2 else "Member"
        conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO approved_users (user_id, role) VALUES (?, ?)", (target_id, role))
        cursor.execute("INSERT OR REPLACE INTO all_users (user_id, name) VALUES (?, ?)", (target_id, role))
        conn.commit(); conn.close()
        await m.answer(f"OK: {target_id} | {role}")
    except: await m.answer("Формат: /add ID Роль")

@dp.message(Command("del"))
async def cmd_delete(m: types.Message):
    if m.from_user.id != ADMIN_ID: return
    try:
        target_id = int(m.text.split()[1])
        conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
        cursor.execute("DELETE FROM all_users WHERE user_id = ?", (target_id,))
        cursor.execute("DELETE FROM approved_users WHERE user_id = ?", (target_id,))
        conn.commit(); conn.close()
        await m.answer(f"Удален: {target_id}")
    except: await m.answer("Формат: /del ID")

@dp.message(Command("list"))
async def cmd_list(m: types.Message):
    if m.from_user.id != ADMIN_ID: return
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute("SELECT user_id, name FROM all_users"); rows = cursor.fetchall(); conn.close()
    if not rows:
        await m.answer("EMPTY")
        return
    text = "LIST:\n"
    for r in rows: text += f"<code>{r[0]}</code> | {r[1]}\n"
    await m.answer(text, parse_mode="HTML")

@dp.message(Command("all"))
async def cmd_all(m: types.Message):
    if m.from_user.id != ADMIN_ID: return
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM all_users"); rows = cursor.fetchall(); conn.close()
    if not rows: return
    mentions = "".join([f"<a href='tg://user?id={r[0]}'>\u2060</a>" for r in rows])
    await m.answer(f"Общий сбор! 📢{mentions}", parse_mode="HTML")

@dp.callback_query(F.data == "start_reg")
async def start_reg(call: CallbackQuery, state: FSMContext):
    await call.message.answer("Укажите роль:")
    await state.set_state(Form.role); await call.answer()

@dp.message(Form.role)
async def p_role(m: types.Message, state: FSMContext):
    await state.update_data(role=m.text); await m.answer("Укажите ник:"); await state.set_state(Form.user)

@dp.message(Form.user)
async def p_user(m: types.Message, state: FSMContext):
    data = await state.get_data(); role = data.get('role'); uid = m.from_user.id
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Принять", callback_data=f"adm_ok_{uid}"),
         InlineKeyboardButton(text="Отклонить", callback_data=f"adm_no_{uid}")]
    ])
    await bot.send_message(ADMIN_ID, f"ANKETA\nUSER: {m.text}\nID: {uid}\nROLE: {role}", reply_markup=kb)
    await m.answer("Заявка отправлена."); await state.clear()

@dp.callback_query(F.data.startswith("adm_"))
async def admin_btns(call: CallbackQuery, state: FSMContext):
    action = call.data.split("_")[1]; target_uid = int(call.data.split("_")[2])
    if action == "ok":
        role = "Member"
        if "ROLE: " in call.message.text:
            role = call.message.text.split("ROLE: ")[1].split("\n")[0]
        conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO approved_users (user_id, role) VALUES (?, ?)", (target_uid, role))
        cursor.execute("INSERT OR REPLACE INTO all_users (user_id, name) VALUES (?, ?)", (target_uid, role))
        conn.commit(); conn.close()
        await bot.send_message(target_uid, f"Принято! Роль: {role}\n{CHAT_LINK}")
        await call.message.edit_text(call.message.text + "\nSTATUS: OK")
    elif action == "no":
        await bot.send_message(target_uid, "Отклонено.")
        await call.message.edit_text(call.message.text + "\nSTATUS: NO")
    await call.answer()

@dp.chat_join_request()
async def auto_approve(request: ChatJoinRequest):
    user_id = request.from_user.id
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM approved_users WHERE user_id = ?", (user_id,))
    is_approved = cursor.fetchone(); conn.close()
    if is_approved: await request.approve()

@dp.chat_member()
async def on_chat_member_update(update: ChatMemberUpdated):
    if update.chat.id == CHAT_ID:
        if update.new_chat_member.status in ["left", "kicked"]:
            uid = update.from_user.id
            conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
            cursor.execute("DELETE FROM all_users WHERE user_id = ?", (uid,))
            cursor.execute("DELETE FROM approved_users WHERE user_id = ?", (uid,))
            conn.commit(); conn.close()

        elif update.new_chat_member.status == "member" and update.old_chat_member.status != "member":

            uid = update.new_chat_member.user.id

            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()

            cursor.execute("SELECT role FROM approved_users WHERE user_id = ?", (uid,))
            res = cursor.fetchone()

            role = res[0] if res else "Member"

            try:

                await bot.promote_chat_member(
                    chat_id=CHAT_ID,
                    user_id=uid,
                    can_manage_chat=False,
                    can_post_messages=False,
                    can_edit_messages=False,
                    can_delete_messages=False,
                    can_invite_users=False,
                    can_restrict_members=False,
                    can_pin_messages=False,
                    can_promote_members=False,
                    can_manage_video_chats=False,
                    can_anonymous=False,
                    can_manage_topics=False
                )

                await asyncio.sleep(1)

                await bot.set_chat_administrator_custom_title(
                    chat_id=CHAT_ID,
                    user_id=uid,
                    custom_title=role
                )

            except:
                pass

            cursor.execute("SELECT user_id FROM all_users")
            rows = cursor.fetchall()
            conn.close()

            mentions = "".join([f"<a href='tg://user?id={r[0]}'>\u2060</a>" for r in rows])

            await bot.send_message(
                CHAT_ID,
                f"<b>Harmony Bot: Общий сбор!</b>\nНовый участник: <b>{role}</b>\n✨{mentions}",
                parse_mode="HTML"
            )

@dp.message(F.chat.id == CHAT_ID)
async def collect_msg(m: types.Message):
    if m.from_user.is_bot: return
    name = m.from_user.first_name
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO all_users (user_id, name) VALUES (?, ?)", (m.from_user.id, name))
    conn.commit(); conn.close()

async def main():
    init_db(); keep_alive()
    await bot.set_my_commands([
        BotCommand(command="start", description="Меню"),
        BotCommand(command="all", description="Сбор"),
        BotCommand(command="list", description="База"),
        BotCommand(command="add", description="Добавить ID Роль"),
        BotCommand(command="del", description="Удалить ID")
    ])
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot, allowed_updates=["message", "callback_query", "chat_member", "chat_join_request"])

if __name__ == "__main__":
    asyncio.run(main())
