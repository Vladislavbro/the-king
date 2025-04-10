from typing import List, Type, Optional, TYPE_CHECKING
import random

from events.base import Event
# Импортируем типы событий (пока только базовый, позже добавим остальные)
# from events.random import RandomEvent
# from events.conditional import ConditionalEvent
# from events.seasonal import SeasonalEvent

if TYPE_CHECKING:
    from game.core import Country

# --- Пример тестовых событий --- 

class HarvestFestivalEvent(Event):
    def __init__(self):
        options = [
            ("Устроить скромный праздник (+5 поддержки, -100 казны)", {"support": 5, "treasury": -100}),
            ("Закатить пир на весь мир! (+15 поддержки, -500 казны)", {"support": 15, "treasury": -500}),
            ("Отказаться от праздника (-5 поддержки)", {"support": -5})
        ]
        super().__init__(
            description="Крестьяне собрали урожай! Время для праздника урожая?",
            options=options
        )

class MerchantCaravanEvent(Event):
    def __init__(self):
        options = [
            ("Хорошо поторговать (+500 казны)", {"treasury": 500}),
            ("Обложить купцов данью (+200 казны, -5 поддержки)", {"treasury": 200, "support": -5}),
            ("Прогнать их (-100 казны)", {"treasury": -100}) # Возможно, они обиделись и что-то сломали
        ]
        super().__init__(
            description="В столицу прибыл богатый торговый караван.",
            options=options
        )

# Список ВСЕХ доступных событий (пока только тестовые)
# Позже сюда добавятся события из других модулей (random, conditional, seasonal)
AVAILABLE_EVENTS: List[Type[Event]] = [
    HarvestFestivalEvent,
    MerchantCaravanEvent,
    # Добавить другие классы событий здесь
]

# Список событий, которые могут происходить только раз в год (например, сбор налогов)
YEARLY_EVENTS: List[Type[Event]] = [
    # Например, TaxCollectionEvent
]

# Список событий, которые уже произошли в текущем году (чтобы не повторялись слишком часто)
# Эту логику нужно будет сбрасывать каждый "год"
# Возможно, лучше хранить это состояние в объекте Player или Country
_events_this_year: set = set()


def get_next_event(country: 'Country') -> Optional[Event]:
    """Выбирает и возвращает следующее событие для игрока.

    Args:
        country: Текущее состояние страны игрока.

    Returns:
        Объект события или None, если подходящих событий нет (маловероятно).
    """
    
    # TODO: Реализовать логику выбора события:
    # 1. Проверить, не пора ли для годового события (налоги и т.д.)?
    # 2. Проверить условные события (ConditionalEvent), срабатывают ли их is_triggered?
    # 3. Выбрать случайное событие (RandomEvent) из оставшихся, учитывая _events_this_year
    # 4. Если ничего не найдено (крайне редкий случай), вернуть None или стандартное событие.

    # --- Пока что просто выбираем случайное из доступных тестовых ---
    possible_events = [event_class for event_class in AVAILABLE_EVENTS if event_class.is_triggered(country)]

    if not possible_events:
        print("Предупреждение: Не найдено подходящих событий!")
        return None # Или вернуть какое-то событие по умолчанию?

    # Выбираем случайный класс события и создаем его экземпляр
    SelectedEventClass = random.choice(possible_events)
    return SelectedEventClass()
