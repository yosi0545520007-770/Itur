from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, Optional, Sequence
import csv
import re


@dataclass
class GeocodeResult:
    address: str
    lat: Optional[float]
    lon: Optional[float]


Locator = Callable[[str], Optional[tuple[float, float]]]


def _default_locator() -> Locator:
    from geopy.geocoders import Nominatim  # type: ignore
    from geopy.extra.rate_limiter import RateLimiter  # type: ignore

    geolocator = Nominatim(user_agent="itur-geocoder")
    rate_limited = RateLimiter(geolocator.geocode, min_delay_seconds=1.0)

    def locate(address: str) -> Optional[tuple[float, float]]:
        """מגאוקד עם כללים:
        - עיר בלבד → מרכז העיר
        - עיר + רחוב ללא מספר → תחילת הרחוב
        - עיר + מספר בלבד → מרכז העיר
        - עיר + רחוב + מספר → הכתובת המלאה
        אם לא ניתן לזהות — ניסיון גנרי.
        """
        text = address.strip()
        if not text:
            return None

        # פיצול בסיסי לפי מפרידים נפוצים
        parts = [p.strip() for p in re.split(r"[;|,]+", text) if p.strip()]

        try:
            # עיר בלבד
            if len(parts) == 1:
                location = rate_limited(parts[0], addressdetails=True)
                if not location:
                    return None
                return float(location.latitude), float(location.longitude)

            city = parts[-1]
            prev = parts[-2]

            # עיר + מספר בלבד → מרכז העיר
            if len(parts) == 2 and re.fullmatch(r"\d+", prev):
                location = rate_limited(city, addressdetails=True)
                if not location:
                    return None
                return float(location.latitude), float(location.longitude)

            # אם יש מספר בתוך רכיב הרחוב → נתייחס כרחוב+מספר
            if re.search(r"\d", prev):
                q = f"{prev}, {city}"
                location = rate_limited(q, addressdetails=True)
                if not location:
                    return None
                return float(location.latitude), float(location.longitude)

            # עיר + רחוב ללא מספר → נבקש גיאומטריה וניקח את תחילת הרחוב
            location = geolocator.geocode(
                {"city": city, "street": prev}, addressdetails=True, geometry="geojson"
            )
            if location:
                raw = getattr(location, "raw", {}) or {}
                geo = raw.get("geojson")
                if isinstance(geo, dict):
                    gtype = geo.get("type")
                    coords = geo.get("coordinates")
                    if gtype == "LineString" and isinstance(coords, list) and coords:
                        lon, lat = coords[0]
                        return float(lat), float(lon)
                    if gtype == "MultiLineString" and isinstance(coords, list) and coords and coords[0]:
                        lon, lat = coords[0][0]
                        return float(lat), float(lon)
                # נפילה חזרה לנקודה אם אין גאו־ג׳יסון
                return float(location.latitude), float(location.longitude)

            # אם לא נמצא — ניסיון גנרי
            location = rate_limited(text, addressdetails=True)
            if not location:
                return None
            return float(location.latitude), float(location.longitude)

        except Exception:
            # לא להפיל את כל הריצה — נחזיר None במקרה חריג
            return None

    return locate


def geocode_addresses(
    addresses: Iterable[str], locator: Optional[Locator] = None
) -> list[GeocodeResult]:
    loc = locator or _default_locator()
    results: list[GeocodeResult] = []
    for addr in addresses:
        coords = loc(addr)
        lat, lon = (coords if coords is not None else (None, None))
        results.append(GeocodeResult(address=addr, lat=lat, lon=lon))
    return results


def _deg_to_ddm(value: float, *, is_lat: bool) -> str:
    sign = ('N' if is_lat else 'E') if value >= 0 else ('S' if is_lat else 'W')
    deg = int(abs(value))
    minutes = (abs(value) - deg) * 60
    return (f"{deg:02d}° {minutes:06.3f}' {sign}" if is_lat
            else f"{deg:03d}° {minutes:06.3f}' {sign}")


def _deg_to_dms(value: float, *, is_lat: bool) -> str:
    sign = ('N' if is_lat else 'E') if value >= 0 else ('S' if is_lat else 'W')
    deg = int(abs(value))
    rem = (abs(value) - deg) * 60
    minutes = int(rem)
    seconds = (rem - minutes) * 60
    return (f"{deg:02d}° {minutes:02d}' {seconds:05.2f}\" {sign}" if is_lat
            else f"{deg:03d}° {minutes:02d}' {seconds:05.2f}\" {sign}")


def geocode_csv(
    in_path: str,
    out_path: str,
    *,
    address_column: Optional[str] = None,
    delimiter: str = ",",
    locator: Optional[Locator] = None,
) -> None:
    loc = locator or _default_locator()

    with open(in_path, "r", encoding="utf-8-sig", newline="") as f_in:
        sample = f_in.read(2048)
        f_in.seek(0)
        try:
            has_header = csv.Sniffer().has_header(sample)
        except Exception:
            has_header = True

        reader = csv.reader(f_in, delimiter=delimiter)
        header: Optional[Sequence[str]] = None
        if has_header:
            header = next(reader, None)  # type: ignore[assignment]

        addr_index = 0
        if address_column and header:
            try:
                addr_index = list(header).index(address_column)
            except ValueError as exc:
                raise ValueError(
                    f"העמודה '{address_column}' לא נמצאה בכותרת: {header}"
                ) from exc

        rows = list(reader)
        addresses = [row[addr_index] if row else "" for row in rows]

    results = geocode_addresses(addresses, locator=loc)

    with open(out_path, "w", encoding="utf-8", newline="") as f_out:
        writer = csv.writer(f_out, delimiter=delimiter)
        extra_cols = ["lat", "lon", "lat_ddm", "lon_ddm", "lat_dms", "lon_dms"]
        if header:
            writer.writerow([*header, *extra_cols])
            for row, res in zip(rows, results):
                lat = res.lat
                lon = res.lon
                ddm_lat = _deg_to_ddm(lat, is_lat=True) if lat is not None else ""
                ddm_lon = _deg_to_ddm(lon, is_lat=False) if lon is not None else ""
                dms_lat = _deg_to_dms(lat, is_lat=True) if lat is not None else ""
                dms_lon = _deg_to_dms(lon, is_lat=False) if lon is not None else ""
                writer.writerow([*row, lat, lon, ddm_lat, ddm_lon, dms_lat, dms_lon])
        else:
            writer.writerow(["address", *extra_cols])
            for res in results:
                lat = res.lat
                lon = res.lon
                ddm_lat = _deg_to_ddm(lat, is_lat=True) if lat is not None else ""
                ddm_lon = _deg_to_ddm(lon, is_lat=False) if lon is not None else ""
                dms_lat = _deg_to_dms(lat, is_lat=True) if lat is not None else ""
                dms_lon = _deg_to_dms(lon, is_lat=False) if lon is not None else ""
                writer.writerow([res.address, lat, lon, ddm_lat, ddm_lon, dms_lat, dms_lon])
