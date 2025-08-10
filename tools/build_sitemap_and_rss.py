#!/usr/bin/env python3
import os, re, pathlib, subprocess, html
from datetime import datetime, timezone
from email.utils import format_datetime

ROOT = pathlib.Path(__file__).resolve().parents[1]
SITE = "https://vpnhub-cyber.github.io"
ART = ROOT / "articles"

def git_date(path: pathlib.Path) -> datetime:
    try:
        iso = subprocess.check_output(
            ["git","log","-1","--format=%cI", str(path)],
            cwd=str(ROOT)).decode().strip()
        return datetime.fromisoformat(iso.replace('Z', '+00:00'))
    except Exception:
        return datetime.now(timezone.utc)

def extract_title_meta(p: pathlib.Path):
    text = p.read_text(encoding="utf-8", errors="ignore")
    t = re.search(r"<title>(.*?)</title>", text, re.I|re.S)
    d = re.search(r'<meta\s+name="description"\s+content="([^"]*)"', text, re.I)
    title = html.escape((t.group(1).strip() if t else p.stem))
    desc = html.escape((d.group(1).strip() if d else ""))
    return title, desc

def rel_url(p: pathlib.Path) -> str:
    if p.name == "index.html" and p.parent == ROOT:
        return "/"
    return "/" + str(p.relative_to(ROOT)).replace("\\","/")

# Собираем все страницы
files = [ROOT/"index.html"] if (ROOT/"index.html").exists() else []
files += sorted(ART.glob("*.html"))

# Сортировка по дате коммита (новые первыми)
items = []
for f in files:
    dt = git_date(f)
    title, desc = extract_title_meta(f)
    items.append({
        "path": f, "url": SITE + rel_url(f),
        "rel": rel_url(f), "title": title, "desc": desc, "dt": dt
    })
items.sort(key=lambda x: x["dt"], reverse=True)

# ---------- RSS ----------
rss_max = 60
rss_items = []
for it in items[:rss_max]:
    if it["rel"] == "/":  # главную не включаем в RSS
        continue
    pub = format_datetime(it["dt"])
    rss_items.append(
f'''    <item>
      <title>{it["title"]}</title>
      <link>{SITE}{it["rel"]}</link>
      <guid>{SITE}{it["rel"]}</guid>
      <pubDate>{pub}</pubDate>
      <description>{it["desc"]}</description>
    </item>''')

rss = f'''<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>VPNhub-Cyber — Свежие статьи</title>
    <link>{SITE}/</link>
    <description>Свежие SEO-статьи и инструкции по VPN: гайды, лайфхаки, YouTube без блокировок, настройка для всех устройств.</description>
    <language>ru</language>
    <lastBuildDate>{format_datetime(datetime.now(timezone.utc))}</lastBuildDate>
    <generator>vpnhub-cyber autobuilder</generator>
{os.linesep.join(rss_items)}
  </channel>
</rss>
'''
(ROOT/"rss.xml").write_text(rss, encoding="utf-8")

# ---------- SITEMAP ----------
def url_row(loc, lastmod, pr="0.8", cf="weekly"):
    return f'  <url><loc>{loc}</loc><lastmod>{lastmod}</lastmod><changefreq>{cf}</changefreq><priority>{pr}</priority></url>'

smap = ['<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
# главная
home_last = format_datetime(items[0]["dt"])
smap.append(url_row(f"{SITE}/", home_last, "1.0", "daily"))
# статьи
for it in items:
    if it["rel"] == "/": continue
    smap.append(url_row(it["url"], format_datetime(it["dt"])))
smap.append("</urlset>")
(ROOT/"sitemap.xml").write_text("\n".join(smap), encoding="utf-8")

# ---------- ALL ARTICLES PAGE ----------
STYLE = '''
<style>
body{background: radial-gradient(ellipse at bottom,#1b2735 0%,#090a0f 100%);color:#e0e6ff;font-family:Montserrat,Arial,sans-serif;margin:0}
main{max-width:860px;margin:0 auto;background:rgba(31,44,75,.93);border-radius:1.6rem;box-shadow:0 4px 36px #243768aa;padding:1.6em 1em}
h1{font-family:"Russo One",Arial,sans-serif;color:#a0c7ff;text-align:center;margin:22px 0}
.section{margin:1.2em 0}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:10px}
.card{background:rgba(25,28,48,.93);border-radius:14px;padding:10px 12px}
.card a{color:#6abfff;text-decoration:none;font-weight:700}
.search{margin:10px auto 18px auto;max-width:680px}
.search input{width:100%;border-radius:12px;border:1px solid #354a7c;background:#0e1425;color:#e0e6ff;padding:10px 12px}
</style>
'''
def render_list(title, subset):
    cards=[]
    for it in subset:
        if it["rel"]=="/": continue
        cards.append(f'<div class="card"><a href="{it["rel"]}">{it["title"]}</a></div>')
    return f'<div class="section"><h2>{title}</h2><div class="grid">{"".join(cards)}</div></div>'

# Поиск
search_box = '<div class="search"><input id="q" placeholder="Поиск по названию..."></div>'

html_all = f'''<!DOCTYPE html><html lang="ru"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Все статьи — VPNhub-Cyber</title>
<meta name="description" content="Все статьи VPNhub-Cyber: гайды, инструкции и решения. Автообновляется.">
<link href="https://fonts.googleapis.com/css2?family=Russo+One&family=Montserrat:wght@400;700&display=swap" rel="stylesheet">
{STYLE}
</head><body><main>
<h1>Все статьи</h1>
{search_box}
<div id="list" class="grid">
{"".join(f'<div class="card"><a href="{it["rel"]}">{it["title"]}</a></div>' for it in items if it["rel"]!="/")}
</div>
<a href="/index.html" style="display:inline-block;margin:18px 0;color:#a7f2ff">← На главную</a>
</main>
<script>
const q=document.getElementById('q'), list=document.getElementById('list');
q&&q.addEventListener('input',()=>{
  const val=q.value.toLowerCase();
  list.querySelectorAll('.card').forEach(c=>{
    const t=c.textContent.toLowerCase();
    c.style.display = t.includes(val) ? '' : 'none';
  });
});
</script>
</body></html>'''
(ROOT/"all-articles.html").write_text(html_all, encoding="utf-8")

# ---------- Year page: /articles/2025.html ----------
y2025 = [it for it in items if it["rel"].startswith("/articles/") and "/2025" in it["rel"] or "-2025" in it["rel"]]
html_2025 = f'''<!DOCTYPE html><html lang="ru"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Статьи 2025 года — VPNhub-Cyber</title>
<meta name="description" content="Все публикации 2025 года на VPNhub-Cyber. Автоматический список.">
<link href="https://fonts.googleapis.com/css2?family=Russo+One&family=Montserrat:wght@400;700&display=swap" rel="stylesheet">
{STYLE}
</head><body><main>
<h1>Статьи 2025 года</h1>
{render_list("2025", y2025)}
<a href="/all-articles.html" style="display:inline-block;margin:18px 0;color:#a7f2ff">← Ко всем статьям</a>
</main></body></html>'''
(ART/"2025.html").write_text(html_2025, encoding="utf-8")
print("rss.xml, sitemap.xml, all-articles.html и articles/2025.html — обновлены.")
