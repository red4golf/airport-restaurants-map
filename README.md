# Airport Restaurants Map

An interactive directory of restaurants at and near general aviation airports across the United States. Built for pilots who want to find their next fly-in meal.

**Live site:** https://red4golf.github.io/airport-restaurants-map/
**Newsletter:** https://airportrestaurants.substack.com

---

## What This Is

A GitHub Pages-hosted map that loads from `data/restaurants.geojson`. A Python build script regenerates the GeoJSON (and a `sitemap.xml`) from a simple CSV file — no database, no backend, no cost.

Features:
- Interactive Leaflet map with airport pins (click to see all restaurants at that airport)
- Sidebar with search, type filter (on-field / near airport), region filter
- Detail panel with notes, website link, and direct link to Substack review
- Reviewed badge on any entry with a Substack post linked
- Road / Topo / Satellite map toggle
- Submit a Restaurant modal for community contributions
- JSON-LD structured data for Google indexing
- Auto-generated `sitemap.xml` with entries for every restaurant, airport, and region

---

## Quick Start (First Deploy)

1. Fork or clone this repo
2. Run the build script locally (see below) to generate `data/restaurants.geojson` and `sitemap.xml`
3. Commit and push everything
4. In GitHub: **Settings → Pages → Source: Deploy from branch → main (root)**
5. Your site will be live at `https://YOUR_USERNAME.github.io/YOUR_REPO/`

---

## Adding or Editing Restaurants

All restaurant data lives in one file:

```
data/restaurants_seed.csv
```

### CSV Columns

| Column | Required | Description |
|---|---|---|
| `restaurant_name` | ✅ | Full name of the restaurant |
| `airport_ident` | ✅ | ICAO (e.g. `KPWT`) or FAA LID (e.g. `0S9`) — must match OurAirports |
| `airport_name` | | Human-readable airport name |
| `city` | | City (falls back to OurAirports municipality) |
| `state` | | Two-letter state abbreviation |
| `type` | | `on-airport` or `near-airport` |
| `region` | | Any label: `PNW`, `SoCal`, `Midwest`, `FL`, etc. |
| `source` | | Where you found it: `Substack review`, `Seed list`, `Submitted`, etc. |
| `website` | | Restaurant website URL (optional) |
| `substack_post` | | Full URL to the Substack review post (optional — enables ✉ Reviewed badge) |
| `notes` | | 1–2 sentence description shown in the detail panel (optional but recommended) |

### Example Row

```csv
Amelia's Hangar Restaurant and Lounge,KPWT,Bremerton National Airport,Bremerton,WA,on-airport,PNW,Substack review,https://www.ameliashangarrestaurant.com,https://airportrestaurants.substack.com/p/amelias-hangar-restaurant-and-lounge-d29,Amelia Earhart-themed restaurant inside a plane hangar. American classics with generous portions. Tue–Thu 6AM–8PM · Fri–Sat 6AM–9PM · Sun 6AM–8PM.
```

### Finding the Right Airport Identifier

Use the [OurAirports search](https://ourairports.com/airports/) to look up the correct identifier. ICAO codes (e.g. `KPWT`) work for towered airports; FAA LIDs (e.g. `0S9`) work for smaller fields. If the build script reports a "missing ident", double-check against OurAirports.

---

## Running the Build Script

The build script does three things:
1. Fetches current airport coordinates from OurAirports
2. Generates `data/restaurants.geojson`
3. Generates `sitemap.xml`

### Locally

```bash
python tools/build_geojson.py
```

Then commit and push:

```bash
git add data/restaurants.geojson sitemap.xml
git commit -m "Add [restaurant name]"
git push
```

GitHub Pages will redeploy automatically within ~30 seconds.

### Via GitHub Actions (Automated)

The workflow at `.github/workflows/build_geojson.yml` runs automatically every Sunday at 09:15 UTC. You can also trigger it manually:

1. Go to your repo on GitHub
2. Click **Actions → Build GeoJSON + Sitemap**
3. Click **Run workflow**

The action commits the updated files directly to `main`.

---

## Submitting a Restaurant (Community)

The map includes a "Submit a Restaurant" form. To wire it up for real email delivery:

1. Create a free account at [Formspree.io](https://formspree.io)
2. Create a new form and copy your Form ID (looks like `xpzgkwrb`)
3. In `index.html`, find the comment `// TODO: wire to Formspree` and replace with:

```javascript
const formData = new FormData();
formData.append('restaurant', document.getElementById('f-name').value);
formData.append('airport', document.getElementById('f-ident').value);
formData.append('location', document.getElementById('f-loc').value);
formData.append('type', document.getElementById('f-type').value);
formData.append('notes', document.getElementById('f-notes').value);
formData.append('email', document.getElementById('f-email').value);

fetch('https://formspree.io/f/YOUR_FORM_ID', {
  method: 'POST',
  body: formData,
  headers: { 'Accept': 'application/json' }
}).then(() => {
  alert('Thanks! Submitted for review. ✈');
  overlay.classList.remove('open');
});
```

---

## SEO

The site includes:
- Meta title, description, and Open Graph tags
- JSON-LD `WebSite` schema with `SearchAction` (enables Google Sitelinks search)
- JSON-LD `ItemList` of all restaurants as `FoodEstablishment` entries
- Auto-generated `sitemap.xml` submitted to Google Search Console

To submit your sitemap to Google after first deploy:
1. Go to [Google Search Console](https://search.google.com/search-console)
2. Add your property (`https://red4golf.github.io/airport-restaurants-map/`)
3. Go to **Sitemaps** and submit: `https://red4golf.github.io/airport-restaurants-map/sitemap.xml`

---

## Roadmap

- [ ] Formspree integration for live form submissions
- [ ] Custom domain (`airportrestaurants.com`)
- [ ] Per-restaurant slug pages (Astro or Eleventy static site generator)
- [ ] Per-airport guide pages (dining + fuel + FBO info)
- [ ] Featured listing monetization
- [ ] Google Sheet as live data source via Make.com

---

## Tech Stack

- [Leaflet.js](https://leafletjs.com/) — interactive maps
- [CartoDB](https://carto.com/) / [OpenTopoMap](https://opentopomap.org/) / [Esri](https://www.esri.com/) — tile layers
- [OurAirports](https://ourairports.com/) — airport coordinates (open data)
- [GitHub Pages](https://pages.github.com/) — free static hosting
- [GitHub Actions](https://github.com/features/actions) — automated builds
- Python 3 (stdlib only, no dependencies to install)

---

*Built to complement the [Airport Restaurants newsletter](https://airportrestaurants.substack.com) by Charles Einarson.*
