import logging
import random # Потребуется для поиска события по имени класса
from typing import Dict, Optional, Type

from aiogram import Router, F, types
from aiogram.filters import CommandStart
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramBadRequest

from game.core import Player, Country # Импортируем Country для создания нового состояния
from game.events import get_next_event, AVAILABLE_EVENTS # Нужен список событий для поиска по имени
from events.base import Event # Нужен базовый класс для type hint
from game.mechanics import check_game_over_conditions
from data.database import load_player_state, save_player_state
from data.models import PlayerState, CountryState # Импортируем Pydantic модели

# Используем Router для лучшей организации
router = Router()

# Временное хранилище player_states больше НЕ ИСПОЛЬЗУЕТСЯ
# player_states: Dict[int, Player] = {}


def build_event_keyboard(event: Event) -> types.InlineKeyboardMarkup:
    """Строит клавиатуру с вариантами ответов для события."""
    builder = InlineKeyboardBuilder()
    options_text = event.get_options_text()
    for i, text in enumerate(options_text):
        builder.button(text=text, callback_data=f"choice_{i}")
    builder.adjust(1)
    return builder.as_markup()

async def send_event_to_player(message_or_callback: types.Message | types.CallbackQuery, player: Player, event: Event):
    """Отправляет или редактирует сообщение с новым событием.
       Также сохраняет состояние игрока с ID нового события в БД.
    """
    keyboard = build_event_keyboard(event)
    
    # Сохраняем текущее состояние И имя класса события в БД ПЕРЕД отправкой
    player_state_to_save = PlayerState(
        telegram_id=player.telegram_id,
        country_state=CountryState.model_validate(player.country.get_state()), # Используем Pydantic модель
        current_event_class_name=event.__class__.__name__ # Сохраняем имя класса
    )
    await save_player_state(player_state_to_save)
    
    try:
        if isinstance(message_or_callback, types.Message):
            sent_message = await message_or_callback.answer(event.description, reply_markup=keyboard)
            player.message_history.append(sent_message.message_id)
        elif isinstance(message_or_callback, types.CallbackQuery):
            # Важно: сначала отвечаем на callback, потом редактируем
            await message_or_callback.answer()
            await message_or_callback.message.edit_text(event.description, reply_markup=keyboard)
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

    # Получаем первое (или следующее, если игрок продолжил) событие
    current_event = get_next_event(player.country)

    if current_event:
        await send_event_to_player(message, player, current_event)
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

    # --- Восстановление объекта события --- 
    event_class_name = player_state_data.current_event_class_name
    CurrentEventClass: Optional[Type[Event]] = None
    if event_class_name:
        # Ищем класс события по имени в списке доступных
        for event_cls in AVAILABLE_EVENTS:
            if event_cls.__name__ == event_class_name:
                CurrentEventClass = event_cls
                break
        
    if not CurrentEventClass:
        await callback.answer("Ошибка: Не удалось определить предыдущее событие. Попробуйте /start", show_alert=True)
        logging.error(f"Could not find event class '{event_class_name}' for player {player_id}")
        return
    
    # Создаем экземпляр события (важно для метода apply_effects)
    # Мы не передаем аргументы в __init__, т.к. наши тестовые события их не требуют.
    # Если события будут сложнее, возможно, понадобится сохранять и аргументы.
    try:
        current_event = CurrentEventClass()
    except Exception as e:
        await callback.answer("Ошибка: Не удалось воссоздать событие. Попробуйте /start", show_alert=True)
        logging.error(f"Failed to instantiate event '{event_class_name}' for player {player_id}: {e}")
        return
    # --- Конец восстановления события --- 

    # Извлекаем индекс выбора
    try:
        choice_index = int(callback.data.split("_")[1])
    except (IndexError, ValueError):
        await callback.answer("Ошибка обработки выбора.", show_alert=True)
        logging.error(f"Invalid callback data format: {callback.data}")
        return

    # Создаем объект Player и загружаем состояние
    player = Player(telegram_id=player_id)
    player.load_country_state(player_state_data.country_state.model_dump())
    
    # --- Применяем эффекты! --- 
    current_event.apply_effects(choice_index, player.country)
    logging.info(f"Player {player_id} chose option {choice_index} for event {event_class_name}. Year: {player.country.current_year}")
    logging.info(f"New state for player {player_id}: {player.country.get_state()}")

    # Проверяем условия конца игры ПОСЛЕ применения эффектов
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

    # Если игра не окончена, получаем следующее событие
    next_event = get_next_event(player.country)

    if next_event:
        # Отправляем новое событие и СОХРАНЯЕМ состояние (внутри функции)
        await send_event_to_player(callback, player, next_event)
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
