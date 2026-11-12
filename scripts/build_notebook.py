"""Собрать учебный ноутбук из проверяемых Markdown- и code-ячеек."""

from __future__ import annotations

from pathlib import Path

import nbformat


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = PROJECT_ROOT / "notebooks" / "HW_03_python_ds.ipynb"


def md(text: str) -> nbformat.NotebookNode:
    """Создать Markdown-ячейку."""

    return nbformat.v4.new_markdown_cell(text.strip())


def code(text: str) -> nbformat.NotebookNode:
    """Создать кодовую ячейку."""

    return nbformat.v4.new_code_cell(text.strip())


cells = [
    md(
        """
# Домашнее задание 3. Парсинг, Git и тестирование на Python

Этот ноутбук является исполняемой учебной демонстрацией локального проекта `books_scraper`.

## Преамбула и дисклеймер

Исходный шаблон содержит технические противоречия и не определяет часть контракта. Мы сохраняем официальные учебные цели, но явно вводим рабочие гипотезы:

1. используется Python 3.10+ и HTTPS;
2. единственный источник реализации — `scraper.py`;
3. данные книги имеют фиксированные ключи и типы;
4. пагинация идёт по ссылке `next`;
5. результат сохраняется как JSON в UTF-8;
6. запросы имеют тайм-аут и проверку статуса;
7. 19:00 — локальное время компьютера;
8. бесконечный планировщик не запускается при `Run All`;
9. основные тесты работают без живой сети.

Эти уточнения не выдаются за дополнительные требования преподавателя. Их назначение — сделать решение воспроизводимым и проверяемым. Подробности находятся в `УЧЕБНЫЙ_РАЗБОР_HW03.md` и отчёте по шаблону.
"""
    ),
    md(
        """
## Подготовка окружения

Ноутбук импортирует код из корня проекта. Если он открыт из каталога `notebooks/`, корень определяется как родительская папка.

### Комментарии по доработкам и гипотезам

- Зависимости устанавливаются в отдельное виртуальное окружение.
- В кодовых ячейках нет `pip install`: установка является отдельным воспроизводимым шагом из README.
- Это исключает ситуацию, когда ноутбук незаметно меняет глобальное окружение.
"""
    ),
    code(
        """
from pathlib import Path
import json
import schedule
import subprocess
import sys

PROJECT_ROOT = Path.cwd().resolve()
if PROJECT_ROOT.name == "notebooks":
    PROJECT_ROOT = PROJECT_ROOT.parent
if not (PROJECT_ROOT / "scraper.py").exists():
    raise RuntimeError(f"Не найден scraper.py в {PROJECT_ROOT}")
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scraper import (
    DEFAULT_OUTPUT_PATH,
    SCHEDULE_TAG,
    configure_schedule,
    extract_book_links,
    extract_next_page_url,
    get_book_data,
    load_books,
    parse_book_html,
    scrape_books,
)

print(f"Корень проекта: {PROJECT_ROOT}")
print(f"Python: {sys.version.split()[0]}")
"""
    ),
    md(
        """
# Задание 1. Сбор данных об одной книге

## Теория перед решением

Сетевой запрос и разбор HTML — разные операции. `get_book_data` отвечает за получение страницы, а `parse_book_html` преобразует готовый HTML в словарь. Такое разделение позволяет тестировать парсинг на локальной фикстуре.

Контракт результата: URL, название, цена как число, рейтинг 1–5, наличие, количество, описание и таблица Product Information.
"""
    ),
    md(
        """
## Комментарии по доработкам и гипотезам — задание 1

- **Гипотеза:** цена нормализуется в `float`, рейтинг — в `int`, описание может быть `None`.
- **Доработка:** добавлена чистая функция `parse_book_html`.
- **Зачем:** один и тот же HTML должен давать один и тот же результат без зависимости от сети.
- **Влияние:** обязательная функция `get_book_data` сохранена; дополнительный уровень делает её тестируемой.
"""
    ),
    code(
        """
fixture_path = PROJECT_ROOT / "tests" / "fixtures" / "book_page.html"
fixture_html = fixture_path.read_text(encoding="utf-8")
sample_url = "https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html"

sample_book = parse_book_html(fixture_html, sample_url)
sample_book
"""
    ),
    code(
        """
required_keys = {
    "url", "title", "price_gbp", "rating", "availability",
    "stock_count", "description", "product_information",
}
assert required_keys == set(sample_book)
assert sample_book["title"] == "A Light in the Attic"
assert sample_book["price_gbp"] == 51.77
assert sample_book["rating"] == 3
print("Задание 1: локальная проверка пройдена")
"""
    ),
    md(
        """
### Необязательная сетевая демонстрация

По умолчанию она отключена, чтобы `Run All` оставался воспроизводимым без интернета. Для ручной проверки установите `RUN_NETWORK_DEMO = True`.
"""
    ),
    code(
        """
RUN_NETWORK_DEMO = False

if RUN_NETWORK_DEMO:
    live_book = get_book_data(sample_url)
    print(live_book)
else:
    print("Сетевая демонстрация пропущена; использована локальная HTML-фикстура.")
"""
    ),
    md(
        """
# Задание 2. Сбор данных обо всех книгах

## Теория перед решением

Состояние цикла состоит из текущего URL, множества посещённых страниц и накопленного списка книг. После каждой итерации список содержит книги всех уже посещённых страниц. Обход завершается, когда ссылка `next` отсутствует.

`max_pages` не заменяет полный режим: это дополнительный ограничитель для демонстрации и тестов. При значении `None` собирается весь каталог.
"""
    ),
    md(
        """
## Комментарии по доработкам и гипотезам — задание 2

- **Гипотеза:** ссылка `next` определяет продолжение каталога; число 50 не зашивается в код.
- **Доработка:** добавлены защита от цикла, `urljoin`, `max_pages` и управляемая задержка.
- **Зачем:** алгоритм должен корректно завершаться и не зависеть от текущего размера сайта.
- **Влияние:** стандартный вызов собирает всё, ограниченный режим ускоряет демонстрацию.
"""
    ),
    code(
        """
catalogue_fixture = (
    PROJECT_ROOT / "tests" / "fixtures" / "catalogue_page_1.html"
).read_text(encoding="utf-8")
catalogue_url = "https://example.test/catalogue/page-1.html"

print("Ссылки книг:")
for link in extract_book_links(catalogue_fixture, catalogue_url):
    print(" -", link)
print("Следующая страница:", extract_next_page_url(catalogue_fixture, catalogue_url))
"""
    ),
    code(
        """
artifact_path = PROJECT_ROOT / "artifacts" / "books_data.txt"
if artifact_path.exists():
    books = load_books(artifact_path)
    source = "готовый полный артефакт"
else:
    books = scrape_books(max_pages=1)
    source = "сетевая демонстрация одной страницы"

print(f"Источник: {source}")
print(f"Количество книг: {len(books)}")
print("Первая книга:", books[0]["title"] if books else "нет данных")
"""
    ),
    md(
        """
# Задание 3. Настройка регулярной выгрузки

## Теория перед решением

`schedule` хранит задачи в памяти процесса. Настройка задания и бесконечный цикл ожидания разделены: ноутбук показывает созданное задание, а реальный цикл запускается командой `python scraper.py --schedule --at 19:00`.
"""
    ),
    md(
        """
## Комментарии по доработкам и гипотезам — задание 3

- **Гипотеза:** 19:00 — локальное время компьютера.
- **Доработка:** `configure_schedule` не запускает бесконечный цикл.
- **Зачем:** ноутбук обязан завершать `Run All`.
- **Влияние:** расписание проверяется безопасно, постоянный процесс запускается отдельно.
"""
    ),
    code(
        """
job = configure_schedule("19:00", output_path=DEFAULT_OUTPUT_PATH)
print("Созданное задание:", job)
print("Количество задач с тегом:", len(schedule.get_jobs(SCHEDULE_TAG)))
schedule.clear(SCHEDULE_TAG)
print("После демонстрации очередь очищена.")
"""
    ),
    md(
        """
# Задание 4. Автотесты

## Теория перед решением

Модульные тесты должны проверять наш код, а не доступность интернета. Поэтому используются HTML-фикстуры, поддельная HTTP-сессия и временный каталог `tmp_path`.
"""
    ),
    md(
        """
## Комментарии по доработкам и гипотезам — задание 4

- **Гипотеза:** обычный `pytest` работает без живой сети.
- **Доработка:** тесты покрывают разбор, пагинацию, ошибки, сохранение и расписание.
- **Зачем:** сетевой сбой не должен создавать ложное падение тестов.
- **Влияние:** результат повторяем и выполняется значительно быстрее полного парсинга.
"""
    ),
    code(
        """
test_result = subprocess.run(
    [sys.executable, "-m", "pytest", "-q"],
    cwd=PROJECT_ROOT,
    text=True,
    capture_output=True,
    check=False,
)
print(test_result.stdout)
if test_result.stderr:
    print(test_result.stderr)
assert test_result.returncode == 0, "Тесты завершились с ошибкой"
"""
    ),
    md(
        """
# Задание 5. Локальная структура и подготовка к GitHub

Локальные артефакты собраны. Удалённый репозиторий, ветка и Pull Request намеренно не создавались: публикация является отдельным внешним действием.
"""
    ),
    md(
        """
## Комментарии по доработкам и гипотезам — задание 5

- **Гипотеза:** сначала проект проходит локальную проверку, затем публикуется.
- **Доработка:** добавлены README, учебный разбор, фикстуры и генератор ноутбука.
- **Зачем:** проверяющий должен воспроизвести проект после чистого клонирования.
- **Влияние:** локальная часть готова; GitHub-часть выполняется только после явного разрешения пользователя.
"""
    ),
    code(
        """
expected_paths = [
    "scraper.py",
    "README.md",
    "requirements.txt",
    ".gitignore",
    "artifacts/books_data.txt",
    "tests/test_scraper.py",
    "notebooks/HW_03_python_ds.ipynb",
]

for relative_path in expected_paths:
    exists = (PROJECT_ROOT / relative_path).exists()
    print(f"{'OK' if exists else 'НЕТ'}: {relative_path}")
"""
    ),
    md(
        """
# Итоговая трассировка

```text
HTML каталога
→ ссылки книг
→ HTML каждой книги
→ нормализованные словари
→ единый список
→ JSON-артефакт
→ проверка pytest
→ ежедневный запуск по расписанию
```

## Что необходимо уметь объяснить

- почему сетевой слой отделён от парсинга;
- как определяется последняя страница;
- зачем нужны тайм-аут и `raise_for_status`;
- почему тесты используют фикстуры;
- почему бесконечный цикл не запускается в ноутбуке;
- какие гипотезы введены из-за недостаточности исходного шаблона.
"""
    ),
    md(
        """
# Рефлексия

Рефлексию необходимо заполнить самостоятельно, своими словами, в соответствии с исходным заданием.

1. Что было задано и что получилось:  
   `Ответ: ...`

2. Как выполняли:  
   `Ответ: ...`

3. Использование ИИ:  
   `Ответ: ...`

4. Что осталось непонятным:  
   `Ответ: ...`

5. Самооценка по критериям:  
   `Ответ: ...`

6. Обратная связь по заданию:  
   `Ответ: ...`
"""
    ),
]


notebook = nbformat.v4.new_notebook(
    cells=cells,
    metadata={
        "kernelspec": {
            "display_name": "Python 3 (ipykernel)",
            "language": "python",
            "name": "python3",
        },
        "language_info": {
            "name": "python",
            "version": "3.12",
        },
    },
)

OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
nbformat.write(notebook, OUTPUT_PATH)
print(OUTPUT_PATH)
