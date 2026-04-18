#!/usr/bin/env python3
"""
Scrapes con-nect.de/wennigsen and writes an RSS feed to feed.xml.
Only articles from the last 7 days are included.
For each recent article the full text is fetched from the detail page.
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
        return r.read().decode("utf-8", errors="replace")


def fetch_full_text(url):
    """Fetch full article text from the detail page."""
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


def parse_articles(html):
    articles = []

    blocks = re.findall(
        r'<div[^>]+class="teaser-text"[^>]*>(.*?)</div>\s*</div>\s*</div>',
        html,
        re.DOTALL,
    )

    for block in blocks:
        # --- date ---
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

        articles.append({"title": title, "link": link, "date": pub_date, "desc": ""})

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

        # Fetch full text only for recent articles (minimises HTTP requests)
        for a in recent:
            a["desc"] = fetch_full_text(a["link"])
            print(f"  [{a['date'].strftime('%d.%m.%Y')}] {a['title'][:60]}")

        rss = build_rss(recent)

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
