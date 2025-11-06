#!/usr/bin/env python3
from telegram.ext import Application, CommandHandler

BOT_TOKEN = "8529950290:AAGkrleqXbaWAujfEgjfu_oh3pQxiCtjUDs"

async def start(update, context):
    await update.message.reply_text("✅ Бот работает! Тест успешен.")

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    print("Тестовый бот запущен...")
    app.run_polling()

if __name__ == '__main__':
    main()
