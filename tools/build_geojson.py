import csv
import json
import re
import urllib.request
from pathlib import Path
from datetime import date
import xml.etree.ElementTree as ET

OURAIRPORTS_AIRPORTS_CSV = "https://ourairports.com/data/airports.csv"

SEED_CSV    = Path("data/restaurants_seed.csv")
OUT_GEOJSON = Path("data/restaurants.geojson")
OUT_SITEMAP = Path("sitemap.xml")
INDEX_HTML  = Path("index.html")

BASE_URL    = "https://red4golf.github.io/airport-restaurants-map"
AIRNAV_BASE = "https://www.airnav.com/airport/"

# ─── SEO: State abbreviation → full name for richer structured data ────────────
STATE_NAMES = {
    "AL":"Alabama","AK":"Alaska","AZ":"Arizona","AR":"Arkansas","CA":"California",
    "CO":"Colorado","CT":"Connecticut","DE":"Delaware","FL":"Florida","GA":"Georgia",
    "HI":"Hawaii","ID":"Idaho","IL":"Illinois","IN":"Indiana","IA":"Iowa",
    "KS":"Kansas","KY":"Kentucky","LA":"Louisiana","ME":"Maine","MD":"Maryland",
    "MA":"Massachusetts","MI":"Michigan","MN":"Minnesota","MS":"Mississippi",
    "MO":"Missouri","MT":"Montana","NE":"Nebraska","NV":"Nevada","NH":"New Hampshire",
    "NJ":"New Jersey","NM":"New Mexico","NY":"New York","NC":"North Carolina",
    "ND":"North Dakota","OH":"Ohio","OK":"Oklahoma","OR":"Oregon","PA":"Pennsylvania",
    "RI":"Rhode Island","SC":"South Carolina","SD":"South Dakota","TN":"Tennessee",
    "TX":"Texas","UT":"Utah","VT":"Vermont","VA":"Virginia","WA":"Washington",
    "WV":"West Virginia","WI":"Wisconsin","WY":"Wyoming",
}


def download_text(url: str) -> str:
    with urllib.request.urlopen(url) as resp:
        return resp.read().decode("utf-8", errors="replace")


def load_ourairports_index() -> dict:
    print("Fetching OurAirports data…")
    text   = download_text(OURAIRPORTS_AIRPORTS_CSV)
    reader = csv.DictReader(text.splitlines())
    idx    = {}
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
    if ident in idx:
        return idx[ident]
    k_ident = "K" + ident
    if k_ident in idx:
        return idx[k_ident]
    return None


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")


def html_escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


# ─── BUILD GEOJSON ────────────────────────────────────────────────────────────
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
                "airnav_url":      f"{AIRNAV_BASE}{ident}",
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


# ─── BUILD SITEMAP ────────────────────────────────────────────────────────────
# Commit 3 change: sitemap now uses real hash fragment URLs (#airport/IDENT)
# instead of ?q= query parameters. Google treats these as distinct pages,
# not as parameter variants of a single URL.
def build_sitemap(features: list):
    today  = date.today().isoformat()
    urlset = ET.Element("urlset", xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")

    def add_url(loc, priority="0.8", changefreq="monthly"):
        url_el = ET.SubElement(urlset, "url")
        ET.SubElement(url_el, "loc").text        = loc
        ET.SubElement(url_el, "lastmod").text    = today
        ET.SubElement(url_el, "changefreq").text = changefreq
        ET.SubElement(url_el, "priority").text   = priority

    # Homepage
    add_url(f"{BASE_URL}/", priority="1.0", changefreq="weekly")

    # Per-airport pages using hash fragments
    seen_airports = set()
    for f in features:
        p     = f["properties"]
        ident = p.get("airport_ident", "")
        if ident and ident not in seen_airports:
            add_url(
                f"{BASE_URL}/#airport/{ident.lower()}",
                priority="0.7",
                changefreq="monthly"
            )
            seen_airports.add(ident)

    # Per-restaurant pages using hash fragments
    seen_slugs = set()
    for f in features:
        p    = f["properties"]
        slug = p.get("slug", "")
        if slug and slug not in seen_slugs:
            add_url(
                f"{BASE_URL}/#restaurant/{slug}",
                priority="0.6",
                changefreq="monthly"
            )
            seen_slugs.add(slug)

    # Region pages
    regions = sorted(set(
        f["properties"].get("region", "")
        for f in features
        if f["properties"].get("region")
    ))
    for region in regions:
        add_url(
            f"{BASE_URL}/#region/{region.lower()}",
            priority="0.5",
            changefreq="monthly"
        )

    tree = ET.ElementTree(urlset)
    ET.indent(tree, space="  ")
    OUT_SITEMAP.write_bytes(
        b'<?xml version="1.0" encoding="UTF-8"?>\n' +
        ET.tostring(urlset, encoding="utf-8", xml_declaration=False)
    )
    print(f"  Wrote {OUT_SITEMAP} with {len(urlset)} URLs.")


# ─── GENERATE JSON-LD ─────────────────────────────────────────────────────────
def build_jsonld(features: list) -> str:
    """Generate the full JSON-LD structured data block from all features."""

    items = []
    for i, f in enumerate(features, start=1):
        p    = f["properties"]
        name = p.get("restaurant_name", "")
        if not name:
            continue

        item = {
            "@type": "ListItem",
            "position": i,
            "item": {
                "@type": "FoodEstablishment",
                "name": name,
            }
        }

        entry = item["item"]

        if p.get("notes"):
            entry["description"] = p["notes"]

        if p.get("website"):
            entry["url"] = p["website"]

        city  = p.get("city", "")
        state = p.get("state", "")
        if city or state:
            entry["address"] = {
                "@type":          "PostalAddress",
                "addressLocality": city,
                "addressRegion":   state,
                "addressCountry":  "US",
            }

        airport_name  = p.get("airport_name", "")
        airport_ident = p.get("airport_ident", "")
        if airport_name or airport_ident:
            entry["containedInPlace"] = {
                "@type":      "Airport",
                "name":       airport_name,
                "identifier": airport_ident,
            }

        items.append(item)

    graph = [
        {
            "@type": "WebSite",
            "@id":   f"{BASE_URL}/#website",
            "url":   f"{BASE_URL}/",
            "name":  "Airport Restaurants",
            "description": (
                "The pilot's guide to fly-in dining and $100 hamburger destinations "
                "across the United States."
            ),
            "publisher": {
                "@type": "Person",
                "name":  "Charles Einarson",
                "url":   "https://airportrestaurants.substack.com",
            },
            "potentialAction": {
                "@type":  "SearchAction",
                "target": {
                    "@type":       "EntryPoint",
                    "urlTemplate": f"{BASE_URL}/?q={{search_term_string}}",
                },
                "query-input": "required name=search_term_string",
            },
        },
        {
            "@type":       "ItemList",
            "name":        "Fly-In Restaurants at US General Aviation Airports",
            "description": (
                "A curated directory of the best on-field and near-airport restaurants "
                "for pilots across the United States — from classic $100 hamburger diners "
                "to upscale fly-in destinations."
            ),
            "url":           f"{BASE_URL}/",
            "numberOfItems": len(items),
            "itemListElement": items,
        },
    ]

    return json.dumps({"@context": "https://schema.org", "@graph": graph},
                      ensure_ascii=False, indent=2)


# ─── INJECT JSON-LD INTO index.html ──────────────────────────────────────────
def inject_jsonld(jsonld_str: str):
    """Replace the static JSON-LD block in index.html with a freshly generated one."""
    if not INDEX_HTML.exists():
        print(f"  index.html not found at {INDEX_HTML} — skipping JSON-LD injection.")
        return

    html = INDEX_HTML.read_text(encoding="utf-8")

    new_block = (
        '<script type="application/ld+json">\n'
        + jsonld_str
        + '\n  </script>'
    )

    # Replace existing ld+json block
    pattern = r'<script type="application/ld\+json">.*?</script>'
    if re.search(pattern, html, flags=re.DOTALL):
        html = re.sub(pattern, new_block, html, flags=re.DOTALL)
        print("  Injected updated JSON-LD into index.html.")
    else:
        # No existing block — insert before </head>
        html = html.replace("</head>", f"  {new_block}\n</head>", 1)
        print("  Inserted new JSON-LD block into index.html.")

    INDEX_HTML.write_text(html, encoding="utf-8")


# ─── GENERATE CRAWLABLE HTML LIST ────────────────────────────────────────────
def build_seo_html_list(features: list) -> str:
    """Generate the hidden-but-crawlable restaurant <ul> block."""
    lines = []
    lines.append(
        '<!--\n'
        '  SEO: Hidden restaurant index for search engine crawlers.\n'
        '  This block is visually hidden but fully readable by Googlebot.\n'
        '  Generated at build time by tools/build_geojson.py.\n'
        '  DO NOT edit manually — it will be overwritten on the next build.\n'
        '-->'
    )
    lines.append(
        '<section id="seo-restaurant-index" aria-hidden="true" '
        'style="position:absolute;left:-9999px;width:1px;height:1px;overflow:hidden;">'
    )
    lines.append('  <h1>Airport Restaurants — Fly-In Dining Guide for Pilots</h1>')
    lines.append(
        '  <p>Airport Restaurants is a directory of fly-in dining destinations at general '
        'aviation airports across the United States. Browse on-field restaurants, classic '
        '$100 hamburger stops, and the best fly-in meals by state and region.</p>'
    )
    lines.append('  <h2>Featured Fly-In Restaurants by State</h2>')
    lines.append('  <ul>')

    for f in features:
        p     = f["properties"]
        name  = html_escape(p.get("restaurant_name", ""))
        aname = html_escape(p.get("airport_name", ""))
        ident = html_escape(p.get("airport_ident", ""))
        city  = html_escape(p.get("city", ""))
        state = html_escape(p.get("state", ""))
        rtype = "On-airport" if p.get("type") == "on-airport" else "Near airport"
        notes = html_escape(p.get("notes", ""))

        loc = f"{city}, {state}" if city and state else (city or state)
        h3  = f"{name} — {aname} ({ident}), {loc}" if loc else f"{name} — {aname} ({ident})"

        lines.append(f'    <li><h3>{h3}</h3>')
        if notes:
            lines.append(f'      <p>{rtype}. {notes}</p>')
        else:
            lines.append(f'      <p>{rtype}.</p>')
        lines.append('    </li>')

    lines.append('  </ul>')
    lines.append(
        '  <p>Browse the full interactive map to find fly-in restaurants near any general '
        'aviation airport in the United States. Filter by region, state, or restaurant type. '
        'Subscribe to the <a href="https://airportrestaurants.substack.com">Airport Restaurants '
        'newsletter</a> for in-depth fly-in dining reviews.</p>'
    )
    lines.append('</section>')
    return "\n".join(lines)


# ─── INJECT SEO HTML LIST INTO index.html ────────────────────────────────────
def inject_seo_html_list(seo_html: str):
    """Replace or insert the hidden SEO restaurant list in index.html."""
    if not INDEX_HTML.exists():
        print(f"  index.html not found at {INDEX_HTML} — skipping SEO list injection.")
        return

    html = INDEX_HTML.read_text(encoding="utf-8")

    # Replace existing block if present
    pattern = r'<!--\s*SEO: Hidden restaurant index.*?</section>'
    if re.search(pattern, html, flags=re.DOTALL):
        html = re.sub(pattern, seo_html, html, flags=re.DOTALL)
        print("  Updated SEO restaurant list in index.html.")
    else:
        # Insert before the first <script> tag in the body
        html = html.replace("<script>\nfunction loadScript", seo_html + "\n\n<script>\nfunction loadScript", 1)
        print("  Inserted SEO restaurant list into index.html.")

    INDEX_HTML.write_text(html, encoding="utf-8")


# ─── MAIN ─────────────────────────────────────────────────────────────────────
def main():
    print("\n=== Airport Restaurants Build ===")

    idx      = load_ourairports_index()
    features = build_geojson(idx)
    build_sitemap(features)

    # SEO: Regenerate and inject JSON-LD into index.html
    jsonld_str = build_jsonld(features)
    inject_jsonld(jsonld_str)

    # SEO: Regenerate and inject hidden crawlable restaurant list into index.html
    seo_html = build_seo_html_list(features)
    inject_seo_html_list(seo_html)

    print(f"\nDone. {len(features)} restaurants across "
          f"{len(set(f['properties']['airport_ident'] for f in features))} airports.\n")


if __name__ == "__main__":
    main()
