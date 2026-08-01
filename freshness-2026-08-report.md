# Airport Restaurants Map — Freshness Pass, August 2026

Acting on the monthly freshness check posted 2026-07-06. Every flagged listing was
re-verified independently before anything was changed. Closures are recorded, not
deleted, per your instruction.

**Result:** 43 open restaurants at 43 airports · 11 closed listings retained · 0 rows
dropped · 47 static pages generated. Branch `freshness-2026-08`, one commit.

---

## 1. Closures confirmed — all 10

Each is marked `status: closed` with a date and a reason. The listing text stays.

| Airport | Restaurant | Closed | Reason |
|---|---|---|---|
| 11R | Southern Flyer Diner | Aug 2020 | COVID dine-in shutdown. A successor (Dreamliner Diner) ran Dec 2021 – Dec 2022; space now under renovation. |
| KLUK | Sky Galley | Sep 20, 2020 | Closed after decades at Lunken. Terminal vacant since; boutique hotel with restaurant under construction as of 2026. |
| KOXC | Restaurant 121 | Mar 16, 2020 | Connecticut COVID dine-in ban, never reopened. |
| KWWD | Flight Deck Diner | Mar 14, 2026 | Fire-suppression leak caused structural and electrical damage to the WWII tower building; lease terminated. |
| 6B6 | Nancy's Air Field Café | Spring 2023 | Nancy McPherson retired after running it since 1996. |
| 7FL6 | The Downwind Café | Jun 2023 | Sold abruptly; new owners remodeled and rebranded. |
| KFOK | The Apron Cafe | Oct 2020 | Chef Phil Capobianco took over and rebranded. |
| KGMU | Runway Café | May 26, 2025 | Airport Commission chose not to renew the lease after 15 years. |
| KBOW | Runways at Bartow | 2024 | Ceased operations, no public announcement. |
| KOCF | Tailwind Café | ~2019 | Airport re-tenanted with a full-service concept. |

**KWWD is worth noting:** capemayairport.com still advertises the Flight Deck Diner as
open daily 7:30–2:00. It closed in March. Aggregators are likely still wrong on this one.

## 2. Watch item — resolved as OPEN

**Flo's Airport Café (KCNO)** is open and the closure rumour does not hold up. San
Bernardino County still lists it as a tenant; Yelp went from 812 to 826 reviews between
February and July 2026. The construction that probably started the rumour is the City of
Chino's **Pine Avenue** widening, south of the field — not Merrill Avenue, which is the
access road. County work at the airport itself is signage and perimeter fencing.

One caveat: sources disagree on hours (Tue–Sun 6AM–3PM vs. 5:30AM–8PM daily). The Monday
closure is the detail most likely to burn a reader. Worth a call to (909) 597-3416.

## 3. Successors added — 7 fields still have food

The checker said 4 fields had successors. There are 7.

| Airport | New restaurant | Notes |
|---|---|---|
| KOXC | Volo | Same terminal space, runway views, dinner Thu–Sat. |
| 6B6 | Fourth & Field | Farm-to-table, opened Sep 2023, new operator. |
| 7FL6 | Fly In Cafe | **See flag below.** |
| KFOK | Cafe Volo | Under the tower, breakfast/lunch, seasonal dinner. |
| KGMU | Hangar 28 Kitchen & Events | Opened Jul 8, 2026 — three weeks old. |
| KBOW | Tantrums Flightside Cafe | Old Florida menu, 7AM–2PM Mon–Sat. |
| KOCF | Elevation 89 | Full restaurant and bar, 11AM–9PM. Lunch/dinner, not a breakfast stop. |

Two fields have no restaurant at all right now: **11R** (under renovation) and **KLUK**
(terminal being converted to a hotel with a restaurant). Both have announced plans — worth
re-checking in 6–12 months.

## 4. New listings added — all 3

- **Starduster Cafe (7S5)**, Independence OR — breakfast-forward diner, ~200 ft from free
  tie-downs, kitchen closes at 2PM. Clean fly-in.
- **Buzz Inn Steakhouse (S43)**, Harvey Field WA — lease secured through Sep 2027, courtesy
  car, deck over the grass strip. Note 15L/33R is 2,672 × 36 ft and the turf parallel is
  closed Nov–May.
- **The Airplane Restaurant (KCOS)** — tagged **near-airport**. It is outside the fence on
  Newport Rd, about a 10-minute walk from the FBOs. Real, but not a taxi-up.

## 5. Bugs found while editing — neither was in the checker's report

**15 of 44 listings had truncated descriptions.** Unquoted commas in the `notes` column
split the field, so everything after the first comma was being discarded at build time.
The Hub at Gig Harbor, for example, was publishing as *"On-field restaurant right at Tacoma
Narrows with runway views."* — losing the burgers, Cajun tots, Harmon beers and the hours.
All 15 rejoined and re-quoted.

**One listing was invisible.** McGehee Catfish (T40) was silently skipped by every build
because the ident is no longer in OurAirports — that is why the checker kept reporting
43 of 44. Its record also had the wrong city and state (Cresson TX; it is Marietta OK).
The build now takes optional `lat`/`lon` overrides, warns loudly on any dropped row, and
reports the count in the summary line, so this class of bug can't hide again.

## 6. How closures behave now

Blank status means open, so nothing older breaks.

- Closed listings **never** count toward restaurant totals and **never** appear in JSON-LD.
- They are hidden from every map view except a new **⛔ Closed** filter pill.
- Airport pages list them under *"Previously at this Airport"* with the date and reason.
- An airport with nothing open gets an honest meta description instead of advertising
  dining that isn't there, and a grey marker rather than a knife-and-fork.

---

## Decisions for you

1. **Fly In Cafe (7FL6)** — I tagged it `near-airport`. Spruce Creek is a private
   residential airpark with a strict invitee policy, and the restaurant's own site says
   the runway may not be used to visit it. Physically it is on the field; practically no
   reader can fly in. Tagging it `on-airport` would put it under the "On Field" filter and
   break the promise that filter makes. Say the word if you'd rather flip it.
2. **McGehee Catfish (T40)** — the restaurant is open but the strip has been closed
   indefinitely since Feb 2020, so I marked the listing closed *as a fly-in destination*
   with that explanation. The alternative is re-pointing it to Love County (1F0) as a
   near-airport listing. Your call.
3. **Phone confirmations worth making** — Cafe Volo (631) 998-3573 has the weakest recency
   evidence of the seven successors; Hangar 28 is three weeks old and its hours will move;
   Flo's (909) 597-3416 for the hours discrepancy.

## Applying the branch

The sandbox has no GitHub push credentials, so the work is delivered as a patch:

```bash
cd C:\DEV\airport-restaurants-map
git checkout -b freshness-2026-08
git am < freshness-2026-08.patch
python tools/build_geojson.py   # optional — output is already committed
```

Or with the bundle, which carries the commit as-is:

```bash
git fetch /path/to/freshness-2026-08.bundle freshness-2026-08:freshness-2026-08
git checkout freshness-2026-08
```
