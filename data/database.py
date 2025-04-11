import logging
from typing import Optional

# Импортируем асинхронные Client и create_client из _async
from supabase._async.client import AsyncClient, create_client
from pydantic import ValidationError

import config
from .models import PlayerState, CountryState

# УБИРАЕМ ГЛОБАЛЬНУЮ ПЕРЕМЕННУЮ
# supabase: Optional[AsyncClient] = None

# Функция инициализации теперь только возвращает клиент
async def init_supabase_client() -> Optional[AsyncClient]:
    """Асинхронно инициализирует и ВОЗВРАЩАЕТ асинхронный клиент Supabase.
       Использует SERVICE_ROLE ключ.
       Возвращает созданный клиент или None в случае ошибки.
    """
    # Убираем global supabase
    # global supabase
    if not config.SUPABASE_URL or config.SUPABASE_URL == "YOUR_SUPABASE_URL_HERE":
        logging.warning("Supabase URL не настроен. Работа с БД будет невозможна.")
        return None
    if not config.SUPABASE_SERVICE_ROLE_KEY or config.SUPABASE_SERVICE_ROLE_KEY == "YOUR_SUPABASE_SERVICE_KEY_HERE":
        logging.warning("Supabase SERVICE_ROLE Key не настроен. Работа с БД будет невозможна.")
        return None

    try:
        client = await create_client(config.SUPABASE_URL, config.SUPABASE_SERVICE_ROLE_KEY)
        # Убираем присваивание глобальной переменной
        # supabase = client
        logging.info("Supabase async client initialized successfully using SERVICE_ROLE key.")
        return client
    except Exception as e:
        logging.exception(f"Failed to initialize Supabase client: {e}")
        # Убираем обнуление глобальной переменной
        # supabase = None
        return None

# Функции теперь принимают db_client как первый аргумент
async def load_player_state(db_client: AsyncClient, telegram_id: int) -> Optional[PlayerState]:
    """Загружает состояние игрока из Supabase по его telegram_id.

    Args:
        db_client: Инициализированный клиент Supabase.
        telegram_id: ID игрока в Telegram.

    Returns:
        Объект PlayerState если игрок найден и данные валидны, иначе None.
    """
    # Проверяем переданный клиент
    if not db_client:
        logging.error("Invalid db_client provided to load_player_state.")
        return None

    try:
        query = (
            db_client.table("players") # Используем db_client
            .select("telegram_id", "state", "current_event_id", "playthrough_count", "completed_narrative_block_ids", "message_ids")
            .eq("telegram_id", telegram_id)
            .maybe_single() # Ожидаем одну строку или None
        )
        response = await query.execute()
        # logging.debug(f"Supabase load response for {telegram_id}: {response}") # Отключаем debug лог

        if not response.data:
            logging.info(f"No state found for player {telegram_id}. Creating new state.")
            return None
        
        player_data_raw = response.data
        full_player_data = {
            "telegram_id": player_data_raw.get("telegram_id"),
            "country_state": player_data_raw.get("state"),
            "current_event_id": player_data_raw.get("current_event_id"),
            "playthrough_count": player_data_raw.get("playthrough_count", 1), # Default to 1 if missing
            "completed_narrative_block_ids": player_data_raw.get("completed_narrative_block_ids", []),
            "message_ids": player_data_raw.get("message_ids", [])
        }
        
        try:
            player_state = PlayerState.model_validate(full_player_data)
            logging.info(f"Loaded state for player {telegram_id} (Playthrough: {player_state.playthrough_count}, EventID: {player_state.current_event_id}, Msgs: {len(player_state.message_ids)}).")
            return player_state
        except ValidationError as e:
            logging.error(f"Data validation error for player {telegram_id}: {e}")
            return None

    except Exception as e:
        logging.exception(f"Error loading player state for {telegram_id} from Supabase: {e}")
        return None

async def save_player_state(db_client: AsyncClient, player_state: PlayerState) -> bool:
    """Сохраняет или обновляет состояние игрока в Supabase.

    Args:
        db_client: Инициализированный клиент Supabase.
        player_state: Pydantic модель с данными игрока.

    Returns:
        True если сохранение прошло успешно, иначе False.
    """
    if not db_client:
        logging.error("Invalid db_client provided to save_player_state.")
        return False

    try:
        data_to_upsert = {
            "telegram_id": player_state.telegram_id,
            "state": player_state.country_state.model_dump(),
            "current_event_id": player_state.current_event_id,
            "playthrough_count": player_state.playthrough_count,
            "completed_narrative_block_ids": player_state.completed_narrative_block_ids,
            "message_ids": player_state.message_ids
        }

        query = (
            db_client.table("players") # Используем db_client
            .upsert(data_to_upsert)
        )
        response = await query.execute()
        # logging.debug(f"Supabase save response for {player_state.telegram_id}: {response}") # Отключаем debug лог
        
        if not hasattr(response, 'data') or not response.data:
            logging.warning(f"Save operation for player {player_state.telegram_id} might not have been successful, response data is empty or missing.")
            return False

        if response.data or (hasattr(response, 'error') and response.error is None):
            logging.info(f"Successfully saved state for player {player_state.telegram_id} (Playthrough: {player_state.playthrough_count}, EventID: {player_state.current_event_id}, Msgs: {len(player_state.message_ids)}).")
            return True
        else:
            logging.error(f"Failed to save player state for {player_state.telegram_id}. Response: {response}")
            return False

    except Exception as e:
        logging.exception(f"Error saving player state for {player_state.telegram_id} to Supabase: {e}")
        return False
