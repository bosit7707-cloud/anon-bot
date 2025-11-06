#!/usr/bin/env python3
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters
import sqlite3
import hashlib

BOT_TOKEN = "8529950290:AAGkrleqXbaWAujfEgjfu_oh3pQxiCtjUDs"

# Минимальное логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Простое хранение состояний в памяти
user_states = {}

def init_db():
    conn = sqlite3.connect('anon_bot.db')
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, first_name TEXT, referral_code TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, from_user_id INTEGER, to_user_id INTEGER, message_text TEXT)')
    conn.commit()
    conn.close()

async def start(update: Update, context):
    user = update.effective_user
    args = context.args
    
    print(f"START: User {user.id}, args: {args}")
    
    # Если перешли по ссылке - отправляем сообщение
    if args and len(args) > 0:
        referral_code = args[0]
        
        conn = sqlite3.connect('anon_bot.db')
        c = conn.cursor()
        c.execute('SELECT user_id, first_name FROM users WHERE referral_code = ?', (referral_code,))
        target_user = c.fetchone()
        conn.close()
        
        if target_user:
            target_user_id, target_name = target_user
            
            if target_user_id == user.id:
                # Сам себе - показываем ссылку
                referral_code = hashlib.md5(f"anon_{user.id}".encode()).hexdigest()[:8]
                conn = sqlite3.connect('anon_bot.db')
                c = conn.cursor()
                c.execute('INSERT OR REPLACE INTO users (user_id, first_name, referral_code) VALUES (?, ?, ?)', 
                          (user.id, user.first_name, referral_code))
                conn.commit()
                conn.close()
                
                personal_link = f"https://t.me/AnonyMsgeBot?start={referral_code}"
                await update.message.reply_text(f"🔗 Ваша ссылка:\n{personal_link}")
                return
            
            # Сохраняем состояние
            user_states[user.id] = {
                'target_user_id': target_user_id,
                'target_name': target_name
            }
            
            await update.message.reply_text(
                f"📝 Анонимное сообщение для {target_name}\n\n"
                f"Напишите ваше сообщение:"
            )
            return
        else:
            await update.message.reply_text("❌ Пользователь не найден")
            return
    
    # Обычный старт - создаем ссылку
    referral_code = hashlib.md5(f"anon_{user.id}".encode()).hexdigest()[:8]
    
    conn = sqlite3.connect('anon_bot.db')
    c = conn.cursor()
    c.execute('INSERT OR REPLACE INTO users (user_id, first_name, referral_code) VALUES (?, ?, ?)', 
              (user.id, user.first_name, referral_code))
    conn.commit()
    conn.close()
    
    # Очищаем состояние
    if user.id in user_states:
        del user_states[user.id]
    
    personal_link = f"https://t.me/AnonyMsgeBot?start={referral_code}"
    await update.message.reply_text(f"🔗 Ваша ссылка для анонимных сообщений:\n{personal_link}")

async def handle_message(update: Update, context):
    user = update.effective_user
    message_text = update.message.text
    
    print(f"MESSAGE: User {user.id}, text: {message_text}")
    
    # Проверяем состояние
    if user.id in user_states:
        state = user_states[user.id]
        target_user_id = state['target_user_id']
        target_name = state['target_name']
        
        print(f"SENDING: {user.id} -> {target_user_id}")
        
        # Сохраняем в базу
        conn = sqlite3.connect('anon_bot.db')
        c = conn.cursor()
        c.execute('INSERT INTO messages (from_user_id, to_user_id, message_text) VALUES (?, ?, ?)', 
                  (user.id, target_user_id, message_text))
        conn.commit()
        conn.close()
        
        # Отправляем получателю
        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text=f"💌 Новое анонимное сообщение:\n\n{message_text}"
            )
            await update.message.reply_text("✅ Сообщение отправлено анонимно!")
        except Exception as e:
            await update.message.reply_text("❌ Ошибка отправки")
        
        # Очищаем состояние
        del user_states[user.id]
    else:
        await update.message.reply_text("Напишите /start для получения ссылки")

def main():
    init_db()
    
    # Простая инициализация
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Минимальные обработчики
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🤖 Бот запущен")
    app.run_polling()

if __name__ == '__main__':
    main()
