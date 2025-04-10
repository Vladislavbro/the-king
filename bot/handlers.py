import logging
import random # Потребуется для поиска события по имени класса
from typing import Dict, Optional, Type

from aiogram import Router, F, types
from aiogram.filters import CommandStart
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramBadRequest

from game.core import Player, Country # Импортируем Country для создания нового состояния
from game.events import get_next_event, EventData, fetch_event_options # Импортируем EventData и fetch_event_options
from game.mechanics import check_game_over_conditions
from data.database import load_player_state, save_player_state
from data.models import PlayerState, CountryState # Импортируем Pydantic модели

# Используем Router для лучшей организации
router = Router()

# Временное хранилище player_states больше НЕ ИСПОЛЬЗУЕТСЯ
# player_states: Dict[int, Player] = {}


def build_event_keyboard(event_data: EventData) -> types.InlineKeyboardMarkup:
    """Строит клавиатуру с вариантами ответов для события (использует EventData)."""
    builder = InlineKeyboardBuilder()
    options = event_data.get_options_data()
    for i, (text, _effects, _outcome, _img) in enumerate(options):
        builder.button(text=text, callback_data=f"choice_{i}")
    builder.adjust(1)
    return builder.as_markup()

async def send_event_to_player(message_or_callback: types.Message | types.CallbackQuery, player: Player, event_data: EventData):
    """Отправляет или редактирует сообщение с новым событием и текущим статусом.
       Сохраняет состояние игрока с ID нового события в БД.
    """
    keyboard = build_event_keyboard(event_data)
    
    # --- Формирование статус-блока --- 
    status_lines = [
        f"*Год:* {player.country.current_year}",
        f"*Поддержка:* {player.country.support}",
        f"*Казна:* {player.country.treasury}",
        f"*Армия:* {player.country.army.capitalize()}", # low -> Low
        f"*Крестьяне:* {player.country.peasants.capitalize()}"
    ]
    status_block = "\n\n" + "\n".join(status_lines)
    # ----------------------------------

    # Формируем текст сообщения с описанием, персонажем и статусом
    description = event_data.description
    if event_data.character_name:
        description = f"**{event_data.character_name}:**\n{description}"
        
    full_description = description + status_block # Добавляем статус
        
    # TODO: Добавить отправку картинки event_data.image_url_prompt
    
    # Сохраняем текущее состояние И ID события в БД ПЕРЕД отправкой
    player_state_to_save = PlayerState(
        telegram_id=player.telegram_id,
        country_state=CountryState.model_validate(player.country.get_state()),
        current_event_id=event_data.id # Сохраняем ID
    )
    await save_player_state(player_state_to_save)
    
    try:
        if isinstance(message_or_callback, types.Message):
            # Отправляем с картинкой и полным описанием
            sent_message = await message_or_callback.answer(full_description, reply_markup=keyboard, parse_mode="Markdown")
            player.message_history.append(sent_message.message_id)
        elif isinstance(message_or_callback, types.CallbackQuery):
            await message_or_callback.answer()
            # Редактируем с полным описанием
            await message_or_callback.message.edit_text(full_description, reply_markup=keyboard, parse_mode="Markdown")
    except TelegramBadRequest as e:
        # Частая ошибка - попытка отредактировать сообщение без изменений
        logging.warning(f"Failed to edit/send message for player {player.telegram_id}: {e}")
    except Exception as e:
        logging.exception(f"Unexpected error sending/editing message for player {player.telegram_id}: {e}")

@router.message(CommandStart())
async def handle_start(message: types.Message):
    """Обработчик команды /start.
       Загружает существующее состояние или создает новое.
    """
    player_id = message.from_user.id
    logging.info(f"Player {player_id} interacting via /start.")

    # Пытаемся загрузить состояние из БД
    loaded_state = await load_player_state(player_id)

    if loaded_state:
        logging.info(f"Found existing state for player {player_id}.")
        # Создаем объект Player и загружаем состояние страны
        player = Player(telegram_id=player_id)
        player.load_country_state(loaded_state.country_state.model_dump()) # Загружаем данные страны
        # TODO: Добавить логику удаления старых сообщений, если нужно
        # player.message_history = [] # Очистить историю?
    else:
        logging.info(f"Creating new state for player {player_id}.")
        # Создаем нового игрока с начальным состоянием
        player = Player(telegram_id=player_id)
        # Начальное состояние УЖЕ установлено в __init__ Player/Country
        # Но мы все равно должны его сохранить в БД в первый раз
        # Это сделается при отправке первого события в send_event_to_player

    # Получаем первое событие из БД
    current_event_data = await get_next_event(player.country)

    if current_event_data:
        await send_event_to_player(message, player, current_event_data)
    else:
        await message.answer("Не удалось начать игру. Нет доступных событий.")
        logging.warning(f"No initial/next event found for player {player_id}.")


@router.callback_query(F.data.startswith("choice_"))
async def handle_event_choice(callback: types.CallbackQuery):
    """Обработчик нажатия на кнопку выбора варианта события.
       Теперь с загрузкой/сохранением и применением эффектов!
    """
    player_id = callback.from_user.id

    # Загружаем ПОСЛЕДНЕЕ сохраненное состояние игрока из БД
    player_state_data = await load_player_state(player_id)

    if not player_state_data:
        await callback.answer("Ошибка: Не найдено состояние игры. Начните заново /start", show_alert=True)
        logging.warning(f"Player state not found for {player_id} on callback.")
        try:
            await callback.message.edit_text("Игра не найдена. Пожалуйста, начните заново командой /start.", reply_markup=None)
        except TelegramBadRequest:
            pass # Ошибки редактирования здесь не критичны
        return

    # --- Восстановление данных о событии и его вариантах --- 
    event_id = player_state_data.current_event_id
    if not event_id:
        # Случай, когда у игрока не было активного события (ошибка?) 
        await callback.answer("Ошибка: Не найдено активное событие. Попробуйте /start", show_alert=True)
        logging.error(f"Player {player_id} has no current_event_id in loaded state.")
        return
    
    # Загружаем варианты для этого события (эффекты нужны здесь)
    options_data = await fetch_event_options(event_id)
    if not options_data:
         await callback.answer("Ошибка: Не удалось загрузить варианты для события. Попробуйте /start", show_alert=True)
         logging.error(f"Could not fetch options for event_id {event_id} for player {player_id}")
         return
    # --- Конец восстановления --- 

    # Извлекаем индекс выбора
    try:
        choice_index = int(callback.data.split("_")[1])
        if not 0 <= choice_index < len(options_data):
            raise IndexError("Choice index out of range")
    except (IndexError, ValueError):
        await callback.answer("Ошибка обработки выбора.", show_alert=True)
        logging.error(f"Invalid callback data format: {callback.data}")
        return

    # Получаем данные выбранного варианта
    chosen_option = options_data[choice_index]
    effects = chosen_option.get('effects', {})
    outcome_text = chosen_option.get('outcome_text')
    # image_url_result = chosen_option.get('image_url_result') # TODO: Использовать для показа результата
    # next_event_name = chosen_option.get('next_event_name') # TODO: Использовать для цепочек событий

    # Создаем объект Player и загружаем состояние
    player = Player(telegram_id=player_id)
    player.load_country_state(player_state_data.country_state.model_dump())
    
    # --- Применяем эффекты! --- 
    player.country.update(effects)
    player.country.current_year += 1 # Увеличиваем год после эффектов
    logging.info(f"Player {player_id} chose option {choice_index} for event {event_id}. Year: {player.country.current_year}")
    logging.info(f"New state for player {player_id}: {player.country.get_state()}")

    # TODO: Показать outcome_text и image_url_result перед следующим событием? 
    # await callback.message.answer(f"Результат: {outcome_text}") # Например

    # Проверяем условия конца игры
    game_over_reason = check_game_over_conditions(player.country)
    if game_over_reason:
        logging.info(f"Game over for player {player_id}. Reason: {game_over_reason}")
        # TODO: Реализовать логику удаления сообщений (пока просто редактируем)
        # await delete_player_messages(callback.bot, player_id, player.message_history)
        # Удалять ли запись из БД? Пока оставим.
        # await delete_player_state(player_id)
        try:
            await callback.message.edit_text(f"Игра окончена! {game_over_reason}\nНачать заново? /start", reply_markup=None)
        except TelegramBadRequest:
             pass # Может быть ошибка, если сообщение уже удалено
        await callback.answer() # Отвечаем на callback
        return

    # Если игра не окончена, получаем следующее событие из БД
    # TODO: Учесть next_event_name, если он есть
    next_event_data = await get_next_event(player.country)

    if next_event_data:
        # Отправляем новое событие и СОХРАНЯЕМ состояние
        await send_event_to_player(callback, player, next_event_data)
    else:
        # Ситуация, когда событий больше нет
        logging.warning(f"No next event found for player {player_id} after year {player.country.current_year}.")
        try:
             await callback.message.edit_text("Странно, но событий больше нет... Возможно, вы достигли конца? Начните заново? /start", reply_markup=None)
        except TelegramBadRequest:
             pass
        await callback.answer()
        # Может быть, стоит удалить состояние игрока?
        # await delete_player_state(player_id)

# Важное TODO:
# - Реализовать удаление сообщений при game over или /start.
# - Улучшить механизм восстановления события (если __init__ потребует аргументов).
# - Рассмотреть удаление записи из БД при game over.

# Дополнительное TODO: 
# - Реализовать отправку/редактирование с картинками (image_url_prompt/image_url_result).
# - Реализовать показ outcome_text.
# - Учесть next_event_name для цепочек событий в get_next_event или здесь.
# - Добавить обработку истории событий (is_unique, избегание повторов).
