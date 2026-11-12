"""Собрать заполненный ноутбук на основе исходного шаблона преподавателя."""

from __future__ import annotations

from pathlib import Path

import nbformat


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_PATH = PROJECT_ROOT.parent / "Задание.txt"
OUTPUT_PATH = PROJECT_ROOT / "notebooks" / "HW_03_python_ds_2025.ipynb"


def md(text: str) -> nbformat.NotebookNode:
    """Создать дополнительную Markdown-ячейку."""

    return nbformat.v4.new_markdown_cell(text.strip())


def replace_code(
    cell: nbformat.NotebookNode,
    source: str,
) -> nbformat.NotebookNode:
    """Заполнить предусмотренную кодовую ячейку и очистить старый вывод."""

    if cell.cell_type != "code":
        raise TypeError("Ожидалась кодовая ячейка исходного шаблона")
    cell.source = source.strip()
    cell.execution_count = None
    cell.outputs = []
    return cell


template = nbformat.read(TEMPLATE_PATH, as_version=4)
if len(template.cells) != 15:
    raise ValueError("Структура исходного шаблона неожиданно изменилась")

original_markdown = [
    cell.source for cell in template.cells if cell.cell_type == "markdown"
]

template.cells[1] = replace_code(
    template.cells[1],
    """
# Исходная команда шаблона была предназначена для ручной установки:
# ! pip install -q schedule pytest  # установка библиотек, если ещё не
#
# В проекте зависимости устанавливаются один раз из requirements.txt.
# Эта ячейка только проверяет, что нужные пакеты доступны в текущем ядре.
from importlib.util import find_spec

required_packages = {
    "bs4": "beautifulsoup4",
    "pytest": "pytest",
    "requests": "requests",
    "schedule": "schedule",
}
missing_packages = [
    package_name
    for module_name, package_name in required_packages.items()
    if find_spec(module_name) is None
]

if missing_packages:
    raise RuntimeError(
        "Не установлены зависимости: " + ", ".join(missing_packages)
    )

print("Зависимости доступны; установка из ноутбука не требуется.")
""",
)

template.cells[2] = replace_code(
    template.cells[2],
    """
# Библиотеки, которые могут вам понадобиться
# При необходимости расширяйте список
import time
import requests
import schedule
from bs4 import BeautifulSoup

from pathlib import Path
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
    get_book_data as project_get_book_data,
    load_books,
    parse_book_html,
    scrape_books as project_scrape_books,
)

print(f"Корень проекта: {PROJECT_ROOT}")
print(f"Python: {sys.version.split()[0]}")
""",
)

template.cells[4] = replace_code(
    template.cells[4],
    '''
def get_book_data(book_url: str) -> dict:
    """Получить нормализованные данные об одной книге.

    Args:
        book_url: Абсолютный URL страницы книги на Books to Scrape.

    Returns:
        Словарь с URL, названием, ценой, рейтингом, наличием,
        количеством, описанием и таблицей Product Information.

    Raises:
        requests.RequestException: Если страницу не удалось загрузить.
        ValueError: Если обязательные элементы страницы отсутствуют.
    """

    return project_get_book_data(book_url)
''',
)

template.cells[5] = replace_code(
    template.cells[5],
    """
# Используйте для самопроверки
book_url = (
    "https://books.toscrape.com/catalogue/"
    "a-light-in-the-attic_1000/index.html"
)
RUN_NETWORK_DEMO = False

if RUN_NETWORK_DEMO:
    book_data = get_book_data(book_url)
    source = "живая страница сайта"
else:
    fixture_path = PROJECT_ROOT / "tests" / "fixtures" / "book_page.html"
    fixture_html = fixture_path.read_text(encoding="utf-8")
    book_data = parse_book_html(fixture_html, book_url)
    source = "локальная HTML-фикстура"

required_keys = {
    "url",
    "title",
    "price_gbp",
    "rating",
    "availability",
    "stock_count",
    "description",
    "product_information",
}
assert set(book_data) == required_keys
print(f"Источник проверки: {source}")
book_data
""",
)

template.cells[7] = replace_code(
    template.cells[7],
    '''
def scrape_books(is_save: bool = False, **kwargs) -> list[dict]:
    """Собрать данные обо всех книгах каталога.

    Args:
        is_save: Сохранить ли результат в ``books_data.txt``.
        **kwargs: Дополнительные параметры проверяемой реализации:
            путь сохранения, тайм-аут, задержка и лимит страниц.

    Returns:
        Список нормализованных словарей с данными книг.

    Raises:
        requests.RequestException: Если сетевой запрос завершился ошибкой.
        RuntimeError: Если обнаружен цикл пагинации.
        ValueError: Если передан некорректный лимит страниц.
    """

    return project_scrape_books(is_save=is_save, **kwargs)
''',
)

template.cells[8] = replace_code(
    template.cells[8],
    """
# Проверка работоспособности функции.
# Полный сетевой запуск соответствует исходной строке:
# res = scrape_books(is_save=True)
# Чтобы Run All не выполнял повторно более тысячи запросов, используем
# уже сформированный тем же кодом артефакт. При его отсутствии запускается
# демонстрационный сбор одной страницы.
artifact_path = PROJECT_ROOT / "artifacts" / "books_data.txt"

if artifact_path.exists():
    res = load_books(artifact_path)
    source = "готовый полный артефакт"
else:
    res = scrape_books(is_save=True, max_pages=1)
    source = "сетевая демонстрация одной страницы"

assert isinstance(res, list)
assert all(isinstance(book, dict) for book in res)
print("Источник:", source)
print(type(res), len(res))
""",
)

template.cells[10] = replace_code(
    template.cells[10],
    """
# НАЧАЛО ВАШЕГО РЕШЕНИЯ
# Создаём задание на 19:00, но не запускаем бесконечный цикл в ноутбуке.
job = configure_schedule("19:00", output_path=DEFAULT_OUTPUT_PATH)

print("Созданное задание:", job)
print("Задач с тегом проекта:", len(schedule.get_jobs(SCHEDULE_TAG)))
print("Постоянный запуск: python scraper.py --schedule --at 19:00")

# Очищаем очередь после демонстрации, чтобы повторный Run All был стабильным.
schedule.clear(SCHEDULE_TAG)
# КОНЕЦ ВАШЕГО РЕШЕНИЯ
""",
)

template.cells[12] = replace_code(
    template.cells[12],
    """
# Ячейка для демонстрации работоспособности.
# В исходном шаблоне указан путь test/test_scraper.py; фактическая папка
# по требованиям задания называется tests, поэтому запускаем её явно.
test_result = subprocess.run(
    [sys.executable, "-m", "pytest", "-q", "tests/test_scraper.py"],
    cwd=PROJECT_ROOT,
    text=True,
    capture_output=True,
    check=False,
)

print(test_result.stdout)
if test_result.stderr:
    print(test_result.stderr)
assert test_result.returncode == 0, "Тесты завершились с ошибкой"
""",
)

preamble = md(
    """
# Преамбула и дисклеймер

Этот файл собран на основе исходного `Задание.txt`. Официальные Markdown-формулировки задания сохранены без редактирования, включая спорные формулировки и опечатки. Заполняются только предусмотренные кодовые ячейки; пояснения добавляются отдельными блоками.

## Как уточняется постановка задачи

1. Единственным источником рабочей реализации считается `scraper.py`; ноутбук показывает её применение и результаты проверки.
2. Данные сохраняются как JSON в UTF-8, хотя расширение файла по заданию остаётся `.txt`.
3. Пагинация идёт по фактической ссылке `next`, а не по жёстко заданному числу страниц.
4. Сетевые запросы имеют тайм-аут и проверку HTTP-статуса.
5. Автотесты не зависят от живого сайта и используют локальные HTML-фикстуры.
6. Время `19:00` трактуется как локальное время компьютера.
7. Бесконечный цикл планировщика не запускается при `Run All`.
8. GitHub-публикация не выполняется без отдельного явного запроса.

Эти гипотезы не подменяют требования преподавателя: они делают неоднозначные места проверяемыми и воспроизводимыми.
"""
)

environment_notes = md(
    """
## Комментарии по доработкам и гипотезам — окружение

- **Исправление:** установка пакетов из ячейки заменена проверкой зависимостей; полный список хранится в `requirements.txt`.
- **Гипотеза:** блокнот запускается из корня проекта либо из папки `notebooks`.
- **Зачем:** повторный запуск не должен менять глобальное окружение или зависеть от текущего каталога.
- **Влияние:** перед первым запуском окружение устанавливается один раз по инструкции из `README.md`.
"""
)

task_1_notes = md(
    """
### Комментарии по доработкам и гипотезам — задание 1

- **Исправление:** сетевой запрос отделён от функции `parse_book_html`, разбирающей уже полученный HTML.
- **Гипотеза:** цена хранится как `float`, рейтинг как `int`, количество как `int | None`, описание как `str | None`.
- **Зачем:** разбор страницы можно проверить без интернета на фиксированном HTML.
- **Влияние:** требуемая `get_book_data` сохранена, но её результат имеет явный контракт и типы.
"""
)

task_2_notes = md(
    """
### Комментарии по доработкам и гипотезам — задание 2

- **Исправление:** следующая страница определяется по ссылке `next`, абсолютные адреса собираются через `urljoin`.
- **Гипотеза:** `max_pages=None` означает полный каталог; положительное значение используется только для быстрой демонстрации.
- **Зачем:** число страниц сайта может измениться, а цикл пагинации должен быть обнаружен явно.
- **Влияние:** обычный вызов собирает весь каталог; `is_save=True` сохраняет тот же список в `books_data.txt`.
"""
)

task_3_notes = md(
    """
### Комментарии по доработкам и гипотезам — задание 3

- **Исправление:** настройка расписания отделена от бесконечного цикла ожидания.
- **Гипотеза:** `19:00` относится к часовому поясу локальной операционной системы.
- **Зачем:** выполнение всех ячеек должно завершаться, а не зависать в `while True`.
- **Влияние:** ноутбук проверяет созданное задание; постоянный процесс запускается отдельно через `scraper.py --schedule`.
"""
)

task_4_notes = md(
    """
### Комментарии по доработкам и гипотезам — задание 4

- **Исправление:** путь из шаблона `test/test_scraper.py` заменён на фактический `tests/test_scraper.py`.
- **Гипотеза:** модульные тесты должны проверять наш код, а не доступность внешнего сайта.
- **Зачем:** сетевой сбой не должен давать ложное падение домашней работы.
- **Влияние:** тесты используют фикстуры и поддельную HTTP-сессию, но дополнительно был выполнен полный сетевой сбор.
"""
)

task_5_notes = md(
    """
### Комментарии по доработкам и гипотезам — задание 5

- **Исправление:** локальная готовность проекта проверяется до публикации.
- **Гипотеза:** создание репозитория, отправка ветки и Pull Request являются отдельными внешними действиями.
- **Зачем:** проверка структуры не требует доступа к аккаунту GitHub и не создаёт публикаций без разрешения.
- **Влияние:** обязательные локальные файлы готовы; GitHub-этап остаётся неподтверждённым до отдельного запроса.
"""
)

structure_check = nbformat.v4.new_code_cell(
    """
expected_paths = [
    "scraper.py",
    "README.md",
    "requirements.txt",
    ".gitignore",
    "artifacts/books_data.txt",
    "tests/test_scraper.py",
    "notebooks/HW_03_python_ds_2025.ipynb",
]

missing_paths = []
for relative_path in expected_paths:
    exists = (PROJECT_ROOT / relative_path).exists()
    print(f"{'OK' if exists else 'НЕТ'}: {relative_path}")
    if not exists:
        missing_paths.append(relative_path)

assert not missing_paths, f"Не найдены файлы: {missing_paths}"
""".strip()
)

cells = [
    preamble,
    template.cells[0],
    environment_notes,
    template.cells[1],
    template.cells[2],
    template.cells[3],
    task_1_notes,
    template.cells[4],
    template.cells[5],
    template.cells[6],
    task_2_notes,
    template.cells[7],
    template.cells[8],
    template.cells[9],
    task_3_notes,
    template.cells[10],
    template.cells[11],
    task_4_notes,
    template.cells[12],
    template.cells[13],
    task_5_notes,
    structure_check,
    template.cells[14],
]

notebook = nbformat.v4.new_notebook(
    cells=cells,
    metadata=template.metadata,
)
notebook.metadata.language_info.version = "3.12.0"

result_markdown = [
    cell.source for cell in notebook.cells if cell.cell_type == "markdown"
]
for source in original_markdown:
    if source not in result_markdown:
        raise AssertionError("Исходная Markdown-ячейка была изменена")

nbformat.validate(notebook)
nbformat.write(notebook, OUTPUT_PATH)
print(OUTPUT_PATH)
