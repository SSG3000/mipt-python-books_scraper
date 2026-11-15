# Books Scraper

Учебный проект МФТИ: сбор данных о книгах с Books to Scrape, ежедневный запуск по расписанию и автотесты.

## Запуск

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
jupyter lab notebooks\ГалкинСС_HW_03_python_ds.ipynb
```

## Тесты

```powershell
python -m pytest -q
```

## Библиотеки

`requests`, `beautifulsoup4`, `schedule`, `pytest`, `jupyterlab`.
