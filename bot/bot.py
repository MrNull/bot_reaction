import asyncio

from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest
from dotenv import load_dotenv
import os


from aiogram import Bot, Dispatcher, types
from aiogram.types import ReactionTypeEmoji, Message, CallbackQuery, ChatMemberUpdated
from aiogram.enums import ChatType
from aiogram.filters import Command, ChatMemberUpdatedFilter, IS_NOT_MEMBER, JOIN_TRANSITION
import logging
from pythonjsonlogger import jsonlogger

from apscheduler.schedulers.asyncio import AsyncIOScheduler

import texts
import keyboards
import database
import validation


load_dotenv()
API_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = os.getenv('ADMIN_ID')
#ADMIN_CHAT = os.getenv('ADMIN_ID')

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Создаём логгер
logger = logging.getLogger("bot")
logger.setLevel(logging.INFO)

# Хэндлер — в stdout (чтобы Docker / systemd / Promtail их видел)
handler = logging.StreamHandler()

# Формат — JSON (удобно для Loki/Grafana)
formatter = jsonlogger.JsonFormatter(
    '%(asctime)s %(name)s %(levelname)s %(message)s',
    timestamp=True
)
handler.setFormatter(formatter)
logger.addHandler(handler)


async def daily_task():
    """Ежедневная статистика за день для администратора"""
    users = await database.get_new_users_24hours()
    await bot.send_message(ADMIN_ID, f'Новых юзеров за сегодня: {users}')


async def _(user_id: int, key: str):
    """Получает перевод в зависимости от языка пользователя"""
    lang = await database.get_user_language(user_id)
    return texts.translations.get(key, {}).get(lang, "⚠️ Translation not found")


async def _f(user_id: int, key: str, **kwargs):
    """
    Возвращает переведённую строку для пользователя с учётом языка.
    Позволяет подставлять значения в шаблон через {placeholders}.
    """
    lang = await database.get_user_language(user_id)
    template = texts.translations.get(key, {}).get(lang)

    if not template:
        return "⚠️ Translation not found"
    try:
        return template.format(**kwargs)
    except KeyError as e:
        return f"⚠️ Missing placeholder {e.args[0]} in translation template"


async def get_button_key_by_text(user_text: str) -> str | None:
    """Возвращает ключ кнопки (например 'button_settings') по тексту, который пришёл от пользователя"""
    for key, langs in texts.translations_buttons.items():
        if user_text in langs.values():
            return key
    return None


def is_valid_reaction(emoji: str) -> bool:
    """
    Проверяет, является ли переданный emoji допустимой реакцией Telegram.
    Возвращает True/False.
    """
    if not emoji or len(emoji.strip()) == 0:
        return False
    return emoji in validation.VALID_REACTIONS


async def get_message(message):
    """Обработка всех сообщений полученных в личку бота"""
    user_id = message.chat.id
    language = await database.get_user_language(user_id)
    button_key = await get_button_key_by_text(message.text)
    user_status = await database.get_user_status(user_id)

    if button_key == "button_settings":
        keyboard = await keyboards.settings_keyboard(language)
        await bot.send_message(user_id, await _(user_id, "bot_settings"), reply_markup = keyboard)
        return

    elif button_key == "button_help":
        await bot.send_message(user_id, await _(user_id, "help"), parse_mode='HTML')
        return

    elif button_key == "button_set_reaction_channel":
        user_channels = await database.get_user_channels(user_id)
        if not user_channels:
            await bot.send_message(user_id, await _(user_id, "user_not_have_channels"), parse_mode='HTML')

        else:
            keyboard = await keyboards.inline_keyboard_user_channels(user_channels, language)
            await bot.send_message(user_id, await _(user_id, "user_channels"),reply_markup=keyboard, parse_mode='HTML')
        return

    if user_status.status == 'WAITING_USER_CHANNEL_REACTION':
        valid_reaction = await validation.is_valid_reaction(message.text)
        if valid_reaction:
            res = await database.set_channel_reaction(user_status.data, message.text)
            await bot.send_message(user_id, await _f(user_id, "added_channel_reaction", reaction=message.text), parse_mode='HTML')
            await database.set_user_status(user_id, 0, 0)

        else:
            await bot.send_message(user_id, await _(user_id, "wrong_reaction"), parse_mode='HTML')
        return

    elif user_status.status == 'WAITING_USER_CHAT_REACTION':
        valid_reaction = await validation.is_valid_reaction(message.text)
        if valid_reaction:
            res = await database.set_chat_reaction(user_status.data, user_id, message.text)
            await bot.send_message(user_id, await _f(user_id, "added_chat_reaction_myself", reaction=message.text), parse_mode='HTML')
            await database.set_user_status(user_id, 0, 0)

        else:
            await bot.send_message(user_id, await _(user_id, "wrong_reaction"), parse_mode='HTML')
        return


async def check_bot_permissions(chat):
    """Проверка, является ли бот админом"""
    try:
        member = await bot.get_chat_member(chat_id=chat, user_id=bot.id)
        channel = await database.get_channel(chat)

        if member.status != "administrator":
            if channel.chat_type == "group" or "supergroup":  # Если это группа, то она могла преобразоваться в супергруппу и у неё отлетел старый id
                return False, "⚠️ Бот не является администратором в чате. Добавьте бота в администраторы."

        return True, "✅ Бот имеет все необходимые права в чате!"

    except TelegramForbiddenError:
        return False, "🚫 Бот не может получить информацию о чате — доступ запрещён"


async def admin_keyboard_channel_settings(user_id, channel_id, message):
    """Получение всех данных о канале и перерисовка инлайн клавиатуры"""
    language = await database.get_user_language(user_id)
    keyboard = await keyboards.inline_keyboard_admin_channel_setting(channel_id, language)
    channel_reaction = await database.get_channel_reaction(channel_id)
    if not channel_reaction.emoji:
        channel_reaction.emoji = '-'
    text = await _f(user_id,
                    "channel_settings",
                    reaction=channel_reaction.emoji)
    await message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")


async def admin_keyboard_chat_settings(user_id, chat_id, message):
    """Получение данных о чате и перерисовка клавиатуры"""
    language = await database.get_user_language(user_id)
    keyboard = await keyboards.inline_keyboard_admin_chat_setting(chat_id, language)
    chat_reaction = await database.get_chat_reaction(chat_id, user_id)
    if not chat_reaction.emoji:
        chat_reaction.emoji = '-'
    text = await _f(user_id,
                    "chat_settings",
                    reaction=chat_reaction.emoji)
    await message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")


@dp.message(Command(commands=['start']))
async def send_welcome(message: Message):

    user_id = message.from_user.id
    new_user = await database.check_and_add_user(user_id, message.from_user.username, message.from_user.language_code, message.from_user.full_name)
    if new_user == True:
        await bot.send_message(user_id,"🌍 Choose your language:", reply_markup=keyboards.language_keyboard())

    elif new_user == False:
        lang_code = await database.get_user_language(user_id)
        keyboard = await keyboards.start_keyboard(lang_code)
        await bot.send_message(user_id, await _(user_id, "welcome"), reply_markup=keyboard, parse_mode='HTML')


@dp.message(Command(commands=['help']))
async def send_help(message: Message):
    user_id = message.from_user.id
    await bot.send_message(user_id, await _(user_id, "help"), parse_mode='HTML')



@dp.channel_post()
async def on_new_post(message: types.Message):
    """Проставление реакции на пост в канале"""
    channel_id = message.chat.id

    # Проверяем, что это канал
    if message.chat.type == ChatType.CHANNEL:
        channel_reaction = await database.get_channel_reaction(channel_id)
        if channel_reaction:
            if channel_reaction.active == True:
                try:
                    # Добавляем реакцию
                    await bot.set_message_reaction(
                        chat_id=message.chat.id,
                        message_id=message.message_id,
                        reaction=[ReactionTypeEmoji(emoji=channel_reaction.emoji)]
                    )
                    logger.info("Reaction added", extra={
                        "event": "reaction_added",
                        "emoji": channel_reaction.emoji,
                        "channel_id": channel_id
                    })
                except Exception as error:
                    # Если не получилось поставить реакцию, то пишем об ошибке админу канала
                    logging.error(f"Ошибка при добавлении реакции {message.message_id} в канале {channel_id}: {error}")
                    user_id = await database.check_and_get_admin(channel_id)
                    await bot.send_message(
                        user_id,
                        await _f(user_id,
                                 "error_added_channel_reaction",
                                 error=error,
                                 channel_id=channel_id,
                                 message_id=message.message_id),
                                           parse_mode='HTML')
                    logger.error("Failed to add reaction", extra={
                        "event": "reaction_failed",
                        "error": error,
                        "channel_id": channel_id
                    })
                    return

                try:
                    await database.add_reaction(channel_id, message.message_id, channel_reaction.emoji, 0)
                except Exception as db_error:
                    logger.error("Failed to add reaction db", extra={
                        "event": "failed_db",
                        "error": db_error,
                        "channel_id": channel_id
                    })


@dp.my_chat_member(ChatMemberUpdatedFilter(member_status_changed=JOIN_TRANSITION))
async def bot_added_as_admin(event: types.ChatMemberUpdated):
    # Проверяем, что бот добавлен в канал и имеет статус администратора
    user_id = event.from_user.id
    if event.new_chat_member.status in ['administrator', 'creator', 'member']: # бот добавлен админом
        channel_id = event.chat.id

        print(channel_id, event.chat.title, event.chat.username, event.from_user.id, event.from_user.first_name, event.from_user.username)
        await database.bot_add_chat(channel_id, event.chat.type, event.new_chat_member.status, event.chat.title, event.chat.username, event.from_user.id, event.from_user.first_name, event.from_user.username)
        if event.new_chat_member.status in ['administrator', 'creator']:
            await bot.send_message(
                user_id,
                await _f(
                    user_id,
                    "bot_added_in_channel",
                    channel_id=channel_id,
                    chat_title=event.chat.title
                ),
                parse_mode='HTML'
            )
            await bot.send_message(ADMIN_ID, f"✅ Бот добавлен в канал с ID {channel_id}\nНазвание канала: {event.chat.title}")
            return

        elif event.new_chat_member.status in ['member']: # бот добавлен подписчиком
            await bot.send_message(
                user_id,
                await _f(
                    user_id,
                    "bot_added_in_chat_not_admin",
                    channel_id=channel_id,
                    chat_title=event.chat.title
                ),
                parse_mode='HTML'
            )
            await bot.send_message(ADMIN_ID, f"✅ Бот добавлен в чат с ID {channel_id}\nНазвание чата: {event.chat.title}")
            return


@dp.my_chat_member(ChatMemberUpdatedFilter(member_status_changed=IS_NOT_MEMBER))
async def bot_removed_as_admin(event: types.ChatMemberUpdated):
    #  бот удален из канала или потерял статус администратора
    if event.new_chat_member.status in ['left', 'kicked']:
        channel_id = event.chat.id
        await database.bot_delete_chat(channel_id)

        await bot.send_message(ADMIN_ID, f"Бот удален из админов канала с ID {channel_id}")
        return



@dp.message()
async def echo_handler(message: types.Message) -> None:
    """Получение всех сообщений"""
    chat_id = message.chat.id
    user_id = message.from_user.id
    # Если сообщение в чате, то проверяем нужно ли ставить реакцию автору поста
    if message.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
        reaction_chat = await database.get_chat_reaction(chat_id, user_id)
        if reaction_chat:
            try:
                await bot.set_message_reaction(
                    chat_id=message.chat.id,
                    message_id=message.message_id,
                    reaction=[ReactionTypeEmoji(emoji=reaction_chat.emoji)],
                )
                logger.info("Reaction added", extra={
                    "event": "reaction_added",
                    "emoji": reaction_chat.emoji,
                    "channel_id": chat_id
                })
            except Exception as error:
                user_id = await database.check_and_get_admin(chat_id)
                await bot.send_message(
                    user_id,
                    await _f(user_id,
                             "error_added_channel_reaction",
                             error=error,
                             channel_id=chat_id,
                             message_id=message.message_id),
                    parse_mode='HTML')
                logger.error("Failed to add reaction", extra={
                    "event": "reaction_failed",
                    "error": error,
                    "channel_id": chat_id
                })
                return

            try:
                await database.add_reaction(chat_id, message.message_id, reaction_chat.emoji, user_id)
            except Exception as db_error:
                logger.error("Failed to add reaction db", extra={
                    "event": "failed_db",
                    "error": db_error,
                    "channel_id": chat_id
                })
        return
    # Если сообщение не в чате, то определяем что с ним делать
    await get_message(message)


@dp.callback_query(lambda call: call.data.startswith("lang_"))
async def set_language(call: types.CallbackQuery):
    """Устанавливает новый язык"""
    lang_code = call.data.split("_")[1]  # Получаем код языка (en, ru, es)
    user_id = call.from_user.id
    await database.set_user_language(call.from_user.id, lang_code)

    await call.message.edit_text(await _(user_id, "language_changed"))
    keyboard = await keyboards.start_keyboard(lang_code)
    await bot.send_message(user_id, await _(user_id, "welcome"), reply_markup=keyboard, parse_mode='HTML')


@dp.callback_query(lambda call: call.data.startswith("settings_language"))
async def settings_language(callback: types.CallbackQuery):
    """настройки/изменение языка"""
    user_id = callback.from_user.id
    await bot.send_message(user_id,"🌍 Choose your language:", reply_markup=keyboards.language_keyboard())


@dp.callback_query(lambda c: c.data.startswith("channel_settings:"))
async def channel_settings(callback: types.CallbackQuery):
    """Настройки канала"""
    _, channel_id = callback.data.split(":")
    message = callback.message

    permission, text = await check_bot_permissions(channel_id)
    if permission == False:
        await bot.send_message(callback.from_user.id, text)
    await admin_keyboard_channel_settings(callback.from_user.id, channel_id, message)


@dp.callback_query(lambda c: c.data.startswith("group_settings:"))
async def group_settings(callback: types.CallbackQuery):
    """Настройки группы/чата"""
    _, channel_id = callback.data.split(":")
    message = callback.message

    permission, text = await check_bot_permissions(channel_id)
    if permission == False:
        await bot.send_message(callback.from_user.id, text)
    await admin_keyboard_chat_settings(callback.from_user.id, channel_id, message)


@dp.callback_query(lambda call: call.data.startswith("channel_set_reaction:"))
async def set_reaction(callback: types.CallbackQuery):
    """настройки реакций в канале"""
    __, channel_id = callback.data.split(":")
    user_id = callback.from_user.id
    await database.set_user_status(user_id, "WAITING_USER_CHANNEL_REACTION", channel_id)
    await bot.send_message(user_id, await _(user_id, "add_channel_reaction"), parse_mode='HTML')


@dp.callback_query(lambda call: call.data.startswith("chat_set_reaction:"))
async def set_reaction(callback: types.CallbackQuery):
    """настройки реакций в чате на самого себя"""
    __, channel_id = callback.data.split(":")
    user_id = callback.from_user.id
    await database.set_user_status(user_id, "WAITING_USER_CHAT_REACTION", channel_id)
    await bot.send_message(user_id, await _(user_id, "add_chat_reaction_myself"), parse_mode='HTML')


@dp.callback_query(lambda c: c.data.startswith("back_channels:"))
async def back_channels(callback: types.CallbackQuery):
    """Клавиатура со всеми каналами. Приходим к ней по кнопке Назад"""
    message = callback.message
    user_id = callback.from_user.id
    user_channels = await database.get_user_channels(user_id)
    language = await database.get_user_language(user_id)
    if not user_channels:
        await message.edit_text(await _(user_id, "user_not_have_channels"), parse_mode='HTML')

    else:
        keyboard = await keyboards.inline_keyboard_user_channels(user_channels, language)
        await message.edit_text(await _(user_id, "user_channels"), reply_markup=keyboard, parse_mode='HTML')
    return


@dp.callback_query(lambda call: call.data.startswith("channel_statistic:"))
async def get_reaction(callback: types.CallbackQuery):
    """Статистика реакций"""
    __, channel_id = callback.data.split(":")
    user_id = callback.from_user.id
    channel = await database.get_channel(channel_id)
    formatted_date = channel.created_at.strftime('%Y-%m-%d')
    count = await database.get_statistic_reactions_count(channel_id)
    reactions = ""

    if count > 0:
        type_reactions = await database.get_statistic_reactions(channel_id)
        for x in type_reactions:
            reactions += f"{x.emoji} X {x.count} \n"

    await bot.send_message(
        user_id,
        await _f(user_id,
                 "bot_statistic",
                 bot_added=formatted_date,
                 count_reactions=count,
                 reactions=reactions
                 ),
        parse_mode='HTML')


@dp.callback_query(lambda call: call.data.startswith("chat_statistic:"))
async def chat_statistic(callback: types.CallbackQuery):
    """Статистика реакций чата"""
    __, channel_id = callback.data.split(":")
    user_id = callback.from_user.id
    channel = await database.get_channel(channel_id)
    formatted_date = channel.created_at.strftime('%Y-%m-%d')
    count = await database.get_statistic_reactions_count(channel_id)
    reactions = ""

    if count > 0:
        type_reactions = await database.get_statistic_reactions(channel_id)
        for x in type_reactions:
            reactions += f"{x.emoji} X {x.count} \n"

    await bot.send_message(
        user_id,
        await _f(user_id,
                 "bot_statistic",
                 bot_added=formatted_date,
                 count_reactions=count,
                 reactions=reactions
                 ),
        parse_mode='HTML')


async def on_shutdown():
    print("🛑 Завершение работы бота...")
    await database.close_database()


async def main():
    try:
        scheduler = AsyncIOScheduler()
        scheduler.add_job(daily_task, 'cron', hour=23, minute=59)
        scheduler.start()
        await dp.start_polling(bot)
    except asyncio.CancelledError:
        pass
    finally:
        await on_shutdown()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("🧹 Принудительная остановка")
