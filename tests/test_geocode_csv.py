from pathlib import Path
from itur.geocode import geocode_csv


def test_geocode_csv_with_header_and_col(tmp_path: Path) -> None:
    in_csv = tmp_path / "in.csv"
    out_csv = tmp_path / "out.csv"
    in_csv.write_text("address\nTel Aviv\nJerusalem\n", encoding="utf-8")

    def fake_locator(addr: str):  # type: ignore[override]
        if addr == "Tel Aviv":
            return (32.0853, 34.7818)
        return None

    geocode_csv(str(in_csv), str(out_csv), address_column="address", locator=fake_locator)

    content = out_csv.read_text(encoding="utf-8").strip().splitlines()
    assert content[0].startswith("address,lat,lon")
    assert content[1].startswith("Tel Aviv,32.0853,34.7818")
    assert content[2].startswith("Jerusalem,,")
