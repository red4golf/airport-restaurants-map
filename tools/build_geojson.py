import csv
import json
import re
import urllib.request
from pathlib import Path
from datetime import date
import xml.etree.ElementTree as ET

OURAIRPORTS_AIRPORTS_CSV = "https://ourairports.com/data/airports.csv"

SEED_CSV      = Path("data/restaurants_seed.csv")
OUT_GEOJSON   = Path("data/restaurants.geojson")
OUT_SITEMAP   = Path("sitemap.xml")
INDEX_HTML    = Path("index.html")
AIRPORTS_DIR  = Path("airports")

BASE_URL    = "https://red4golf.github.io/airport-restaurants-map"
AIRNAV_BASE = "https://www.airnav.com/airport/"

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
    return (s.replace("&", "&amp;")
             .replace("<", "&lt;")
             .replace(">", "&gt;")
             .replace('"', "&quot;"))


# ─── STATUS HELPERS ───────────────────────────────────────────────────────────
# A blank `status` means open. Older seed files with no status column keep working.
def is_open(props: dict) -> bool:
    return (props.get("status") or "").strip().lower() != "closed"


def split_open_closed(rests: list) -> tuple:
    return [r for r in rests if is_open(r)], [r for r in rests if not is_open(r)]


# ─── BUILD GEOJSON ────────────────────────────────────────────────────────────
def build_geojson(idx: dict) -> tuple:
    """Returns (features, stats). Every seed row is accounted for — nothing is
    dropped silently. Rows the geocoder cannot place are reported loudly."""
    features = []
    dropped  = []
    rows_read = 0

    with SEED_CSV.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            ident = (r.get("airport_ident") or "").strip()
            name  = (r.get("restaurant_name") or "").strip()

            if not ident or not name or name.startswith("ADD YOUR"):
                continue

            rows_read += 1

            # Manual lat/lon overrides win over OurAirports, and are the fallback
            # for idents OurAirports no longer carries (closed or private strips).
            lat = (r.get("lat") or "").strip()
            lon = (r.get("lon") or "").strip()

            oa = lookup_airport(idx, ident)
            if not lat or not lon:
                if oa:
                    lat = oa.get("latitude_deg") or ""
                    lon = oa.get("longitude_deg") or ""

            if not lat or not lon:
                dropped.append((ident, name,
                                "not in OurAirports and no lat/lon override in the seed file"
                                if not oa else "OurAirports record has no coordinates"))
                continue

            oa = oa or {}

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
                # Only link AirNav for fields it still carries. Decommissioned strips
                # (the ones we place by lat/lon override) 404 there.
                "airnav_url":      f"{AIRNAV_BASE}{ident}" if oa else "",
                # Blank status = open. Closures are recorded, never deleted.
                "status":          (r.get("status")      or "").strip(),
                "status_date":     (r.get("status_date") or "").strip(),
                "status_note":     (r.get("status_note") or "").strip(),
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

    open_f, closed_f = split_open_closed([f["properties"] for f in features])
    print(f"  Read {rows_read} seed rows → wrote {len(features)} features "
          f"({len(open_f)} open · {len(closed_f)} closed).")

    if dropped:
        print()
        print("  " + "!" * 68)
        print(f"  !! {len(dropped)} SEED ROW(S) DROPPED — these are invisible to the build:")
        for ident, name, why in dropped:
            print(f"  !!   {ident:<6} {name}  —  {why}")
        print("  !! Fix: add lat/lon columns for these rows in data/restaurants_seed.csv")
        print("  " + "!" * 68)
        print()

    stats = {
        "rows_read": rows_read,
        "dropped":   len(dropped),
        "open":      len(open_f),
        "closed":    len(closed_f),
    }
    return features, stats


# ─── GROUP FEATURES BY AIRPORT ────────────────────────────────────────────────
def group_by_airport(features: list) -> dict:
    airports = {}
    for f in features:
        p     = f["properties"]
        ident = p["airport_ident"]
        if ident not in airports:
            airports[ident] = {
                "ident":      ident,
                "name":       p.get("airport_name", ident),
                "city":       p.get("city", ""),
                "state":      p.get("state", ""),
                "lat":        f["geometry"]["coordinates"][1],
                "lng":        f["geometry"]["coordinates"][0],
                "airnav_url": p.get("airnav_url", ""),
                "restaurants": [],   # open only
                "closed":      [],   # retained history
            }
        if is_open(p):
            airports[ident]["restaurants"].append(p)
        else:
            airports[ident]["closed"].append(p)
    return airports


# ─── GENERATE SINGLE AIRPORT PAGE ─────────────────────────────────────────────
def render_airport_page(airport: dict) -> str:
    ident      = html_escape(airport["ident"])
    aname      = html_escape(airport["name"])
    city       = html_escape(airport["city"])
    state      = airport["state"]
    state_full = html_escape(STATE_NAMES.get(state, state))
    state_esc  = html_escape(state)
    lat        = airport["lat"]
    lng        = airport["lng"]
    airnav     = html_escape(airport["airnav_url"])
    rests      = airport["restaurants"]
    closed     = airport.get("closed", [])
    page_url   = f"{BASE_URL}/airports/{ident.lower()}/"

    loc_str    = f"{city}, {state_full}" if city else state_full
    count      = len(rests)
    count_str  = f"{count} restaurant{'s' if count != 1 else ''}"

    title      = f"Fly-In Dining at {aname} ({ident}) — Airport Restaurants"
    if count:
        desc = (
            f"Find fly-in restaurants at {aname} ({ident}) in {loc_str}. "
            f"{count_str} listed — on-field dining and $100 hamburger destinations for pilots."
        )
    else:
        # Don't promise a meal that isn't there. Phrased around flying rather than around
        # the restaurant existing, because at least one of these fields (T40) has a
        # restaurant that is very much open next to a runway that is very much closed.
        former = closed[0]["restaurant_name"] if len(closed) == 1 else "its restaurants"
        desc = (
            f"There is nothing you can fly in for at {aname} ({ident}) in {loc_str}. "
            f"We track what closed and when — {former} is listed here with the details."
        )

    # ── JSON-LD for this airport page ────────────────────────────────────────
    jsonld_items = []
    for i, r in enumerate(rests, start=1):
        entry = {
            "@type": "FoodEstablishment",
            "name":  html_escape(r.get("restaurant_name", "")),
            "address": {
                "@type":           "PostalAddress",
                "addressLocality":  html_escape(r.get("city", "")),
                "addressRegion":    state_esc,
                "addressCountry":   "US",
            },
            "containedInPlace": {
                "@type":      "Airport",
                "name":       aname,
                "identifier": ident,
            }
        }
        if r.get("notes"):
            entry["description"] = r["notes"]
        if r.get("website"):
            entry["url"] = r["website"]
        jsonld_items.append({"@type": "ListItem", "position": i, "item": entry})

    graph = [
        {
            "@type":      "Airport",
            "name":       aname,
            "identifier": ident,
            "address": {
                "@type":          "PostalAddress",
                "addressLocality": city,
                "addressRegion":   state_esc,
                "addressCountry":  "US",
            },
            "geo": {
                "@type":     "GeoCoordinates",
                "latitude":  lat,
                "longitude": lng,
            },
        },
    ]
    # Closed restaurants never appear in structured data — we are not telling
    # Google about a place a pilot can't eat.
    if count:
        graph.append({
            "@type":           "ItemList",
            "name":            f"Fly-In Restaurants at {aname}",
            "numberOfItems":   count,
            "itemListElement": jsonld_items,
        })

    jsonld = json.dumps({"@context": "https://schema.org", "@graph": graph},
                        ensure_ascii=False, indent=2)

    # ── Restaurant cards HTML ─────────────────────────────────────────────────
    cards_html = []
    for r in rests:
        rname    = html_escape(r.get("restaurant_name", ""))
        rtype    = r.get("type", "")
        rtype_lbl = "✅ On Field" if rtype == "on-airport" else "🚗 Near Airport"
        notes    = html_escape(r.get("notes", ""))
        website  = r.get("website", "")
        substack = r.get("substack_post", "")
        reviewed = bool(substack)

        links = ""
        if website:
            links += f'<a href="{html_escape(website)}" target="_blank" rel="noopener" class="card-link">Website →</a>'
        if substack:
            links += f'<a href="{html_escape(substack)}" target="_blank" rel="noopener" class="card-link card-link-sub">✉ Full Review →</a>'

        cards_html.append(f"""
  <article class="rest-card">
    <div class="card-header">
      <h2 class="card-name">{rname}</h2>
      <div class="card-badges">
        <span class="badge">{rtype_lbl}</span>
        {"<span class='badge badge-reviewed'>✉ Reviewed</span>" if reviewed else ""}
      </div>
    </div>
    {f'<p class="card-notes">{notes}</p>' if notes else ""}
    {f'<div class="card-links">{links}</div>' if links else ""}
  </article>""")

    cards = "\n".join(cards_html)

    # ── "Previously at this Airport" — closures are recorded, not deleted ─────
    closed_html = ""
    if closed:
        closed_cards = []
        for r in closed:
            rname = html_escape(r.get("restaurant_name", ""))
            when  = html_escape(r.get("status_date", ""))
            why   = html_escape(r.get("status_note", ""))
            closed_cards.append(f"""
  <article class="rest-card rest-card-closed">
    <div class="card-header">
      <h3 class="card-name">{rname}</h3>
      <div class="card-badges">
        <span class="badge badge-closed">⛔ Closed{f" &middot; {when}" if when else ""}</span>
      </div>
    </div>
    {f'<p class="card-notes">{why}</p>' if why else ""}
  </article>""")
        heading = ("Nothing Here You Can Fly In For"
                   if not count else "Previously at this Airport")
        intro = ""
        if not count:
            intro = ('<p class="empty-note">There is nothing here to fly in for at the moment. '
                     'We keep the record so you know why, and so a stale listing somewhere '
                     'else doesn\'t send you on a wasted flight.</p>')
        closed_html = (f'\n  <div class="section-label">{heading}</div>\n'
                       f'  {intro}\n' + "\n".join(closed_cards))

    # ── Breadcrumb JSON-LD ────────────────────────────────────────────────────
    breadcrumb_jsonld = json.dumps({
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Airport Restaurants", "item": f"{BASE_URL}/"},
            {"@type": "ListItem", "position": 2, "name": f"{aname} ({ident})", "item": page_url},
        ]
    })

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{title}</title>
  <meta name="description" content="{html_escape(desc)}" />
  <link rel="canonical" href="{page_url}" />
  <meta property="og:type" content="website" />
  <meta property="og:url" content="{page_url}" />
  <meta property="og:title" content="{html_escape(title)}" />
  <meta property="og:description" content="{html_escape(desc)}" />
  <meta property="og:site_name" content="Airport Restaurants" />
  <script type="application/ld+json">{jsonld}</script>
  <script type="application/ld+json">{breadcrumb_jsonld}</script>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,700;0,900;1,700&family=Source+Sans+3:wght@300;400;600&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet" />
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <style>
    :root {{
      --cream:     #f5f0e8;
      --parchment: #ede5d4;
      --navy:      #1a2744;
      --navy-mid:  #243460;
      --amber:     #c8821a;
      --amber-lt:  #e8a040;
      --rust:      #b84c2a;
      --ink:       #2a2420;
      --ink-mid:   #5a4f48;
      --border:    rgba(26,39,68,0.15);
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    html, body {{ background: var(--cream); color: var(--ink); font-family: 'Source Sans 3', sans-serif; }}

    /* ── Header ── */
    header {{
      background: var(--navy);
      border-bottom: 3px solid var(--amber);
      padding: 0 28px;
      height: 70px;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }}
    .brand {{ line-height: 1; text-decoration: none; }}
    .brand-name {{
      font-family: 'Playfair Display', serif;
      font-size: 20px; font-weight: 900;
      color: var(--cream); letter-spacing: 0.5px; display: block;
    }}
    .brand-sub {{
      font-family: 'DM Mono', monospace;
      font-size: 9px; letter-spacing: 4px; text-transform: uppercase;
      color: var(--amber-lt); display: block; margin-top: 2px;
    }}
    .header-right {{ display: flex; gap: 12px; align-items: center; }}
    .btn {{
      font-family: 'DM Mono', monospace;
      font-size: 10px; letter-spacing: 1.5px; text-transform: uppercase;
      text-decoration: none; padding: 7px 16px; border-radius: 2px;
      transition: all 0.2s;
    }}
    .btn-amber {{ color: var(--navy); background: var(--amber-lt); }}
    .btn-amber:hover {{ background: var(--cream); }}
    .btn-ghost {{ color: var(--cream); border: 1px solid rgba(245,240,232,0.3); }}
    .btn-ghost:hover {{ border-color: var(--amber-lt); color: var(--amber-lt); }}

    /* ── Breadcrumb ── */
    .breadcrumb {{
      background: var(--parchment);
      border-bottom: 1px solid var(--border);
      padding: 10px 28px;
      font-family: 'DM Mono', monospace;
      font-size: 10px; letter-spacing: 1px; text-transform: uppercase;
      color: var(--ink-mid);
    }}
    .breadcrumb a {{ color: var(--amber); text-decoration: none; }}
    .breadcrumb a:hover {{ text-decoration: underline; }}

    /* ── Page layout ── */
    .page {{ max-width: 900px; margin: 0 auto; padding: 40px 24px 80px; }}

    /* ── Airport hero ── */
    .airport-hero {{ margin-bottom: 36px; }}
    .airport-ident {{
      font-family: 'DM Mono', monospace;
      font-size: 11px; letter-spacing: 3px; text-transform: uppercase;
      color: var(--amber); margin-bottom: 8px;
    }}
    .airport-title {{
      font-family: 'Playfair Display', serif;
      font-size: 36px; font-weight: 900;
      color: var(--navy); line-height: 1.1; margin-bottom: 10px;
    }}
    .airport-meta {{
      font-size: 15px; color: var(--ink-mid); margin-bottom: 16px;
    }}
    .airport-meta a {{ color: var(--amber); text-decoration: none; }}
    .airport-meta a:hover {{ text-decoration: underline; }}
    .airport-count {{
      display: inline-block;
      font-family: 'DM Mono', monospace;
      font-size: 10px; letter-spacing: 2px; text-transform: uppercase;
      color: var(--rust); background: rgba(184,76,42,0.08);
      border: 1px solid rgba(184,76,42,0.2);
      padding: 4px 10px; border-radius: 2px;
    }}
    .airport-count-none {{
      color: var(--ink-mid); background: rgba(90,79,72,0.06);
      border-color: rgba(90,79,72,0.25);
    }}

    /* ── Mini map ── */
    #mini-map {{
      width: 100%; height: 280px;
      border: 1px solid var(--border);
      border-radius: 4px;
      margin-bottom: 40px;
      z-index: 1;
    }}

    /* ── Section heading ── */
    .section-label {{
      font-family: 'DM Mono', monospace;
      font-size: 9px; letter-spacing: 3px; text-transform: uppercase;
      color: var(--amber); margin-bottom: 16px;
      padding-bottom: 10px;
      border-bottom: 1px solid var(--border);
    }}

    /* ── Restaurant cards ── */
    .rest-card {{
      background: #fff;
      border: 1px solid var(--border);
      border-radius: 4px;
      padding: 20px 22px;
      margin-bottom: 16px;
      transition: box-shadow 0.15s;
    }}
    .rest-card:hover {{ box-shadow: 0 4px 16px rgba(26,39,68,0.08); }}
    .card-header {{
      display: flex; justify-content: space-between;
      align-items: flex-start; gap: 12px; margin-bottom: 10px;
    }}
    .card-name {{
      font-family: 'Playfair Display', serif;
      font-size: 20px; font-weight: 700; color: var(--navy); line-height: 1.2;
    }}
    .card-badges {{ display: flex; gap: 6px; flex-wrap: wrap; flex-shrink: 0; }}
    .badge {{
      font-family: 'DM Mono', monospace;
      font-size: 9px; letter-spacing: 1px; text-transform: uppercase;
      padding: 3px 8px; border-radius: 2px;
      border: 1px solid var(--border); color: var(--ink-mid);
    }}
    .badge-reviewed {{
      background: rgba(200,130,26,0.1);
      border-color: var(--amber); color: var(--amber);
    }}
    .badge-closed {{
      background: rgba(90,79,72,0.08);
      border-color: rgba(90,79,72,0.35); color: var(--ink-mid);
    }}
    .rest-card-closed {{
      background: rgba(237,229,212,0.5);
      border-style: dashed;
    }}
    .rest-card-closed .card-name {{ color: var(--ink-mid); }}
    .rest-card-closed:hover {{ box-shadow: none; }}
    .empty-note {{
      font-size: 14px; line-height: 1.7; color: var(--ink-mid);
      margin-bottom: 18px; max-width: 62ch;
    }}
    .card-notes {{
      font-size: 14px; line-height: 1.7;
      color: var(--ink-mid); margin-bottom: 14px;
    }}
    .card-links {{ display: flex; gap: 12px; flex-wrap: wrap; }}
    .card-link {{
      font-family: 'DM Mono', monospace;
      font-size: 10px; letter-spacing: 1.5px; text-transform: uppercase;
      text-decoration: none; padding: 6px 14px; border-radius: 2px;
      border: 1px solid var(--border); color: var(--ink-mid);
      transition: all 0.15s;
    }}
    .card-link:hover {{ border-color: var(--navy); color: var(--navy); }}
    .card-link-sub {{
      background: var(--navy); color: var(--cream); border-color: var(--navy);
    }}
    .card-link-sub:hover {{ background: var(--amber); border-color: var(--amber); }}

    /* ── Back link ── */
    .back-section {{
      margin-top: 48px; padding-top: 24px;
      border-top: 1px solid var(--border);
      text-align: center;
    }}
    .back-link {{
      font-family: 'DM Mono', monospace;
      font-size: 10px; letter-spacing: 2px; text-transform: uppercase;
      color: var(--amber); text-decoration: none;
    }}
    .back-link:hover {{ color: var(--navy); }}

    /* ── Footer ── */
    footer {{
      background: var(--navy);
      border-top: 3px solid var(--amber);
      padding: 20px 28px;
      text-align: center;
      font-family: 'DM Mono', monospace;
      font-size: 10px; letter-spacing: 1px; text-transform: uppercase;
      color: rgba(245,240,232,0.4);
    }}
    footer a {{ color: var(--amber-lt); text-decoration: none; }}
    footer a:hover {{ text-decoration: underline; }}

    @media (max-width: 600px) {{
      header {{ padding: 0 16px; }}
      .page {{ padding: 24px 16px 60px; }}
      .airport-title {{ font-size: 26px; }}
      .card-header {{ flex-direction: column; }}
    }}
  </style>
</head>
<body>

<header>
  <a href="{BASE_URL}/" class="brand">
    <span class="brand-name">Airport Restaurants</span>
    <span class="brand-sub">The Pilot's Dining Guide</span>
  </a>
  <div class="header-right">
    <a href="{BASE_URL}/" class="btn btn-ghost">← Back to Map</a>
    <a href="https://airportrestaurants.substack.com" target="_blank" class="btn btn-amber">✉ Newsletter</a>
  </div>
</header>

<nav class="breadcrumb" aria-label="Breadcrumb">
  <a href="{BASE_URL}/">Airport Restaurants</a> &rsaquo; {aname} ({ident})
</nav>

<main class="page">

  <div class="airport-hero">
    <div class="airport-ident">✈ {ident} &mdash; {state_full}</div>
    <h1 class="airport-title">{aname}</h1>
    <p class="airport-meta">
      📍 {loc_str}
      {f' &nbsp;·&nbsp; <a href="{airnav}" target="_blank" rel="noopener">AirNav ✈</a>' if airnav else ""}
    </p>
    <span class="airport-count{'' if count else ' airport-count-none'}">{count_str if count else 'No fly-in dining'}</span>
  </div>

  <div id="mini-map"></div>

  {f'<div class="section-label">Restaurants at this Airport</div>{cards}' if count else ''}
  {closed_html}

  <div class="back-section">
    <a href="{BASE_URL}/" class="back-link">← View All Airports on the Map</a>
  </div>

</main>

<footer>
  <a href="{BASE_URL}/">Airport Restaurants</a> &nbsp;·&nbsp;
  <a href="https://airportrestaurants.substack.com">Newsletter</a> &nbsp;·&nbsp;
  Built for pilots who fly for food.
</footer>

<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
  const map = L.map('mini-map', {{
    center: [{lat}, {lng}],
    zoom: 12,
    zoomControl: true,
    scrollWheelZoom: false,
  }});

  L.tileLayer('https://{{s}}.basemaps.cartocdn.com/light_all/{{z}}/{{x}}/{{y}}{{r}}.png', {{
    attribution: '&copy; OpenStreetMap &copy; CARTO',
    subdomains: 'abcd',
    maxZoom: 19,
  }}).addTo(map);

  const icon = L.divIcon({{
    className: '',
    html: '<div style="width:32px;height:32px;background:{"#1a2744" if count else "#8a8178"};border:2px solid {"#e8a040" if count else "#b3aca4"};border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:15px;box-shadow:0 2px 8px rgba(0,0,0,0.3);">✈</div>',
    iconSize: [32, 32],
    iconAnchor: [16, 16],
    popupAnchor: [0, -18],
  }});

  L.marker([{lat}, {lng}], {{ icon }})
    .addTo(map)
    .bindPopup('<strong>{aname}</strong><br>{ident} &mdash; {loc_str}')
    .openPopup();
</script>

</body>
</html>
"""


# ─── BUILD ALL AIRPORT PAGES ──────────────────────────────────────────────────
def build_airport_pages(features: list) -> list:
    """Generate one HTML page per airport. Returns list of relative paths created."""
    airports  = group_by_airport(features)
    created   = []

    AIRPORTS_DIR.mkdir(exist_ok=True)

    for ident, airport in airports.items():
        slug     = ident.lower()
        out_dir  = AIRPORTS_DIR / slug
        out_dir.mkdir(exist_ok=True)
        out_file = out_dir / "index.html"

        html = render_airport_page(airport)
        out_file.write_text(html, encoding="utf-8")
        created.append(f"airports/{slug}/index.html")

    print(f"  Generated {len(created)} airport pages in /{AIRPORTS_DIR}/")
    return created


# ─── BUILD SITEMAP ────────────────────────────────────────────────────────────
def build_sitemap(features: list, airport_page_paths: list):
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

    # Static airport pages — real crawlable URLs, highest priority after homepage
    for path in sorted(airport_page_paths):
        # path is like "airports/kpwt/index.html" → URL is BASE_URL/airports/kpwt/
        url_path = path.replace("index.html", "")
        add_url(f"{BASE_URL}/{url_path}", priority="0.8", changefreq="monthly")

    # Hash fragment fallbacks for regions (still useful for internal navigation)
    regions = sorted(set(
        f["properties"].get("region", "")
        for f in features
        if f["properties"].get("region")
    ))
    for region in regions:
        add_url(f"{BASE_URL}/#region/{region.lower()}", priority="0.4", changefreq="monthly")

    tree = ET.ElementTree(urlset)
    ET.indent(tree, space="  ")
    OUT_SITEMAP.write_bytes(
        b'<?xml version="1.0" encoding="UTF-8"?>\n' +
        ET.tostring(urlset, encoding="utf-8", xml_declaration=False)
    )
    print(f"  Wrote {OUT_SITEMAP} with {len(urlset)} URLs.")


# ─── GENERATE JSON-LD ─────────────────────────────────────────────────────────
def build_jsonld(features: list) -> str:
    items = []
    # Closed listings are excluded from structured data entirely.
    open_features = [f for f in features if is_open(f["properties"])]
    for i, f in enumerate(open_features, start=1):
        p    = f["properties"]
        name = p.get("restaurant_name", "")
        if not name:
            continue
        entry = {
            "@type": "FoodEstablishment",
            "name":  name,
        }
        if p.get("notes"):
            entry["description"] = p["notes"]
        if p.get("website"):
            entry["url"] = p["website"]
        city  = p.get("city", "")
        state = p.get("state", "")
        if city or state:
            entry["address"] = {
                "@type":           "PostalAddress",
                "addressLocality":  city,
                "addressRegion":    state,
                "addressCountry":   "US",
            }
        airport_name  = p.get("airport_name", "")
        airport_ident = p.get("airport_ident", "")
        if airport_name or airport_ident:
            entry["containedInPlace"] = {
                "@type":      "Airport",
                "name":       airport_name,
                "identifier": airport_ident,
            }
        items.append({"@type": "ListItem", "position": i, "item": entry})

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
            "@type":           "ItemList",
            "name":            "Fly-In Restaurants at US General Aviation Airports",
            "description": (
                "A curated directory of the best on-field and near-airport restaurants "
                "for pilots across the United States — from classic $100 hamburger diners "
                "to upscale fly-in destinations."
            ),
            "url":             f"{BASE_URL}/",
            "numberOfItems":   len(items),
            "itemListElement": items,
        },
    ]
    return json.dumps({"@context": "https://schema.org", "@graph": graph},
                      ensure_ascii=False, indent=2)


def inject_jsonld(jsonld_str: str):
    if not INDEX_HTML.exists():
        print(f"  index.html not found — skipping JSON-LD injection.")
        return
    html = INDEX_HTML.read_text(encoding="utf-8")
    new_block = '<script type="application/ld+json">\n' + jsonld_str + '\n  </script>'
    pattern   = r'<script type="application/ld\+json">.*?</script>'
    if re.search(pattern, html, flags=re.DOTALL):
        html = re.sub(pattern, new_block, html, flags=re.DOTALL)
        print("  Injected updated JSON-LD into index.html.")
    else:
        html = html.replace("</head>", f"  {new_block}\n</head>", 1)
        print("  Inserted new JSON-LD block into index.html.")
    INDEX_HTML.write_text(html, encoding="utf-8")


# ─── GENERATE CRAWLABLE HTML LIST ────────────────────────────────────────────
def build_seo_html_list(features: list) -> str:
    lines = [
        '<!--\n'
        '  SEO: Hidden restaurant index for search engine crawlers.\n'
        '  Generated at build time by tools/build_geojson.py.\n'
        '  DO NOT edit manually — overwritten on next build.\n'
        '-->',
        '<section id="seo-restaurant-index" aria-hidden="true" '
        'style="position:absolute;left:-9999px;width:1px;height:1px;overflow:hidden;">',
        '  <h1>Airport Restaurants — Fly-In Dining Guide for Pilots</h1>',
        '  <p>Airport Restaurants is a directory of fly-in dining destinations at general '
        'aviation airports across the United States. Browse on-field restaurants, classic '
        '$100 hamburger stops, and the best fly-in meals by state and region.</p>',
        '  <h2>Featured Fly-In Restaurants by State</h2>',
        '  <ul>',
    ]

    airports = group_by_airport(features)
    for ident, airport in airports.items():
        slug      = ident.lower()
        page_url  = f"{BASE_URL}/airports/{slug}/"
        aname     = html_escape(airport["name"])
        city      = html_escape(airport["city"])
        state     = html_escape(airport["state"])
        loc       = f"{city}, {state}" if city and state else (city or state)
        rcount    = len(airport["restaurants"])
        rcount_s  = f"{rcount} restaurant{'s' if rcount != 1 else ''}"

        lines.append(f'    <li>')
        lines.append(f'      <h3><a href="{page_url}">{aname} ({html_escape(ident)}) — {loc}</a></h3>')
        if rcount:
            lines.append(f'      <p>{rcount_s} listed for pilots.</p>')
        else:
            lines.append(f'      <p>Nothing you can fly in for at this airport right now. '
                         f'See the airport page for what closed and when.</p>')
        lines.append(f'      <ul>')
        for r in airport["restaurants"]:
            rname  = html_escape(r.get("restaurant_name", ""))
            rtype  = "On-airport" if r.get("type") == "on-airport" else "Near airport"
            notes  = html_escape(r.get("notes", ""))
            lines.append(f'        <li><strong>{rname}</strong> — {rtype}.'
                         + (f' {notes}' if notes else '') + '</li>')
        lines.append(f'      </ul>')
        lines.append(f'    </li>')

    lines += [
        '  </ul>',
        '  <p>Browse the full interactive map to find fly-in restaurants near any general '
        'aviation airport in the United States. Filter by region, state, or restaurant type. '
        'Subscribe to the <a href="https://airportrestaurants.substack.com">Airport Restaurants '
        'newsletter</a> for in-depth fly-in dining reviews.</p>',
        '</section>',
    ]
    return "\n".join(lines)


def inject_seo_html_list(seo_html: str):
    if not INDEX_HTML.exists():
        print(f"  index.html not found — skipping SEO list injection.")
        return
    html    = INDEX_HTML.read_text(encoding="utf-8")
    pattern = r'<!--\s*SEO: Hidden restaurant index.*?</section>'
    if re.search(pattern, html, flags=re.DOTALL):
        html = re.sub(pattern, seo_html, html, flags=re.DOTALL)
        print("  Updated SEO restaurant list in index.html.")
    else:
        html = html.replace(
            "<script>\nfunction loadScript",
            seo_html + "\n\n<script>\nfunction loadScript", 1
        )
        print("  Inserted SEO restaurant list into index.html.")
    INDEX_HTML.write_text(html, encoding="utf-8")


# ─── MAIN ─────────────────────────────────────────────────────────────────────
def main():
    print("\n=== Airport Restaurants Build ===")

    idx                = load_ourairports_index()
    features, stats    = build_geojson(idx)
    airport_page_paths = build_airport_pages(features)
    build_sitemap(features, airport_page_paths)

    jsonld_str = build_jsonld(features)
    inject_jsonld(jsonld_str)

    seo_html = build_seo_html_list(features)
    inject_seo_html_list(seo_html)

    airports      = group_by_airport(features)
    airport_count = len(airports)
    open_airports = sum(1 for a in airports.values() if a["restaurants"])

    print(f"\nDone. {stats['rows_read']}/{stats['rows_read']} seed rows built "
          f"({stats['dropped']} dropped).")
    print(f"      {stats['open']} open restaurants · {stats['closed']} closed listings retained")
    print(f"      {airport_count} airports ({open_airports} with something open) · "
          f"{len(airport_page_paths)} static pages generated.\n")

    if stats["dropped"]:
        raise SystemExit(f"Build finished with {stats['dropped']} dropped row(s) — see above.")


if __name__ == "__main__":
    main()
