import logging
import random # Потребуется для поиска события по имени класса
from typing import Dict, Optional, Type, Any, List

from aiogram import Router, F, types, Bot
from aiogram.filters import CommandStart
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramBadRequest

from game.core import Player, Country # Импортируем Country для создания нового состояния
from game.events import EventData, get_next_event, fetch_event_options # ИМПОРТИРУЕМ обновленные функции из game.events
from game.mechanics import check_game_over_conditions
from data.database import load_player_state, save_player_state
from data.models import PlayerState, CountryState # Импортируем Pydantic модели
import config

# Добавляем AsyncClient для type hinting
from supabase._async.client import AsyncClient 

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

async def send_event_to_player(message_or_callback: types.Message | types.CallbackQuery, player: Player, event_data: EventData) -> Optional[types.Message]:
    """Отправляет НОВОЕ сообщение с событием и статусом.
       Возвращает отправленное сообщение или None в случае ошибки.
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

    sent_message = None
    chat_id = None
    bot = None
    if isinstance(message_or_callback, types.Message):
        chat_id = message_or_callback.chat.id
        bot = message_or_callback.bot
    elif isinstance(message_or_callback, types.CallbackQuery):
        # Отвечаем на коллбек, чтобы убрать "часики"
        await message_or_callback.answer()
        if message_or_callback.message:
            chat_id = message_or_callback.message.chat.id
            bot = message_or_callback.bot

    if chat_id and bot:
        try:
            # Всегда отправляем новое сообщение
            sent_message = await bot.send_message(
                chat_id=chat_id,
                text=full_description,
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
            logging.info(f"Sent new event message {sent_message.message_id} to player {player.telegram_id}")
        except Exception as e:
            logging.exception(f"Unexpected error sending message for player {player.telegram_id}: {e}")
    else:
        logging.error(f"Could not determine chat_id or bot to send event to player {player.telegram_id}")

    # НЕ СОХРАНЯЕМ состояние здесь
    # НЕ ДОБАВЛЯЕМ ID сообщения здесь

    return sent_message # Возвращаем объект сообщения

# --- Вспомогательные функции для нарративных блоков --- 

async def find_next_narrative_block(db_client: AsyncClient, playthrough: int, completed_ids: list[int]) -> Optional[dict]:
    """Находит следующий доступный нарративный блок."""
    # logging.debug(f"[find_next_narrative_block] Using db_client: {db_client}")
    if not db_client:
        logging.error("Invalid db_client provided to find_next_narrative_block.")
        return None

    try:
        # logging.debug(f"[find_next_narrative_block] Executing query...")
        query = (
            db_client.table("narrative_blocks")
            .select("id", "text", "image_url", "button_text", "is_final_in_sequence")
            .eq("block_type", block_type)
            .or_(f"required_playthrough.eq.0,required_playthrough.is.null,required_playthrough.eq.{playthrough}")
            # Используем not_.in_ для исключения уже просмотренных
            .not_.in_("id", completed_ids if completed_ids else [-1]) # -1 если список пуст
            .order("sequence_order", desc=False) # Сортируем по порядку
            .limit(1) # Берем первый не просмотренный
        )
        response = await query.execute()
        # logging.debug(f"[find_next_narrative_block] Query response object: {response}")

        if response.data:
            # logging.debug(f"Narrative block query for playthrough {playthrough}, completed {completed_ids}: Response data: {response.data}")
            return response.data[0]
        else:
            logging.info(f"No narrative blocks found for playthrough {playthrough} excluding IDs {completed_ids}")
    except Exception as e:
        # Убедимся, что исключение логируется
        logging.exception(f"[find_next_narrative_block] EXCEPTION during query execution or processing for type '{block_type}': {e}")
        return None

async def mark_narrative_block_completed(player_state: PlayerState, block_id: int):
    """Добавляет ID блока в список просмотренных. НЕ СОХРАНЯЕТ состояние."""
    if block_id not in player_state.completed_narrative_block_ids:
        player_state.completed_narrative_block_ids.append(block_id)
        # НЕ вызываем save_player_state здесь, сохранение будет при отправке сообщения

async def start_game_proper(db_client: AsyncClient, message_or_callback: types.Message | types.CallbackQuery, player: Player, player_state: PlayerState):
    """Начинает основной игровой цикл, используя db_client."""
    # Используем импортированную функцию get_next_event
    first_event_data = await get_next_event(db_client, player.country) 

    if first_event_data:
        sent_message = await send_event_to_player(message_or_callback, player, first_event_data)
        if sent_message:
            player_state.message_ids = [sent_message.message_id]
            player_state.current_event_id = first_event_data.id
            await save_player_state(db_client, player_state)
        else:
            logging.error(f"Failed to send initial event for player {player_state.telegram_id}")
            # Пытаемся отправить сообщение об ошибке, если возможно
            chat_id = message_or_callback.chat.id if isinstance(message_or_callback, types.Message) else message_or_callback.message.chat.id
            bot = message_or_callback.bot if isinstance(message_or_callback, types.Message) else message_or_callback.bot
            if chat_id and bot:
                await bot.send_message(chat_id, "Не удалось начать игру. Ошибка при отправке события.")
    else:
        logging.warning(f"No initial game event found for player {player_state.telegram_id}.")
        # Пытаемся отправить сообщение об ошибке
        chat_id = message_or_callback.chat.id if isinstance(message_or_callback, types.Message) else message_or_callback.message.chat.id
        bot = message_or_callback.bot if isinstance(message_or_callback, types.Message) else message_or_callback.bot
        if chat_id and bot:
            await bot.send_message(chat_id, "Не удалось начать игру. Нет доступных игровых событий.")

# --- Обновленные обработчики --- 

@router.message(CommandStart())
async def handle_start(message: types.Message, bot: Bot, db_client: AsyncClient):
    """Обработчик /start: Удаляет старые сообщения, загружает игрока и запускает нарративный блок или игру."""
    player_id = message.from_user.id
    logging.info(f"Player {player_id} interacting via /start.")

    # Передаем db_client в load_player_state
    loaded_state = await load_player_state(db_client, player_id) 
    player_state: PlayerState # Для аннотации типа

    if loaded_state:
        player_state = loaded_state
        logging.info(f"Found existing state for player {player_id}, playthrough {player_state.playthrough_count}.")
        
        # --- Удаление старых сообщений --- 
        await delete_player_messages(bot, player_id, player_state.message_ids)
        player_state.message_ids = [] # Очищаем список в объекте
        # Сохранять пустое состояние не обязательно сразу, оно сохранится при первом сообщении
        # await save_player_state(player_state)
        # ---------------------------------
        
    else:
        # Создаем Pydantic модель для нового игрока
        player_state = PlayerState(
            telegram_id=player_id,
            country_state=CountryState() # Начальное состояние страны
        )
        logging.info(f"Creating new state for player {player_id}.")
        # Первое сохранение произойдет при отправке первого блока/события

    # --- Создаем объект Player из PlayerState ---
    player = Player(telegram_id=player_id)
    player.load_country_state(player_state.country_state.model_dump())
    player.playthrough_count = player_state.playthrough_count
    player.completed_narrative_block_ids = player_state.completed_narrative_block_ids
    player.message_ids = player_state.message_ids # Загружаем ID сообщений
    # ------------------------------------------

    # Ищем следующий блок вступления ('intro')
    next_intro_block = await find_next_narrative_block(db_client, player_state, 'intro')

    if next_intro_block:
        # Показываем блок вступления
        logging.info(f"Showing intro block {next_intro_block['id']} to player {player_id}")
        builder = InlineKeyboardBuilder()
        builder.button(text=next_intro_block['button_text'], callback_data=f"narrative_next_{next_intro_block['id']}")
        
        # TODO: Отправить картинку, если есть next_intro_block['image_url']
        sent_block_message = await message.answer(next_intro_block['text'], reply_markup=builder.as_markup())
        
        # --- Сохраняем ID сообщения и отмечаем блок как пройденный --- 
        if sent_block_message:
            player_state.message_ids = [sent_block_message.message_id] # Обновляем модель для сохранения
            # Отмечаем ИМЕННО ЭТОТ блок как пройденный (добавит ID в список)
            await mark_narrative_block_completed(player_state, next_intro_block['id'])
            # Сохраняем состояние с ID сообщения И обновленным списком пройденных блоков
            await save_player_state(db_client, player_state)
            logging.info(f"Saved initial state for player {player_id} with intro block {next_intro_block['id']} and message {sent_block_message.message_id}")
        else:
             logging.error(f"Failed to send intro block message {next_intro_block['id']} for player {player_id}")
             # Если не удалось отправить, состояние не сохраняем, чтобы блок не считался пройденным

    else:
        # Вступление пройдено или не требуется, начинаем игру
        logging.info(f"Intro sequence complete or not required for player {player_id}. Starting game proper.")
        # Передаем db_client в start_game_proper
        await start_game_proper(db_client, message, player, player_state)


@router.callback_query(F.data.startswith("narrative_next_"))
async def handle_narrative_next(callback: types.CallbackQuery, bot: Bot, db_client: AsyncClient):
    """Обработчик нажатия кнопки 'Далее' в нарративных блоках."""
    player_id = callback.from_user.id
    chat_id = callback.message.chat.id # Получаем chat_id
    try:
        block_id = int(callback.data.split("_")[-1])
    except (ValueError, IndexError):
        await callback.answer("Ошибка обработки кнопки.", show_alert=True)
        return

    logging.info(f"Player {player_id} pressed next on narrative block {block_id}")
    loaded_state = await load_player_state(db_client, player_id)
    if not loaded_state:
        await callback.answer("Ошибка: Не найдено состояние игры. Начните заново /start", show_alert=True)
        return

    # --- Удаляем предыдущие сообщения --- 
    if loaded_state.message_ids:
        await delete_player_messages(bot, chat_id, loaded_state.message_ids)
        loaded_state.message_ids = [] # Очищаем сразу
    # ---------------------------------
    await callback.answer() # Отвечаем на коллбек здесь, т.к. дальше не всегда будет вызван send_event_to_player

    # Отмечаем ТЕКУЩИЙ блок как пройденный (но пока не сохраняем)
    # Используем функцию, которая не сохраняет сама
    await mark_narrative_block_completed(loaded_state, block_id)

    # Загружаем данные текущего блока, чтобы узнать тип и финальность
    current_block_data = None
    if db_client:
        try:
            resp = await db_client.table("narrative_blocks").select("block_type, is_final_in_sequence").eq("id", block_id).limit(1).execute()
            current_block_data = resp.data[0] if resp.data else None
        except Exception as e:
            logging.error(f"Failed to fetch current block data {block_id}: {e}")

    if not current_block_data:
         # await callback.answer("Ошибка: Не удалось получить данные блока.", show_alert=True) # Уже ответили
         logging.error(f"Failed to get current block data {block_id} for player {player_id}")
         # Возможно, стоит попытаться начать игру?
         await bot.send_message(chat_id, "Произошла ошибка при загрузке данных повествования. Попробуйте /start")
         return

    # Убирать кнопку из предыдущего сообщения больше не нужно, т.к. оно удалено
    # try:
    #     await callback.message.edit_reply_markup(reply_markup=None)
    # except TelegramBadRequest: pass

    if current_block_data.get('is_final_in_sequence'):
        # Это был последний блок в последовательности, начинаем игру
        logging.info(f"Final narrative block {block_id} completed for player {player_id}. Starting game proper.")
        # Создаем объект Player перед вызовом
        player = Player(telegram_id=player_id)
        player.load_country_state(loaded_state.country_state.model_dump())
        player.playthrough_count = loaded_state.playthrough_count
        player.completed_narrative_block_ids = loaded_state.completed_narrative_block_ids # Передаем обновленный список
        player.message_ids = [] # Начинаем с пустыми ID
        # Передаем db_client
        await start_game_proper(db_client, callback, player, loaded_state) # Передаем callback, а не callback.message
    else:
        # Ищем следующий блок того же типа
        next_block = await find_next_narrative_block(db_client, loaded_state, current_block_data['block_type'])
        if next_block:
            logging.info(f"Showing next narrative block {next_block['id']} to player {player_id}")
            builder = InlineKeyboardBuilder()
            builder.button(text=next_block['button_text'], callback_data=f"narrative_next_{next_block['id']}")
            # TODO: Отправить картинку
            # Отправляем как НОВОЕ сообщение
            sent_block_message = await bot.send_message(
                chat_id=chat_id,
                text=next_block['text'],
                reply_markup=builder.as_markup()
            )

            # --- Сохраняем ID нового сообщения и состояние --- 
            if sent_block_message:
                loaded_state.message_ids = [sent_block_message.message_id] # Обновляем ID в Pydantic модели
                # completed_narrative_block_ids уже обновлен ранее вызовом mark_narrative_block_completed
                await save_player_state(db_client, loaded_state) # Сохраняем состояние
                logging.info(f"Saved state for player {player_id} with next narrative block {next_block['id']} and message {sent_block_message.message_id}")
            else:
                logging.error(f"Failed to send next narrative block message {next_block['id']} for player {player_id}")
                # Состояние не сохранено с новым ID, но блок block_id отмечен пройденным в loaded_state
        else:
            # Не нашли следующий блок (хотя не должно быть, если не is_final) - начинаем игру
            logging.warning(f"Could not find next narrative block after {block_id}, but not final. Starting game proper for player {player_id}.")
            # Создаем объект Player перед вызовом
            player = Player(telegram_id=player_id)
            player.load_country_state(loaded_state.country_state.model_dump())
            player.playthrough_count = loaded_state.playthrough_count
            player.completed_narrative_block_ids = loaded_state.completed_narrative_block_ids # Передаем обновленный список
            player.message_ids = [] # Начинаем с пустыми ID
            # Передаем db_client
            await start_game_proper(db_client, callback, player, loaded_state) # Передаем callback

    # Отвечать на callback в конце больше не нужно
    # await callback.answer()


# --- Обработчик игровых событий (остается похожим, но нужны правки) --- 

@router.callback_query(F.data.startswith("choice_"))
async def handle_event_choice(callback: types.CallbackQuery, bot: Bot, db_client: AsyncClient):
    """Обработчик нажатия на кнопку выбора варианта игрового события."""
    player_id = callback.from_user.id
    chat_id = callback.message.chat.id # Получаем chat_id для удаления
    player_state_data = await load_player_state(db_client, player_id)

    if not player_state_data:
        await callback.answer("Ошибка: Не найдено состояние игры. Начните заново /start", show_alert=True)
        return

    # --- Удаляем предыдущие сообщения --- 
    if player_state_data.message_ids:
        await delete_player_messages(bot, chat_id, player_state_data.message_ids)
        player_state_data.message_ids = [] # Очищаем сразу в Pydantic модели
    # ---------------------------------

    event_id = player_state_data.current_event_id
    if not event_id:
        await callback.answer("Ошибка: Нет активного события. Возможно, стоит начать заново /start", show_alert=True)
        logging.warning(f"No current_event_id found for player {player_id} on choice callback.")
        return

    # Используем импортированную функцию fetch_event_options
    options_data = await fetch_event_options(db_client, event_id) 
    if not options_data:
         await callback.answer("Ошибка: Не удалось загрузить варианты для события.", show_alert=True)
         logging.error(f"Failed to fetch event options for event {event_id}")
         return

    try:
        choice_index = int(callback.data.split("_")[1])
        if not 0 <= choice_index < len(options_data):
            raise IndexError("Choice index out of range")
    except (IndexError, ValueError):
        await callback.answer("Ошибка: Неверный формат кнопки.", show_alert=True)
        logging.error(f"Invalid callback data format for player {player_id}: {callback.data}")
        return

    chosen_option = options_data[choice_index]
    effects = chosen_option.get('effects', {})
    # outcome_text = chosen_option.get('outcome_text') # TODO
    # next_event_name = chosen_option.get('next_event_name') # TODO

    # --- Обновляем объект Player --- 
    player = Player(telegram_id=player_id)
    player.load_country_state(player_state_data.country_state.model_dump())
    player.playthrough_count = player_state_data.playthrough_count
    player.completed_narrative_block_ids = player_state_data.completed_narrative_block_ids
    player.message_ids = [] # Начинаем с пустого списка ID для этого хода
    # -----------------------------

    # --- Применяем эффекты! --- 
    player.country.update(effects)
    player.country.current_year += 1
    logging.info(f"Player {player_id} chose option {choice_index} for event {event_id}. Year: {player.country.current_year}")
    logging.info(f"New state for player {player_id}: {player.country.get_state()}")

    # --- Подготовка состояния для сохранения (промежуточного или финального) --- 
    state_to_save = PlayerState(
        telegram_id=player.telegram_id,
        country_state=CountryState.model_validate(player.country.get_state()),
        playthrough_count=player.playthrough_count,
        completed_narrative_block_ids=player.completed_narrative_block_ids,
        message_ids=[], # Сохраняем пустой список ID перед отправкой нового сообщения
        current_event_id=None # Сбрасываем ID перед поиском нового
    )
    # ------------------------------------------------------------------------

    # Проверяем условия конца игры
    game_over_reason = check_game_over_conditions(player.country)
    if game_over_reason:
        logging.info(f"Game over for player {player_id}. Reason: {game_over_reason}")

        # --- Обновляем состояние для начала новой игры --- 
        new_playthrough_count = state_to_save.playthrough_count + 1
        new_country = Country()
        state_to_save.country_state = CountryState.model_validate(new_country.get_state())
        state_to_save.playthrough_count = new_playthrough_count
        state_to_save.completed_narrative_block_ids = []
        state_to_save.message_ids = [] # ID сообщений остаются пустыми
        # --------------------------------------------------

        await save_player_state(db_client, state_to_save) # Сохраняем состояние для СЛЕДУЮЩЕЙ игры
        logging.info(f"Player {player_id} state reset for new playthrough {new_playthrough_count}.")

        # Отправляем сообщение о конце игры (это будет единственное сообщение)
        game_over_message = await bot.send_message(
            chat_id=chat_id,
            text=f"Игра окончена! {game_over_reason}\n\nНачать новое правление (прохождение #{new_playthrough_count})? /start",
            reply_markup=None
        )
        # Сохраняем ID сообщения о конце игры, чтобы при следующем /start оно удалилось
        if game_over_message:
            state_to_save.message_ids = [game_over_message.message_id]
            await save_player_state(db_client, state_to_save)

        await callback.answer() # Отвечаем на коллбек
        return

    # --- Если игра НЕ окончена --- 
    # НЕ сохраняем промежуточное состояние здесь, сохраним ПОСЛЕ отправки нового события

    # TODO: Показать outcome_text? (Можно отправить отдельным сообщением, которое не удалится?)

    # Используем импортированную функцию get_next_event
    next_event_data = await get_next_event(db_client, player.country) 

    if next_event_data:
        # Отправляем новое сообщение через обновленную функцию
        sent_message = await send_event_to_player(callback, player, next_event_data)
        if sent_message:
            # Сохраняем состояние с ID нового события И ID нового сообщения
            state_to_save.message_ids = [sent_message.message_id]
            state_to_save.current_event_id = next_event_data.id
            await save_player_state(db_client, state_to_save)
            logging.info(f"Saved state for player {player_id} with new event {next_event_data.id} and message {sent_message.message_id}")
        else:
            logging.error(f"Failed to send next event message for player {player_id}")
            await callback.answer("Ошибка при отправке следующего события.", show_alert=True)
    else:
        # Если следующих событий нет - Game Over?
        logging.warning(f"No next event found for player {player_id} after event {event_id}.")
        # TODO: Что делать в этом случае? Пока просто отвечаем.
        await callback.answer("Не найдено следующее событие.", show_alert=True)
        # Возможно, стоит отправить сообщение об окончании и сохранить состояние?
        await bot.send_message(chat_id, "Похоже, история вашего правления подошла к концу.")
        # Сохраним последнее состояние без current_event_id и без message_ids
        state_to_save.current_event_id = None
        state_to_save.message_ids = []
        await save_player_state(db_client, state_to_save)

    # Отвечать на callback уже не нужно, т.к. send_event_to_player это делает
    # await callback.answer()

# TODO: 
# - Логика инкремента playthrough_count и сброса completed_narrative_block_ids при game over.
# - Реализовать показ character_intro перед событиями персонажей.
# - Реализовать отправку картинок.
# - Реализовать показ outcome_text.
# - Добавить обработку next_event_name.
# - Улучшить get_next_event (is_unique, max_year).
# - Удаление сообщений.

# --- Вспомогательная функция для удаления --- 

async def delete_player_messages(bot: Bot, chat_id: int, message_ids: List[int]):
    """Пытается удалить список сообщений для игрока."""
    logging.info(f"Attempting to delete {len(message_ids)} messages for chat {chat_id}")
    deleted_count = 0
    for msg_id in message_ids:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=msg_id)
            deleted_count += 1
        except TelegramBadRequest as e:
            # Частая ошибка: сообщение уже удалено или не найдено
            logging.warning(f"Failed to delete message {msg_id} for chat {chat_id}: {e}")
        except Exception as e:
            logging.exception(f"Unexpected error deleting message {msg_id} for chat {chat_id}: {e}")
    logging.info(f"Deleted {deleted_count}/{len(message_ids)} messages for chat {chat_id}")
