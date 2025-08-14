#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import csv
import time
import subprocess
from datetime import datetime
from pathlib import Path

from unidecode import unidecode
from slugify import slugify
from openai import OpenAI

# ==== Настройки ====
CSV_PATH = Path("content/keywords.csv")
OUT_DIR = Path(".")              # корень сайта (страницы как earlier: slug.html)
MARK_DIR = Path(".autogen")      # метки "сделано", чтобы безопасно перезапускать
SITEMAP_PATH = Path("sitemap.xml")  # если у тебя своя сборка — можно отключить обновление
PAUSE_SECONDS = 60               # пауза между публикациями
MIN_WORDS = 900                  # целевой объём (примерно)
# ====================

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "").strip()
MODEL_ID = (os.environ.get("MODEL_ID") or os.environ.get("FALLBACK_MODEL_ID") or "gpt-4.1-mini").strip()

if not OPENAI_API_KEY:
    raise SystemExit("OPENAI_API_KEY is empty (add it in repo Settings → Secrets → Actions).")

client = OpenAI(api_key=OPENAI_API_KEY)

MARK_DIR.mkdir(exist_ok=True)
OUT_DIR.mkdir(exist_ok=True, parents=True)

def norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())

def make_slug(base: str) -> str:
    base = base or ""
    # сначала unidecode для корректного транслита, затем slugify
    ascii_title = unidecode(base)
    s = slugify(ascii_title, lowercase=True, max_length=120)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s or datetime.utcnow().strftime("page-%Y%m%d-%H%M%S")

def html_template(title: str, description: str, body_html: str) -> str:
    now_iso = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <title>{title}</title>
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="description" content="{description}">
  <link rel="canonical" href="https://{os.environ.get('GITHUB_REPOSITORY', 'example.com').split('/')[-1]}.github.io/{''}">
  <meta property="og:type" content="article">
  <meta property="og:title" content="{title}">
  <meta property="og:description" content="{description}">
  <meta property="og:site_name" content="VPNHub">
  <meta property="article:modified_time" content="{now_iso}">
</head>
<body>
<main class="container">
  <h1>{title}</h1>
  {body_html}
</main>
</body>
</html>
"""

def ask_llm(keyword: str, h1: str, primary_key: str) -> str:
    """
    Возвращает HTML фрагмент <p>...</p><h2>...</h2>... (без <html> оболочки).
    """
    pk = primary_key or ""
    # не дублируем, если совпадает по смыслу
    use_primary = pk and norm(pk) not in {norm(keyword), norm(h1)}

    system_prompt = (
        "Ты — технический редактор. Пиши подробные статьи на русском, структурируй подзаголовками, списками, "
        "без воды, с практическими шагами. Не добавляй ничего об авторстве и отказах от ответственности."
    )
    user_prompt = f"""
Тема: «{h1 or keyword}».

Задача:
- Дай чёткое вступление (3–4 предложения). {(f'Во вступлении однажды употреби фразу: “{pk}”.' if use_primary else 'Не добавляй специальные ключевые фразы во вступление.')}
- Дай план и раскрой блоками с подзаголовками h2/h3: как это работает, пошаговые инструкции, чек-листы, частые ошибки, FAQ.
- Упоминай VPN-провайдеры без реф-ссылок и без явной рекламы.
- Тон: нейтральный, полезный, без воды.
- Объём не меньше {MIN_WORDS} слов.
- Верни только HTML фрагмент для <body> (т.е. <p>, <h2>, <ul>, <code> и т.п.), без <html>/<head>.
"""
    resp = client.chat.completions.create(
        model=MODEL_ID,
        temperature=0.5,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
    )
    content = resp.choices[0].message.content.strip()
    # На всякий — удалим случайные <html>, если модель вдруг добавит
    content = re.sub(r"</?(html|head|body)[^>]*>", "", content, flags=re.I)
    return content

def update_sitemap(slug: str):
    """
    Простейший апдейт: если есть sitemap.xml — дописываем URL, если его ещё нет в файле.
    Если у тебя есть свой сборщик карты — можно отключить.
    """
    if not SITEMAP_PATH.exists():
        return
    url = f"https://{os.environ.get('GITHUB_REPOSITORY', '').split('/')[-1]}.github.io/{slug}.html"
    txt = SITEMAP_PATH.read_text(encoding="utf-8", errors="ignore")
    if url in txt:
        return
    # грубо: вставим перед </urlset>
    lastmod = datetime.utcnow().strftime("%Y-%m-%d")
    entry = f"\n  <url>\n    <loc>{url}</loc>\n    <lastmod>{lastmod}</lastmod>\n  </url>\n"
    txt = re.sub(r"</urlset>\s*$", entry + "</urlset>", txt, flags=re.S)
    SITEMAP_PATH.write_text(txt, encoding="utf-8")

def git(*args):
    subprocess.run(["git", *args], check=True)

def commit_and_push(message: str, paths=None):
    if paths:
        if isinstance(paths, (list, tuple, set)):
            for p in paths:
                git("add", str(p))
        else:
            git("add", str(paths))
    else:
        git("add", "-A")
    # настроим кто коммитит
    git("config", "user.name", "github-actions[bot]")
    git("config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")
    # rebase pull (мягкая синхронизация)
    try:
        git("pull", "--rebase", "origin", os.environ.get("GITHUB_REF_NAME", "main"))
    except subprocess.CalledProcessError:
        # если кто-то только что пушнул – попробуем продолжить
        pass
    # коммитим, если есть изменения
    res = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True)
    if res.stdout.strip():
        git("commit", "-m", message)
        git("push", "origin", os.environ.get("GITHUB_REF_NAME", "main"))

def process_row(row: dict) -> bool:
    """
    Обрабатывает одну строку CSV. Возвращает True, если страница была создана/обновлена.
    """
    publish = (row.get("publish") or "").strip().lower() in {"yes", "y", "1", "true"}
    if not publish:
        return False

    keyword = (row.get("keyword") or "").strip()
    h1 = (row.get("h1") or "").strip() or keyword
    primary_key = (row.get("primary_key") or "").strip()
    slug = (row.get("slug") or "").strip() or make_slug(keyword or h1)
    force = (row.get("force") or "").strip().lower() in {"yes", "y", "1", "true"}

    mark_file = MARK_DIR / f"{slug}.done"
    html_path = OUT_DIR / f"{slug}.html"

    # idempotency: если уже сделали и не force — пропускаем
    if mark_file.exists() and not force and html_path.exists():
        return False

    # если файл существует и force==False — пропускаем, чтобы не перетирать вручную правленые страницы
    if html_path.exists() and not force and not mark_file.exists():
        return False

    # генерим контент
    body_html = ask_llm(keyword, h1, primary_key)

    # description: первая строка без HTML
    plain_intro = re.sub(r"<[^>]+>", " ", body_html)
    plain_intro = re.sub(r"\s+", " ", plain_intro).strip()
    description = plain_intro[:160]

    full_html = html_template(h1, description, body_html)
    html_path.write_text(full_html, encoding="utf-8")

    # простое обновление карты сайта (если есть)
    update_sitemap(slug)

    # ставим метку «сделано» (для безопасных перезапусков)
    mark_file.write_text(datetime.utcnow().isoformat(), encoding="utf-8")

    # коммитим только изменённое
    commit_and_push(f"autogen: {slug}", paths=[html_path, mark_file, SITEMAP_PATH if SITEMAP_PATH.exists() else None])

    return True

def iterate_csv_rows():
    with CSV_PATH.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    # идём по порядку, но публикуем по одной за запуск скрипта
    published = 0
    for i, row in enumerate(rows, 1):
        did = process_row(row)
        if did:
            published += 1
            print(f"[{i}/{len(rows)}] ✓ опубликовано: {row.get('keyword') or row.get('h1')}")
            # пауза перед следующей публикацией
            time.sleep(PAUSE_SECONDS)
        else:
            print(f"[{i}/{len(rows)}] – пропуск")

    if published == 0:
        print("Новых страниц нет (всё уже сделано или publish != yes).")

if __name__ == "__main__":
    iterate_csv_rows()
