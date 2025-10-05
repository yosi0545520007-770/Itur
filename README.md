# Itur — גאוקודינג לכתובות (CLI + Web)

מערכת קטנה להמרת כתובות לנקודות ציון (lat/lon), עם ממשק וובי נקי ו-CLI.

## התחלה מהירה (Windows PowerShell)

```powershell
# יצירת סביבת פיתוח והתקנות
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"

# או עם סקריפט עזר
./scripts/setup.ps1
```

## ממשק וובי

```powershell
./scripts/serve.ps1     # מריץ שרת בפורט 8000
```

פתח דפדפן אל: http://127.0.0.1:8000

- העלה קובץ CSV
- בחר מפריד (או זיהוי אוטומטי)
- ציין שם עמודת הכתובת (אם יש כותרת)
- קבל טבלת תצוגה מקדימה וכפתור הורדת CSV

## CLI (אופציונלי)

```powershell
python -m itur geocode --in input.csv --out output.csv --col address --sep ","
```

## בדיקות

```powershell
./scripts/test.ps1
```

## מבנה

- `src/itur/webapp.py` — אפליקציית FastAPI
- `src/itur/geocode.py` — לוגיקת גאוקודינג ו-CSV
- `src/itur/templates/` — תבניות HTML (Jinja2)
- `src/itur/static/` — קבצי עיצוב
- `scripts/` — סקריפטים (setup, serve)

הערות: השירות Nominatim (OpenStreetMap) מוגבל בקצב. לשימוש כבד שקול ספק עם מפתח API.
