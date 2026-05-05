"""
Выводит все Telegram-каналы и группы текущего аккаунта,
включая те, от которых пользователь отписался (через Takeout API).
Поддержка вывода: stdout, .txt, .pdf (с кликабельными ссылками).
"""
import os
import sys
import asyncio
import argparse
from pathlib import Path
from datetime import datetime
from contextlib import contextmanager
from xml.sax.saxutils import escape as xml_escape

from telethon import TelegramClient
from telethon.tl.functions.channels import GetLeftChannelsRequest, GetFullChannelRequest
from telethon.tl.functions.account import (
    FinishTakeoutSessionRequest,
    InitTakeoutSessionRequest,
)
from telethon.tl.functions import InvokeWithTakeoutRequest
from telethon.tl.types import Channel, PeerChannel
from telethon.errors.rpcerrorlist import TakeoutInitDelayError

try:
    from wcwidth import wcswidth as _wcswidth
except ImportError:
    _wcswidth = None


# ----- Width helpers --------------------------------------------------------

def vwidth(s: str) -> int:
    if _wcswidth is not None:
        w = _wcswidth(s)
        if w >= 0:
            return w
    return len(s)


def vpad(s: str, width: int, truncate: bool = True) -> str:
    w = vwidth(s)
    if w <= width:
        return s + " " * (width - w)
    if not truncate:
        return s
    out = ""
    cur = 0
    for ch in s:
        cw = vwidth(ch)
        if cur + cw > width - 1:
            break
        out += ch
        cur += cw
    out += "…"
    cur += 1
    if cur < width:
        out += " " * (width - cur)
    return out


# ----- Config ---------------------------------------------------------------

def load_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


# ----- CLI ------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="list_channels.py",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "Выгружает список Telegram-каналов и групп текущего аккаунта.\n"
            "Включает активные подписки и покинутые каналы (через Takeout API).\n\n"
            "Требуется API_ID / API_HASH с https://my.telegram.org\n"
            "(задать в окружении или в файле .env рядом со скриптом)."
        ),
        epilog=(
            "Примеры:\n"
            "  python list_channels.py\n"
            "  python list_channels.py --type channels\n"
            "  python list_channels.py --type groups -o groups.txt\n"
            "  python list_channels.py -o report.pdf       # PDF с кликабельными ссылками\n"
            "  python list_channels.py --no-left\n"
            "  python list_channels.py --lookup 1312540285\n"
        ),
    )
    p.add_argument(
        "-t", "--type",
        dest="type",
        choices=("all", "channels", "groups"),
        default="all",
        help="Какие типы выводить (по умолчанию: all). "
             "'channels' = только broadcast-каналы; 'groups' = только супергруппы.",
    )
    p.add_argument(
        "-o", "--output",
        type=Path,
        default=None,
        help="Записать отчёт в файл вместо stdout. "
             "Формат определяется по расширению: .pdf → PDF (кликабельные ссылки), "
             "иначе — обычный текст.",
    )
    p.add_argument(
        "-f", "--format",
        choices=("auto", "txt", "pdf", "md", "xlsx"),
        default="auto",
        help="Формат вывода (по умолчанию: auto — по расширению файла: "
             ".pdf/.md/.xlsx/.txt).",
    )
    p.add_argument(
        "--no-current",
        action="store_true",
        help="Пропустить секцию активных подписок.",
    )
    p.add_argument(
        "--no-left",
        action="store_true",
        help="Пропустить покинутые каналы (без Takeout — не нужен аппрув).",
    )
    p.add_argument(
        "--session",
        default="anon",
        help="Имя Telethon-сессии (по умолчанию: anon).",
    )
    p.add_argument(
        "--poll",
        type=int,
        default=15,
        help="Интервал ретраев Takeout-инициации в секундах (по умолчанию: 15).",
    )
    p.add_argument(
        "--lookup",
        type=int,
        nargs="+",
        metavar="ID",
        help="Найти канал(ы) по id и показать подробности. "
             "В этом режиме секции активных/покинутых не выводятся.",
    )
    return p.parse_args()


def resolve_format(args) -> str:
    if args.format != "auto":
        return args.format
    if args.output:
        ext = args.output.suffix.lower()
        if ext == ".pdf":
            return "pdf"
        if ext in (".md", ".markdown"):
            return "md"
        if ext == ".xlsx":
            return "xlsx"
    return "txt"


# ----- Record helpers -------------------------------------------------------

def type_of(e) -> str:
    return "channel" if getattr(e, "broadcast", False) else "group"


def keep(entity, type_filter: str) -> bool:
    t = type_of(entity)
    if type_filter == "all":
        return True
    if type_filter == "channels":
        return t == "channel"
    if type_filter == "groups":
        return t == "group"
    return False


def to_record(entity) -> dict:
    uname = getattr(entity, "username", None)
    return {
        "id": entity.id,
        "title": getattr(entity, "title", "") or "",
        "username": f"@{uname}" if uname else "-",
        "link": f"https://t.me/{uname}" if uname else "",
        "type": type_of(entity),
    }


# ----- Telegram fetchers ----------------------------------------------------

async def fetch_current(client, type_filter: str, log) -> list[dict]:
    out = []
    seen_ids: set[int] = set()
    async for d in client.iter_dialogs():
        e = d.entity
        if not isinstance(e, Channel):
            continue
        if e.id in seen_ids:
            continue
        if not keep(e, type_filter):
            continue
        seen_ids.add(e.id)
        out.append(to_record(e))
    log(f"  получено активных записей: {len(out)}")
    return out


async def fetch_left(client, type_filter: str, exclude_ids: set[int], poll: int, log) -> list[dict]:
    log("  сбрасываю прежний takeout_id (если был)")
    client.session.takeout_id = None
    client.session.save()

    log("  инициирую takeout-сессию...")
    attempt = 0
    while True:
        try:
            init = await client(InitTakeoutSessionRequest(
                contacts=False,
                message_users=False,
                message_chats=False,
                message_megagroups=False,
                message_channels=False,
                files=False,
            ))
            break
        except TakeoutInitDelayError as ex:
            attempt += 1
            wait_total = getattr(ex, "seconds", 86400)
            log(
                f"  Telegram требует подтверждение. Открой офиц. клиент → "
                f"уведомление 'Запрос на экспорт данных' → Подтвердить. "
                f"Серверная задержка={wait_total}с. Попытка #{attempt} через {poll}с..."
            )
            await asyncio.sleep(poll)

    takeout_id = init.id
    log(f"  takeout_id={takeout_id}")

    out = []
    seen_ids: set[int] = set()
    try:
        offset = 0
        fetched = 0
        total = None
        while True:
            res = await client(InvokeWithTakeoutRequest(
                takeout_id, GetLeftChannelsRequest(offset=offset)
            ))
            chats = res.chats
            if not chats:
                break
            total = getattr(res, "count", len(chats))
            for c in chats:
                if c.id in exclude_ids or c.id in seen_ids:
                    continue
                if not keep(c, type_filter):
                    seen_ids.add(c.id)
                    continue
                seen_ids.add(c.id)
                out.append(to_record(c))
            fetched += len(chats)
            if total is not None and fetched >= total:
                break
            offset += len(chats)
    finally:
        try:
            await client(InvokeWithTakeoutRequest(
                takeout_id, FinishTakeoutSessionRequest(success=True)
            ))
        except Exception as ex:
            log(f"  предупреждение: закрытие takeout: {ex}")
        client.session.takeout_id = None
        client.session.save()

    log(f"  получено покинутых записей: {len(out)} (после фильтра)")
    return out


async def lookup_records(client, ids: list[int], log) -> list[dict]:
    out = []
    for cid in ids:
        log(f"  ищу id={cid}...")
        rec = {
            "id": cid, "title": "", "username": "-", "link": "",
            "type": "?", "about": "", "participants": None, "error": None,
        }
        try:
            entity = await client.get_entity(PeerChannel(cid))
        except Exception as ex:
            rec["error"] = str(ex)
            out.append(rec)
            continue
        rec.update(to_record(entity))
        if not rec["link"]:
            rec["link"] = f"https://t.me/c/{entity.id}"
        try:
            full = await client(GetFullChannelRequest(entity))
            rec["about"] = (full.full_chat.about or "").strip()
            rec["participants"] = getattr(full.full_chat, "participants_count", None)
        except Exception as ex:
            log(f"  предупреждение: GetFullChannel id={cid}: {ex}")
        out.append(rec)
    return out


# ----- Text renderer --------------------------------------------------------

def banner_lines(args) -> list[str]:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    width = 64
    L = []
    L.append("╔" + "═" * width + "╗")
    L.append("║" + "  Telegram: список каналов и групп".ljust(width) + "║")
    L.append("╠" + "═" * width + "╣")
    for label, value in [
        ("Время", now),
        ("Тип", args.type),
        ("Активные", "нет" if args.no_current else "да"),
        ("Покинутые", "нет" if args.no_left else "да (через Takeout)"),
    ]:
        line = f"║  {label:<10}: {value}"
        L.append(vpad(line, width + 1) + "║")
    L.append("╚" + "═" * width + "╝")
    return L


def render_text_section(out, title: str, items: list[dict]) -> None:
    header = f"━━━ {title}  ({len(items)}) "
    print(header + "━" * max(0, 100 - vwidth(header)), file=out)
    if not items:
        print("  (пусто)", file=out)
        print(file=out)
        return

    title_w = min(max((vwidth(i["title"]) for i in items), default=10), 50)
    uname_w = max((vwidth(i["username"]) for i in items), default=10)
    items.sort(key=lambda x: (x["type"], x["title"].lower()))

    for it in items:
        link = it["link"] or "-"
        print(
            f"  [{it['type']:<7}] {vpad(it['title'], title_w)}  "
            f"{vpad(it['username'], uname_w)}  id={it['id']:<14}  {link}",
            file=out,
        )
    print(file=out)


def render_text_lookup(out, items: list[dict]) -> None:
    print("━━━ Поиск по id ━━━".ljust(80, "━"), file=out)
    print(file=out)
    for it in items:
        if it.get("error"):
            print(f"  id={it['id']}: ОШИБКА — {it['error']}", file=out)
            print(file=out)
            continue
        print(f"  id          : {it['id']}", file=out)
        print(f"  тип         : {it['type']}", file=out)
        print(f"  название    : {it['title']}", file=out)
        print(f"  @username   : {it['username']}", file=out)
        print(f"  ссылка      : {it['link']}", file=out)
        if it.get("participants") is not None:
            print(f"  участников  : {it['participants']}", file=out)
        if it.get("about"):
            print(f"  описание    : {it['about']}", file=out)
        print(file=out)


def write_text(path: Path | None, args, current, left, lookup) -> None:
    @contextmanager
    def _open():
        if path is None:
            yield sys.stdout
        else:
            f = path.open("w", encoding="utf-8")
            try:
                yield f
            finally:
                f.close()

    with _open() as out:
        for line in banner_lines(args):
            print(line, file=out)
        print(file=out)

        if lookup is not None:
            render_text_lookup(out, lookup)
            return

        if not args.no_current:
            render_text_section(out, "Активные подписки", current)
        if not args.no_left:
            render_text_section(out, "Покинутые каналы (через takeout)", left)
        total_n = len(current) + len(left)
        print("━" * 100, file=out)
        print(f"  Всего записей: {total_n}", file=out)
        print("━" * 100, file=out)


# ----- PDF renderer ---------------------------------------------------------

def _register_mono_font() -> str:
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    candidates = [
        ("/System/Library/Fonts/Menlo.ttc", 0),
        ("/System/Library/Fonts/Supplemental/Courier New.ttf", None),
        ("/Library/Fonts/Courier New.ttf", None),
        ("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", None),
        ("/usr/share/fonts/dejavu/DejaVuSansMono.ttf", None),
        ("C:/Windows/Fonts/consola.ttf", None),
        ("C:/Windows/Fonts/cour.ttf", None),
    ]
    for fpath, idx in candidates:
        if not Path(fpath).exists():
            continue
        try:
            kwargs = {"subfontIndex": idx} if idx is not None else {}
            pdfmetrics.registerFont(TTFont("MonoCyr", fpath, **kwargs))
            return "MonoCyr"
        except Exception:
            continue
    return "Courier"


def _esc(s: str) -> str:
    return xml_escape(s).replace(" ", "&nbsp;")


def write_pdf(path: Path, args, current, left, lookup) -> None:
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib import colors

    font_name = _register_mono_font()

    body = ParagraphStyle("body", fontName=font_name, fontSize=8, leading=10)
    body_link = ParagraphStyle("body_link", fontName=font_name, fontSize=8, leading=10,
                               textColor=colors.HexColor("#1a73e8"))
    head = ParagraphStyle("head", fontName=font_name, fontSize=12, leading=15,
                          spaceBefore=8, spaceAfter=4, textColor=colors.HexColor("#222222"))
    title = ParagraphStyle("title", fontName=font_name, fontSize=14, leading=18,
                           spaceAfter=8, textColor=colors.black)
    meta = ParagraphStyle("meta", fontName=font_name, fontSize=9, leading=11)

    doc = SimpleDocTemplate(
        str(path),
        pagesize=landscape(A4),
        leftMargin=10 * mm, rightMargin=10 * mm,
        topMargin=12 * mm, bottomMargin=12 * mm,
        title="Telegram channels report",
    )
    story = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    story.append(Paragraph("Telegram: список каналов и групп", title))
    story.append(Paragraph(
        f"Время: {now} &nbsp;|&nbsp; Тип: {args.type} &nbsp;|&nbsp; "
        f"Активные: {'нет' if args.no_current else 'да'} &nbsp;|&nbsp; "
        f"Покинутые: {'нет' if args.no_left else 'да (Takeout)'}",
        meta,
    ))
    story.append(Spacer(1, 6))

    page_w = landscape(A4)[0] - 20 * mm
    col_widths = [
        18 * mm,   # type
        90 * mm,   # title
        40 * mm,   # username
        28 * mm,   # id
        page_w - (18 + 90 + 40 + 28) * mm,  # link (rest)
    ]

    table_style = TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), font_name),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("LEADING", (0, 0), (-1, -1), 10),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.white, colors.HexColor("#f6f8fa")]),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e0e4ea")),
        ("FONTNAME", (0, 0), (-1, 0), font_name),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#222222")),
    ])

    def make_row(it: dict) -> list:
        link_para = (
            Paragraph(f'<a href="{xml_escape(it["link"])}">{xml_escape(it["link"])}</a>',
                      body_link)
            if it["link"] else Paragraph("-", body)
        )
        return [
            Paragraph(xml_escape(f"[{it['type']}]"), body),
            Paragraph(xml_escape(it["title"]), body),
            Paragraph(xml_escape(it["username"]), body),
            Paragraph(f"id={it['id']}", body),
            link_para,
        ]

    def section(title_text: str, items: list[dict]):
        story.append(Paragraph(xml_escape(f"━━━ {title_text}  ({len(items)})"), head))
        if not items:
            story.append(Paragraph("(пусто)", body))
            return
        items.sort(key=lambda x: (x["type"], x["title"].lower()))
        rows = [["тип", "название", "@username", "id", "ссылка"]]
        for it in items:
            rows.append(make_row(it))
        t = Table(rows, colWidths=col_widths, repeatRows=1)
        t.setStyle(table_style)
        story.append(t)

    if lookup is not None:
        story.append(Paragraph("━━━ Поиск по id ━━━", head))
        for it in lookup:
            if it.get("error"):
                story.append(Paragraph(_esc(f"id={it['id']}: ОШИБКА — {it['error']}"), body))
                story.append(Spacer(1, 4))
                continue
            link_html = (
                f'<a href="{xml_escape(it["link"])}" color="#1a73e8">{_esc(it["link"])}</a>'
                if it["link"] else "-"
            )
            block = [
                f"id&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;:&nbsp;{it['id']}",
                f"тип&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;:&nbsp;{_esc(it['type'])}",
                f"название&nbsp;&nbsp;&nbsp;&nbsp;:&nbsp;{_esc(it['title'])}",
                f"@username&nbsp;&nbsp;&nbsp;:&nbsp;{_esc(it['username'])}",
                f"ссылка&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;:&nbsp;{link_html}",
            ]
            if it.get("participants") is not None:
                block.append(f"участников&nbsp;&nbsp;:&nbsp;{it['participants']}")
            if it.get("about"):
                block.append(f"описание&nbsp;&nbsp;&nbsp;&nbsp;:&nbsp;{_esc(it['about'])}")
            for line in block:
                story.append(Paragraph(line, body))
            story.append(Spacer(1, 6))
    else:
        if not args.no_current:
            section("Активные подписки", current)
        if not args.no_left:
            section("Покинутые каналы (через takeout)", left)
        total_n = len(current) + len(left)
        story.append(Spacer(1, 8))
        story.append(Paragraph(f"Всего записей: {total_n}", head))

    doc.build(story)


# ----- Markdown renderer ----------------------------------------------------

def _md_escape(s: str) -> str:
    return (s or "").replace("|", "\\|").replace("\n", " ").replace("\r", " ")


def _md_link(it: dict) -> str:
    if it["link"]:
        return f"[{_md_escape(it['link'])}]({it['link']})"
    return "—"


def _md_section(out, title: str, items: list[dict]) -> None:
    print(f"## {title}  ({len(items)})\n", file=out)
    if not items:
        print("_(пусто)_\n", file=out)
        return
    print("| тип | название | @username | id | ссылка |", file=out)
    print("|-----|----------|-----------|----|--------|", file=out)
    items.sort(key=lambda x: (x["type"], x["title"].lower()))
    for it in items:
        print(
            f"| {it['type']} "
            f"| {_md_escape(it['title'])} "
            f"| `{_md_escape(it['username'])}` "
            f"| `{it['id']}` "
            f"| {_md_link(it)} |",
            file=out,
        )
    print(file=out)


def write_md(path: Path, args, current, left, lookup) -> None:
    with path.open("w", encoding="utf-8") as out:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print("# Telegram: список каналов и групп\n", file=out)
        print(
            f"**Время:** {now}  \n"
            f"**Тип:** `{args.type}`  \n"
            f"**Активные:** {'нет' if args.no_current else 'да'}  \n"
            f"**Покинутые:** {'нет' if args.no_left else 'да (Takeout)'}\n",
            file=out,
        )
        if lookup is not None:
            print("## Поиск по id\n", file=out)
            print("| id | тип | название | @username | участников | ссылка | описание |", file=out)
            print("|----|-----|----------|-----------|------------|--------|----------|", file=out)
            for it in lookup:
                if it.get("error"):
                    print(
                        f"| `{it['id']}` | — | _ОШИБКА_ | — | — | — | "
                        f"{_md_escape(it['error'])} |",
                        file=out,
                    )
                    continue
                parts = (
                    f"| `{it['id']}` "
                    f"| {it['type']} "
                    f"| {_md_escape(it['title'])} "
                    f"| `{_md_escape(it['username'])}` "
                    f"| {it.get('participants') if it.get('participants') is not None else '—'} "
                    f"| {_md_link(it)} "
                    f"| {_md_escape(it.get('about',''))} |"
                )
                print(parts, file=out)
            print(file=out)
            return
        if not args.no_current:
            _md_section(out, "Активные подписки", current)
        if not args.no_left:
            _md_section(out, "Покинутые каналы (через takeout)", left)
        print(f"---\n**Всего записей:** {len(current) + len(left)}", file=out)


# ----- XLSX renderer --------------------------------------------------------

def _xlsx_autofit(ws, max_widths: dict[int, int]) -> None:
    from openpyxl.utils import get_column_letter
    for col_idx, width in max_widths.items():
        ws.column_dimensions[get_column_letter(col_idx)].width = min(max(width + 2, 8), 80)


def _xlsx_write_table(ws, headers: list[str], rows: list[list], link_col: int | None) -> None:
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

    header_font = Font(name="Menlo", bold=True, color="FFFFFF", size=11)
    header_fill = PatternFill("solid", fgColor="2F5496")
    zebra_fill = PatternFill("solid", fgColor="F2F2F2")
    link_font = Font(name="Menlo", color="1A73E8", underline="single", size=10)
    body_font = Font(name="Menlo", size=10)
    center = Alignment(horizontal="left", vertical="center", wrap_text=True)
    thin = Side(style="thin", color="DDDDDD")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    max_widths: dict[int, int] = {}

    for col_idx, header in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = border
        max_widths[col_idx] = len(header)

    for r_idx, row in enumerate(rows, start=2):
        for c_idx, value in enumerate(row, start=1):
            cell = ws.cell(row=r_idx, column=c_idx, value=value)
            cell.font = body_font
            cell.alignment = center
            cell.border = border
            if r_idx % 2 == 0:
                cell.fill = zebra_fill
            sval = "" if value is None else str(value)
            max_widths[c_idx] = max(max_widths[c_idx], len(sval))
            if link_col is not None and c_idx == link_col and value and str(value).startswith("http"):
                cell.hyperlink = value
                cell.font = link_font

    ws.freeze_panes = "A2"
    _xlsx_autofit(ws, max_widths)


def write_xlsx(path: Path, args, current, left, lookup) -> None:
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment

    wb = Workbook()
    wb.remove(wb.active)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    info = wb.create_sheet("Сводка")
    info["A1"] = "Telegram: список каналов и групп"
    info["A1"].font = Font(bold=True, size=14)
    info["A3"] = "Время"; info["B3"] = now
    info["A4"] = "Тип"; info["B4"] = args.type
    info["A5"] = "Активные"; info["B5"] = "нет" if args.no_current else "да"
    info["A6"] = "Покинутые"; info["B6"] = "нет" if args.no_left else "да (Takeout)"
    info["A7"] = "Активных записей"; info["B7"] = len(current)
    info["A8"] = "Покинутых записей"; info["B8"] = len(left)
    info["A9"] = "Всего"; info["B9"] = len(current) + len(left)
    for r in range(3, 10):
        info.cell(row=r, column=1).font = Font(bold=True)
    info.column_dimensions["A"].width = 22
    info.column_dimensions["B"].width = 40

    def section_sheet(name: str, items: list[dict]):
        ws = wb.create_sheet(name)
        items.sort(key=lambda x: (x["type"], x["title"].lower()))
        rows = [
            [it["type"], it["title"], it["username"], it["id"], it["link"] or ""]
            for it in items
        ]
        _xlsx_write_table(
            ws,
            ["тип", "название", "@username", "id", "ссылка"],
            rows,
            link_col=5,
        )

    if lookup is not None:
        ws = wb.create_sheet("Поиск")
        rows = []
        for it in lookup:
            if it.get("error"):
                rows.append([it["id"], "—", f"ОШИБКА: {it['error']}", "—", "—", "—", "—"])
                continue
            rows.append([
                it["id"], it["type"], it["title"], it["username"],
                it.get("participants") if it.get("participants") is not None else "",
                it["link"] or "",
                it.get("about", ""),
            ])
        _xlsx_write_table(
            ws,
            ["id", "тип", "название", "@username", "участников", "ссылка", "описание"],
            rows,
            link_col=6,
        )
    else:
        if not args.no_current:
            section_sheet("Активные", current)
        if not args.no_left:
            section_sheet("Покинутые", left)

    wb.save(str(path))


# ----- Main -----------------------------------------------------------------

async def run(args) -> None:
    fmt = resolve_format(args)
    if fmt in ("pdf", "md", "xlsx") and args.output is None:
        print(f"ОШИБКА: для формата {fmt} нужен --output PATH.", file=sys.stderr)
        sys.exit(2)

    def log(msg: str) -> None:
        print(msg, file=sys.stderr, flush=True)

    log(f"→ Подключаюсь, сессия={args.session!r}...")
    client = TelegramClient(args.session, API_ID, API_HASH)
    await client.start()
    me = await client.get_me()
    log(f"→ Авторизован: {me.first_name} (@{me.username}) id={me.id}")

    current: list[dict] = []
    left: list[dict] = []
    lookup: list[dict] | None = None

    try:
        if args.lookup:
            log("→ Режим lookup: ищу по id...")
            lookup = await lookup_records(client, args.lookup, log)
        else:
            if not args.no_current:
                log("→ Загружаю АКТИВНЫЕ подписки...")
                current = await fetch_current(client, args.type, log)
            if not args.no_left:
                log("→ Загружаю ПОКИНУТЫЕ каналы через Takeout...")
                exclude = {r["id"] for r in current}
                left = await fetch_left(client, args.type, exclude, args.poll, log)
    finally:
        await client.disconnect()
        log("→ Отключён.")

    log(f"→ Запись отчёта (формат={fmt})...")
    if fmt == "pdf":
        write_pdf(args.output, args, current, left, lookup)
    elif fmt == "md":
        write_md(args.output, args, current, left, lookup)
    elif fmt == "xlsx":
        write_xlsx(args.output, args, current, left, lookup)
    else:
        write_text(args.output, args, current, left, lookup)
    if args.output:
        log(f"→ Готово: {args.output}")


def main() -> None:
    args = parse_args()
    load_env(Path(__file__).parent / ".env")
    if "API_ID" not in os.environ or "API_HASH" not in os.environ:
        print(
            "ОШИБКА: API_ID / API_HASH не заданы. "
            "Положи их в .env рядом со скриптом или экспортируй в окружение.",
            file=sys.stderr,
        )
        sys.exit(2)

    global API_ID, API_HASH
    API_ID = int(os.environ["API_ID"])
    API_HASH = os.environ["API_HASH"]

    asyncio.run(run(args))


if __name__ == "__main__":
    main()
