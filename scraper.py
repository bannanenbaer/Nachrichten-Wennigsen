#!/usr/bin/env python3
"""
Scrapes con-nect.de/wennigsen and writes an RSS feed to feed.xml.
Run once daily (e.g. via Synology Task Scheduler at 06:00).
Only articles from the last 7 days are included.
"""
import urllib.request
import re
import datetime
import os
from email.utils import formatdate
import calendar
import sys

SOURCE_URL = "https://www.con-nect.de/wennigsen"
BASE_URL    = "https://www.con-nect.de"
OUTPUT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "feed.xml")
DAYS_BACK   = 7


def fetch(url):
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (compatible; NachrichtenWennigsen/1.0)"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8")


def parse_articles(html):
    articles = []

    # Each article lives inside a <div class="teaser-text"> block.
    # We grab the block up to the closing </div> of the ortsmarke div or the mehr-link.
    blocks = re.findall(
        r'<div[^>]+class="teaser-text"[^>]*>(.*?)</div>\s*</div>\s*</div>',
        html,
        re.DOTALL,
    )

    for block in blocks:
        # --- date (prefer machine-readable datetime attribute) ---
        date_m = re.search(r'<time[^>]+datetime="(\d{4}-\d{2}-\d{2})"', block)
        if not date_m:
            # fallback: visible text DD.MM.YYYY
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

        # --- link + title ---
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

        # --- teaser description (inside div.ortsmarke[itemprop=description]) ---
        desc_m = re.search(
            r'<div[^>]+itemprop="description"[^>]*>(.*?)</div>',
            block,
            re.DOTALL,
        )
        desc = ""
        if desc_m:
            desc = re.sub(r"<[^>]+>", "", desc_m.group(1))
            desc = re.sub(r"\s+", " ", desc).strip()

        articles.append({"title": title, "link": link, "date": pub_date, "desc": desc})

    return articles


def filter_recent(articles):
    cutoff = datetime.datetime.now() - datetime.timedelta(days=DAYS_BACK)
    return [a for a in articles if a["date"] >= cutoff]


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


def main():
    try:
        html     = fetch(SOURCE_URL)
        articles = parse_articles(html)
        recent   = filter_recent(articles)
        rss      = build_rss(recent)

        with open(OUTPUT_FILE, "w", encoding="utf-8") as fh:
            fh.write(rss)

        print(
            f"[{datetime.datetime.now():%Y-%m-%d %H:%M}] "
            f"OK – {len(recent)} Artikel in feed.xml geschrieben"
        )
    except Exception as exc:
        print(f"[{datetime.datetime.now():%Y-%m-%d %H:%M}] FEHLER: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
