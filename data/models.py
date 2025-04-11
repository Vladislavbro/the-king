from pydantic import BaseModel, Field, field_validator
from typing import Literal, Optional, List, Any

# Определяем возможные значения для статуса армии и крестьян
StatusLevel = Literal["low", "medium", "high"]

class CountryState(BaseModel):
    """Pydantic модель для валидации и структурирования данных состояния страны.
       Используется для сохранения и загрузки из БД.
    """
    support: int = Field(50, ge=0) # Начальная поддержка
    treasury: int = 1000 # Начальная казна
    army: StatusLevel = "medium" # Начальный статус армии
    peasants: StatusLevel = "medium" # Начальный статус крестьян
    current_year: int = Field(1, gt=0) # Начинаем с 1-го года

    class Config:
        # Позволяет использовать модель как со словарями, так и с атрибутами объекта
        from_attributes = True
        # Можно добавить и другие настройки Pydantic при необходимости

class PlayerState(BaseModel):
    """Pydantic модель для валидации и структурирования данных игрока.
       Основная структура, сохраняемая в БД (например, в таблице players).
    """
    telegram_id: int = Field(..., gt=0)
    # В Supabase можно хранить состояние страны как JSONB поле
    country_state: CountryState
    # Изменяем поле: храним ID текущего события из таблицы events
    current_event_id: Optional[int] = None
    # Можно добавить другие поля, например, время последнего обновления
    # last_updated: datetime = Field(default_factory=datetime.utcnow)
    playthrough_count: int = 1
    completed_narrative_block_ids: List[int] = []
    message_ids: List[int] = [] # Добавляем поле для ID сообщений

    # Валидатор, чтобы убедиться, что из БД приходит список int
    @field_validator('completed_narrative_block_ids', mode='before')
    def validate_block_ids(cls, value: Any) -> List[int]:
        if value is None:
            return []
        if isinstance(value, list):
            # Проверяем, что все элементы - целые числа
            if all(isinstance(item, int) for item in value):
                return value
        # Попытка конвертации, если это строка типа "{1,2,3}" из Postgres Array
        if isinstance(value, str) and value.startswith('{') and value.endswith('}'):
            try:
                # Убираем скобки и разделяем по запятой
                cleaned_value = value[1:-1]
                if not cleaned_value: # Пустой массив {} 
                    return []
                return [int(item.strip()) for item in cleaned_value.split(',')]
            except ValueError:
                raise ValueError("Invalid array format for completed_narrative_block_ids")
        raise ValueError("completed_narrative_block_ids must be a list of integers or a valid Postgres array string")

    # Добавляем такой же валидатор для message_ids
    @field_validator('message_ids', mode='before')
    def validate_message_ids(cls, value: Any) -> List[int]:
        if value is None:
            return []
        if isinstance(value, list):
            if all(isinstance(item, int) for item in value):
                return value
        if isinstance(value, str) and value.startswith('{') and value.endswith('}'):
            try:
                cleaned_value = value[1:-1]
                if not cleaned_value: return []
                return [int(item.strip()) for item in cleaned_value.split(',')]
            except ValueError:
                 raise ValueError("Invalid array format for message_ids")
        raise ValueError("message_ids must be a list of integers or a valid Postgres array string")

    class Config:
        from_attributes = True

# Пример использования:
# data_from_db = { # Данные, полученные из Supabase
#     "telegram_id": 12345,
#     "country_state": {
#         "support": 45,
#         "treasury": 1200,
#         "army": "medium",
#         "peasants": "high",
#         "current_year": 3
#     }
# }
# try:
#     player_data = PlayerState.model_validate(data_from_db)
#     print(f"Данные игрока {player_data.telegram_id} валидны.")
#     print(f"Казна: {player_data.country_state.treasury}")
# except ValidationError as e:
#     print(f"Ошибка валидации данных из БД: {e}")
