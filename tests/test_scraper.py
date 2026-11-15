"""Изолированные тесты парсера без обязательного доступа в интернет."""

from __future__ import annotations

from pathlib import Path

import pytest
import requests
import schedule

from scraper import (
    SCHEDULE_TAG,
    configure_schedule,
    extract_book_links,
    extract_next_page_url,
    get_book_data,
    load_books,
    parse_book_html,
    save_books,
    scrape_books,
)


FIXTURES = Path(__file__).parent / "fixtures"
BOOK_URL = "https://example.test/catalogue/book-one_1/index.html"


def read_fixture(name: str) -> str:
    """Прочитать HTML-фикстуру в UTF-8."""

    return (FIXTURES / name).read_text(encoding="utf-8")


class FakeResponse:
    """Минимальный ответ, совместимый с используемой частью requests."""

    def __init__(self, text: str, status_code: int = 200) -> None:
        self._content = text.encode("utf-8")
        self.status_code = status_code
        self.encoding = "ISO-8859-1"
        self.apparent_encoding = "utf-8"

    @property
    def text(self) -> str:
        return self._content.decode(self.encoding)

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


class FakeSession:
    """HTTP-сессия с заранее заданными ответами."""

    def __init__(self, responses: dict[str, FakeResponse]) -> None:
        self.responses = responses
        self.requested_urls: list[str] = []

    def get(self, url: str, timeout: float) -> FakeResponse:
        self.requested_urls.append(url)
        if url not in self.responses:
            raise requests.ConnectionError(f"Нет фикстуры для {url}")
        return self.responses[url]

    def close(self) -> None:
        return None


def test_parse_book_html_returns_normalized_fields() -> None:
    book = parse_book_html(read_fixture("book_page.html"), BOOK_URL)

    assert book["title"] == "A Light in the Attic"
    assert book["price_gbp"] == 51.77
    assert book["rating"] == 3
    assert book["stock_count"] == 22
    assert book["description"] == "Учебное описание книги."
    assert book["product_information"]["UPC"] == "a897fe39b1053632"


def test_parse_book_html_allows_missing_description() -> None:
    html = read_fixture("book_page.html").replace(
        '<div id="product_description"><h2>Product Description</h2></div>\n'
        "    <p>Учебное описание книги.</p>",
        "",
    )

    assert parse_book_html(html, BOOK_URL)["description"] is None


def test_parse_book_html_rejects_missing_required_block() -> None:
    with pytest.raises(ValueError, match="product_main"):
        parse_book_html("<html></html>", BOOK_URL)


def test_get_book_data_uses_session_and_timeout() -> None:
    session = FakeSession(
        {BOOK_URL: FakeResponse(read_fixture("book_page.html"))}
    )

    book = get_book_data(BOOK_URL, session=session, timeout=3.0)

    assert book["url"] == BOOK_URL
    assert session.requested_urls == [BOOK_URL]


def test_get_book_data_uses_detected_utf8_encoding() -> None:
    expected_title = "Café “Pangur Bán”"
    html = read_fixture("book_page.html").replace(
        "A Light in the Attic",
        expected_title,
    )
    session = FakeSession({BOOK_URL: FakeResponse(html)})

    book = get_book_data(BOOK_URL, session=session)

    assert book["title"] == expected_title


def test_get_book_data_adds_url_to_network_error() -> None:
    session = FakeSession({BOOK_URL: FakeResponse("error", status_code=500)})

    with pytest.raises(requests.RequestException, match=BOOK_URL):
        get_book_data(BOOK_URL, session=session)


def test_catalogue_navigation_builds_absolute_urls() -> None:
    page_url = "https://example.test/catalogue/page-1.html"
    html = read_fixture("catalogue_page_1.html")

    assert extract_book_links(html, page_url) == [
        "https://example.test/catalogue/book-one_1/index.html",
        "https://example.test/catalogue/book-two_2/index.html",
    ]
    assert extract_next_page_url(html, page_url) == (
        "https://example.test/catalogue/page-2.html"
    )


def test_scrape_books_traverses_pages_and_stops() -> None:
    base_url = "https://example.test/"
    page_1 = "https://example.test/catalogue/page-1.html"
    page_2 = "https://example.test/catalogue/page-2.html"
    book_urls = [
        "https://example.test/catalogue/book-one_1/index.html",
        "https://example.test/catalogue/book-two_2/index.html",
        "https://example.test/catalogue/book-three_3/index.html",
    ]
    responses = {
        page_1: FakeResponse(read_fixture("catalogue_page_1.html")),
        page_2: FakeResponse(read_fixture("catalogue_page_2.html")),
        **{
            url: FakeResponse(read_fixture("book_page.html"))
            for url in book_urls
        },
    }
    session = FakeSession(responses)

    books = scrape_books(base_url=base_url, session=session)

    assert len(books) == 3
    assert session.requested_urls == [
        page_1,
        book_urls[0],
        book_urls[1],
        page_2,
        book_urls[2],
    ]


def test_scrape_books_rejects_invalid_page_limit() -> None:
    with pytest.raises(ValueError, match="max_pages"):
        scrape_books(max_pages=0)


def test_save_and_load_books_round_trip(tmp_path: Path) -> None:
    books = [parse_book_html(read_fixture("book_page.html"), BOOK_URL)]
    output_path = tmp_path / "books_data.txt"

    saved_path = save_books(books, output_path)

    assert saved_path == output_path
    assert load_books(output_path) == books
    assert not output_path.with_suffix(".txt.tmp").exists()


def test_configure_schedule_creates_one_tagged_job(tmp_path: Path) -> None:
    schedule.clear()
    try:
        job = configure_schedule("19:00", output_path=tmp_path / "books.txt")

        assert SCHEDULE_TAG in job.tags
        assert len(schedule.get_jobs(SCHEDULE_TAG)) == 1
    finally:
        schedule.clear()
