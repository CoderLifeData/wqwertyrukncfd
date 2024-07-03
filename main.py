import sqlite3
from aiogram import Bot, Dispatcher, executor, types, exceptions
from config import API_TOKEN, ADMIN_ID
import time
import re
import datetime
import asyncio


# Инициализация бота и диспетчера
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# Создание таблицы пользователей в базе данных
conn = sqlite3.connect('users.db')
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS users
             (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER UNIQUE, balance REAL DEFAULT 0.0, access_level INTEGER DEFAULT 0)''')
conn.commit()
conn.close()

def check_admin(user_id):
    """
    Функция проверяет, является ли пользователь администратором.
    Возвращает True, если пользователь является администратором, и False в противном случае.
    """
    conn = sqlite3.connect('users.db')
    c = conn.cursor()

    # Проверяем, совпадает ли ID пользователя с ADMIN_ID
    if user_id == ADMIN_ID:
        conn.close()
        return True

    # Проверяем, есть ли у пользователя access_level 1 в базе данных
    c.execute("SELECT access_level FROM users WHERE user_id = ?", (user_id,))
    access_level = c.fetchone()
    if access_level and access_level[0] == 1:
        conn.close()
        return True

    conn.close()
    return False



# Обработчик команды /start
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    user_id = message.from_user.id
    
    # Проверяем, есть ли пользователь в базе данных
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    user = c.fetchone()
    
    if not user:
        # Регистрируем нового пользователя
        c.execute("INSERT INTO users (user_id) VALUES (?)", (user_id,))
        conn.commit()
        await message.reply(f"Спасибо за регистрацию! Ваш идентификатор: <code>{user_id}</code>, уровень доступа: 0 (Пользователь)", parse_mode=types.ParseMode.HTML)
    else:
        access_level = user[3]
        access_level_name = "Пользователь" if access_level == 0 else "Администратор"
        await message.reply(f"Вы уже зарегистрированы. Ваш идентификатор: <code>{user[1]}</code>, уровень доступа: {access_level} ({access_level_name})", parse_mode=types.ParseMode.HTML)
    
    conn.close()

# Обработчик команды /balance
@dp.message_handler(commands=['balance'])
async def balance(message: types.Message):
    user_id = message.from_user.id
    
    # Получаем баланс пользователя из базы данных
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
    user_balance = c.fetchone()
    
    if user_balance:
        await message.reply(f"Ваш баланс: {user_balance[0]} монет")
    else:
        await message.reply("Произошла ошибка при получении вашего баланса.")
    
    conn.close()

# Обработчик команды /transfer
@dp.message_handler(commands=['transfer'])
async def transfer(message: types.Message):
    user_id = message.from_user.id
    
    # Получаем аргументы команды /transfer
    args = message.text.split()
    if len(args) != 3:
        await message.reply("Неправильный формат команды. Используйте: /transfer <сумма> <id получателя>")
        return
    
    if args[1] == "all":
        # Получаем баланс отправителя
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
        sender_balance = c.fetchone()
        if not sender_balance:
            await message.reply("Произошла ошибка при получении вашего баланса.")
            conn.close()
            return
        amount = sender_balance[0]
    else:
        amount = float(args[1])
    
    recipient_id = int(args[2])
    
    # Проверяем, есть ли пользователь в базе данных
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    
    # Получаем баланс отправителя
    c.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
    sender_balance = c.fetchone()
    if not sender_balance or sender_balance[0] < amount:
        await message.reply("Недостаточно средств для перевода.")
        return
    
    # Получаем баланс получателя
    c.execute("SELECT balance FROM users WHERE user_id=?", (recipient_id,))
    recipient_balance = c.fetchone()
    if not recipient_balance:
        await message.reply("Получатель не найден в базе данных.")
        return
    
    # Обновляем балансы
    c.execute("UPDATE users SET balance=? WHERE user_id=?", (sender_balance[0] - amount, user_id))
    c.execute("UPDATE users SET balance=? WHERE user_id=?", (recipient_balance[0] + amount, recipient_id))
    conn.commit()
    
    await message.reply(f"Перевод в размере {amount} монет выполнен успешно.")
    
    conn.close()
    
@dp.message_handler(commands=['give'])
async def give_command(message: types.Message):
    # Проверяем, является ли пользователь администратором
    user_id = message.from_user.id
    if not check_admin(user_id):
        await message.reply("У вас недостаточно прав на использование данной команды.")
        return
    
    # Получаем аргументы команды
    args = message.text.split()
    if len(args) != 3:
        await message.reply("Неправильный формат команды. Используйте: /give [кол-во] [айди]")
        return
    
    try:
        amount = int(args[1])
        recipient_id = int(args[2])
    except ValueError:
        await message.reply("Неправильный формат аргументов. Убедитесь, что вы ввели число.")
        return
    
    # Обновляем баланс получателя в базе данных
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT balance FROM users WHERE user_id=?", (recipient_id,))
    recipient_balance = c.fetchone()
    if recipient_balance:
        new_balance = recipient_balance[0] + amount
        c.execute("UPDATE users SET balance=? WHERE user_id=?", (new_balance, recipient_id))
        conn.commit()
        await message.reply(f"Вы успешно выдали {amount} монет пользователю с ID {recipient_id}.")
    else:
        await message.reply(f"Пользователь с ID {recipient_id} не найден в базе данных.")
    
    conn.close()

@dp.message_handler(commands=['clear'])
async def clear_command(message: types.Message):
    # Проверяем, является ли пользователь администратором
    user_id = message.from_user.id
    if not check_admin(user_id):
        await message.reply("У вас недостаточно прав на использование данной команды.")
        return

    # Получаем аргументы команды
    args = message.text.split()
    if len(args) != 3:
        await message.reply("Неправильный формат команды. Используйте: /clear [кол-во] [айди]")
        return

    try:
        amount = int(args[1])
        recipient_id = int(args[2])
    except ValueError:
        await message.reply("Неправильный формат аргументов. Убедитесь, что вы ввели число.")
        return

    # Обновляем баланс получателя в базе данных
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT balance FROM users WHERE user_id=?", (recipient_id,))
    recipient_balance = c.fetchone()
    if recipient_balance:
        new_balance = recipient_balance[0] - amount
        if new_balance < 0:
            new_balance = 0
        c.execute("UPDATE users SET balance=? WHERE user_id=?", (new_balance, recipient_id))
        conn.commit()
        await message.reply(f"Вы успешно удалили {amount} монет у пользователя с ID {recipient_id}.")
    else:
        await message.reply(f"Пользователь с ID {recipient_id} не найден в базе данных.")

    conn.close()

# Подключение к базе данных
conn = sqlite3.connect('users.db')
c = conn.cursor()

@dp.message_handler(commands=['profile'])
async def profile(message: types.Message):
    user_id = message.from_user.id
    user = message.from_user
    first_name = user.first_name

    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT user_id, balance, access_level FROM users WHERE user_id = ?", (user_id,))
    data = c.fetchone()

    if data:
        user_id, balance, access_level = data
        access_level_text = "Пользователь" if access_level == 0 else "🅰️Админ"
        msg = f"👤Имя: {first_name}\n🆔Айди: <code>{user_id}</code>\n💎Баланс: {balance}\n🔒Доступ: {access_level_text}"
        await message.answer(msg, parse_mode=types.ParseMode.HTML)
    else:
        await message.answer("Ваши данные не найдены в базе данных.")

    conn.close()

@dp.message_handler(commands=['agive'])
async def agive_command(message: types.Message):
    # Проверяем, является ли пользователь администратором
    user_id = message.from_user.id
    if not check_admin(user_id):
        await message.reply("У вас недостаточно прав на использование данной команды.")
        return

    # Получаем аргументы команды
    args = message.text.split()
    if len(args) != 3:
        await message.reply("Неправильный формат команды. Используйте: /agive [0 или 1] [айди пользователя]")
        return

    try:
        access_level = int(args[1])
        recipient_id = int(args[2])
    except ValueError:
        await message.reply("Неправильный формат аргументов. Убедитесь, что вы ввели число.")
        return

    # Обновляем access_level пользователя в базе данных
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("UPDATE users SET access_level=? WHERE user_id=?", (access_level, recipient_id))
    conn.commit()
    
    await message.reply(f"Вы успешно изменили уровень доступа пользователя с ID {recipient_id} на {access_level}.")

    conn.close()


@dp.message_handler(commands=['mute'])
async def mute_command(message: types.Message):
    # Получаем информацию об отправителе сообщения
    sender_id = message.from_user.id

    # Проверяем, является ли пользователь администратором
    if not check_admin(sender_id):
        await message.reply("У вас недостаточно прав на использование данной команды.")
        return

    # Регулярное выражение для поиска временного интервала и ID пользователя
    pattern = r'/mute (\d+)([smhd]) (\d+)'
    match = re.match(pattern, message.text)

    if match:
        time_amount = int(match.group(1))
        time_unit = match.group(2)
        user_id = int(match.group(3))

        # Определяем продолжительность мута в зависимости от указанного временного интервала
        if time_unit == 's':
            duration = datetime.timedelta(seconds=time_amount)
        elif time_unit == 'm':
            duration = datetime.timedelta(minutes=time_amount)
        elif time_unit == 'h':
            duration = datetime.timedelta(hours=time_amount)
        elif time_unit == 'd':
            duration = datetime.timedelta(days=time_amount)
        else:
            await message.reply("Неправильно указано время мута.")
            return

        try:
            await restrict_user(message, user_id, duration)
            await message.reply("Пользователь успешно замучен на {} {}.".format(time_amount, time_unit))
        except exceptions.BadRequest:
            await message.reply("Не удалось замутить пользователя. Ошибка: {e}.")
    else:
        await message.reply("Неправильный формат команды. Используйте /mute [время]s/m/h/d [id].")

async def restrict_user(message, user_id, duration):
    # Ограничиваем пользователя
    await dp.bot.restrict_chat_member(
        chat_id=message.chat.id,
        user_id=user_id,
        permissions=types.ChatPermissions(can_send_messages=False),
        until_date=datetime.datetime.now() + duration
    )

    # Сохраняем время окончания ограничения
    end_time = datetime.datetime.now() + duration

    # Ждем окончания ограничения и снимаем его
    while True:
        if datetime.datetime.now() >= end_time:
            await dp.bot.restrict_chat_member(
                chat_id=message.chat.id,
                user_id=user_id,
                permissions=types.ChatPermissions(can_send_messages=True)
            )


import datetime
import asyncio
from aiogram import types
from aiogram.utils import exceptions

@dp.message_handler(commands=['ban'])
async def ban_command(message: types.Message):
    # Получаем информацию об отправителе сообщения
    sender_id = message.from_user.id

    # Проверяем, является ли пользователь администратором
    if not check_admin(sender_id):
        await message.reply("У вас недостаточно прав на использование данной команды.")
        return

    # Регулярное выражение для поиска временного интервала и ID пользователя
    pattern = r'/ban (\d+)([smhd]) (\d+)'
    match = re.match(pattern, message.text)

    if match:
        time_amount = int(match.group(1))
        time_unit = match.group(2)
        user_id = int(match.group(3))

        # Определяем продолжительность бана в зависимости от указанного временного интервала
        if time_unit == 's':
            duration = datetime.timedelta(seconds=time_amount)
        elif time_unit == 'm':
            duration = datetime.timedelta(minutes=time_amount)
        elif time_unit == 'h':
            duration = datetime.timedelta(hours=time_amount)
        elif time_unit == 'd':
            duration = datetime.timedelta(days=time_amount)
        else:
            await message.reply("Неправильно указано время бана.")
            return

        try:
            await restrict_user(message, user_id, duration)
            await message.reply("Пользователь успешно забанен на {} {}.".format(time_amount, time_unit))
        except exceptions.BadRequest:
            await message.reply("Не удалось забанить пользователя.")
    else:
        await message.reply("Неправильный формат команды. Используйте /ban [время]s/m/h/d [id].")

async def restrict_user(message, user_id, duration):
    # Удаляем пользователя из чата и добавляем в черный список
    await dp.bot.kick_chat_member(
        chat_id=message.chat.id,
        user_id=user_id,
        until_date=datetime.datetime.now() + duration
    )

    # Запускаем задачу на фоне для восстановления пользователя после окончания бана
    asyncio.create_task(unban_user(message.chat.id, user_id, duration))

async def unban_user(chat_id, user_id, duration):
    # Ждем окончания бана
    await asyncio.sleep(duration.total_seconds())

    # Восстанавливаем пользователя в чате
    try:
        await dp.bot.unban_chat_member(
            chat_id=chat_id,
            user_id=user_id
        )
    except exceptions.BadRequest:
        pass



@dp.message_handler(commands=['unban'])
async def unban_command(message: types.Message):
    # Проверяем, является ли пользователь администратором
    user_id = message.from_user.id
    if not check_admin(user_id):
        await message.reply("У вас недостаточно прав на использование данной команды.")
        return

    # Получаем аргументы команды
    args = message.text.split()
    if len(args) != 2:
        await message.reply("Неправильный формат команды. Используйте: /unban [айди пользователя]")
        return

    try:
        recipient_id = int(args[1])
    except ValueError:
        await message.reply("Неправильный формат аргумента. Убедитесь, что вы ввели число.")
        return

    # Разблокируем пользователя в чате
    try:
        await dp.bot.unban_chat_member(
            chat_id=message.chat.id,
            user_id=recipient_id
        )
        await message.reply(f"Пользователь с ID {recipient_id} был успешно разблокирован.")
    except exceptions.BadRequest as e:
        await message.reply(f"Не удалось разблокировать пользователя. Ошибка: {e}")

async def unban_user(chat_id, user_id, duration):
    # Ждем окончания бана
    await asyncio.sleep(duration.total_seconds())

    # Восстанавливаем пользователя в чате
    try:
        await dp.bot.unban_chat_member(
            chat_id=chat_id,
            user_id=user_id
        )
    except exceptions.BadRequest:
        pass


@dp.message_handler(commands=['unmute'])
async def unmute_command(message: types.Message):
    # Проверяем, является ли пользователь администратором
    user_id = message.from_user.id
    if not check_admin(user_id):
        await message.reply("У вас недостаточно прав на использование данной команды.")
        return

    # Получаем аргументы команды
    args = message.text.split()
    if len(args) != 2:
        await message.reply("Неправильный формат команды. Используйте: /unmute [айди пользователя]")
        return

    try:
        recipient_id = int(args[1])
    except ValueError:
        await message.reply("Неправильный формат аргумента. Убедитесь, что вы ввели число.")
        return

    # Разрешаем пользователю писать в чате
    try:
        await dp.bot.restrict_chat_member(
            chat_id=message.chat.id,
            user_id=recipient_id,
            permissions=types.ChatPermissions(can_send_messages=True)
        )
        await message.reply(f"Пользователь с ID {recipient_id} теперь может писать в чате.")
    except exceptions.BadRequest as e:
        await message.reply(f"Не удалось разрешить пользователю писать в чате. Ошибка: {e}")


@dp.message_handler(commands=['aprofile'])
async def aprofile_command(message: types.Message):
    # Получаем информацию об отправителе сообщения
    sender_id = message.from_user.id

    # Проверяем, является ли пользователь администратором
    if not check_admin(sender_id):
        await message.reply("У вас недостаточно прав на использование данной команды.")
        return

    # Проверяем, было ли сообщение ответом на другое сообщение
    if message.reply_to_message:
        user_id = message.reply_to_message.from_user.id
        first_name = message.reply_to_message.from_user.first_name
        # Получаем профиль пользователя из базы данных
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute("SELECT balance, access_level FROM users WHERE user_id = ?", (user_id,))
        data = c.fetchone()

        if data:
            balance, access_level = data
            access_level_text = "Пользователь" if access_level == 0 else "🅰️Админ"
            msg = f"👤Имя: {first_name}\n🆔Айди: <code>{user_id}</code>\n💎Баланс: {balance}\n🔒Доступ: {access_level_text}"
            await message.answer(msg, parse_mode=types.ParseMode.HTML)
        else:
            await message.reply("Пользователь с таким ID не найден в базе данных.")
    else:
        await message.reply("Эта команда должна быть использована в ответ на сообщение пользователя.")


@dp.message_handler(commands=['help'])
async def help_command(message: types.Message):
    await message.reply("Список команд:\n/start - запуск бота\n/balance - посмотреть баланс\n/transfer [кол-во/all] [id] - передать деньги\n"
"/profile - посмотреть свой профиль\n/help - помощь по командам\n\nАДМИН КОМАНДЫ\n/give [кол-во] [id] - выдать coin\n"
"/clear [кол-во] [id] - забрать coin\n/agive [0/1] [id] - доступ\n/ban [time:s/m/h/d] [id] - бан\n"
"/mute [time:s/m/h/d] [id] - мут\n/unban [id] - разбан\n/unmute [id] - размут\n/aprofile [id] - показывает профиль по ID\n/abalance [id] - показывает баланс")


@dp.message_handler(commands=['abalance'])
async def admin_balance(message: types.Message):
    # Получаем информацию об отправителе сообщения
    sender_id = message.from_user.id
    
    # Проверяем, является ли пользователь администратором
    if not check_admin(sender_id):
        await message.reply("У вас недостаточно прав на использование данной команды.")
        return

    # Разбиваем текст сообщения на аргументы
    args = message.text.split()
    
    if len(args) != 2:
        await message.reply("Неправильный формат команды. Используйте /abalance [айди].")
        return

    user_id = int(args[1])

    # Получаем баланс пользователя из базы данных
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
    user_balance = c.fetchone()
    
    if user_balance:
        await message.reply(f"Баланс пользователя с ID {user_id}: {user_balance[0]} монет")
    else:
        await message.reply("Произошла ошибка при получении баланса пользователя.")
    
    conn.close()

@dp.message_handler(commands=['debug'])
async def help_command(message: types.Message):
    try:
        # Здесь может быть код, который вызывает потенциальные ошибки при запуске
        await message.reply("Bot Active✅")
    except Exception as e:
        await message.reply("Found Errors❌: {e}.")

@dp.message_handler(commands=['errordebug'])
async def help_command(message: types.Message):
    try:
        # Вызываем исключение для проверки обработки ошибок
        raise Exception("Debug Error")
        await message.reply("Bot Active✅")
    except Exception as e:
        await message.reply(f"Found Errors: {str(e)}")

@dp.message_handler(commands=['say'])
async def say_command(message: types.Message):
    sender_id = message.from_user.id
    if not check_admin(sender_id):
        await message.reply("У вас недостаточно прав на использование данной команды.")
        return

    try:
        # Получаем текст после команды /say
        text = message.text.split('/say ', 1)[1]
        await message.reply(text)
    except IndexError:
        await message.reply("Пожалуйста укажите аргументы после /say команды")






# Запускаем бота
if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
























# Запуск бота
if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
