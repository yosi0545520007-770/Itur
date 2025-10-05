from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, UploadFile, Request
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .geocode import geocode_addresses


BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="Itur Geocoder")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


def _sniff(sample: str) -> tuple[bool, str]:
    try:
        dialect = csv.Sniffer().sniff(sample)
        has_header = csv.Sniffer().has_header(sample)
        return has_header, dialect.delimiter
    except Exception:
        return False, ","


@app.post("/geocode")
async def geocode_route(
    request: Request,
    file: UploadFile = File(...),
    address_column: Optional[str] = Form(None),
    delimiter: str = Form(","),
):
    raw = await file.read()
    text = raw.decode("utf-8-sig", errors="replace")
    sample = text[:2048]

    has_header, sniff_delim = _sniff(sample)
    if delimiter == "auto":
        delimiter = sniff_delim

    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    header = next(reader, None) if has_header else None
    rows = list(reader) if header else list(csv.reader(io.StringIO(text), delimiter=delimiter))

    addr_index = 0
    if address_column and header:
        try:
            addr_index = list(header).index(address_column)
        except ValueError:
            addr_index = 0

    addresses = [row[addr_index] if row else "" for row in rows]
    results = geocode_addresses(addresses)

    # הכנת תצוגה מקדימה (עד 100 שורות)
    def _ddm(lat, lon):
        from .geocode import _deg_to_ddm as ddm, _deg_to_dms as dms
        def fmt(v, is_lat):
            return ddm(v, is_lat=is_lat) if v is not None else ""
        def fmt2(v, is_lat):
            return dms(v, is_lat=is_lat) if v is not None else ""
        return (
            fmt(lat, True), fmt(lon, False),
            fmt2(lat, True), fmt2(lon, False)
        )

    extra_cols = ["lat", "lon", "lat_ddm", "lon_ddm", "lat_dms", "lon_dms"]
    if header:
        preview_header = [*header, *extra_cols]
        preview_rows = []
        for row, r in zip(rows, results):
            lat, lon = r.lat, r.lon
            lat_ddm, lon_ddm, lat_dms, lon_dms = _ddm(lat, lon)
            preview_rows.append([*row, lat, lon, lat_ddm, lon_ddm, lat_dms, lon_dms])
        preview_rows = preview_rows[:100]
    else:
        preview_header = ["address", *extra_cols]
        preview_rows = []
        for r in results[:100]:
            lat, lon = r.lat, r.lon
            lat_ddm, lon_ddm, lat_dms, lon_dms = _ddm(lat, lon)
            preview_rows.append([r.address, lat, lon, lat_ddm, lon_ddm, lat_dms, lon_dms])

    return templates.TemplateResponse(
        "results.html",
        {
            "request": request,
            "header": preview_header,
            "rows": preview_rows,
            "count": len(results),
            "delimiter": delimiter,
            "address_column": address_column or "",
            "raw_text": text,
            "has_header": has_header,
        },
    )


@app.post("/download")
async def download_csv(
    raw_text: str = Form(...),
    delimiter: str = Form(","),
    address_column: str = Form(""),
    has_header: bool = Form(False),
):
    text = raw_text
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    header = next(reader, None) if has_header else None
    rows = list(reader) if header else list(csv.reader(io.StringIO(text), delimiter=delimiter))

    addr_index = 0
    if address_column and header:
        try:
            addr_index = list(header).index(address_column)
        except ValueError:
            addr_index = 0

    addresses = [row[addr_index] if row else "" for row in rows]
    results = geocode_addresses(addresses)

    def generate():
        out = io.StringIO()
        writer = csv.writer(out, delimiter=delimiter)
        if header:
            writer.writerow([*header, "lat", "lon"])
            for row, res in zip(rows, results):
                writer.writerow([*row, res.lat, res.lon])
        else:
            for res in results:
                writer.writerow([res.address, res.lat, res.lon])
        yield out.getvalue()

    return StreamingResponse(generate(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=geocoded.csv"})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
