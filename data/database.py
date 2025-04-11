import logging
from typing import Optional

# Импортируем асинхронные Client и create_client из _async
from supabase._async.client import AsyncClient, create_client
from pydantic import ValidationError

import config
from .models import PlayerState, CountryState

# Инициализация клиента Supabase
supabase: Optional[AsyncClient] = None # Теперь используем AsyncClient

# Функция инициализации теперь асинхронная
async def init_supabase_client():
    """Асинхронно инициализирует асинхронный клиент Supabase, используя SERVICE_ROLE ключ."""
    global supabase
    if not config.SUPABASE_URL or config.SUPABASE_URL == "YOUR_SUPABASE_URL_HERE":
        logging.warning("Supabase URL не настроен. Работа с БД будет невозможна.")
        return
    # Проверяем наличие SERVICE_ROLE ключа
    if not config.SUPABASE_SERVICE_ROLE_KEY or config.SUPABASE_SERVICE_ROLE_KEY == "YOUR_SUPABASE_SERVICE_KEY_HERE":
        logging.warning("Supabase SERVICE_ROLE Key не настроен. Работа с БД будет невозможна.")
        return

    try:
        # Используем await для асинхронного создания клиента
        supabase = await create_client(config.SUPABASE_URL, config.SUPABASE_SERVICE_ROLE_KEY)
        logging.info("Supabase async client initialized successfully using SERVICE_ROLE key.")
    except Exception as e:
        logging.exception(f"Failed to initialize Supabase client: {e}")
        supabase = None

async def load_player_state(telegram_id: int) -> Optional[PlayerState]:
    """Загружает состояние игрока из Supabase по его telegram_id.

    Args:
        telegram_id: ID игрока в Telegram.

    Returns:
        Объект PlayerState если игрок найден и данные валидны, иначе None.
    """
    if not supabase:
        logging.error("Supabase client not initialized. Cannot load player state.")
        return None

    try:
        # Загружаем все колонки игрока
        query = (
            supabase.table("players")
            # Добавляем message_ids в select
            .select("telegram_id", "state", "current_event_id", "playthrough_count", "completed_narrative_block_ids", "message_ids") 
            .eq("telegram_id", telegram_id)
            .limit(1)
        )
        response = await query.execute()
        logging.debug(f"Supabase load response for {telegram_id}: {response}")

        if not response.data:
            logging.info(f"No existing state found for player {telegram_id}.")
            return None # Игрок не найден

        # Если данные есть:
        player_data_raw = response.data[0]
        full_player_data = {
            "telegram_id": player_data_raw.get("telegram_id"),
            "country_state": player_data_raw.get("state"),
            "current_event_id": player_data_raw.get("current_event_id"),
            # Загружаем новые поля
            "playthrough_count": player_data_raw.get("playthrough_count", 1),
            "completed_narrative_block_ids": player_data_raw.get("completed_narrative_block_ids", []),
            "message_ids": player_data_raw.get("message_ids", []) # Загружаем message_ids
        }
        try:
            player_state = PlayerState.model_validate(full_player_data)
            logging.info(f"Loaded state for player {telegram_id} (Playthrough: {player_state.playthrough_count}, EventID: {player_state.current_event_id}, Msgs: {len(player_state.message_ids)}).")
            return player_state
        except ValidationError as e:
            logging.error(f"Data validation error for player {telegram_id}: {e}")
            return None # Данные в БД некорректны

    except Exception as e:
        logging.exception(f"Error loading player state for {telegram_id} from Supabase: {e}")
        return None

async def save_player_state(player_state: PlayerState) -> bool:
    """Сохраняет или обновляет состояние игрока в Supabase.

    Использует upsert: если запись с таким telegram_id существует, она обновляется,
    иначе создается новая.

    Args:
        player_state: Pydantic модель с данными игрока.

    Returns:
        True если сохранение прошло успешно, иначе False.
    """
    if not supabase:
        logging.error("Supabase client not initialized. Cannot save player state.")
        return False

    try:
        # Сохраняем все актуальные поля
        data_to_upsert = {
            "telegram_id": player_state.telegram_id,
            "state": player_state.country_state.model_dump(),
            "current_event_id": player_state.current_event_id,
            "playthrough_count": player_state.playthrough_count,
            # Преобразуем список Python в формат массива PostgreSQL для сохранения
            "completed_narrative_block_ids": player_state.completed_narrative_block_ids,
            "message_ids": player_state.message_ids # Сохраняем message_ids
        }
        
        query = (
            supabase.table("players")
            .upsert(data_to_upsert)
        )
        response = await query.execute()
        logging.debug(f"Supabase save response for {player_state.telegram_id}: {response}")

        # Проверяем успешность операции (хотя upsert обычно не возвращает ошибку, если PK есть)
        if response.data or (hasattr(response, 'error') and response.error is None):
            logging.info(f"Successfully saved state for player {player_state.telegram_id} (Playthrough: {player_state.playthrough_count}, EventID: {player_state.current_event_id}, Msgs: {len(player_state.message_ids)}).")
            return True
        else:
            logging.error(f"Failed to save player state for {player_state.telegram_id}. Response: {response}")
            return False

    except Exception as e:
        logging.exception(f"Error saving player state for {player_state.telegram_id} to Supabase: {e}")
        return False
