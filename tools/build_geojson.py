import csv
import json
import urllib.request
from pathlib import Path

OURAIRPORTS_AIRPORTS_CSV = "https://ourairports.com/data/airports.csv"

SEED_CSV = Path("data/restaurants_seed.csv")
OUT_GEOJSON = Path("data/restaurants.geojson")

def download_text(url: str) -> str:
    with urllib.request.urlopen(url) as resp:
        return resp.read().decode("utf-8", errors="replace")

def load_ourairports_index() -> dict:
    text = download_text(OURAIRPORTS_AIRPORTS_CSV)
    reader = csv.DictReader(text.splitlines())
    idx = {}
    for row in reader:
        ident = (row.get("ident") or "").strip()
        if ident:
            idx[ident] = row
    return idx

def main():
    idx = load_ourairports_index()

    features = []
    missing = []

    with SEED_CSV.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            ident = (r.get("airport_ident") or "").strip()
            if not ident:
                continue  # skip placeholders / incomplete rows

            oa = idx.get(ident)
            if not oa:
                missing.append(ident)
                continue

            lat = oa.get("latitude_deg")
            lon = oa.get("longitude_deg")
            if not lat or not lon:
                missing.append(ident)
                continue

            props = {
                "restaurant_name": (r.get("restaurant_name") or "").strip(),
                "type": (r.get("type") or "").strip(),
                "region": (r.get("region") or "").strip(),
                "source": (r.get("source") or "").strip(),
                "website": (r.get("website") or "").strip(),
                "substack_post": (r.get("substack_post") or "").strip(),
                "airport_ident": ident,
                "airport_name": (r.get("airport_name") or oa.get("name") or "").strip(),
                "city": (r.get("city") or oa.get("municipality") or "").strip(),
                "state": (r.get("state") or "").strip(),
                "iso_region": (oa.get("iso_region") or "").strip(),
            }

            features.append({
                "type": "Feature",
                "properties": props,
                "geometry": {
                    "type": "Point",
                    "coordinates": [float(lon), float(lat)]
                }
            })

    fc = {"type": "FeatureCollection", "features": features}
    OUT_GEOJSON.write_text(json.dumps(fc, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Wrote {OUT_GEOJSON} with {len(features)} features.")
    if missing:
        print("Missing idents (not found in OurAirports):")
        for m in sorted(set(missing)):
            print(" -", m)

if __name__ == "__main__":
    main()
