# tg-list-channels

[🇷🇺 Русская версия](README.md) (main)

Dump **all your Telegram channels and groups** — including the ones **you have left** (via the official Telegram Takeout API). Output to `txt`, `md`, `pdf` (with clickable links), or `xlsx`.

## Features

- Active channel and supergroup subscriptions.
- Left channels — via the official Takeout API.
- Type filter: `all` / `channels` / `groups`.
- Lookup a channel by `id` (`--lookup`) with description and member count.
- Output formats: `txt`, `md`, `pdf`, `xlsx` (auto-detected from `--output`).

## Requirements

- Python 3.10+
- `API_ID` and `API_HASH` from https://my.telegram.org

## Install

```bash
git clone https://github.com/petrpopov/tg-list-channels.git
cd tg-list-channels
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                # then fill API_ID / API_HASH
```

## Get API_ID and API_HASH

1. Open https://my.telegram.org and sign in with your phone number.
2. Go to **API development tools**.
3. Fill out the form (App title and Short name — anything), platform — Desktop.
4. Copy `App api_id` and `App api_hash` into `.env`:

   ```
   API_ID=1234567
   API_HASH=abcdef0123456789abcdef0123456789
   ```

These credentials are tied to your personal account — never share them.

## Run

```bash
python list_channels.py                              # all → stdout
python list_channels.py --type channels              # only channels
python list_channels.py --type groups -o groups.txt  # only groups → txt
python list_channels.py -o report.pdf                # PDF with clickable links
python list_channels.py -o report.xlsx               # Excel with hyperlinks
python list_channels.py -o report.md                 # Markdown
python list_channels.py --no-left                    # skip left (no Takeout)
python list_channels.py --lookup 1312540285          # lookup channel by id
```

### Options

| Option | Purpose |
|--------|---------|
| `-t, --type {all,channels,groups}` | What to print. Default `all`. |
| `-o, --output PATH` | Save to file. Format auto-detected from extension. |
| `-f, --format {auto,txt,pdf,md,xlsx}` | Force output format. |
| `--no-current` | Skip active subscriptions. |
| `--no-left` | Skip left channels (no Takeout). |
| `--session NAME` | Telethon session name (default `anon`). |
| `--poll N` | Takeout init retry interval, seconds. |
| `--lookup ID [ID ...]` | Lookup channel(s) by id with details. |

### First run

1. The script asks for your **phone number** in international format (e.g. `+12025551234`).
2. Telegram sends a **login code** to the official client — enter it.
3. If 2FA is enabled — enter your **2FA password**.
4. To list **left** channels Telegram will require you to confirm a **Data Export Request** — open the official client, tap "Confirm", then re-run the script. Telegram may impose a wait (up to 24h) — it's a security policy.

> **Security.** Phone, code, password, and session file (`anon.session`) are **never sent anywhere** other than Telegram's official servers. The session stays locally on your computer. Don't commit `.env` or `*.session` — `.gitignore` already excludes them.

For a non-developer step-by-step setup (installing Python on macOS/Windows/Linux, common pitfalls), see the **Russian README** linked at the top — the same steps apply, only the prose is in Russian.

## License

MIT — see [LICENSE](LICENSE).
