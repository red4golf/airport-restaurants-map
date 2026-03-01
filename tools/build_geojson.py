import csv
import json
import urllib.request
from pathlib import Path
from datetime import date
import xml.etree.ElementTree as ET

OURAIRPORTS_AIRPORTS_CSV = "https://ourairports.com/data/airports.csv"

SEED_CSV    = Path("data/restaurants_seed.csv")
OUT_GEOJSON = Path("data/restaurants.geojson")
OUT_SITEMAP = Path("sitemap.xml")

BASE_URL = "https://red4golf.github.io/airport-restaurants-map"

AIRNAV_BASE = "https://www.airnav.com/airport/"

def download_text(url: str) -> str:
    with urllib.request.urlopen(url) as resp:
        return resp.read().decode("utf-8", errors="replace")

def load_ourairports_index() -> dict:
    print("Fetching OurAirports data…")
    text = download_text(OURAIRPORTS_AIRPORTS_CSV)
    reader = csv.DictReader(text.splitlines())
    idx = {}
    for row in reader:
        ident = (row.get("ident") or "").strip()
        if ident:
            idx[ident] = row
        local_code = (row.get("local_code") or "").strip()
        if local_code and local_code not in idx:
            idx[local_code] = row
    print(f"  Loaded {len(idx):,} airports from OurAirports.")
    return idx

def lookup_airport(idx: dict, ident: str):
    """Look up airport by ident with fallbacks for FAA LIDs."""
    # 1. Direct match (ICAO e.g. KPWT, or FAA LID via local_code index)
    if ident in idx:
        return idx[ident]
    # 2. Try prepending K (e.g. 0S9 -> K0S9)
    k_ident = "K" + ident
    if k_ident in idx:
        return idx[k_ident]
    # 3. Not found
    return None

def slugify(text: str) -> str:
    import re
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")

def build_geojson(idx: dict) -> list:
    features = []
    missing  = []

    with SEED_CSV.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            ident = (r.get("airport_ident") or "").strip()
            name  = (r.get("restaurant_name") or "").strip()

            if not ident or not name or name.startswith("ADD YOUR"):
                continue

            oa = lookup_airport(idx, ident)
            if not oa:
                missing.append(ident)
                continue

            lat = oa.get("latitude_deg")
            lon = oa.get("longitude_deg")
            if not lat or not lon:
                missing.append(ident)
                continue

            # Use the resolved OurAirports ident for the AirNav link
            resolved_ident = (oa.get("ident") or ident).strip()

            props = {
                "restaurant_name": name,
                "type":            (r.get("type")            or "").strip(),
                "region":          (r.get("region")          or "").strip(),
                "source":          (r.get("source")          or "").strip(),
                "website":         (r.get("website")         or "").strip(),
                "substack_post":   (r.get("substack_post")   or "").strip(),
                "notes":           (r.get("notes")           or "").strip(),
                "airport_ident":   ident,
                "airport_name":    (r.get("airport_name")    or oa.get("name") or "").strip(),
                "city":            (r.get("city")            or oa.get("municipality") or "").strip(),
                "state":           (r.get("state")           or "").strip(),
                "iso_region":      (oa.get("iso_region")     or "").strip(),
                "slug":            slugify(f"{name}-{ident}"),
                "airnav_url":      f"{AIRNAV_BASE}{resolved_ident}",
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
    OUT_GEOJSON.write_text(
        json.dumps(fc, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    print(f"  Wrote {OUT_GEOJSON} with {len(features)} features.")

    if missing:
        print(f"  Missing idents (not found in OurAirports):")
        for m in sorted(set(missing)):
            print(f"    - {m}")

    return features

def build_sitemap(features: list):
    today = date.today().isoformat()

    urlset = ET.Element("urlset", xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")

    def add_url(loc, priority="0.8", changefreq="monthly"):
        url_el = ET.SubElement(urlset, "url")
        ET.SubElement(url_el, "loc").text = loc
        ET.SubElement(url_el, "lastmod").text = today
        ET.SubElement(url_el, "changefreq").text = changefreq
        ET.SubElement(url_el, "priority").text = priority

    add_url(f"{BASE_URL}/", priority="1.0", changefreq="weekly")

    seen_slugs = set()
    for f in features:
        p = f["properties"]
        slug = p.get("slug", "")
        if slug and slug not in seen_slugs:
            add_url(f"{BASE_URL}/?q={slug}", priority="0.7", changefreq="monthly")
            seen_slugs.add(slug)

    airports = {}
    for f in features:
        p = f["properties"]
        ident = p.get("airport_ident", "")
        if ident and ident not in airports:
            airports[ident] = p.get("airport_name", ident)
    for ident in airports:
        add_url(f"{BASE_URL}/?q={ident.lower()}", priority="0.6", changefreq="monthly")

    regions = set(f["properties"].get("region", "") for f in features if f["properties"].get("region"))
    for region in sorted(regions):
        add_url(f"{BASE_URL}/?q={region.lower()}", priority="0.5", changefreq="monthly")

    tree = ET.ElementTree(urlset)
    ET.indent(tree, space="  ")
    OUT_SITEMAP.write_bytes(
        b'<?xml version="1.0" encoding="UTF-8"?>\n' +
        ET.tostring(urlset, encoding="utf-8", xml_declaration=False)
    )
    print(f"  Wrote {OUT_SITEMAP} with {len(urlset)} URLs.")

def main():
    print("\n=== Airport Restaurants Build ===")
    idx      = load_ourairports_index()
    features = build_geojson(idx)
    build_sitemap(features)
    print(f"\nDone. {len(features)} restaurants across "
          f"{len(set(f['properties']['airport_ident'] for f in features))} airports.\n")

if __name__ == "__main__":
    main()
