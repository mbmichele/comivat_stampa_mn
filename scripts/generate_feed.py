#!/usr/bin/env python3
"""
Genera un unico feed RSS non ufficiale che aggrega tre fonti pubbliche
della Provincia di Mantova:

1. Comunicati stampa
   https://www.provincia.mantova.it/cs_home.jsp?ID_LINK=64&area=24
   (nessun feed nativo: scraping)

2. Eventi
   https://www.provincia.mantova.it/events.jsp?ID_LINK=3&area=5
   (nessun feed nativo: scraping)

3. Notizie
   https://www.provincia.mantova.it/news.jsp?areaNews=11
   (il sito offre già un feed nativo, usato direttamente:
    https://www.provincia.mantova.it/rss/news_rss.jsp?areaNews=11)

Ogni elemento del feed contiene titolo, data, descrizione e link.

Pensato per essere eseguito periodicamente (es. una volta all'ora) da una
GitHub Action, con doppia attivazione: uno schedule interno e un cronjob
esterno (es. cron-job.org) che chiama l'API di GitHub.
"""

from __future__ import annotations

import re
import sys
from datetime import datetime
from email.utils import format_datetime, parsedate_to_datetime
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

TZ = ZoneInfo("Europe/Rome")
OUTPUT_PATH = "docs/feed.xml"

FEED_TITLE = "Comunicati, notizie ed eventi - Provincia di Mantova (feed non ufficiale)"
FEED_LINK = "https://www.provincia.mantova.it/"
FEED_DESCRIPTION = (
    "Feed RSS non ufficiale che aggrega comunicati stampa, notizie ed "
    "eventi pubblicati dalla Provincia di Mantova. Non è un servizio "
    "ufficiale dell'ente."
)

# Numero massimo di elementi totali nel feed finale (le tre fonti vengono
# unite e ordinate per data, poi troncate a questo numero).
MAX_ITEMS = 60

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; comunicaz_prov_mn/1.0; "
        "+https://github.com/mbmichele/comunicaz_prov_mn)"
    )
}

SITE_ROOT = "https://www.provincia.mantova.it"


def _get(url: str, params: dict | None = None) -> str:
    resp = requests.get(url, params=params, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    if not resp.encoding or resp.encoding.lower() in ("iso-8859-1", "latin-1"):
        resp.encoding = resp.apparent_encoding or "ISO-8859-1"
    return resp.text


def _abs_url(href: str) -> str:
    if href.startswith("http"):
        return href
    if href.startswith("/"):
        return SITE_ROOT + href
    return SITE_ROOT + "/" + href.lstrip("/")


# ---------------------------------------------------------------------------
# 1. Comunicati stampa (cs_home.jsp) — scraping
# ---------------------------------------------------------------------------

CS_BASE_URL = f"{SITE_ROOT}/cs_home.jsp"
CS_PARAMS = {"ID_LINK": "64", "area": "24"}
CS_MAX_PAGES = 1  # ~20 comunicati a pagina, sufficiente per un update orario

CS_DATETIME_RE = re.compile(r"(\d{2}\.\d{2}\.\d{4})\s+(\d{2}:\d{2})")
CS_ID_RE = re.compile(r"id_context=(\d+)")


def _find_container_with(anchor, pattern: re.Pattern, max_depth: int = 6):
    node = anchor
    for _ in range(max_depth):
        node = node.parent
        if node is None:
            break
        if pattern.search(node.get_text("\n", strip=True)):
            return node
    return anchor.parent


def _parse_cs_item(anchor) -> dict | None:
    href = anchor.get("href", "")
    match_id = CS_ID_RE.search(href)
    if not match_id:
        return None

    title = anchor.get_text(strip=True)
    if not title:
        title = (anchor.get("title") or "").strip()
        title = re.sub(r"^Vai al dettaglio del comunicato\s*", "", title).strip()
    if not title:
        return None

    link = _abs_url(href)
    container = _find_container_with(anchor, CS_DATETIME_RE)
    raw_text = container.get_text("\n", strip=True)
    lines = [ln.strip() for ln in raw_text.split("\n") if ln.strip()]

    date_match = CS_DATETIME_RE.search(raw_text)
    if not date_match:
        return None
    dt = datetime.strptime(
        f"{date_match.group(1)} {date_match.group(2)}", "%d.%m.%Y %H:%M"
    ).replace(tzinfo=TZ)

    description_parts = []
    for ln in lines:
        if ln == title:
            continue
        if CS_DATETIME_RE.fullmatch(ln) or (CS_DATETIME_RE.search(ln) and len(ln) < 25):
            continue
        # le "categorie" (per il cittadino, per enti ed imprese, ...)
        # terminano sempre con una virgola
        if ln.endswith(","):
            continue
        description_parts.append(ln)

    return {
        "uid": f"cs-{match_id.group(1)}",
        "title": title,
        "link": link,
        "date": dt,
        "description": " ".join(description_parts).strip(),
    }


def fetch_comunicati_stampa() -> list[dict]:
    items: dict[str, dict] = {}
    for page in range(1, CS_MAX_PAGES + 1):
        params = dict(CS_PARAMS)
        if page > 1:
            params.update({"page_38": str(page), "id_schema": "3", "id_scat": "1"})
        html = _get(CS_BASE_URL, params=params)
        soup = BeautifulSoup(html, "lxml")
        anchors = [
            a for a in soup.find_all("a", href=True)
            if "cs_context.jsp" in a["href"] and "id_context=" in a["href"]
        ]
        if not anchors:
            break
        for a in anchors:
            item = _parse_cs_item(a)
            if item and item["uid"] not in items:
                items[item["uid"]] = item
    return list(items.values())


# ---------------------------------------------------------------------------
# 2. Eventi (events.jsp) — scraping
# ---------------------------------------------------------------------------

EVENTS_URL = f"{SITE_ROOT}/events.jsp"
EVENTS_PARAMS = {"ID_LINK": "3", "area": "5"}

EVENT_ID_RE = re.compile(r"ID_EVENT=(\d+)")
EVENT_DATE_ONLY_RE = re.compile(r"^-?\s*(\d{2}\.\d{2}\.\d{4})$")
EVENT_DATE_ANYWHERE_RE = re.compile(r"\d{2}\.\d{2}\.\d{4}")


def _parse_event_item(anchor) -> dict | None:
    href = anchor.get("href", "")
    match_id = EVENT_ID_RE.search(href)
    if not match_id:
        return None

    title = anchor.get_text(strip=True)
    if not title:
        return None

    link = _abs_url(href)
    container = _find_container_with(anchor, EVENT_DATE_ANYWHERE_RE)
    raw_text = container.get_text("\n", strip=True)
    lines = [ln.strip() for ln in raw_text.split("\n") if ln.strip()]

    dates = []
    other_lines = []
    for ln in lines:
        if ln == title:
            continue
        m = EVENT_DATE_ONLY_RE.match(ln)
        if m:
            dates.append(m.group(1))
        else:
            other_lines.append(ln)

    if not dates:
        return None

    start_dt = datetime.strptime(dates[0], "%d.%m.%Y").replace(tzinfo=TZ)

    description_parts = list(other_lines)
    if len(dates) > 1 and dates[1] != dates[0]:
        description_parts.insert(0, f"Fino al {dates[1]}.")

    return {
        "uid": f"ev-{match_id.group(1)}",
        "title": title,
        "link": link,
        "date": start_dt,
        "description": " ".join(description_parts).strip(),
    }


def fetch_eventi() -> list[dict]:
    html = _get(EVENTS_URL, params=EVENTS_PARAMS)
    soup = BeautifulSoup(html, "lxml")
    anchors = [
        a for a in soup.find_all("a", href=True)
        if "events_detail.jsp" in a["href"] and "ID_EVENT=" in a["href"]
    ]
    items: dict[str, dict] = {}
    for a in anchors:
        item = _parse_event_item(a)
        if item and item["uid"] not in items:
            items[item["uid"]] = item
    return list(items.values())


# ---------------------------------------------------------------------------
# 3. Notizie (news.jsp) — il sito offre già un feed RSS nativo, lo leggiamo
# ---------------------------------------------------------------------------

NEWS_RSS_URL = f"{SITE_ROOT}/rss/news_rss.jsp"
NEWS_RSS_PARAMS = {"areaNews": "11"}
NEWS_ID_RE = re.compile(r"ID_NEWS=(\d+)")


def fetch_notizie() -> list[dict]:
    xml_text = _get(NEWS_RSS_URL, params=NEWS_RSS_PARAMS)
    soup = BeautifulSoup(xml_text, "xml")
    items: dict[str, dict] = {}
    for item_tag in soup.find_all("item"):
        title = (item_tag.title.get_text(strip=True) if item_tag.title else "")
        link_raw = (item_tag.link.get_text(strip=True) if item_tag.link else "")
        description = (
            item_tag.description.get_text(" ", strip=True)
            if item_tag.description else ""
        )
        pub_date_raw = item_tag.pubDate.get_text(strip=True) if item_tag.pubDate else ""
        if not title or not link_raw or not pub_date_raw:
            continue

        link = link_raw.replace("http://", "https://", 1)
        match_id = NEWS_ID_RE.search(link_raw)
        uid = f"news-{match_id.group(1)}" if match_id else f"news-{hash(link_raw)}"

        cleaned = re.sub(r"\s+", " ", pub_date_raw).strip()
        try:
            dt = parsedate_to_datetime(cleaned)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=TZ)
        except (TypeError, ValueError):
            continue

        if uid not in items:
            items[uid] = {
                "uid": uid,
                "title": title,
                "link": link,
                "date": dt,
                "description": description,
            }
    return list(items.values())


# ---------------------------------------------------------------------------
# Aggregazione e generazione RSS
# ---------------------------------------------------------------------------

def collect_all() -> list[dict]:
    all_items: list[dict] = []
    fetchers = [
        ("comunicati stampa", fetch_comunicati_stampa),
        ("eventi", fetch_eventi),
        ("notizie", fetch_notizie),
    ]
    for label, fetcher in fetchers:
        try:
            items = fetcher()
            print(f"  {label}: {len(items)} elementi", file=sys.stderr)
            all_items.extend(items)
        except Exception as exc:  # non blocca le altre fonti se una fallisce
            print(f"  {label}: ERRORE ({exc})", file=sys.stderr)

    deduped = {item["uid"]: item for item in all_items}
    ordered = sorted(deduped.values(), key=lambda x: x["date"], reverse=True)
    return ordered[:MAX_ITEMS]


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
        parts.append(f'<guid isPermaLink="true">{escape(item["link"])}</guid>')
        parts.append(f"<pubDate>{format_datetime(item['date'])}</pubDate>")
        parts.append(f"<description>{escape(item['description'])}</description>")
        parts.append("</item>")
    parts.append("</channel>")
    parts.append("</rss>")
    return "\n".join(parts)


def main() -> int:
    print("Scraping delle fonti...", file=sys.stderr)
    items = collect_all()
    if not items:
        print("Nessun elemento trovato: non aggiorno il feed.", file=sys.stderr)
        return 1
    rss = build_rss(items)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(rss)
    print(f"Scritti {len(items)} elementi totali in {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
