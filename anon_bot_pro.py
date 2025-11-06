#!/usr/bin/env python3
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
import sqlite3
import hashlib
from datetime import datetime, timedelta

BOT_TOKEN = "8529950290:AAGkrleqXbaWAujfEgjfu_oh3pQxiCtjUDs"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Глобальные переменные для состояний
user_states = {}

def init_db():
    conn = sqlite3.connect('anon_bot.db')
    c = conn.cursor()
    
    # Удаляем старые таблицы если есть
    c.execute('DROP TABLE IF EXISTS users')
    c.execute('DROP TABLE IF EXISTS messages')
    c.execute('DROP TABLE IF EXISTS threads')
    c.execute('DROP TABLE IF EXISTS bot_stats')
    
    # Создаем новые таблицы с правильной структурой
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            referral_code TEXT UNIQUE,
            message_count INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_activity DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_user_id INTEGER,
            to_user_id INTEGER,
            message_text TEXT,
            is_reply BOOLEAN DEFAULT FALSE,
            thread_id INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS threads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user1_id INTEGER,
            user2_id INTEGER,
            last_activity DATETIME DEFAULT CURRENT_TIMESTAMP,
            message_count INTEGER DEFAULT 0
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS bot_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stat_date DATE UNIQUE,
            total_users INTEGER DEFAULT 0,
            new_users INTEGER DEFAULT 0,
            active_users INTEGER DEFAULT 0,
            messages_sent INTEGER DEFAULT 0,
            threads_created INTEGER DEFAULT 0
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ База данных создана заново")

def update_user_activity(user_id):
    """Обновляем время последней активности пользователя"""
    conn = sqlite3.connect('anon_bot.db')
    c = conn.cursor()
    c.execute('UPDATE users SET last_activity = CURRENT_TIMESTAMP WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()

def get_bot_statistics():
    """Получаем полную статистику бота"""
    conn = sqlite3.connect('anon_bot.db')
    c = conn.cursor()
    
    # Общее количество пользователей
    c.execute('SELECT COUNT(*) FROM users')
    total_users = c.fetchone()[0]
    
    # Новые пользователи за последние 7 дней
    week_ago = datetime.now() - timedelta(days=7)
    c.execute('SELECT COUNT(*) FROM users WHERE created_at > ?', (week_ago,))
    new_users_week = c.fetchone()[0]
    
    # Активные пользователи за последние 7 дней
    c.execute('SELECT COUNT(*) FROM users WHERE last_activity > ?', (week_ago,))
    active_users = c.fetchone()[0]
    
    # Всего сообщений
    c.execute('SELECT COUNT(*) FROM messages')
    total_messages = c.fetchone()[0]
    
    # Сообщения за последние 7 дней
    c.execute('SELECT COUNT(*) FROM messages WHERE created_at > ?', (week_ago,))
    messages_week = c.fetchone()[0]
    
    # Всего тредов
    c.execute('SELECT COUNT(*) FROM threads')
    total_threads = c.fetchone()[0]
    
    # Самые активные пользователи
    c.execute('''
        SELECT u.first_name, u.message_count, COUNT(m.id) as sent_count
        FROM users u
        LEFT JOIN messages m ON u.user_id = m.from_user_id
        GROUP BY u.user_id
        ORDER BY u.message_count DESC
        LIMIT 5
    ''')
    top_users = c.fetchall()
    
    conn.close()
    
    return {
        'total_users': total_users,
        'new_users_week': new_users_week,
        'active_users': active_users,
        'total_messages': total_messages,
        'messages_week': messages_week,
        'total_threads': total_threads,
        'top_users': top_users
    }

def get_user_stats(user_id):
    conn = sqlite3.connect('anon_bot.db')
    c = conn.cursor()
    
    # Количество полученных сообщений
    c.execute('SELECT COUNT(*) FROM messages WHERE to_user_id = ?', (user_id,))
    received = c.fetchone()[0]
    
    # Количество отправленных сообщений
    c.execute('SELECT COUNT(*) FROM messages WHERE from_user_id = ?', (user_id,))
    sent = c.fetchone()[0]
    
    # Количество тредов
    c.execute('SELECT COUNT(*) FROM threads WHERE user1_id = ? OR user2_id = ?', (user_id, user_id))
    threads_count = c.fetchone()[0]
    
    conn.close()
    return received, sent, threads_count

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args
    
    # Обновляем активность пользователя
    update_user_activity(user.id)
    
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
            
            # Сохраняем состояние для отправки сообщения
            user_states[user.id] = {
                'action': 'sending_message',
                'target_user_id': target_user_id,
                'target_name': target_name
            }
            
            keyboard = [
                [InlineKeyboardButton("❌ Отмена", callback_data="cancel_send")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"💌 <b>Анонимное сообщение для {target_name}</b>\n\n"
                f"Напишите ваше сообщение ниже:\n\n"
                f"<i>Сообщение будет доставлено полностью анонимно</i>",
                reply_markup=reply_markup,
                parse_mode="HTML"
            )
            return
        else:
            await update.message.reply_text("❌ Пользователь не найден.")
            return
    
    # Обычный старт
    await show_main_interface(update, user)

async def show_main_interface(update, user):
    # Регистрируем/обновляем пользователя
    referral_code = hashlib.md5(f"anon_{user.id}_{datetime.now().timestamp()}".encode()).hexdigest()[:10]
    
    conn = sqlite3.connect('anon_bot.db')
    c = conn.cursor()
    c.execute('''
        INSERT OR REPLACE INTO users (user_id, username, first_name, last_name, referral_code, last_activity)
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    ''', (user.id, user.username, user.first_name, user.last_name, referral_code))
    conn.commit()
    conn.close()
    
    # Получаем статистику
    received_count, sent_count, threads_count = get_user_stats(user.id)
    personal_link = f"https://t.me/AnonyMsgeBot?start={referral_code}"
    
    # Основной интерфейс
    welcome_text = f"""
🎭 <b>Анонимные сообщения</b>

┌─────────────────
│ 📊 <b>Ваша статистика:</b>
│ 💌 Получено сообщений: <b>{received_count}</b>
│ 📤 Отправлено сообщений: <b>{sent_count}</b>
│ 💬 Активных диалогов: <b>{threads_count}</b>
└─────────────────

🔗 <b>Ваша ссылка:</b>
<a href="{personal_link}">{personal_link}</a>

<i>Поделитесь ссылкой чтобы получать анонимные сообщения!</i>
"""
    
    keyboard = [
        [InlineKeyboardButton("📤 Поделиться ссылкой", 
             url=f"https://t.me/share/url?url={personal_link}&text=💌%20Отправь%20мне%20анонимное%20сообщение!")],
        [InlineKeyboardButton("📨 Мои сообщения", callback_data="my_messages"),
         InlineKeyboardButton("📊 Статистика", callback_data="bot_stats")],
        [InlineKeyboardButton("ℹ️ Помощь", callback_data="help")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        welcome_text,
        reply_markup=reply_markup,
        parse_mode="HTML"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    message_text = update.message.text
    
    # Обновляем активность пользователя
    update_user_activity(user.id)
    
    # Проверяем состояние пользователя
    if user.id in user_states:
        state = user_states[user.id]
        
        if state['action'] == 'sending_message':
            target_user_id = state['target_user_id']
            target_name = state['target_name']
            
            # Создаем или находим тред
            thread_id = get_or_create_thread(user.id, target_user_id)
            
            # Сохраняем сообщение
            conn = sqlite3.connect('anon_bot.db')
            c = conn.cursor()
            c.execute('''
                INSERT INTO messages (from_user_id, to_user_id, message_text, thread_id)
                VALUES (?, ?, ?, ?)
            ''', (user.id, target_user_id, message_text, thread_id))
            
            # Обновляем счетчик сообщений пользователя
            c.execute('UPDATE users SET message_count = message_count + 1 WHERE user_id = ?', (target_user_id,))
            conn.commit()
            conn.close()
            
            # Отправляем уведомление получателю
            try:
                keyboard = [
                    [InlineKeyboardButton("💌 Ответить анонимно", callback_data=f"reply_{thread_id}")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await context.bot.send_message(
                    chat_id=target_user_id,
                    text=f"💌 <b>У вас новое анонимное сообщение!</b>\n\n{message_text}",
                    reply_markup=reply_markup,
                    parse_mode="HTML"
                )
                
                await update.message.reply_text(
                    "✅ <b>Сообщение отправлено анонимно!</b>\n\n"
                    f"Получатель: {target_name}",
                    parse_mode="HTML"
                )
                
            except Exception as e:
                await update.message.reply_text("❌ Не удалось отправить сообщение")
            
            # Очищаем состояние
            del user_states[user.id]
            return
        
        elif state['action'] == 'replying':
            thread_id = state['thread_id']
            
            # Находим собеседника в треде
            conn = sqlite3.connect('anon_bot.db')
            c = conn.cursor()
            c.execute('SELECT user1_id, user2_id FROM threads WHERE id = ?', (thread_id,))
            thread = c.fetchone()
            
            if thread:
                user1_id, user2_id = thread
                target_user_id = user1_id if user1_id != user.id else user2_id
                
                # Сохраняем ответ
                c.execute('''
                    INSERT INTO messages (from_user_id, to_user_id, message_text, thread_id, is_reply)
                    VALUES (?, ?, ?, ?, TRUE)
                ''', (user.id, target_user_id, message_text, thread_id))
                
                # Обновляем тред
                c.execute('UPDATE threads SET last_activity = CURRENT_TIMESTAMP, message_count = message_count + 1 WHERE id = ?', (thread_id,))
                conn.commit()
                conn.close()
                
                # Отправляем ответ
                try:
                    keyboard = [
                        [InlineKeyboardButton("💌 Ответить", callback_data=f"reply_{thread_id}")]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    
                    await context.bot.send_message(
                        chat_id=target_user_id,
                        text=f"💌 <b>Новый ответ в анонимном диалоге!</b>\n\n{message_text}",
                        reply_markup=reply_markup,
                        parse_mode="HTML"
                    )
                    
                    await update.message.reply_text("✅ <b>Ответ отправлен!</b>", parse_mode="HTML")
                    
                except Exception as e:
                    await update.message.reply_text("❌ Не удалось отправить ответ")
            
            # Очищаем состояние
            del user_states[user.id]
            return
    
    # Если не в состоянии отправки - показываем подсказку
    await update.message.reply_text(
        "💌 Напишите /start чтобы получить вашу ссылку для анонимных сообщений!"
    )

def get_or_create_thread(user1_id, user2_id):
    conn = sqlite3.connect('anon_bot.db')
    c = conn.cursor()
    
    # Ищем существующий тред
    c.execute('''
        SELECT id FROM threads 
        WHERE (user1_id = ? AND user2_id = ?) OR (user1_id = ? AND user2_id = ?)
    ''', (user1_id, user2_id, user2_id, user1_id))
    
    thread = c.fetchone()
    
    if thread:
        thread_id = thread[0]
        # Обновляем время последней активности
        c.execute('UPDATE threads SET last_activity = CURRENT_TIMESTAMP, message_count = message_count + 1 WHERE id = ?', (thread_id,))
    else:
        # Создаем новый тред
        c.execute('''
            INSERT INTO threads (user1_id, user2_id, message_count)
            VALUES (?, ?, 1)
        ''', (user1_id, user2_id))
        thread_id = c.lastrowid
    
    conn.commit()
    conn.close()
    return thread_id

async def show_my_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    
    conn = sqlite3.connect('anon_bot.db')
    c = conn.cursor()
    
    # Получаем последние треды
    c.execute('''
        SELECT t.id, 
               CASE 
                   WHEN t.user1_id = ? THEN u2.first_name 
                   ELSE u1.first_name 
               END as partner_name,
               t.message_count,
               t.last_activity
        FROM threads t
        LEFT JOIN users u1 ON t.user1_id = u1.user_id
        LEFT JOIN users u2 ON t.user2_id = u2.user_id
        WHERE t.user1_id = ? OR t.user2_id = ?
        ORDER BY t.last_activity DESC
        LIMIT 10
    ''', (user.id, user.id, user.id))
    
    threads = c.fetchall()
    conn.close()
    
    if not threads:
        await query.edit_message_text(
            "📭 <b>У вас пока нет сообщений</b>\n\n"
            "Поделитесь своей ссылкой чтобы начать получать анонимные сообщения!",
            parse_mode="HTML"
        )
        return
    
    messages_text = "💬 <b>Ваши диалоги:</b>\n\n"
    
    for thread in threads:
        thread_id, partner_name, msg_count, last_activity = thread
        messages_text += f"👤 {partner_name}\n"
        messages_text += f"   📨 Сообщений: {msg_count}\n"
        messages_text += f"   💬 Нажмите 'Ответить' под сообщением\n\n"
    
    await query.edit_message_text(
        messages_text,
        parse_mode="HTML"
    )

async def show_bot_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    stats = get_bot_statistics()
    
    stats_text = f"""
📊 <b>Статистика бота</b>

┌─────────────────
│ 👥 <b>Пользователи:</b>
│   Всего: <b>{stats['total_users']}</b>
│   Новые (7 дней): <b>{stats['new_users_week']}</b>
│   Активные (7 дней): <b>{stats['active_users']}</b>
├─────────────────
│ 💌 <b>Сообщения:</b>
│   Всего: <b>{stats['total_messages']}</b>
│   За 7 дней: <b>{stats['messages_week']}</b>
├─────────────────
│ 💬 <b>Диалоги:</b>
│   Всего тредов: <b>{stats['total_threads']}</b>
└─────────────────

🏆 <b>Топ пользователей:</b>
"""
    
    for i, (name, received, sent) in enumerate(stats['top_users'], 1):
        stats_text += f"{i}. {name} - 📨{received} 📤{sent}\n"
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        stats_text,
        reply_markup=reply_markup,
        parse_mode="HTML"
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data == "my_messages":
        await show_my_messages(update, context)
    
    elif data == "bot_stats":
        await show_bot_stats(update, context)
    
    elif data == "back_to_main":
        await show_main_interface(update, query.from_user)
    
    elif data == "help":
        help_text = """
🆘 <b>Помощь по боту</b>

💫 <b>Как получать сообщения:</b>
1. Поделитесь своей ссылкой из /start
2. Друзья переходят по ней и пишут вам
3. Получайте анонимные сообщения здесь!

✉️ <b>Как отправлять сообщения:</b>
1. Попросите друга прислать его ссылку
2. Перейдите по ссылке
3. Напишите сообщение — оно придёт анонимно

📊 <b>Статистика:</b>
• Нажмите кнопку "Статистика" чтобы увидеть аналитику бота
"""
        await query.edit_message_text(help_text, parse_mode="HTML")
    
    elif data == "cancel_send":
        if query.from_user.id in user_states:
            del user_states[query.from_user.id]
        await query.edit_message_text("❌ Отправка сообщения отменена")
    
    elif data.startswith("reply_"):
        thread_id = int(data.split("_")[1])
        user_states[query.from_user.id] = {
            'action': 'replying',
            'thread_id': thread_id
        }
        
        await query.edit_message_text(
            "💌 <b>Ответ на анонимное сообщение</b>\n\n"
            "Напишите ваш ответ:",
            parse_mode="HTML"
        )

def main():
    init_db()
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🎭 Продвинутый анонимный бот запущен!")
    print("📊 Статистика доступна по кнопке 'Статистика'")
    application.run_polling()

if __name__ == '__main__':
    main()
