#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Автоген страниц из CSV (по одной за цикл) с мгновенной публикацией.

Ожидаемый CSV: content/keywords.csv в UTF-8 без BOM
Колонки (порядок важен):
  0 enabled         - "yes" чтобы брать в работу, иначе пропуск
  1 keyword         - ключевая фраза (для текста/семантики)
  2 title           - <title> и H1
  3 slug            - имя файла без .html (уникально!)
  4 done            - "0" или "1" (будет проставлено "1" после публикации)
  5 description     - (необязательно) meta description; если пусто — сгенерируем

Скрипт:
- Создаёт /articles, рендерит HTML по шаблону «в стиле сайта».
- Вставляет ТОЛЬКО одну кнопку SAFENET (в начале и в конце статьи).
- После записи файла: коммитит и пушит сразу (по одной странице).
- Обновляет CSV (done=1) и коммитит это изменение.
- Пауза 60 секунд и берём следующую строку.
"""

import csv
import os
import re
import sys
import time
import subprocess
from pathlib import Path
from datetime import datetime

REPO_ROOT = Path(__file__).resolve().parents[1]
CSV_PATH   = REPO_ROOT / "content" / "keywords.csv"
OUT_DIR    = REPO_ROOT / "articles"
DONE_MARK  = "1"
PAUSE_SEC  = 60

YANDEX_METRIKA_ID = "103602117"

SAFENET_BTN_HTML = (
    '<a class="vpn-btn" href="https://t.me/SafeNetVpn_bot?start=afrrica" '
    'target="_blank" rel="nofollow noopener sponsored">'
    'SAFENET: стабильный YouTube 1080p/4K — 3 дня теста и −15% на 1-ю оплату'
    '</a>'
)

def run(cmd, cwd=REPO_ROOT):
    """Run a shell command, raise on error, return output."""
    print("+", " ".join(cmd))
    out = subprocess.check_output(cmd, cwd=str(cwd))
    return out.decode("utf-8", "ignore")

def ensure_git_identity():
    """Set bot identity if not set (safe default for Actions)."""
    try:
        run(["git", "config", "--global", "user.name"])
    except subprocess.CalledProcessError:
        run(["git", "config", "user.name", "github-actions[bot]"])
        run(["git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com"])

def sanitize_slug(s: str) -> str:
    s = s.strip().lower()
    s = s.replace(" ", "-")
    s = re.sub(r"[^a-z0-9\-]+", "-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s or "page"

def generate_description(keyword: str, title: str) -> str:
    base = f"{title}. Подробный гид: что это, как работает и пошаговые инструкции. Ключевое: {keyword}."
    return base[:155]

def render_html(title: str, description: str, h1: str) -> str:
    today = datetime.utcnow().strftime("%d.%m.%Y")
    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{title}</title>
  <meta name="description" content="{description}">
  <link href="https://fonts.googleapis.com/css2?family=Russo+One&family=Montserrat:wght@400;700&display=swap" rel="stylesheet">
  <!-- Yandex.Metrika counter -->
  <script type="text/javascript">
    (function(m,e,t,r,i,k,a){{
        m[i]=m[i]||function(){{(m[i].a=m[i].a||[]).push(arguments)}}
        m[i].l=1*new Date();
        for (var j = 0; j < document.scripts.length; j++) {{if (document.scripts[j].src === r) {{ return; }}}}
        k=e.createElement(t),a=e.getElementsByTagName(t)[0],k.async=1,k.src=r,a.parentNode.insertBefore(k,a)
    }})(window, document,'script','https://mc.yandex.ru/metrika/tag.js?id={YANDEX_METRIKA_ID}', 'ym');
    ym({YANDEX_METRIKA_ID}, 'init', {{ssr:true, webvisor:true, clickmap:true, ecommerce:"dataLayer", accurateTrackBounce:true, trackLinks:true}});
  </script>
  <noscript><div><img src="https://mc.yandex.ru/watch/{YANDEX_METRIKA_ID}" style="position:absolute; left:-9999px;" alt=""></div></noscript>
  <!-- /Yandex.Metrika counter -->
  <style>
    :root{{
      --bg-main:#1b2735; --bg-deep:#090a0f; --panel: rgba(31, 44, 75, 0.93);
      --panel-soft: rgba(25, 28, 48, 0.93); --text:#e0e6ff; --accent:#9ec5ff;
      --brand1:#4776e6; --brand2:#8e54e9; --h2-bg: rgba(255, 232, 128, 0.10);
      --h2-border: rgba(255, 232, 128, 0.35); --h2-color:#ffe08a;
      --h3-color:#cfe1ff;
    }}
    *{{box-sizing:border-box}}
    body {{background: radial-gradient(ellipse at bottom, var(--bg-main) 0%, var(--bg-deep) 100%); color: var(--text); font-family: 'Montserrat', Arial, sans-serif; margin: 0; min-height: 100vh; overflow-x: hidden;}}
    header {{ text-align: center; padding: 52px 18px 22px 18px; position: relative; z-index: 1;}}
    h1 {{ font-family: 'Russo One', Arial, sans-serif; font-size: 2.02rem; color: var(--accent); margin-bottom: 13px; letter-spacing: .6px; text-shadow: 0 0 9px #2f49ce, 0 0 14px #283593;}}
    .cosmo {{ font-size: 1.08rem; margin-bottom: 21px; color: #fffde4; text-shadow: 0 0 6px #232c47;}}
    main {{ max-width: 860px; margin: 0 auto; background: var(--panel); border-radius: 2rem; box-shadow: 0 4px 36px #243768aa; padding: 2em 1.3em 2.1em 1.3em; position: relative; z-index: 1;}}
    h2 {{
      font-family: 'Russo One', Arial, sans-serif; color: var(--h2-color); font-size: 1.18rem;
      letter-spacing: .4px; margin: 1.7em 0 .85em 0; padding: 10px 12px; background: var(--h2-bg);
      border-left: 4px solid var(--h2-border); border-radius: 12px; text-shadow: none;
      -webkit-font-smoothing: antialiased; text-rendering: optimizeLegibility;
    }}
    h3 {{ color: var(--h3-color); margin: 1.05em 0 .45em 0; font-size: 1.04rem; letter-spacing:.2px; text-shadow: none; -webkit-font-smoothing: antialiased; }}
    p {{ line-height: 1.62; }}
    ul, ol {{ margin: 1em 0 1em 1em; padding-left: 1.3em;}}
    li {{ margin-bottom: 0.65em;}}
    code, pre {{ background: rgba(0,0,0,0.25); padding: 2px 6px; border-radius: 6px; }}
    pre {{ overflow: auto; padding: 10px 12px; }}
    .vpn-buttons {{ margin: 1.3em 0 2.1em 0; display: flex; flex-direction: column; gap: 0.6em;}}
    .vpn-btn {{ display: inline-block; background: linear-gradient(90deg, var(--brand1) 15%, var(--brand2) 85%); color: #fff; font-weight: 700; padding: 11px 30px; border-radius: 1.2rem; font-size: 1.05rem; text-decoration: none; transition: background 0.19s, box-shadow 0.19s, transform 0.15s; box-shadow: 0 4px 18px #303f8e77; letter-spacing: 1px; text-align: center;}}
    .vpn-btn:hover {{ background: linear-gradient(90deg, var(--brand2) 10%, var(--brand1) 90%); box-shadow: 0 8px 32px #82e2fd88; color: #fff200; transform: scale(1.06);}}
    a {{ color: #6abfff; text-decoration: underline;}}
    .back-link {{ display: inline-block; margin-top: 2em; color: #a7f2ff; background: rgba(25,28,48,0.83); border-radius: 1.3em; padding: 10px 28px; text-decoration: none; font-size: 1.05em; transition: background .16s, color .14s;}}
    .back-link:hover {{ background: #36f6ff; color: #20244c;}}
    .topics-links {{ margin-top: 28px; background: var(--panel-soft); border-radius: 1.1em; padding: 1em 1.1em 1em 1.1em;}}
    .topics-links ul {{ margin: 0; padding-left: 1.2em;}}
    .topics-links li {{ margin-bottom: 0.5em;}}
    details {{ background: rgba(40,50,90,0.91); margin: 0.7em 0; padding: 0.8em 1em; border-radius: 1em;}}
    summary {{ color: var(--h2-color); font-weight: bold; font-size: 1.05em; cursor: pointer;}}
    details[open] summary {{ color: var(--accent);}}
    .note {{ background: rgba(255,255,255,0.07); border-left: 3px solid var(--h2-color); padding: 10px 12px; border-radius: 8px; margin: 12px 0;}}
    .warn {{ background: rgba(255, 87, 51, 0.12); border-left: 3px solid #ff8a65; padding: 10px 12px; border-radius: 8px; margin: 12px 0;}}
    footer {{ text-align: center; padding: 30px 10px 12px 10px; color: #475674; font-size: 0.97rem; letter-spacing: 0.2px; z-index: 2; position: relative;}}
    @media (max-width: 860px) {{ h1 {{ font-size: 1.26rem;}} main {{ padding: 1.1em 0.6em;}} }}
  </style>
</head>
<body>
  <header>
    <h1>{h1}</h1>
    <div class="cosmo">Актуально на {today}. Краткое руководство и ответы на частые вопросы.</div>
  </header>

  <main>
    <div class="vpn-buttons">
      {SAFENET_BTN_HTML}
    </div>

    <div class="note"><b>Как пользоваться материалом:</b> идите сверху вниз и проверяйте результат после каждого шага.</div>

    <h2>Что это даёт</h2>
    <p>На этой странице собраны понятные шаги и рекомендации по теме «{h1}». Здесь — быстрая диагностика, практические советы и ссылки на смежные руководства.</p>

    <h2>Быстрый чек-лист</h2>
    <ol>
      <li>Обновите приложения и перезапустите устройство/роутер.</li>
      <li>Проверьте настройки DNS/DoH/SmartDNS и режимы энергосбережения сети.</li>
      <li>При необходимости включите частичный VPN (split-tunnel) только для нужных сервисов.</li>
    </ol>

    <h2>Подробности</h2>
    <p>Используйте современные протоколы, избегайте сомнительных расширений и «рандом-прокси». Для Smart TV — лучше 5 ГГц или Ethernet, а на роутере — QoS/SQM.</p>

    <div class="topics-links">
      <b>Читайте также:</b>
      <ul>
        <li><a href="/articles/">Все статьи раздела</a></li>
      </ul>
    </div>

    <div class="vpn-buttons">
      {SAFENET_BTN_HTML}
    </div>

    <a class="back-link" href="../index.html">На главную</a>
  </main>

  <footer>
    © 2025 VPNhub-Cyber
  </footer>
</body>
</html>
"""

def commit_and_push(message: str, paths):
    if isinstance(paths, (str, Path)):
        paths = [paths]
    paths = [str(p) for p in paths]
    run(["git", "add"] + paths)
    # rebase-pull (мягкая защита от конфликтов в Actions)
    try:
        run(["git", "pull", "--rebase", "origin", os.environ.get("GITHUB_REF_NAME", "main")])
    except subprocess.CalledProcessError:
        # если не удалось — продолжаем, это не критично для пустых изменений
        pass
    run(["git", "commit", "-m", message])
    run(["git", "push", "origin", os.environ.get("GITHUB_REF_NAME", "main")])

def load_rows():
    with open(CSV_PATH, "r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        rows = [row for row in reader]
    return rows

def save_rows(rows):
    with open(CSV_PATH, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(rows)

def main():
    ensure_git_identity()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    rows = load_rows()
    if not rows:
        print("CSV пустой.")
        return

    # Индексы колонок
    IDX_ENABLED = 0
    IDX_KEYWORD = 1
    IDX_TITLE   = 2
    IDX_SLUG    = 3
    IDX_DONE    = 4
    IDX_DESC    = 5 if len(rows[0]) > 5 else None

    # защита от дублей slug внутри CSV
    seen_slugs = set()

    processed_any = False

    for i, row in enumerate(rows):
        # пропустим пустые
        if not row or all(not c.strip() for c in row):
            continue

        # расширяем до нужной длины
        while len(row) <= 5:
            row.append("")

        enabled   = (row[IDX_ENABLED] or "").strip().lower()
        keyword   = (row[IDX_KEYWORD] or "").strip()
        title     = (row[IDX_TITLE] or "").strip() or keyword or "Новая статья"
        slug_raw  = (row[IDX_SLUG] or "").strip()
        done      = (row[IDX_DONE] or "").strip()
        desc      = (row[IDX_DESC] or "").strip() if IDX_DESC is not None else ""

        slug = sanitize_slug(slug_raw or title)
        row[IDX_SLUG] = slug  # нормализуем

        # дубли slug в одном CSV
        if slug in seen_slugs:
            print(f"Дубликат slug в CSV: {slug} — пропуск.")
            continue
        seen_slugs.add(slug)

        # условия пропуска
        if enabled != "yes":
            print(f"[{slug}] disabled — пропуск.")
            continue
        if done == DONE_MARK:
            print(f"[{slug}] уже done — пропуск.")
            continue

        # Если файл уже существует — считаем сделанным и отметим done
        out_path = OUT_DIR / f"{slug}.html"
        if out_path.exists():
            print(f"[{slug}] файл уже существует — отмечаю done=1.")
            rows[i][IDX_DONE] = DONE_MARK
            save_rows(rows)
            commit_and_push(f"mark done for existing article: {slug}", [CSV_PATH])
            continue

        # Сборка описания
        meta_description = desc or generate_description(keyword, title)

        # Рендер
        html = render_html(title=title, description=meta_description, h1=title)
        out_path.write_text(html, encoding="utf-8")
        print(f"[{slug}] создано: {out_path.relative_to(REPO_ROOT)}")

        # Коммитим страницу
        commit_and_push(f"add article: {slug}", [out_path])

        # Помечаем done=1 и коммитим CSV
        rows[i][IDX_DONE] = DONE_MARK
        save_rows(rows)
        commit_and_push(f"mark done: {slug}", [CSV_PATH])

        processed_any = True

        # Пауза перед следующей
        print(f"[{slug}] опубликовано. Пауза {PAUSE_SEC} сек...")
        time.sleep(PAUSE_SEC)

    if not processed_any:
        print("Нет задач для обработки (всё done или отключено).")

if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as e:
        sys.stderr.write(e.output.decode("utf-8", "ignore") if hasattr(e, "output") else str(e))
        sys.exit(e.returncode)

