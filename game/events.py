import logging
from typing import List, Dict, Any, Optional, Tuple
import random
import json # Для работы с JSONB из БД

# Импортируем AsyncClient для type hinting
from supabase._async.client import AsyncClient

from game.core import Country # Нужен для проверки условий

# --- Классы событий и AVAILABLE_EVENTS теперь не нужны --- 

class EventData:
    """Структура для хранения данных события, загруженных из БД."""
    def __init__(self, event_row: Dict[str, Any], options: List[Dict[str, Any]]):
        self.id: int = event_row['id']
        self.name: Optional[str] = event_row.get('name')
        self.description: str = event_row['description']
        self.image_url_prompt: Optional[str] = event_row.get('image_url_prompt')
        self.character_name: Optional[str] = event_row.get('character_name')
        self.options: List[Dict[str, Any]] = options # Список словарей с данными опций

    def get_options_data(self) -> List[Tuple[str, Dict, Optional[str], Optional[str]]]:
        """Возвращает список кортежей (текст_кнопки, эффекты, текст_результата, url_картинки_результата)."""
        return [
            (
                opt.get('button_text', '???'), 
                opt.get('effects', {}), 
                opt.get('outcome_text'), 
                opt.get('image_url_result')
            ) 
            for opt in sorted(self.options, key=lambda x: x.get('display_order', 0))
        ]

# Функция теперь принимает db_client
async def fetch_event_options(db_client: AsyncClient, event_id: int) -> List[Dict[str, Any]]:
    """Загружает варианты ответов для заданного ID события."""
    # Убираем импорт и проверку глобальной supabase
    # from data.database import supabase
    if not db_client:
        logging.error("Invalid db_client provided to fetch_event_options.")
        return []
    try:
        # Используем db_client
        query = (
            db_client.table("event_options")
            .select("id", "button_text", "effects", "outcome_text", "image_url_result", "next_event_name", "display_order")
            .eq("event_id", event_id)
            .order("display_order") # Запрашиваем сортировку сразу
        )
        response = await query.execute()
        return response.data if response.data else []
    except Exception as e:
        logging.exception(f"Error fetching options for event_id {event_id}: {e}")
        return []

def check_trigger_conditions(conditions: Optional[Dict[str, Any]], country: Country) -> bool:
    """Проверяет, выполняются ли условия события для текущего состояния страны."""
    if not conditions: # Если условий нет, событие может сработать
        return True
    
    for key, condition in conditions.items():
        if not hasattr(country, key):
            continue # Неизвестный параметр в условиях
            
        country_value = getattr(country, key)
        
        for operator, value in condition.items():
            if operator == "<=" and not (country_value <= value):
                return False
            if operator == ">=" and not (country_value >= value):
                return False
            if operator == "<" and not (country_value < value):
                return False
            if operator == ">" and not (country_value > value):
                return False
            if operator == "==" and not (country_value == value):
                return False
            if operator == "!=" and not (country_value != value):
                 return False
            # Можно добавить другие операторы при необходимости
            
    return True # Все условия выполнены

# Функция теперь принимает db_client
async def get_next_event(db_client: AsyncClient, country: Country) -> Optional[EventData]:
    """Выбирает и возвращает следующее событие из базы данных.

    Логика выбора (упрощенная):
    1. Ищет подходящие условные события.
    2. Если нет, ищет подходящие случайные/персонажные события.
    3. Выбирает одно случайным образом с учетом веса.
    4. Загружает варианты ответов для выбранного события.
    """
    # Убираем импорт и проверку глобальной supabase
    # from data.database import supabase
    if not db_client:
        logging.error("Invalid db_client provided to get_next_event.")
        return None

    possible_events = []
    try:
        # Используем db_client
        query_conditional = (
            db_client.table("events")
            .select("id", "name", "description", "image_url_prompt", "character_name", "trigger_conditions", "frequency_weight")
            .eq("event_type", "conditional")
            .lte("min_year", country.current_year)
            # TODO: Добавить проверку max_year, is_unique (по истории событий)
        )
        response_conditional = await query_conditional.execute()

        if response_conditional.data:
            for event_row in response_conditional.data:
                conditions = event_row.get("trigger_conditions")
                if check_trigger_conditions(conditions, country):
                    possible_events.append(event_row)
        
        if not possible_events:
            # Используем db_client
            query_random = (
                db_client.table("events")
                .select("id", "name", "description", "image_url_prompt", "character_name", "trigger_conditions", "frequency_weight")
                .in_("event_type", ["random", "character"]) # Ищем случайные и персонажные
                .lte("min_year", country.current_year)
                # TODO: Добавить проверку max_year, is_unique (по истории событий)
            )
            response_random = await query_random.execute()
            if response_random.data:
                possible_events.extend(response_random.data)

        if not possible_events:
            logging.warning(f"No suitable events found for player state: {country.get_state()}")
            return None # Или вернуть стандартное "ничего не происходит" событие?

        # Взвешенный случайный выбор
        weights = [event.get('frequency_weight', 1) for event in possible_events]
        chosen_event_row = random.choices(possible_events, weights=weights, k=1)[0]

        # --- Шаг 4: Загрузка вариантов --- 
        event_id = chosen_event_row['id']
        # Передаем db_client в fetch_event_options
        options = await fetch_event_options(db_client, event_id)

        if not options:
            logging.error(f"No options found for chosen event_id {event_id}! Skipping event.")
            # Передаем db_client при рекурсивном вызове
            return await get_next_event(db_client, country) # Рекурсивная попытка найти другое событие

        logging.info(f"Selected event: ID={event_id}, Name={chosen_event_row.get('name')}")
        return EventData(chosen_event_row, options)

    except Exception as e:
        logging.exception(f"Error getting next event: {e}")
        return None
