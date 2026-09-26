# Gridlock: where two utilities' construction plans collide

Sperry Tech / Shell Hacks 2026 challenge. Compares the public planned transmission projects of
**Dominion Energy South Carolina** and **Georgia Power**, finds the pairs that are within 25 miles of
each other, and ranks them as coordination opportunities.

**Open `gridlock_map.html` in a browser** for the interactive map. Needs internet for the map tiles.

## How to read the map

* Pick a card in the ranked list. The map draws a **25-mile circle centred on the Dominion project**
  (blue). A Georgia Power project (orange) whose centre is inside the circle overlaps it. The two
  projects are labelled with their company name, and a red line shows the distance between the centres.
* Other Georgia Power projects inside the same circle are drawn too, so you can see what crosses it.
* Red glow around a project = it takes part in an overlap. Dotted line = low-confidence location.
* Filters: maximum distance, time gap, location quality. Tick *draw the 25-mile circle for every
  overlapping Dominion project* to see all the circles at once.

## Result

| | |
|---|---|
| Projects parsed | 44 Dominion + 208 Georgia (138 Georgia Power, 70 from its ITS partners GTC / MEAG / DU) |
| Located | 42 of 44 Dominion, 117 of 138 Georgia Power |
| Overlaps (centres < 25 mi) | **55 pairs**: 8 Dominion projects x 17 Georgia Power projects, which merge into **7 distinct opportunities** |
| Closer than 10 mi | 13 pairs (3 under 5 mi) |
| Close in *both* distance and time (< 10 mi and <= 1 yr) | 3 pairs |

Most projects do **not** overlap: 82 % of Dominion and 88 % of Georgia Power projects have no
neighbour inside 25 miles. The overlaps sit in two clusters, **Savannah / Hilton Head**
(Jasper, Okatie, McIntosh, Goshen) and **Augusta / Thurmond** (Urquhart, Stevens Creek,
Evans, Thomson).

### Top coordination opportunities (duplicates removed)

The 55 pairs are not 55 separate opportunities: several projects repeat (the "#5" and "#6" circuits
of Evans - Thurmond, two phases of Stevens Creek - Hooks) and one Dominion project can sit near many
Georgia projects. The ranked list therefore merges sibling projects into one corridor (same utility,
identical end points and location) and lets each corridor appear in **at most one** opportunity,
best pair first. The other nearby pairs stay attached to it as "related". Result: **7 opportunities**.
The workbook's `overlaps` sheet still lists every pair, one row each; `top_opportunities` is the ranked list.

| # | mi apart | days apart | Dominion project | Georgia Power project | notes |
|---|---|---|---|---|---|
| 1 | 5.7 | 152 | Jasper - Okatie 230 kV #2: Construct | McIntosh - Purrysburg 230 kV reactors | $0.26-0.61M avoided (shared substation area) |
| 2 | 3.5 | 578 | Urquhart - Aiken PSA 46 kV rebuild | Fenwick St - Sand Bar Ferry 115 kV | low-confidence location |
| 3 | 4.1 | 3074 | Hooks - Thurmond 115 kV tie rebuild | Evans Primary - Thurmond Dam 115 kV (#5, #6 merged) | same terminal, but ~8 yr apart so no savings |
| 4 | 17.6 | 0 | Okatie - Bluffton 115 kV rebuild | Deptford - Magnolia 115 kV reconductor | same in-service date, but far apart |
| 5 | 15.0 | 882 | Okatie 230-115 kV substation | Goshen (SAV) - Kraft 115 kV rebuild | |
| 6 | 16.4 | 1389 | Urquhart - Toolebeck 115 kV rebuild | Goshen Area Strategic Solution | high-confidence location |
| 7 | 16.6 | 3652 | Stevens Creek - Hooks 115 kV (2 phases merged) | Evans Primary - Thomson Primary 115 kV rebuild | |

## How to run it

```
pip install -r requirements.txt
python run_all.py "path/to/Project Listings"     # folder holding "Dominion Energy/" and "Georgia Power/" PDFs
```

That is the only setup (Python 3.9+). Everything happens in memory, so there are no intermediate files.
`data/` holds saved copies of the OpenStreetMap downloads (substations, state outlines, place lookups) so
the answer is the same every time; anything missing is downloaded automatically (the first run without
them takes a few minutes because place lookups are limited to one per second, and a handful of
low-confidence place-name guesses can shift). `python run_all.py --refresh` forces a fresh download.
The run prints the ranked opportunities in the terminal and writes `gridlock_map.html` and
`Projects_Overlaps.xlsx`. You don't need to run anything to *view* the results: open either file.

**What is in the repo:** the two deliverables (`gridlock_map.html`, `Projects_Overlaps.xlsx`), the code
(`run_all.py`, 8 scripts, `map_template.html`, `requirements.txt`) and the 3 saved downloads in `data/`.

| Script | What it does |
|---|---|
| `parse_projects.py` | Reads the two PDFs (PyMuPDF) into project tables. Georgia project detail sections give name / TEAMS # / need date / description; Table 2 gives the sponsor and transmission zone. |
| `fetch_osm.py`, `fetch_border.py`, `geocode.py` | One bulk Overpass query for every GA/SC substation and plant, then name-matches each project's two end points. Unnamed substations are found by geocoding the place name and snapping to the nearest voltage-matched substation. |
| `verify.py` | Grades every location high / medium / low / none and rejects false matches (see below). |
| `overlaps.py` | Centre = midpoint of the two located end points; haversine distance; overlap if < 25 mi; time gap in days; score = 70 % distance + 30 % schedule; rough shared-corridor / shared-site value; merges duplicates into opportunities. |
| `build_map.py`, `export_xlsx.py` | `gridlock_map.html` and `Projects_Overlaps.xlsx` (same columns as the starter workbook plus confidence and estimate columns). |

### Confirming matches (Part 2)

A similarly named substation in the wrong place is the common false match, so every match is checked:

* **State check**: Dominion projects must be in South Carolina and Georgia Power's in Georgia, using
  the real state outlines (facilities on the Savannah River count as either).
* **Span check**: a line whose two ends are > 60 mi apart drops the weaker end.
* **Zone check**: Georgia Power lists a transmission zone per project; a match > 120 mi from where
  the rest of that zone sits is rejected (caught "Riverside", "Tomochichi", "Grady", "Glenwood").
* **Customer-connection projects** ("CC - ...") are named after customer sites, so they are capped at *low*.
* **Description check by hand**: `OVERRIDES` in `verify.py` holds the matches re-read against the PDF
  text, each with the quote that justifies it (Fenwick St / East Augusta Jct, Big Ogeechee).
* Ambiguous names are resolved with the description: "Goshen (SAV) - Kraft" is the Savannah-area
  Goshen; "Goshen - Vogtle corridor" is the Augusta-area one.

Sanity check against the starter workbook: the same pairs come out at 4.09 mi (Hooks - Thurmond vs
Evans - Thurmond), 8.01 mi (Stevens Creek - Hooks vs Evans - Thurmond) and 5.65 mi (Jasper - Okatie vs
McIntosh - Purrysburg).

### Rough cost / impact estimate (bonus)

Georgia costs are REDACTED in the IRP, so estimates use the Dominion cost as a floor. A pair is a
*shared corridor* (lines run within 3 mi of each other), a *shared site* (end points within 3.5 mi),
or just *nearby*. Savings = 5-12 % of the shared cost, faded to zero as the in-service gap
reaches 3 years. Right-of-way land savings are counted only when a project is a new build.
All assumptions are listed in `overlaps.py` (`ASSUMPTIONS`), in the workbook's `assumptions`
sheet, and under every estimate in the map. These are order-of-magnitude figures, not quotes.

## Limits to keep in mind

* **Most overlaps involve dates that have already passed.** Only 4 of the 55 pairs have both in-service
  dates after 2026-09-26; the source plans are 2024-2025 vintage. There is no "upcoming only" filter yet.
* Locations are matched by **name**, not surveyed. 1 of 55 overlaps is *high* confidence, 49 *medium*
  (usually one end point of two located), 5 *low* (street / place level). The map and workbook show this.
* Projects are drawn as **straight lines** between their two substations; real routes are longer.
* 21 Georgia Power projects and 2 Dominion projects could not be located. "Rice Hope" is close to
  Savannah but has no public coordinates, so it is left unlocated instead of guessed.
* Georgia dates are the plan's *need date*; Dominion dates are *planned in-service*.
* The ITS-partner (GTC / MEAG / DU) projects produce no overlaps with Dominion and are left out of the
  workbook and the map.
* Only public filings were used.
