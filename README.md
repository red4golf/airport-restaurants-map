# Airport Restaurants Map (Wargame)

This is a **static GitHub Pages** Leaflet map that loads pins from `data/restaurants.geojson`.

It also includes an optional **GitHub Actions** workflow that runs a Python script to rebuild the GeoJSON
from `data/restaurants_seed.csv` using airport lat/lon from OurAirports.

## Quick Start (GitHub Pages)

1. Create a new GitHub repo (public is easiest).
2. Upload this package contents to the repo root.
3. In GitHub: **Settings → Pages**
   - Source: Deploy from a branch
   - Branch: `main` (root)
4. Your site will be at:
   `https://YOUR_USERNAME.github.io/YOUR_REPO/`

## Add / Edit Restaurants

Edit:
- `data/restaurants_seed.csv`

Fields you’ll likely change:
- `restaurant_name`
- `airport_ident` (ICAO like `KCMA`, or FAA/LID like `0S9`)
- `type` (`on-airport` or `near-airport`)
- `region` (any label you want: `PNW`, `SoCal`, `TX`, etc.)
- `website`, `substack_post` (optional links)

## Build the GeoJSON (Option A: locally)

Run:
```bash
python tools/build_geojson.py
```

Then commit + push the updated `data/restaurants.geojson`.

## Auto-build with GitHub Actions (Option B: recommended)

This repo includes:
- `.github/workflows/build_geojson.yml`

It will:
- run weekly (and you can also run it manually)
- regenerate `data/restaurants.geojson`
- commit + push changes automatically

If your repo is public, Actions are effectively free for this use case.

## Notes

- GitHub Pages is static hosting; Python runs only in Actions (or your own machine), not in the browser.
- Leaflet uses OpenStreetMap tiles (no API key).
