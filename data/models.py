from pydantic import BaseModel, Field
from typing import Literal, Optional

# Определяем возможные значения для статуса армии и крестьян
StatusLevel = Literal["low", "medium", "high"]

class CountryState(BaseModel):
    """Pydantic модель для валидации и структурирования данных состояния страны.
       Используется для сохранения и загрузки из БД.
    """
    support: int = Field(..., ge=0) # Поддержка не может быть отрицательной (хотя <=0 - конец игры)
    treasury: int
    army: StatusLevel
    peasants: StatusLevel
    current_year: int = Field(..., gt=0) # Год должен быть положительным

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
    # Добавляем поле для хранения имени класса текущего активного события
    current_event_class_name: Optional[str] = None
    # Можно добавить другие поля, например, время последнего обновления
    # last_updated: datetime = Field(default_factory=datetime.utcnow)

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
