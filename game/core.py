from typing import Dict, Any
import config

class Country:
    """Класс, представляющий состояние страны игрока."""
    def __init__(self):
        self.support: int = config.INITIAL_SUPPORT
        self.treasury: int = config.INITIAL_TREASURY
        self.army: str = config.INITIAL_ARMY # Возможные значения: low, medium, high
        self.peasants: str = config.INITIAL_PEASANTS # Возможные значения: low, medium, high
        # Дополнительные параметры можно добавить позже (например, год правления)
        self.current_year: int = 1

    def update(self, effects: Dict[str, Any]):
        """Обновляет показатели страны на основе словаря эффектов события."""
        for key, value in effects.items():
            if hasattr(self, key):
                current_value = getattr(self, key)
                if isinstance(current_value, int):
                    setattr(self, key, current_value + value)
                elif isinstance(current_value, str):
                    # Пока просто присваиваем новое строковое значение (для army, peasants)
                    setattr(self, key, value)
                # Добавить обработку других типов, если потребуется
            else:
                # Можно добавить логирование или обработку неизвестных ключей
                print(f"Предупреждение: Неизвестный ключ '{key}' в эффектах события.")

    def get_state(self) -> Dict[str, Any]:
        """Возвращает текущее состояние страны в виде словаря."""
        return {
            "support": self.support,
            "treasury": self.treasury,
            "army": self.army,
            "peasants": self.peasants,
            "current_year": self.current_year
        }

    def load_state(self, state_data: Dict[str, Any]):
        """Загружает состояние страны из словаря."""
        self.support = state_data.get("support", config.INITIAL_SUPPORT)
        self.treasury = state_data.get("treasury", config.INITIAL_TREASURY)
        self.army = state_data.get("army", config.INITIAL_ARMY)
        self.peasants = state_data.get("peasants", config.INITIAL_PEASANTS)
        self.current_year = state_data.get("current_year", 1)


class Player:
    """Класс, представляющий игрока."""
    def __init__(self, telegram_id: int):
        self.telegram_id: int = telegram_id
        self.country: Country = Country()
        # Можно добавить другие атрибуты игрока, например, историю сообщений
        self.message_history: list[int] = []

    def get_country_state(self) -> Dict[str, Any]:
        """Возвращает состояние страны текущего игрока."""
        return self.country.get_state()

    def load_country_state(self, state_data: Dict[str, Any]):
        """Загружает состояние страны для текущего игрока."""
        self.country.load_state(state_data)
