#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Собирает sitemap.xml и rss.xml. Главное отличие: <lastmod> теперь строго ISO-8601.
"""

from __future__ import annotations
from pathlib import Path
import re
from datetime import datetime, timezone
try:
    from zoneinfo import ZoneInfo  # Py3.9+
except Exception:
    ZoneInfo = None

ROOT = Path(__file__).resolve().parents[1]
SITE = "https://vpnhub-cyber.github.io"  # канонический хост

# ---- парсинг html ----
RE_TITLE = re.compile(r"<title>(.*?)</title>", re.I | re.S)
RE_DESC  = re.compile(r'<meta\s+name="description"\s+content="(.*?)"', re.I | re.S)
RE_MOD   = re.compile(r'<meta\s+property="article:modified_time"\s+content="(.*?)"', re.I | re.S)

def parse_html(path: Path):
    txt = path.read_text("utf-8", errors="ignore")
    title = (RE_TITLE.search(txt).group(1).strip() if RE_TITLE.search(txt) else path.stem)
    desc  = (RE_DESC.search(txt).group(1).strip()  if RE_DESC.search(txt)  else "")
    # modified_time берём из меты (если есть), иначе mtime файла
    if (m := RE_MOD.search(txt)):
        raw = m.group(1).strip().replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(raw)
        except Exception:
            dt = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    else:
        dt = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    return title, desc, dt

# ---- правильные форматы времени ----
def to_sitemap_lastmod(dt: datetime, tz_hint: str = "Europe/Moscow") -> str:
    """
    Требования Sitemap: ISO-8601/RFC-3339. Возвращаем UTC c 'Z'.
    """
    if dt.tzinfo is None:
        if ZoneInfo:
            dt = dt.replace(tzinfo=ZoneInfo(tz_hint))
        else:
            dt = dt.replace(tzinfo=timezone.utc)
    dt_utc = dt.astimezone(timezone.utc).replace(microsecond=0)
    return dt_utc.isoformat().replace("+00:00", "Z")

def to_rss_pubdate(dt: datetime, tz_hint: str = "Europe/Moscow") -> str:
    """
    Для RSS нужно RFC-822: Mon, 11 Aug 2025 20:04:06 +0300
    """
    if dt.tzinfo is None:
        if ZoneInfo:
            dt = dt.replace(tzinfo=ZoneInfo(tz_hint))
        else:
            dt = dt.replace(tzinfo=timezone.utc)
    return dt.strftime("%a, %d %b %Y %H:%M:%S %z")

def rel_url(path: Path) -> str:
    p = path.relative_to(ROOT).as_posix()
    return "/" if p == "index.html" else f"/{p}"

def collect_items():
    files = []
    # корень
    for p in [ROOT / "index.html", ROOT / "all-articles.html"]:
        if p.exists():
            files.append(p)
    # статьи
    art = ROOT / "articles"
    if art.exists():
        files += sorted(art.rglob("*.html"))
    items = []
    for p in files:
        title, desc, dt = parse_html(p)
        items.append({
            "path": p,
            "url": SITE + rel_url(p),
            "title": title,
            "desc": desc,
            "dt": dt
        })
    # от новых к старым
    items.sort(key=lambda x: x["dt"], reverse=True)
    return items

def escape_xml(s: str) -> str:
    return (s.replace("&","&amp;").replace("<","&lt;")
             .replace(">","&gt;").replace('"',"&quot;").replace("'","&apos;"))

def build_sitemap(items):
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for it in items:
        out.append("  <url>")
        out.append(f"    <loc>{it['url']}</loc>")
        out.append(f"    <lastmod>{to_sitemap_lastmod(it['dt'])}</lastmod>")
        out.append("  </url>")
    out.append("</urlset>")
    (ROOT / "sitemap.xml").write_text("\n".join(out), encoding="utf-8")

def build_rss(items):
    now_dt = items[0]["dt"] if items else datetime.now(timezone.utc)
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<rss version="2.0">','  <channel>',
           '    <title>VPNhub-Cyber — новые статьи</title>',
           f'    <link>{SITE}/</link>',
           '    <description>Последние публикации о VPN и доступе к сервисам</description>',
           '    <language>ru</language>',
           f'    <lastBuildDate>{to_rss_pubdate(now_dt)}</lastBuildDate>']
    for it in items[:50]:
        out.append("    <item>")
        out.append(f"      <title>{escape_xml(it['title'])}</title>")
        out.append(f"      <link>{it['url']}</link>")
        if it["desc"]:
            out.append(f"      <description>{escape_xml(it['desc'])}</description>")
        out.append(f"      <pubDate>{to_rss_pubdate(it['dt'])}</pubDate>")
        out.append("    </item>")
    out += ["  </channel>", "</rss>"]
    (ROOT / "rss.xml").write_text("\n".join(out), encoding="utf-8")

def main():
    items = collect_items()
    build_sitemap(items)
    build_rss(items)

if __name__ == "__main__":
    main()
