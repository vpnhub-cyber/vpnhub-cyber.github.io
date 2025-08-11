from datetime import datetime
from zoneinfo import ZoneInfo
import re
from pathlib import Path
import json

# --- настройки ---
TZ = ZoneInfo("Europe/Moscow")

# Можно ограничить обновление только списком файлов (опционально):
MANIFEST = Path("tools/daily-pages.json")
use_manifest = MANIFEST.exists()

if use_manifest:
    pages = json.loads(MANIFEST.read_text(encoding="utf-8")).get("pages", [])
    files = [Path(p) for p in pages if Path(p).suffix == ".html" and Path(p).exists()]
else:
    # По умолчанию обновляем ВСЕ .html, кроме архивов/вендор-папок
    excludes = {"node_modules", ".git", "daily-archive", "tools", ".github"}
    files = [p for p in Path(".").rglob("*.html") if all(x not in p.parts for x in excludes)]

now = datetime.now(TZ)
today_dmy = now.strftime("%d.%m.%Y")
today_iso = now.strftime("%Y-%m-%dT%H:%M:%S+03:00")
today_long = now.strftime("%d %B %Y")  # “12 August 2025”; для рус. месяцев ниже маппинг

# русские месяцы
months_ru = {
    "January":"января","February":"февраля","March":"марта","April":"апреля","May":"мая",
    "June":"июня","July":"июля","August":"августа","September":"сентября",
    "October":"октября","November":"ноября","December":"декабря"
}
for en, ru in months_ru.items():
    today_long = today_long.replace(en, ru)

def replace_between(mark, text, value):
    # заменяет содержимое между <!--MARK-->...<!--/MARK--> на value
    pattern = re.compile(rf"(<!--{mark}-->)(.*?)(<!--/{mark}-->)", re.DOTALL)
    return pattern.sub(rf"\1{value}\3", text)

changed = 0
for f in files:
    s = f.read_text(encoding="utf-8")
    orig = s
    s = replace_between("DAILY_DMY", s, today_dmy)
    s = replace_between("DAILY_ISO", s, today_iso)
    s = replace_between("DAILY_LONG_RU", s, today_long)
    if s != orig:
        f.write_text(s, encoding="utf-8")
        changed += 1

print(f"Updated {changed} file(s) to {today_dmy} / {today_iso}")
