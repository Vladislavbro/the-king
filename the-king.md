# Описание игры: "Государь"

## Основная идея

"Государь" — это текстовая игра, реализованная в виде Telegram-бота, где игрок берет на себя роль правителя государства. Основная цель — управлять страной как можно дольше, принимая решения по различным событиям, которые влияют на ключевые показатели: поддержку народа, казну, армию и крестьян. Игра заканчивается, когда правитель "умирает" одним из возможных способов: свержение из-за низкой поддержки народа, банкротство из-за пустой казны, болезнь, завоевание врагами или естественная старость. Задача игрока — сбалансировать ресурсы и выжить как можно дольше.

## Механика игры

### События:
Игра строится вокруг событий, которые требуют от игрока выбора. События бывают:
- Случайные (например, наводнение или находка клада).
- Повторяющиеся (например, ежегодный сбор налогов).
- Уникальные (например, появление таинственного пророка).
- Зависящие от состояния страны (например, восстание крестьян при низкой поддержке народа).

Каждое событие сопровождается описанием и несколькими вариантами действий, которые игрок выбирает через кнопки.

### Показатели страны:
- **Поддержка народа** (от 0 до 100): показывает, насколько население доверяет правителю.
- **Казна** (число): деньги, доступные для расходов на армию, праздники или другие нужды.
- **Армия** (много, средне, мало): защищает страну, но требует финансирования.
- **Крестьяне** (много, средне, мало): производят доход для казны, но их число уменьшается при увеличении армии.

Показатели взаимосвязаны: больше армии — меньше крестьян, что снижает доход, а низкая поддержка народа может привести к бунту.

### Решения:
Игроку предлагаются варианты действий для каждого события (например, "потратить 500 на армию" или "дать крестьянам отдых"). Выбор влияет на показатели страны: повышение армии может уменьшить казну и крестьян, а щедрые траты на народ поднимут поддержку, но опустошат казну.

### Конец игры:
Игра завершается при достижении одного из условий "смерти" правителя. После этого бот удаляет все свои сообщения в чате и предлагает начать новую игру.

## Особенности игры

- **Платформа**: Telegram-бот, написанный на Python с использованием фреймворка `aiogram`.
- **Интерфейс**: Взаимодействие только через кнопки (без ввода текста игроком), чтобы бот мог управлять сообщениями и удалять их в конце игры.
- **Хранение данных**: Используется Supabase (на базе PostgreSQL) для сохранения прогресса игроков. Должна быть возможность переключиться на SQLite без больших изменений в коде.
- **Масштабируемость**: Игра должна поддерживать модульную структуру, чтобы разработчики могли легко добавлять новые события, механики или даже DLC (дополнительный контент).
- **Многопользовательность**: Бот должен поддерживать одновременную игру множества пользователей, каждый со своим состоянием страны.

## Пример сценария

1.  Игрок запускает бота командой `/start`.
2.  Бот отправляет сообщение: "На страну напали разбойники. Что делать?"
3.  Кнопки:
    - Кнопка 1: "Отправить армию (-200 казны, +10 поддержки)".
    - Кнопка 2: "Заплатить выкуп (-500 казны)".
    - Кнопка 3: "Ничего не делать (-20 поддержки)".
4.  Игрок выбирает вариант, бот обновляет показатели и отправляет следующее событие.
5.  Если казна падает до 0, бот пишет: "Вы обанкротились. Игра окончена", удаляет сообщения и предлагает начать заново.

## Цели для разработчиков

- Создать увлекательный симулятор с простой, но глубокой механикой.
- Обеспечить чистый интерфейс через кнопки и управление сообщениями.
- Сделать код модульным, чтобы можно было расширять игру в будущем.
- Реализовать надежное хранение данных с возможностью выбора базы данных.

Теперь, как вы просили, я прикладываю мое предыдущее сообщение об архитектуре игры, чтобы вы могли использовать его вместе с описанием для реализации проекта.

## Архитектура игры (из предыдущего сообщения)

Архитектура спроектирована так, чтобы быть модульной, масштабируемой и удобной для разработки. Ниже приведена структура директорий и описание модулей.

### Структура директорий

```text
/game-bot
├── /bot              # Логика Telegram-бота
│   ├── __init__.py
│   ├── handlers.py   # Обработчики команд и кнопок
│   └── main.py       # Точка входа, запуск бота
├── /game             # Игровая логика
│   ├── __init__.py
│   ├── core.py       # Основные классы (Country, Player)
│   ├── events.py     # Логика генерации событий
│   └── mechanics.py  # Механики игры (распределение ресурсов)
├── /data             # Работа с данными
│   ├── __init__.py
│   ├── database.py   # Подключение и запросы к Supabase
│   └── models.py     # Модели данных (таблицы)
├── /events           # Описание событий
│   ├── __init__.py
│   ├── base.py       # Базовый класс для событий
│   ├── random.py     # Случайные события
│   ├── seasonal.py   # Сезонные события (начало/конец года)
│   └── conditional.py# События, зависящие от состояния
├── /utils            # Вспомогательные утилиты
│   ├── __init__.py
│   ├── logger.py     # Логирование
│   └── helpers.py    # Полезные функции
├── config.py         # Конфигурация (токен бота, настройки)
├── requirements.txt  # Зависимости (aiogram, supabase-py)
└── README.md         # Описание проекта
```

### Описание модулей

-   **/bot** — Логика Telegram-бота
    -   `main.py`: Запускает бота, инициализирует `aiogram`, подключает обработчики из `handlers.py`.
    -   `handlers.py`: Обрабатывает команды (`/start`, `/stats`) и нажатия кнопок. Передает данные в игровую логику (`/game`).
-   **/game** — Игровая логика
    -   `core.py`: Классы `Country` (поддержка народа, казна, армия, крестьяне) и `Player` (Telegram ID, состояние игры).
    -   `events.py`: Генерация событий с учетом условий (время года, состояние страны, предыдущие решения).
    -   `mechanics.py`: Управление распределением ресурсов (армия и крестьяне: много, средне, мало) и влиянием решений на показатели.
-   **/data** — Хранение данных
    -   `database.py`: Подключение к Supabase через `supabase-py`. Функции для сохранения/загрузки данных игроков и сессий.
    -   `models.py`: Описание таблиц базы данных:
        -   `players`: Telegram ID, текущая сессия.
        -   `countries`: показатели страны для каждого игрока.
        -   `event_history`: история событий для учета зависимостей.
-   **/events** — Описание событий
    -   `base.py`: Базовый класс `Event` с общими методами (описание, варианты решений, применение эффектов).
    -   `random.py`: Случайные события с заданной вероятностью.
    -   `seasonal.py`: События, привязанные к началу, середине или концу года.
    -   `conditional.py`: События, зависящие от состояния страны (например, низкая поддержка народа).
-   **/utils** — Вспомогательные утилиты
    -   `logger.py`: Логирование для отладки и отслеживания ошибок.
    -   `helpers.py`: Утилиты для форматирования сообщений и генерации кнопок.
-   **config.py** — Конфигурация
    -   Хранит токен бота, настройки Supabase (URL, ключ), параметры игры.

### Как это работает

1.  **Старт игры**:
    Игрок пишет `/start`, бот создает запись в базе данных через `/data/database.py`, инициализирует объект `Country` с начальными показателями.
2.  **Генерация событий**:
    Модуль `/game/events.py` выбирает событие из `/events` на основе условий (вероятность, время года, состояние страны).
3.  **Взаимодействие**:
    Бот отправляет сообщение с описанием события и кнопками. Игрок нажимает кнопку, выбор обрабатывается, обновляются показатели.
4.  **Сохранение**:
    После каждого решения состояние игрока сохраняется в Supabase.
5.  **Конец игры**:
    При "смерти" правителя бот выводит итоговые результаты и предлагает начать заново. Если игрок хочет продолжить, бот удаляет все свои сообщения и игра начинается заново.

### Пример кода

#### `bot/main.py`:

```python
from aiogram import Bot, Dispatcher, executor
from bot.handlers import register_handlers
from config import TELEGRAM_TOKEN

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher(bot)

def main():
    register_handlers(dp)
    executor.start_polling(dp, skip_updates=True)

if __name__ == "__main__":
    main()
```

#### `game/core.py`:

```python
class Country:
    def __init__(self):
        self.support = 50  # Поддержка народа
        self.treasury = 1000  # Казна
        self.army = "medium"  # Армия: low, medium, high
        self.peasants = "medium"  # Крестьяне: low, medium, high

    def update(self, effects):
        for key, value in effects.items():
            if key in ["army", "peasants"]:
                setattr(self, key, value)
            else:
                current = getattr(self, key)
                setattr(self, key, current + value)
```

#### `events/base.py`:

```python
class Event:
    def __init__(self, description, options):
        self.description = description
        self.options = options  # {0: {"army": "high", "treasury": -200}, ...}

    def apply(self, choice, country):
        effects = self.options[choice]
        country.update(effects)
```

#### `bot/handlers.py`:

```python
from aiogram import Dispatcher, types
from game.core import Country
from game.events import get_next_event
from data.database import save_player_state, load_player_state

async def start_command(message: types.Message):
    player_id = message.from_user.id
    country = Country()
    save_player_state(player_id, country.__dict__)
    event = get_next_event(country)
    buttons = [types.InlineKeyboardButton(text=f"Вариант {i}", callback_data=f"choice_{i}")
               for i in range(len(event.options))]
    keyboard = types.InlineKeyboardMarkup().add(*buttons)
    await message.answer(event.description, reply_markup=keyboard)

async def button_callback(callback: types.CallbackQuery):
    player_id = callback.from_user.id
    choice = int(callback.data.split("_")[1])
    country_data = load_player_state(player_id)
    country = Country()
    country.__dict__.update(country_data)
    event = get_next_event(country) # Assumption: get_next_event needs the current state to decide
    event.apply(choice, country)
    save_player_state(player_id, country.__dict__)

    # Logic to determine next event or end game
    next_event = get_next_event(country)
    if next_event:
         buttons = [types.InlineKeyboardButton(text=f"Вариант {i}", callback_data=f"choice_{i}")
                   for i in range(len(next_event.options))]
         keyboard = types.InlineKeyboardMarkup().add(*buttons)
         await callback.message.edit_text(next_event.description, reply_markup=keyboard)
    else:
        # Game over logic
        await callback.message.edit_text("Игра окончена! (Логика завершения еще не реализована)")
        # Here add logic to delete messages etc.


def register_handlers(dp: Dispatcher):
    dp.register_message_handler(start_command, commands=["start"])
    dp.register_callback_query_handler(button_callback, lambda c: c.data.startswith("choice_"))
