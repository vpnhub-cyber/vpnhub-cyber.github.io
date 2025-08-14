#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Генератор статей из /content/keywords.csv.
Для каждого ключа создаёт /articles/<slug>.html по нашему шаблону
с метрикой, OG, JSON-LD и маркерами дат <!--DAILY_*-->.
Контент пишет LLM через OpenAI API.
"""

from __future__ import annotations
import csv, html, os, re
from pathlib import Path
from datetime import datetime, timezone
import base64
import sys

# --- Настройки
REPO_ROOT = Path(__file__).resolve().parents[1]
CONTENT_CSV = REPO_ROOT / "content" / "keywords.csv"
ART_DIR     = REPO_ROOT / "articles"

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
MODEL_ID = os.getenv("MODEL_ID", "gpt-4o-mini")  # поменяй при желании

if not OPENAI_API_KEY:
    print("!! OPENAI_API_KEY не задан (Secrets → Actions).", file=sys.stderr)
    sys.exit(1)

# --- Простой транслит для slug
_sub = {
    "а":"a","б":"b","в":"v","г":"g","д":"d","е":"e","ё":"e","ж":"zh","з":"z","и":"i","й":"y",
    "к":"k","л":"l","м":"m","н":"n","о":"o","п":"p","р":"r","с":"s","т":"t","у":"u","ф":"f",
    "х":"h","ц":"c","ч":"ch","ш":"sh","щ":"sch","ъ":"","ы":"y","ь":"","э":"e","ю":"yu","я":"ya",
}
def slugify(s: str) -> str:
    s = s.strip().lower()
    out = []
    for ch in s:
        if "a"<=ch<="z" or "0"<=ch<="9":
            out.append(ch)
        elif ch in " _-–—.":
            out.append("-")
        else:
            out.append(_sub.get(ch, ""))
    slug = re.sub("-{2,}","-", "".join(out)).strip("-")
    return slug or "page"

# --- LLM (через OpenAI API совместимый клиент)
import json, urllib.request

def openai_chat(messages, model=MODEL_ID, max_tokens=2000):
    url = "https://api.openai.com/v1/chat/completions"
    req = urllib.request.Request(url,
        headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        },
        data=json.dumps({
            "model": model,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": max_tokens,
        }).encode("utf-8")
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        j = json.loads(r.read().decode("utf-8"))
    return j["choices"][0]["message"]["content"]

STRUCTURE_PROMPT = """
Ты пишешь продающую SEO-статью на русском для обычных людей. Строго придерживайся структуры и чек-листа:

1) Введение 120–150 слов: включи фразу «{primary_key}» в первом абзаце, добавь кратко: в России РКН ограничивает сервисы, VPN помогает.
2) Рекламный блок (50–70 слов) с призывом и 2 кнопками: SAFENET и Норм VPN.
3) «Почему это происходит» (150–180 слов): просто и без жаргона.
4) Короткий план (4–5 пунктов).
5) Подробно «Х способов…» (7–9 способов; каждый 120–180 слов, с плюсами/минусами и шагами).
6) Предупреждения (100–150 слов) — бесплатные прокси/«ускорители» опасны.
7) Итог с CTA (120–150 слов).
8) FAQ: 6–8 вопросов, ответы по 50–80 слов. Обязательно упоминай проверку шифрования и ссылку на статью про утечки: /articles/how-to-check-vpn-leaks.html

Запреты: не используй пафос, жаргон, «на стероидах», «как твой бывший», не больше 2 метафор и не более 2 «не X, а Y».
Верни ТОЛЬКО внутренний HTML-контент для <main> (без <html>/<head>/<body>). Ссылки на кнопки:
- https://t.me/SafeNetVpn_bot?start=afrrica
- https://t.me/normwpn_bot?start=referral_228691787
Тема: {keyword}
H1: {h1}
"""

PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{title} (<!--DAILY_DMY-->{dmy}<!--/DAILY_DMY-->)</title>
  <meta name="description" content="{desc}">
  <link rel="canonical" href="https://vpnhub-cyber.github.io/articles/{slug}.html">
  <link rel="icon" href="/favicon.png" type="image/png">

  <meta property="og:type" content="article">
  <meta property="og:title" content="{title} (<!--DAILY_DMY-->{dmy}<!--/DAILY_DMY-->)">
  <meta property="og:description" content="{desc}">
  <meta property="og:url" content="https://vpnhub-cyber.github.io/articles/{slug}.html">
  <meta property="og:image" content="https://vpnhub-cyber.github.io/og-image.png">
  <meta property="article:modified_time" content="<!--DAILY_ISO-->{iso}<!--/DAILY_ISO-->">
  <meta name="twitter:card" content="summary_large_image">

  <link href="https://fonts.googleapis.com/css2?family=Russo+One&family=Montserrat:wght@400;600;700&display=swap" rel="stylesheet">
  <style>
    :root{{--card:#121836;--b:#2f3f7a;--t:#e6edff}}
    body{{margin:0;background:radial-gradient(ellipse at bottom,#1b2735 0%,#090a0f 100%);color:var(--t);font-family:'Montserrat',Arial,sans-serif}}
    a{{color:#7fc8ff}} header,main,footer{{max-width:880px;margin:0 auto;padding:16px}}
    h1{{font-family:'Russo One',Arial,sans-serif;color:#a0c7ff}}
    .meta{{color:#9fb7ff}}
    .card{{background:rgba(18,24,54,.92);border:1px solid var(--b);border-radius:16px;padding:14px;margin:14px 0}}
  </style>

  <!-- Yandex.Metrika -->
  <script type="text/javascript">
    (function(m,e,t,r,i,k,a){{m[i]=m[i]||function(){{(m[i].a=m[i].a||[]).push(arguments)}};m[i].l=1*new Date();
      for (var j=0;j<document.scripts.length;j++){{if (document.scripts[j].src===r){{return;}}}}
      k=e.createElement(t),a=e.getElementsByTagName(t)[0],k.async=1,k.src=r,a.parentNode.insertBefore(k,a)}})
      (window, document,'script','https://mc.yandex.ru/metrika/tag.js?id=103602117', 'ym');
    ym(103602117, 'init', {{ssr:true, webvisor:true, clickmap:true, ecommerce:"dataLayer", accurateTrackBounce:true, trackLinks:true}});
  </script>
  <noscript><div><img src="https://mc.yandex.ru/watch/103602117" style="position:absolute;left:-9999px;" alt=""></div></noscript>
</head>
<body>
  <header>
    <nav class="meta"><a href="/">🏠 На главную</a> · <a href="/all-articles.html">Все статьи</a></nav>
    <h1>{h1} (<!--DAILY_DMY-->{dmy}<!--/DAILY_DMY-->)</h1>
    <div class="meta">Обновлено: <!--DAILY_DMY-->{dmy}<!--/DAILY_DMY--></div>
  </header>

  <main>
{body}
    <section class="card">
      <h2>Полезные материалы</h2>
      <ul>
        <li><a href="/articles/vpn-bypass-blocks-2025.html">Обход блокировок и DPI</a></li>
        <li><a href="/articles/vpn-for-smartphone-2025.html">VPN для смартфона</a></li>
        <li><a href="/articles/vpn-slow-speed-fix.html">Медленный интернет с VPN — как ускорить</a></li>
        <li><a href="/articles/how-to-check-vpn-leaks.html">Проверка утечек IP/DNS/WebRTC</a></li>
      </ul>
    </section>
    <div class="card">Теги: {tags} · сегодня <!--DAILY_DMY-->{dmy}<!--/DAILY_DMY--></div>
  </main>

  <footer>
    <div class="meta">© 2025 VPNhub-Cyber · Связь: <a href="mailto:admin@vpnhub-cyber.ru">admin@vpnhub-cyber.ru</a></div>
  </footer>
</body>
</html>
"""

def render_page(keyword: str, h1: str, primary_key: str, slug: str, tags: str) -> str:
    dmy = datetime.now().strftime("%d.%m.%Y")
    iso = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z")
    title = h1 or keyword
    desc = f"{keyword}: простой план на сегодня — сеть, DNS, VPN (скрытый режим), кэш и быстрые настройки."
    # запросим у LLM только тело <main>
    prompt = STRUCTURE_PROMPT.format(keyword=keyword, h1=h1 or keyword, primary_key=primary_key or keyword)
    body = openai_chat([
        {"role":"system","content":"Ты практичный техредактор. Пишешь ясно и по делу."},
        {"role":"user","content":prompt}
    ], model=MODEL_ID, max_tokens=3000)

    return PAGE_TEMPLATE.format(
        title=html.escape(title),
        desc=html.escape(desc),
        h1=html.escape(h1 or title),
        slug=slug,
        dmy=dmy,
        iso=iso,
        body=body,
        tags=html.escape(tags or keyword)
    )

def main():
    ART_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONTENT_CSV, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    changed = 0
    for r in rows:
        if not (r.get("publish","").lower().startswith("y")):
            continue
        kw  = (r.get("keyword") or "").strip()
        if not kw: 
            continue
        h1  = (r.get("h1") or kw).strip()
        pk  = (r.get("primary_key") or kw).strip()
        slug = (r.get("slug") or slugify(kw)).strip()
        force = r.get("force","").lower().startswith("y")
        tags = (r.get("tags") or kw).strip()

        out = ART_DIR / f"{slug}.html"
        if out.exists() and not force:
            print(f"skip exists: {out.name}")
            continue

        html_page = render_page(kw, h1, pk, slug, tags)
        out.write_text(html_page, encoding="utf-8")
        print("written:", out.name)
        changed += 1

    print(f"Generated/updated: {changed} file(s).")

if __name__ == "__main__":
    main()
