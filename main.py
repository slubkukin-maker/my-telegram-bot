import asyncio
import sqlite3
import logging
import os
from flask import Flask
from threading import Thread
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import BotCommand

# --- ЛОГИРОВАНИЕ (Чтобы видеть ошибки в Render) ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- SERVER ---
app = Flask('')
@app.route('/')
def home(): return "Бот в сети!"

def run():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# --- CONFIG ---
TOKEN = "8344752199:AAFwouRQZYV2ztyDwC44qCu8uTxq2lgWtoc"
ADMIN_ID = 8294726083 # ПРОВЕРЬ ЭТОТ ID ЕЩЕ РАЗ!
CHAT_ID = -1003393441169 
DB_PATH = "database.db"

bot = Bot(token=TOKEN)
dp = Dispatcher()

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS approved_users (user_id INTEGER PRIMARY KEY, role TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS all_users (user_id INTEGER PRIMARY KEY, name TEXT)")
    conn.commit()
    conn.close()

# --- КОМАНДЫ (БЕЗ ПРОВЕРКИ ID ДЛЯ ТЕСТА) ---

@dp.message(Command("check"))
async def cmd_check(m: types.Message):
    logger.info(f"Команда /check от {m.from_user.id}")
    if m.from_user.id != ADMIN_ID:
        await m.answer(f"Твой ID ({m.from_user.id}) не совпадает с ADMIN_ID ({ADMIN_ID})")
        return
    
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM approved_users"); approved = [r[0] for r in cursor.fetchall()]
    cursor.execute("SELECT user_id, name FROM all_users"); all_u = cursor.fetchall(); conn.close()
    
    bad = [f"<code>{u[0]}</code> | {u[1]}" for u in all_u if u[0] not in approved]
    if not bad: await m.answer("Все подтверждены! ✅")
    else: await m.answer("<b>Без роли:</b>\n\n" + "\n".join(bad), parse_mode="HTML")

@dp.message(Command("start"))
async def cmd_start(m: types.Message):
    await m.answer(f"Привет! Твой ID: <code>{m.from_user.id}</code>\nADMIN_ID в коде: <code>{ADMIN_ID}</code>", parse_mode="HTML")

# --- СБОР (С ФИЛЬТРОМ, ЧТОБЫ НЕ ЖРАЛ КОМАНДЫ) ---
@dp.message(F.chat.id == CHAT_ID, ~F.text.startswith("/"))
async def collect(m: types.Message):
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO all_users (user_id, name) VALUES (?, ?)", (m.from_user.id, m.from_user.full_name))
    conn.commit(); conn.close()

async def main():
    init_db()
    Thread(target=run, daemon=True).start()
    await bot.set_my_commands([
        BotCommand(command="start", description="Старт"),
        BotCommand(command="check", description="Проверка")
    ])
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
