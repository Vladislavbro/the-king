from typing import Dict, Any, List, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from game.core import Country

class Event:
    """Базовый класс для всех игровых событий."""
    def __init__(self, description: str, options: List[Tuple[str, Dict[str, Any]]]):
        """
        Args:
            description: Текстовое описание события, которое увидит игрок.
            options: Список кортежей. Каждый кортеж содержит:
                     - Текст варианта ответа (для кнопки)
                     - Словарь эффектов этого варианта (ключ - атрибут Country, значение - изменение)
        """
        if not description:
            raise ValueError("Описание события не может быть пустым.")
        if not options:
            raise ValueError("Событие должно иметь хотя бы один вариант ответа.")

        self.description: str = description
        # Храним варианты как список кортежей (текст_кнопки, словарь_эффектов)
        self.options: List[Tuple[str, Dict[str, Any]]] = options

    def apply_effects(self, choice_index: int, country: 'Country'):
        """Применяет эффекты выбранного варианта к состоянию страны."""
        if not 0 <= choice_index < len(self.options):
            # Обработка неверного индекса, хотя при использовании кнопок это маловероятно
            print(f"Ошибка: Неверный индекс выбора ({choice_index}) для события.")
            return

        _text, effects = self.options[choice_index]
        country.update(effects)
        # После применения прямых эффектов, увеличиваем год
        country.current_year += 1
        # Можно добавить вызов для непрямых эффектов из mechanics.py здесь,
        # если они должны применяться после каждого события
        # from game.mechanics import apply_indirect_effects
        # apply_indirect_effects(country)

    def get_options_text(self) -> List[str]:
        """Возвращает список текстов вариантов для кнопок."""
        return [text for text, _effects in self.options]

    @classmethod
    def is_triggered(cls, country: 'Country') -> bool:
        """Метод для проверки, должно ли событие сработать при текущем состоянии страны.
           В базовом классе всегда True, переопределяется в наследниках (особенно conditional).
        """
        return True
