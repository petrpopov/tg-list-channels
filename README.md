# tg-list-channels

[🇬🇧 English version](README.en.md)

Скрипт выгружает список **всех Telegram-каналов и групп** твоего аккаунта — включая те, **от которых ты отписался** (через Telegram Takeout API). Результат можно сохранить в `txt`, `md`, `pdf` (с кликабельными ссылками) или `xlsx`.

## Возможности

- Активные подписки на каналы и супергруппы.
- Покинутые каналы — через официальный Takeout API.
- Фильтр по типу: `all` / `channels` / `groups`.
- Поиск канала по `id` (`--lookup`) с описанием и количеством участников.
- Форматы вывода: `txt`, `md`, `pdf`, `xlsx` (определяется по расширению `--output`).

## Требования

- Python 3.10+
- `API_ID` и `API_HASH` с https://my.telegram.org

## Установка

```bash
git clone https://github.com/petrpopov/tg-list-channels.git
cd tg-list-channels
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                # затем впиши API_ID / API_HASH
```

## Получение API_ID и API_HASH

1. Открой https://my.telegram.org и войди по номеру телефона.
2. Перейди в **API development tools**.
3. Заполни форму (App title и Short name — любые), платформа — Desktop.
4. Скопируй `App api_id` и `App api_hash` в файл `.env`:

   ```
   API_ID=1234567
   API_HASH=abcdef0123456789abcdef0123456789
   ```

Эти данные привязаны лично к твоему аккаунту, никому их не передавай.

## Запуск

```bash
python list_channels.py                              # всё в stdout
python list_channels.py --type channels              # только каналы
python list_channels.py --type groups -o groups.txt  # только группы → txt
python list_channels.py -o report.pdf                # PDF c кликабельными ссылками
python list_channels.py -o report.xlsx               # Excel с гиперссылками
python list_channels.py -o report.md                 # Markdown
python list_channels.py --no-left                    # без покинутых (без Takeout)
python list_channels.py --lookup 1312540285          # поиск канала по id
```

### Опции

| Опция | Назначение |
|-------|-----------|
| `-t, --type {all,channels,groups}` | Что выводить. По умолчанию `all`. |
| `-o, --output PATH` | Сохранить в файл. Формат — по расширению. |
| `-f, --format {auto,txt,pdf,md,xlsx}` | Принудительно задать формат. |
| `--no-current` | Не выгружать активные подписки. |
| `--no-left` | Не выгружать покинутые каналы (без Takeout). |
| `--session NAME` | Имя сессии Telethon (по умолчанию `anon`). |
| `--poll N` | Интервал ретраев инициации Takeout, сек. |
| `--lookup ID [ID ...]` | Поиск канала по id с подробностями. |

### Что произойдёт при первом запуске

1. Скрипт спросит **номер телефона** в международном формате (например, `+79991234567`).
2. Telegram пришлёт **код подтверждения** в официальный клиент — введи его.
3. Если включена двухфакторная аутентификация — спросит **пароль 2FA**.
4. Для выгрузки **покинутых** каналов Telegram попросит подтвердить **запрос на экспорт данных (Data Export Request)** — открой официальный клиент, нажми «Подтвердить» и снова запусти скрипт. Telegram может потребовать подождать (до 24 часов) — это политика безопасности.

> **Безопасность.** Телефон, код, пароль и сессия (`anon.session`) **никуда не отправляются**, кроме официальных серверов Telegram. Файл сессии остаётся локально на твоём компьютере. Не выкладывай `.env` и `*.session` в публичный репозиторий — `.gitignore` уже это учитывает.

---

## Как запустить, если ты не разработчик

Не пугайся, по шагам справится любой.

### 1. Открой консоль

- **macOS** — `Cmd + Space`, набери `Terminal`, Enter.
- **Windows** — `Win`, набери `PowerShell`, Enter.
- **Linux** — `Ctrl + Alt + T`.

### 2. Установи Python 3.10+

- **macOS** — самый простой путь: установи [Homebrew](https://brew.sh/), затем
  ```bash
  brew install python git
  ```
- **Windows** — скачай инсталлятор с https://www.python.org/downloads/windows/ → запусти → **обязательно поставь галочку «Add Python to PATH»** → Install. Также поставь Git: https://git-scm.com/download/win
- **Linux (Ubuntu/Debian)** —
  ```bash
  sudo apt update && sudo apt install -y python3 python3-venv python3-pip git
  ```

Проверь:
```bash
python3 --version
```

> **Частая ошибка на Mac/Linux:** `command not found: python`. Это нормально — там команда называется **`python3`** (а `pip` — **`pip3`**). На Windows обычно работает `python`.

### 3. Скачай проект

```bash
cd ~                                  # или любая удобная папка
git clone https://github.com/petrpopov/tg-list-channels.git
cd tg-list-channels
```

### 4. Создай виртуальное окружение и поставь зависимости

**macOS / Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**Windows (PowerShell):**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

> Если PowerShell ругается на запуск скриптов — выполни один раз:
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

### 5. Получи `API_ID` / `API_HASH`

См. раздел [Получение API_ID и API_HASH](#получение-api_id-и-api_hash) выше. Скопируй `.env.example` в `.env` и впиши значения.

**macOS / Linux:** `cp .env.example .env && nano .env`
**Windows:** `copy .env.example .env && notepad .env`

### 6. Запусти

```bash
python list_channels.py -o report.pdf
```

Скрипт спросит телефон, код из Telegram, при необходимости пароль 2FA. Для покинутых каналов — подтверди в Telegram запрос на Data Export. Готовый файл `report.pdf` появится в папке проекта.

### Типичные проблемы

| Проблема | Решение |
|----------|---------|
| `command not found: python` | Используй `python3` (Mac/Linux). |
| `pip: command not found` | Используй `pip3`, или активируй venv. |
| `'python' is not recognized` (Windows) | Переустанови Python с галочкой «Add to PATH». |
| `ModuleNotFoundError: telethon` | Активируй venv (`source .venv/bin/activate`) и `pip install -r requirements.txt`. |
| Telegram просит ждать сутки на Takeout | Это нормально. Подтверди уведомление в официальном клиенте, скрипт сам дождётся. |
| Кириллица «кракозябрами» в PDF | Установи системный шрифт Menlo / DejaVu Sans Mono / Courier New. |

---

## Лицензия

MIT — см. [LICENSE](LICENSE).
