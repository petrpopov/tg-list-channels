# tg-list-channels

[🇬🇧 English version](README.en.md)

Скрипт выгружает список **всех Telegram-каналов и групп** вашего аккаунта — включая те, **от которых вы отписались** (через Telegram Takeout API). Результат можно сохранить в `txt`, `md`, `pdf` (с кликабельными ссылками) или `xlsx`.

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
cp .env.example .env                # затем впишите API_ID / API_HASH
```

## Получение API_ID и API_HASH

1. Откройте https://my.telegram.org и войдите по номеру телефона.
2. Перейдите в **API development tools**.
3. Заполните форму (App title и Short name — любые), платформа — Desktop.
4. Скопируйте `App api_id` и `App api_hash` в файл `.env`:

   ```
   API_ID=1234567
   API_HASH=abcdef0123456789abcdef0123456789
   ```

Эти данные привязаны лично к вашему аккаунту, никому их не передавайте.

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
2. Telegram пришлёт **код подтверждения** в официальный клиент — введите его.
3. Если включена двухфакторная аутентификация — спросит **пароль 2FA**.
4. Для выгрузки **покинутых** каналов Telegram попросит подтвердить **запрос на экспорт данных (Data Export Request)** — откройте официальный клиент, нажмите «Подтвердить» и снова запустите скрипт. Telegram может потребовать подождать (до 24 часов) — это политика безопасности.

> **Безопасность.** Телефон, код, пароль и сессия (`anon.session`) **никуда не отправляются**, кроме официальных серверов Telegram. Файл сессии остаётся локально на вашем компьютере. Не выкладывайте файлы `.env` и `*.session` в публичный доступ и не давайте никому к ним доступ.

---

## Как запустить, если вы не разработчик

### 1. Откройте консоль

- **macOS** — `Cmd + Space`, наберите `Terminal`, Enter.
- **Windows** — `Win`, наберите `PowerShell`, Enter.
- **Linux** — `Ctrl + Alt + T`.

### 2. Установите Python 3.10+

- **macOS** — самый простой путь: установите [Homebrew](https://brew.sh/), затем
  ```bash
  brew install python git
  ```
- **Windows** — скачайте инсталлятор с https://www.python.org/downloads/windows/ → запустите → **обязательно поставьте галочку «Add Python to PATH»** → Install. Также поставьте Git: https://git-scm.com/download/win
- **Linux (Ubuntu/Debian)** —
  ```bash
  sudo apt update && sudo apt install -y python3 python3-venv python3-pip git
  ```

Проверьте:
```bash
python3 --version
```

> **Частая ошибка на Mac/Linux:** `command not found: python`. Это нормально — там команда называется **`python3`** (а `pip` — **`pip3`**). На Windows обычно работает `python`.

### 3. Скачайте проект

```bash
cd ~                                  # или любая удобная папка
git clone https://github.com/petrpopov/tg-list-channels.git
cd tg-list-channels
```

### 4. Создайте виртуальное окружение и поставьте зависимости

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

> Если PowerShell ругается на запуск скриптов — выполните один раз:
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

### 5. Получите `API_ID` / `API_HASH`

См. раздел [Получение API_ID и API_HASH](#получение-api_id-и-api_hash) выше. Скопируйте `.env.example` в `.env` и впишите значения.

**macOS / Linux:** `cp .env.example .env && nano .env`
**Windows:** `copy .env.example .env && notepad .env`

### 6. Запустите

```bash
python list_channels.py -o report.pdf
```

Скрипт спросит телефон, код из Telegram, при необходимости пароль 2FA. Для покинутых каналов — подтвердите в Telegram запрос на Data Export. Готовый файл `report.pdf` появится в папке проекта.

### Типичные проблемы

| Проблема | Решение |
|----------|---------|
| `command not found: python` | Используйте `python3` (Mac/Linux). |
| `pip: command not found` | Используйте `pip3` или активируйте venv. |
| `'python' is not recognized` (Windows) | Переустановите Python с галочкой «Add to PATH». |
| `ModuleNotFoundError: telethon` | Активируйте venv (`source .venv/bin/activate`) и `pip install -r requirements.txt`. |
| Telegram просит ждать сутки на Takeout | Это нормально. Подтвердите уведомление в официальном клиенте, скрипт сам дождётся. |
| Кириллица «кракозябрами» в PDF | Установите системный шрифт Menlo / DejaVu Sans Mono / Courier New. |

---

## Лицензия

MIT — см. [LICENSE](LICENSE).
