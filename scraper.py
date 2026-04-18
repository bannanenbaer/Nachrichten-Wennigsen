#!/usr/bin/env python3
"""
Scrapes con-nect.de/wennigsen and writes an RSS feed to feed.xml.

Two-phase strategy:
  Phase 1 (fast): write feed.xml immediately with teaser text for new articles
                  and full text for already-cached articles.
  Phase 2 (background): fetch full text for new articles one by one,
                  update cache.json and rewrite feed.xml after each fetch.

This keeps startup fast even when many new articles appear.
"""
import urllib.request
import re
import datetime
import os
import json
import threading
from email.utils import formatdate
import calendar
import sys

SOURCE_URL  = "https://www.con-nect.de/wennigsen"
BASE_URL    = "https://www.con-nect.de"
DIR         = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(DIR, "feed.xml")
CACHE_FILE  = os.path.join(DIR, "cache.json")
DAYS_BACK   = 7

_write_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, encoding="utf-8") as fh:
            return json.load(fh)
    return {}


def save_cache(cache):
    with open(CACHE_FILE, "w", encoding="utf-8") as fh:
        json.dump(cache, fh, ensure_ascii=False, indent=2)


def expire_cache(cache):
    cutoff = (datetime.datetime.now() - datetime.timedelta(days=DAYS_BACK)).strftime("%Y-%m-%d")
    return {url: data for url, data in cache.items() if data.get("date", "") >= cutoff}


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def fetch(url):
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (compatible; NachrichtenWennigsen/1.0)"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")


def fetch_full_text(url):
    try:
        html = fetch(url)
        m = re.search(
            r'itemprop="articleBody">(.*?)</div>\s*</div>\s*</div>',
            html,
            re.DOTALL,
        )
        if not m:
            return ""
        body = m.group(1)
        paragraphs = re.findall(r'<p[^>]*>(.*?)</p>', body, re.DOTALL)
        texts = []
        for p in paragraphs:
            text = re.sub(r'<[^>]+>', '', p)
            text = (text
                    .replace('&nbsp;', ' ')
                    .replace('&amp;', '&')
                    .replace('&lt;', '<')
                    .replace('&gt;', '>'))
            text = re.sub(r'\s+', ' ', text).strip()
            if text:
                texts.append(text)
        return '\n\n'.join(texts)
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def parse_articles(html):
    articles = []

    blocks = re.findall(
        r'<div[^>]+class="teaser-text"[^>]*>(.*?)</div>\s*</div>\s*</div>',
        html,
        re.DOTALL,
    )

    for block in blocks:
        # date
        date_m = re.search(r'<time[^>]+datetime="(\d{4}-\d{2}-\d{2})"', block)
        if not date_m:
            date_m = re.search(r'<time[^>]*>\s*(\d{2}\.\d{2}\.\d{4})\s*</time>', block)
            if not date_m:
                continue
            try:
                pub_date = datetime.datetime.strptime(date_m.group(1), "%d.%m.%Y")
            except ValueError:
                continue
        else:
            try:
                pub_date = datetime.datetime.strptime(date_m.group(1), "%Y-%m-%d")
            except ValueError:
                continue

        # link + title
        link_m = re.search(
            r'<a[^>]+href="(/wennigsen/[^"]+)"[^>]*>.*?'
            r'<span[^>]*itemprop="headline"[^>]*>(.*?)</span>',
            block,
            re.DOTALL,
        )
        if not link_m:
            continue
        href  = link_m.group(1)
        title = re.sub(r"<[^>]+>", "", link_m.group(2))
        title = re.sub(r"\s+", " ", title).strip()
        link  = BASE_URL + href

        # teaser text (short, from list page — used as placeholder until full text is cached)
        teaser = ""
        teaser_m = re.search(r'<div[^>]+itemprop="description"[^>]*>(.*?)</div>', block, re.DOTALL)
        if teaser_m:
            teaser = re.sub(r"<[^>]+>", "", teaser_m.group(1))
            teaser = re.sub(r"\s+", " ", teaser).strip()

        articles.append({
            "title":  title,
            "link":   link,
            "date":   pub_date,
            "desc":   teaser,   # placeholder; replaced by full text once cached
        })

    return articles


def filter_recent(articles):
    cutoff = datetime.datetime.now() - datetime.timedelta(days=DAYS_BACK)
    return [a for a in articles if a["date"] >= cutoff]


# ---------------------------------------------------------------------------
# RSS builder
# ---------------------------------------------------------------------------

def xml_escape(s):
    return (
        s.replace("&", "&amp;")
         .replace("<", "&lt;")
         .replace(">", "&gt;")
         .replace('"', "&quot;")
    )


def build_rss(articles):
    items = []
    for a in articles:
        rss_title   = xml_escape(f"{a['date'].strftime('%d.%m.%Y')} | {a['title']}")
        rss_link    = xml_escape(a["link"])
        rss_desc    = xml_escape(a["desc"])
        rss_pubdate = formatdate(calendar.timegm(a["date"].timetuple()))

        items.append(
            f"    <item>\n"
            f"      <title>{rss_title}</title>\n"
            f"      <link>{rss_link}</link>\n"
            f"      <description>{rss_desc}</description>\n"
            f"      <pubDate>{rss_pubdate}</pubDate>\n"
            f"      <guid isPermaLink=\"true\">{rss_link}</guid>\n"
            f"    </item>"
        )

    now = formatdate()
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0">\n'
        '  <channel>\n'
        '    <title>Nachrichten Wennigsen</title>\n'
        '    <link>https://www.con-nect.de/wennigsen</link>\n'
        '    <description>Lokale Nachrichten Wennigsen – letzte 7 Tage</description>\n'
        '    <language>de-DE</language>\n'
        f'    <lastBuildDate>{now}</lastBuildDate>\n'
        '    <ttl>1440</ttl>\n'
        + "\n".join(items)
        + "\n  </channel>\n</rss>\n"
    )


def _write_feed(recent):
    rss = build_rss(recent)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as fh:
        fh.write(rss)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(background=False):
    """
    background=True  → full-text fetches run in a daemon thread (used by Flask/APScheduler)
    background=False → wait for all fetches before returning (used on command line)
    """
    try:
        cache  = load_cache()
        cache  = expire_cache(cache)

        html     = fetch(SOURCE_URL)
        articles = parse_articles(html)
        recent   = filter_recent(articles)

        new_articles = []
        for a in recent:
            if a["link"] in cache:
                a["desc"] = cache[a["link"]]["desc"]
            else:
                # desc already set to teaser from parse_articles
                new_articles.append(a)

        # Phase 1: write feed immediately (teasers for new, full text for cached)
        with _write_lock:
            _write_feed(recent)

        cached_count = len(recent) - len(new_articles)
        if new_articles:
            print(
                f"[{datetime.datetime.now():%Y-%m-%d %H:%M}] "
                f"Phase 1 fertig – {len(recent)} Artikel "
                f"({cached_count} aus Cache, {len(new_articles)} neu mit Teaser)"
            )
        else:
            print(
                f"[{datetime.datetime.now():%Y-%m-%d %H:%M}] "
                f"OK – {len(recent)} Artikel (alle aus Cache)"
            )
            save_cache(cache)
            return

        # Phase 2: fetch full texts in background
        def fetch_all():
            for a in new_articles:
                full = fetch_full_text(a["link"])
                a["desc"] = full
                with _write_lock:
                    cache[a["link"]] = {
                        "date": a["date"].strftime("%Y-%m-%d"),
                        "desc": full,
                    }
                    save_cache(cache)
                    _write_feed(recent)
                print(
                    f"  [fertig] [{a['date'].strftime('%d.%m.%Y')}] {a['title'][:55]}"
                )
            print(
                f"[{datetime.datetime.now():%Y-%m-%d %H:%M}] "
                f"Phase 2 fertig – {len(new_articles)} Volltexte gecacht"
            )

        t = threading.Thread(target=fetch_all, daemon=True)
        t.start()
        if not background:
            t.join()

    except Exception as exc:
        print(f"[{datetime.datetime.now():%Y-%m-%d %H:%M}] FEHLER: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main(background=False)
