"""Парсер учебного каталога Books to Scrape.

Модуль является единственным источником рабочей реализации проекта. Ноутбук
импортирует функции отсюда, а тесты проверяют этот же код.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests
import schedule
from bs4 import BeautifulSoup


BASE_URL = "https://books.toscrape.com/"
PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "artifacts" / "books_data.txt"
DEFAULT_TIMEOUT = 10.0
SCHEDULE_TAG = "books-scraper"

RATING_MAP = {
    "One": 1,
    "Two": 2,
    "Three": 3,
    "Four": 4,
    "Five": 5,
}


def _new_session() -> requests.Session:
    """Создать HTTP-сессию с понятным идентификатором клиента."""

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "MIPT-Python-Homework-Books-Scraper/1.0 "
                "(educational project)"
            )
        }
    )
    return session


def _request_html(
    url: str,
    *,
    session: requests.Session,
    timeout: float,
) -> str:
    """Загрузить HTML или выбросить ошибку с адресом проблемной страницы."""

    try:
        response = session.get(url, timeout=timeout)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise requests.RequestException(
            f"Не удалось загрузить страницу: {url}"
        ) from exc
    if response.apparent_encoding:
        response.encoding = response.apparent_encoding
    return response.text


def _parse_price(price_text: str) -> float:
    """Преобразовать строку вида ``£51.77`` в число ``51.77``."""

    match = re.search(r"\d+(?:[.,]\d+)?", price_text)
    if match is None:
        raise ValueError(f"Не удалось распознать цену: {price_text!r}")
    return float(match.group(0).replace(",", "."))


def _parse_stock_count(availability: str) -> int | None:
    """Извлечь количество доступных экземпляров, если оно указано."""

    match = re.search(r"(\d+)\s+available", availability, flags=re.IGNORECASE)
    return int(match.group(1)) if match else None


def parse_book_html(html: str, book_url: str) -> dict[str, Any]:
    """Разобрать HTML одной книги без сетевого запроса.

    Args:
        html: HTML-код страницы книги.
        book_url: Исходный абсолютный URL страницы.

    Returns:
        Нормализованный словарь с данными книги.

    Raises:
        ValueError: Если обязательные элементы карточки отсутствуют.
    """

    soup = BeautifulSoup(html, "html.parser")
    product_main = soup.select_one(".product_main")
    if product_main is None:
        raise ValueError(f"На странице нет блока product_main: {book_url}")

    title_element = product_main.select_one("h1")
    price_element = product_main.select_one(".price_color")
    availability_element = product_main.select_one(".availability")
    rating_element = product_main.select_one(".star-rating")

    missing = [
        name
        for name, element in (
            ("title", title_element),
            ("price", price_element),
            ("availability", availability_element),
            ("rating", rating_element),
        )
        if element is None
    ]
    if missing:
        raise ValueError(
            f"На странице {book_url} отсутствуют поля: {', '.join(missing)}"
        )

    availability = availability_element.get_text(" ", strip=True)
    rating_classes = set(rating_element.get("class", []))
    rating_word = next(
        (word for word in RATING_MAP if word in rating_classes),
        None,
    )
    if rating_word is None:
        raise ValueError(f"Не удалось определить рейтинг книги: {book_url}")

    description_heading = soup.select_one("#product_description")
    description_element = (
        description_heading.find_next_sibling("p")
        if description_heading is not None
        else None
    )
    description = (
        description_element.get_text(" ", strip=True)
        if description_element is not None
        else None
    )

    product_information = {
        row.select_one("th").get_text(" ", strip=True):
        row.select_one("td").get_text(" ", strip=True)
        for row in soup.select("table.table.table-striped tr")
        if row.select_one("th") is not None
        and row.select_one("td") is not None
    }

    return {
        "url": book_url,
        "title": title_element.get_text(" ", strip=True),
        "price_gbp": _parse_price(price_element.get_text(" ", strip=True)),
        "rating": RATING_MAP[rating_word],
        "availability": availability,
        "stock_count": _parse_stock_count(availability),
        "description": description,
        "product_information": product_information,
    }


def get_book_data(
    book_url: str,
    *,
    session: requests.Session | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    """Загрузить страницу одной книги и вернуть нормализованные данные.

    Args:
        book_url: Абсолютный URL страницы книги.
        session: Необязательная HTTP-сессия для повторного использования
            соединений и для подмены в тестах.
        timeout: Максимальное время ожидания ответа в секундах.

    Returns:
        Словарь, соответствующий контракту ``parse_book_html``.
    """

    owns_session = session is None
    client = session or _new_session()
    try:
        html = _request_html(book_url, session=client, timeout=timeout)
        return parse_book_html(html, book_url)
    finally:
        if owns_session:
            client.close()


def extract_book_links(catalogue_html: str, page_url: str) -> list[str]:
    """Извлечь абсолютные ссылки на книги со страницы каталога."""

    soup = BeautifulSoup(catalogue_html, "html.parser")
    return [
        urljoin(page_url, link["href"])
        for link in soup.select("article.product_pod h3 a[href]")
    ]


def extract_next_page_url(catalogue_html: str, page_url: str) -> str | None:
    """Вернуть адрес следующей страницы каталога либо ``None``."""

    soup = BeautifulSoup(catalogue_html, "html.parser")
    next_link = soup.select_one("li.next a[href]")
    if next_link is None:
        return None
    return urljoin(page_url, next_link["href"])


def save_books(
    books: list[dict[str, Any]],
    output_path: str | Path = DEFAULT_OUTPUT_PATH,
) -> Path:
    """Атомарно сохранить полный список книг как JSON в UTF-8."""

    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(f"{target.suffix}.tmp")
    temporary.write_text(
        json.dumps(books, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary.replace(target)
    return target


def load_books(
    input_path: str | Path = DEFAULT_OUTPUT_PATH,
) -> list[dict[str, Any]]:
    """Прочитать ранее сохранённый JSON-артефакт."""

    return json.loads(Path(input_path).read_text(encoding="utf-8"))


def scrape_books(
    is_save: bool = False,
    *,
    base_url: str = BASE_URL,
    output_path: str | Path = DEFAULT_OUTPUT_PATH,
    session: requests.Session | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    request_delay: float = 0.0,
    max_pages: int | None = None,
) -> list[dict[str, Any]]:
    """Собрать книги со всех доступных страниц каталога.

    Args:
        is_save: Сохранить ли итог в ``output_path``.
        base_url: Базовый адрес учебного сайта.
        output_path: Путь к JSON-файлу с расширением ``.txt``.
        session: Необязательная HTTP-сессия.
        timeout: Тайм-аут каждого HTTP-запроса в секундах.
        request_delay: Пауза между запросами к карточкам книг.
        max_pages: Ограничение числа страниц для демонстрации и тестов.
            ``None`` означает полный каталог.

    Returns:
        Список нормализованных словарей книг в порядке обхода страниц.

    Raises:
        ValueError: Если ``max_pages`` меньше единицы.
        RuntimeError: Если сайт образует цикл пагинации.
        requests.RequestException: Если один из запросов завершился ошибкой.
    """

    if max_pages is not None and max_pages < 1:
        raise ValueError("max_pages должен быть положительным числом")

    owns_session = session is None
    client = session or _new_session()
    page_url: str | None = urljoin(base_url, "catalogue/page-1.html")
    seen_pages: set[str] = set()
    books: list[dict[str, Any]] = []
    processed_pages = 0

    try:
        while page_url is not None:
            if page_url in seen_pages:
                raise RuntimeError(f"Обнаружен цикл пагинации: {page_url}")
            seen_pages.add(page_url)

            catalogue_html = _request_html(
                page_url,
                session=client,
                timeout=timeout,
            )
            processed_pages += 1

            for book_url in extract_book_links(catalogue_html, page_url):
                books.append(
                    get_book_data(
                        book_url,
                        session=client,
                        timeout=timeout,
                    )
                )
                if request_delay > 0:
                    time.sleep(request_delay)

            if max_pages is not None and processed_pages >= max_pages:
                break
            page_url = extract_next_page_url(catalogue_html, page_url)
    finally:
        if owns_session:
            client.close()

    if is_save:
        save_books(books, output_path)
    return books


def configure_schedule(
    at_time: str = "19:00",
    *,
    output_path: str | Path = DEFAULT_OUTPUT_PATH,
    request_delay: float = 0.05,
) -> schedule.Job:
    """Настроить один ежедневный запуск полной выгрузки."""

    schedule.clear(SCHEDULE_TAG)
    return (
        schedule.every()
        .day.at(at_time)
        .do(
            scrape_books,
            is_save=True,
            output_path=output_path,
            request_delay=request_delay,
        )
        .tag(SCHEDULE_TAG)
    )


def run_scheduler(check_interval: float = 30.0) -> None:
    """Бесконечно выполнять ожидающие задачи планировщика."""

    while True:
        schedule.run_pending()
        time.sleep(check_interval)


def build_argument_parser() -> argparse.ArgumentParser:
    """Создать парсер аргументов командной строки."""

    parser = argparse.ArgumentParser(
        description="Сбор данных с учебного сайта Books to Scrape"
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help="сохранить результат в artifacts/books_data.txt",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="путь к выходному JSON-файлу",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="ограничить число страниц для демонстрации",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.0,
        help="пауза между карточками книг в секундах",
    )
    parser.add_argument(
        "--schedule",
        action="store_true",
        help="запустить ежедневный планировщик вместо разового сбора",
    )
    parser.add_argument(
        "--at",
        default="19:00",
        help="локальное время ежедневного запуска в формате HH:MM",
    )
    return parser


def main() -> None:
    """Точка входа командной строки."""

    args = build_argument_parser().parse_args()
    if args.schedule:
        job = configure_schedule(
            args.at,
            output_path=args.output,
            request_delay=args.delay,
        )
        print(f"Планировщик настроен: {job}")
        run_scheduler()
        return

    books = scrape_books(
        is_save=args.save,
        output_path=args.output,
        request_delay=args.delay,
        max_pages=args.max_pages,
    )
    print(f"Собрано книг: {len(books)}")
    if args.save:
        print(f"Результат сохранён: {args.output}")


if __name__ == "__main__":
    main()
