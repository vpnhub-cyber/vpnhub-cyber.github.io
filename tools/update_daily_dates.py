#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Обновляет в HTML-макетах маркеры дат:
  <!--DAILY_DMY-->11.08.2025<!--/DAILY_DMY-->
  <!--DAILY_ISO-->2025-08-11T13:00:00+03:00<!--/DAILY_ISO-->

Правила:
- Обрабатываются только файлы *.html, где реально встречаются маркеры.
- Можно заморозить файл (пропустить), добавив в него <!--DAILY_FREEZE-->
- Таймзона берётся из переменной окружения DAILY_TZ (по умолчанию Europe/Moscow)
"""

from __future__ import annotations
import os
import re
from pathlib import Path
from datetime import datetime
try:
    from zoneinfo import ZoneInfo  # Py3.9+
except Exception:
    ZoneInfo = None

RE_DMY = re.compile(r"<!--DAILY_DMY-->(.*?)<!--/DAILY_DMY-->", re.DOTALL | re.IGNORECASE)
RE_ISO = re.compile(r"<!--DAILY_ISO-->(.*?)<!--/DAILY_ISO-->", re.DOTALL | re.IGNORECASE)

ROOT = Path(__file__).resolve().parents[1]  # repo root (.. от tools/)
TZ_NAME = os.getenv("DAILY_TZ", "Europe/Moscow")

def now_dt():
    if ZoneInfo:
        return datetime.now(ZoneInfo(TZ_NAME))
    # Фоллбек: без zoneinfo пишем ISO без смещения (не критично)
    return datetime.now()

def update_text(txt: str, dmy: str, iso: str) -> str | None:
    if "<!--DAILY_FREEZE-->" in txt:
        return None
    changed = False
    if "DAILY_DMY" in txt:
        new = RE_DMY.sub(f"<!--DAILY_DMY-->{dmy}<!--/DAILY_DMY-->", txt)
        changed |= (new != txt)
        txt = new
    if "DAILY_ISO" in txt:
        new = RE_ISO.sub(f"<!--DAILY_ISO-->{iso}<!--/DAILY_ISO-->", txt)
        changed |= (new != txt)
        txt = new
    return txt if changed else None

def main():
    dt = now_dt()
    dmy = dt.strftime("%d.%m.%Y")
    # ISO 8601 с часовым поясом (например 2025-08-11T06:10:00+03:00)
    if dt.tzinfo:
        iso = dt.isoformat(timespec="seconds")
    else:
        iso = dt.strftime("%Y-%m-%dT%H:%M:%S")

    changed_files = []

    for path in ROOT.rglob("*.html"):
        # Пропускаем системные/генерируемые файлы
        if path.name in {"all-articles.html"}:
            continue
        if any(p in path.parts for p in [".git",]):
            continue

        txt = path.read_text("utf-8", errors="ignore")
        if ("DAILY_DMY" not in txt) and ("DAILY_ISO" not in txt):
            continue  # нет маркеров — не трогаем

        new_txt = update_text(txt, dmy, iso)
        if new_txt is not None:
            path.write_text(new_txt, encoding="utf-8")
            changed_files.append(path.as_posix())

    if changed_files:
        print("Updated files:")
        for f in changed_files:
            print("  -", f)
    else:
        print("No files updated (no markers found or DAILY_FREEZE present).")

if __name__ == "__main__":
    main()
