#!/usr/bin/env python3
"""
Genera un feed RSS non ufficiale a partire dall'archivio dei comunicati
stampa della Provincia di Mantova:
https://www.provincia.mantova.it/cs_home.jsp?ID_LINK=64&area=24

Il sito non offre un proprio feed RSS: questo script fa scraping della
pagina, estrae titolo / data / descrizione / link di ogni comunicato e
genera un file feed.xml valido (RSS 2.0).

Pensato per essere eseguito periodicamente (es. una volta all'ora) da una
GitHub Action, innescata da un cronjob esterno (es. cron-job.org) che
chiama l'API di GitHub per lanciare il workflow.
"""

from __future__ import annotations

import re
import sys
from datetime import datetime
from email.utils import format_datetime
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.provincia.mantova.it/cs_home.jsp"
PAGE_PARAMS = {"ID_LINK": "64", "area": "24"}

# Numero di pagine di archivio da leggere ad ogni esecuzione.
# Ogni pagina contiene circa 20 comunicati; 1 pagina è sufficiente per un
# aggiornamento orario, ma si può aumentare se il sito pubblica molto.
MAX_PAGES = 1

OUTPUT_PATH = "docs/feed.xml"

FEED_TITLE = "Comunicati stampa - Provincia di Mantova (feed non ufficiale)"
FEED_LINK = f"{BASE_URL}?ID_LINK=64&area=24"
FEED_DESCRIPTION = (
    "Feed RSS non ufficiale generato tramite scraping dell'archivio "
    "comunicati stampa della Provincia di Mantova. Non è un servizio "
    "ufficiale dell'ente."
)

TZ = ZoneInfo("Europe/Rome")

DATE_RE = re.compile(r"(\d{2}\.\d{2}\.\d{4})\s+(\d{2}:\d{2})")
ID_CONTEXT_RE = re.compile(r"id_context=(\d+)")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; comivat_stampa_mn/1.0; "
        "+https://github.com/mbmichele/comivat_stampa_mn)"
    )
}


def fetch_page(page: int) -> str:
    params = dict(PAGE_PARAMS)
    if page > 1:
        params.update({"page_38": str(page), "id_schema": "3", "id_scat": "1"})
    resp = requests.get(BASE_URL, params=params, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    # Il sito dichiara ISO-8859-1: lasciamo che requests/chardet rilevi
    # la codifica corretta se diversa da quella dichiarata.
    if not resp.encoding or resp.encoding.lower() == "iso-8859-1":
        resp.encoding = resp.apparent_encoding or "ISO-8859-1"
    return resp.text


def find_dated_container(anchor, max_depth: int = 6):
    """Risale dai genitori dell'anchor finché non trova un blocco di testo
    che contiene una data nel formato gg.mm.aaaa hh:mm — quello è il
    contenitore del singolo comunicato."""
    node = anchor
    for _ in range(max_depth):
        node = node.parent
        if node is None:
            break
        text = node.get_text("\n", strip=True)
        if DATE_RE.search(text):
            return node
    return anchor.parent


def parse_item(anchor) -> dict | None:
    href = anchor.get("href", "")
    match_id = ID_CONTEXT_RE.search(href)
    if not match_id:
        return None

    title = anchor.get_text(strip=True)
    if not title:
        # fallback sull'attributo title, ripulito dal prefisso descrittivo
        title = (anchor.get("title") or "").strip()
        title = re.sub(r"^Vai al dettaglio del comunicato\s*", "", title).strip()
    if not title:
        return None

    link = href
    if link.startswith("/"):
        link = "https://www.provincia.mantova.it" + link
    elif not link.startswith("http"):
        link = "https://www.provincia.mantova.it/" + link.lstrip("/")

    container = find_dated_container(anchor)
    raw_text = container.get_text("\n", strip=True)
    lines = [ln.strip() for ln in raw_text.split("\n") if ln.strip()]

    date_match = DATE_RE.search(raw_text)
    if not date_match:
        return None
    dt_naive = datetime.strptime(
        f"{date_match.group(1)} {date_match.group(2)}", "%d.%m.%Y %H:%M"
    )
    dt = dt_naive.replace(tzinfo=TZ)

    description_parts = []
    for ln in lines:
        if ln == title:
            continue
        if DATE_RE.fullmatch(ln) or DATE_RE.search(ln) and len(ln) < 25:
            continue
        # le "categorie" (per il cittadino, per enti ed imprese, ...)
        # sono sempre rese come frammenti che terminano con una virgola
        if ln.endswith(","):
            continue
        description_parts.append(ln)

    description = " ".join(description_parts).strip()

    return {
        "id": match_id.group(1),
        "title": title,
        "link": link,
        "date": dt,
        "description": description,
    }


def scrape_all() -> list[dict]:
    items: dict[str, dict] = {}
    for page in range(1, MAX_PAGES + 1):
        html = fetch_page(page)
        soup = BeautifulSoup(html, "lxml")
        anchors = [
            a
            for a in soup.find_all("a", href=True)
            if "cs_context.jsp" in a["href"] and "id_context=" in a["href"]
        ]
        if not anchors:
            break
        for a in anchors:
            item = parse_item(a)
            if item and item["id"] not in items:
                items[item["id"]] = item

    ordered = sorted(items.values(), key=lambda x: x["date"], reverse=True)
    return ordered


def build_rss(items: list[dict]) -> str:
    now = datetime.now(TZ)
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0">',
        "<channel>",
        f"<title>{escape(FEED_TITLE)}</title>",
        f"<link>{escape(FEED_LINK)}</link>",
        f"<description>{escape(FEED_DESCRIPTION)}</description>",
        "<language>it-IT</language>",
        f"<lastBuildDate>{format_datetime(now)}</lastBuildDate>",
    ]
    for item in items:
        parts.append("<item>")
        parts.append(f"<title>{escape(item['title'])}</title>")
        parts.append(f"<link>{escape(item['link'])}</link>")
        parts.append(
            f'<guid isPermaLink="true">{escape(item["link"])}</guid>'
        )
        parts.append(f"<pubDate>{format_datetime(item['date'])}</pubDate>")
        parts.append(f"<description>{escape(item['description'])}</description>")
        parts.append("</item>")
    parts.append("</channel>")
    parts.append("</rss>")
    return "\n".join(parts)


def main() -> int:
    items = scrape_all()
    if not items:
        print("Nessun comunicato trovato: non aggiorno il feed.", file=sys.stderr)
        return 1
    rss = build_rss(items)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(rss)
    print(f"Scritti {len(items)} comunicati in {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
