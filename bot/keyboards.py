from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, KeyboardButton, ReplyKeyboardMarkup
import texts



def language_keyboard():
    """Клавиатура выбора языка"""
    button_english = InlineKeyboardButton(
        text="🇺🇸 English",
        callback_data="lang_en")
    button_ru = InlineKeyboardButton(
        text="🇷🇺 Русский",
        callback_data="lang_ru")
    button_es = InlineKeyboardButton(
        text="🇪🇸 Español",
        callback_data="lang_es")

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[button_english],
                         [button_ru],
                         [button_es]],
                         row_width = 1)
    return keyboard


async def start_keyboard(language: str):
    """Основная клавиатура бота"""
    button_set_reaction_channel = KeyboardButton(text=texts.translations_buttons.get("button_set_reaction_channel", {}).get(language, "⚠️ Translation not found"))
    button_settings = KeyboardButton(text=texts.translations_buttons.get("button_settings", {}).get(language, "⚠️ Translation not found"))
    button_help = KeyboardButton(text=texts.translations_buttons.get("button_help", {}).get(language, "⚠️ Translation not found"))

    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [button_set_reaction_channel],
            [button_settings, button_help]
        ],
        resize_keyboard=True
    )
    return keyboard


async def settings_keyboard(language: str):
    """Клавиатура настроек бота. Пока только настройка языка"""
    button_settings_language = InlineKeyboardButton(
        text=texts.translations.get("language_settings", {}).get(language, "⚠️ Translation not found"),
        callback_data="settings_language")

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[button_settings_language]],
                         row_width = 1)
    return keyboard


async def inline_keyboard_user_channels(channels, language):
    """Клавиатура юзера с его каналами и чатами в которых он состоит"""
    keyboard_buttons = []

    for item in channels:
        button_text = ''
        if item.chat_type == 'channel':
            callback_data = 'channel_settings'
            button_text += texts.translations.get("inline_button_channel", {}).get(language, "⚠️ Translation not found")
        elif item.chat_type == 'supergroup':
            callback_data = 'group_settings'
            button_text += texts.translations.get("inline_button_supergroup", {}).get(language, "⚠️ Translation not found")
        elif item.chat_type == 'group':
            callback_data = 'group_settings'
            button_text += texts.translations.get("inline_button_group", {}).get(language, "⚠️ Translation not found")

        button = InlineKeyboardButton(
            text=str(button_text + item.channel_title),
            callback_data=f'{callback_data}:{item.chat_id}'
        )
        keyboard_buttons.append([button])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    return keyboard


async def inline_keyboard_admin_channel_setting(id_channel, language):
    """Клавиатура администратора. настройка канала"""
    button_statistic = InlineKeyboardButton(
        text=texts.translations.get("inline_button_statistic", {}).get(language, "⚠️ Translation not found"),
        callback_data=f"channel_statistic:{id_channel}")

    button_reaction = InlineKeyboardButton(
        text=texts.translations.get("inline_button_setting_reaction", {}).get(language, "⚠️ Translation not found"),
        callback_data=f"channel_set_reaction:{id_channel}")

    button_back = InlineKeyboardButton(
        text=texts.translations.get("inline_button_back", {}).get(language, "⚠️ Translation not found"),
        callback_data=f"back_channels:")

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[button_statistic],
                        [button_reaction],
                        [button_back]],
                         row_width = 1)
    return keyboard


async def inline_keyboard_admin_chat_setting(id_chat, language):
    """Клавиатура администратора. настройка чата"""
    button_statistic = InlineKeyboardButton(
        text=texts.translations.get("inline_button_statistic", {}).get(language, "⚠️ Translation not found"),
        callback_data=f"chat_statistic:{id_chat}")

    button_reaction = InlineKeyboardButton(
        text=texts.translations.get("inline_button_setting_reaction_chat_myself", {}).get(language, "⚠️ Translation not found"),
        callback_data=f"chat_set_reaction:{id_chat}")

    button_back = InlineKeyboardButton(
        text=texts.translations.get("inline_button_back", {}).get(language, "⚠️ Translation not found"),
        callback_data=f"back_channels:")

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[button_statistic],
                        [button_reaction],
                        [button_back]],
                         row_width = 1)
    return keyboard