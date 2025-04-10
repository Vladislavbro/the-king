from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .core import Country

# Определяем уровни для армии и крестьян для удобства сравнения и логики
ARMY_LEVELS = {"low": 1, "medium": 2, "high": 3}
PEASANT_LEVELS = {"low": 1, "medium": 2, "high": 3}

# Примерные правила взаимосвязи (можно усложнить)
# - Увеличение армии может уменьшать крестьян
# - Уменьшение крестьян снижает доход (это будет в логике событий/годового отчета)
# - Низкая поддержка народа < 10 может вызвать событие бунта (это будет в game/events.py)
# - Казна < 0 = конец игры (это будет в bot/handlers.py)


def check_game_over_conditions(country: 'Country') -> str | None:
    """Проверяет, выполняются ли условия конца игры.

    Args:
        country: Объект состояния страны.

    Returns:
        Строку с причиной конца игры или None, если игра продолжается.
    """
    if country.support <= 0:
        return "Народ сверг вас из-за крайне низкой поддержки!"
    if country.treasury < 0: # Позволяем иметь 0 казны, но не отрицательную
        return "Казна пуста! Государство обанкротилось."
    # Другие условия (старость, завоевание) можно добавить позже

    # Пример условия на старость (например, после 40 лет правления)
    if country.current_year > 40: # Устанавливаем лимит в 40 лет правления
       return "Вы правили долго и мудро, но годы берут свое. Вы покинули этот мир от старости."

    return None


def apply_indirect_effects(country: 'Country'):
    """Применяет непрямые эффекты изменения состояния.
       Например, изменение числа крестьян при изменении армии.
       (Пока заглушка, логика будет добавлена позже)
    """
    # Пример: если армия 'high', а крестьяне 'high', уменьшить крестьян до 'medium'
    # if country.army == "high" and country.peasants == "high":
    #     country.peasants = "medium"
    #     print("Из-за большой армии пришлось забрать больше людей у полей.")
    pass # Реализуем позже


def calculate_yearly_income(country: 'Country') -> int:
    """Рассчитывает годовой доход на основе числа крестьян.
       (Пока простая заглушка)
    """
    income_per_level = {"low": 300, "medium": 600, "high": 1000}
    return income_per_level.get(country.peasants, 0)

def calculate_yearly_expenses(country: 'Country') -> int:
    """Рассчитывает годовые расходы на основе размера армии.
       (Пока простая заглушка)
    """
    expense_per_level = {"low": 100, "medium": 300, "high": 700}
    return expense_per_level.get(country.army, 0)
