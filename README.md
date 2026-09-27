# Gridlock: where utilities' construction plans collide

Sperry Tech / Shell Hacks 2026 challenge. Compares the public planned transmission projects of
**5 Southeast utilities** &mdash; **Dominion Energy South Carolina**, **Georgia Power**,
**Georgia Transmission Corporation (GTC)**, **Municipal Electric Authority of Georgia (MEAG)** and
**Dalton Utilities** &mdash; finds every pair of projects (from any two of the five) that are within
25 miles of each other, and ranks them as coordination opportunities. GTC, MEAG and Dalton Utilities
are sponsor codes inside Georgia's own ITS Ten-Year Plan filing, split out into their own companies
rather than lumped under Georgia Power or excluded as "partners" &mdash; adding a 6th company is one more
PDF parser plus one line in `build_map.py`'s company registry, nothing else changes.

**Open `gridlock_map.html` in a browser** for the interactive map. Needs internet for the map tiles.

## Per-company coordination radius

Every company defaults to the same 25-mile threshold, but that's a config value, not a
constant baked into the logic: `overlaps.py`'s `COMPANY_MAX_MILES` dict lets any company
declare its own radius (e.g. `{"Dalton Utilities": 45}` gives Dalton Utilities alone a wider
reach). A pair's actual threshold is the **larger** of the two companies' radii, so widening
one company's setting never needs the other side touched. The map picks this up automatically:
the "Max distance" filter's range, the circle drawn around each project, and every "X-mile
radius" label all read the real per-pair threshold (`overlap.maxMi` in the map's data) instead
of assuming 25 for everyone. When every company shares one radius the map still just says
"25-mile radius" for simplicity; once they differ it switches to labelling each circle with its
own number.

## How to read the map

* Pick a card in the ranked list. The map draws a **25-mile circle centred on one project's centre**
  (its letter badge, colored by that project's company). Every other company's project whose centre is
  inside the circle overlaps it. The two selected projects are labelled with their company name, and a
  red line shows the distance between the centres.
* Other companies' projects inside the same circle are drawn too, each with its own numbered badge and
  color, so you can see everything that crosses it.
* **Click any project on the map** to make it the centre: the 25-mile circle is drawn around it and every
  other company's project whose centre is inside is numbered, with distances in the side panel. Click a
  numbered badge to move the centre to that project. Distance is the same both ways, so this finds the
  same pairs as the list, and it also works for projects that overlap nothing.
* **Letters and numbers:** the project at the centre of the circle has a letter badge, one per company
  (D = Dominion, G = Georgia Power, T = GTC, M = MEAG, U = Dalton Utilities). The numbered badges are the
  *other* companies' projects whose centres are inside the circle, each colored by its own company. A
  number only means "within 25 miles, worth looking at for coordination" &mdash; it does not mean the two
  companies already work together.
* A project with two substations is two dots (the substations) joined by a line, colored by company. A
  project with only one location has no line and is a single dot instead (hollow if it overlaps nothing).
  Red glow = the project takes part in an overlap. Dotted line or dashed outline = low-confidence location.
* Filters: maximum distance, time gap, location quality. Tick a company's box under *draw circles
  for* to see its 25-mile circles on every one of its overlapping projects at once; tick several to
  compare companies' reach side by side.
* **Order by** re-sorts the ranked list: best match (the default 70% distance / 30% schedule score,
  shown as a bar on each card so the ranking is visible at a glance, not just implied by position),
  distance, time gap, or soonest in-service date.
* The **&#10094; button** in the header folds the whole side panel away so the map has the full
  window; a small tab on the map's left edge (**&#10095;**) brings it back.

## Result

| | |
|---|---|
| Projects parsed | 44 Dominion + 208 Georgia-filing (138 Georgia Power, 54 GTC, 14 MEAG, 2 Dalton Utilities) |
| Located | 42/44 Dominion, 120/138 Georgia Power, 47/54 GTC, 13/14 MEAG, 2/2 Dalton Utilities (224 of 252 total) |
| Overlaps (centres < 25 mi), all 10 company pairs checked | **457 pairs**, which merge into **57 distinct opportunities** |
| Dominion x Georgia Power alone (the original 2-company scope) | 55 pairs -> 7 opportunities, unchanged by adding the other 3 companies |
| Closer than 10 mi | 116 pairs (35 under 5 mi) |
| Close in *both* distance and time (< 10 mi and <= 1 yr) | 38 pairs |

Most of the volume comes from the four Georgia-filing companies overlapping **each other**: GTC in
particular builds statewide alongside Georgia Power, so it alone accounts for the majority of pairs.
Dominion, the one out-of-state neighbor, only overlaps Georgia Power &mdash; its projects never land
within 25 mi of a GTC, MEAG or Dalton Utilities project. The Dominion/Georgia-Power overlaps still sit in
two clusters, **Savannah / Hilton Head** (Jasper, Okatie, McIntosh, Goshen) and **Augusta / Thurmond**
(Urquhart, Stevens Creek, Evans, Thomson).

### Top coordination opportunities (duplicates removed)

The 457 pairs are not 457 separate opportunities: sibling projects repeat (the "#5" and "#6" circuits
of Evans - Thurmond, two phases of Stevens Creek - Hooks) and one project can sit near many others. The
ranked list therefore merges sibling projects into one corridor (same utility, identical end points and
location) and lets each corridor appear in **at most one** opportunity, best pair first. The other nearby
pairs stay attached to it as "related". Result: **57 opportunities**; the map and workbook both show the
top 10 by default with a "show all" toggle. The workbook's `overlaps` sheet lists every pair, one row each;
`top_opportunities` is the ranked list.

| # | mi apart | days apart | conf | Company A | Project A | Company B | Project B |
|---|---|---|---|---|---|---|---|
| 1 | 0.0 | 0 | high | Georgia Power | Dresden Line Protective Relaying | GTC | Dresden 500kV Bus Expansion |
| 2 | 0.0 | 31 | medium | Georgia Power | CC - Summer Lake - Villa Rica 230kV Rebuild | GTC | Hickory Level - Villa Rica 230kV Line Reconductor |
| 3 | 0.5 | 0 | medium | Georgia Power | Winder Primary 230kV Bus 1-2 Parallel Bus-Tie | GTC | Shoal Creek - South Hall 230kV Rebuild |
| 4 | 2.0 | 0 | medium | Georgia Power | Echeconnee-Wellston 115kV Rebuild | GTC | Bonaire Pri-Echeconnee 115kV Partial Rebuild |
| 5 | 0.0 | 365 | medium | Georgia Power | Adamsville - Buzzard Roost 230kV Rebuild | GTC | Adamsville - Buzzard Roost 230kV Rebuild |
| 6 | 4.0 | 0 | medium | GTC | Bonaire Pri-Echeconnee 115kV Partial Rebuild | MEAG | Aultman Road - Bonaire Primary 115kV Rebuild |
| 7 | 3.6 | 92 | medium | Georgia Power | Palmyra Reactor Removal | GTC | Lizard Lope - Westover 115kV New Line |
| 8 | 0.0 | 730 | medium | GTC | SKC 115kV Bus and Jumper Replacement | MEAG | Alcovy Road - SKC 115kV Reconductor |
| 9 | 0.0 | 1278 | high | Georgia Power | Gordon-Sandersville #1 115kV Line Rebuild | GTC | Gordon - Sandersville #1 115kV Line Rebuild |
| 10 | 2.2 | 366 | medium | Georgia Power | CC - Villa Rica Upgrades | GTC | Douglasville - Villa Rica 230kV Rebuild |

The original 2-company opportunities (Jasper - Okatie / McIntosh - Purrysburg and the rest, see
`Projects_Overlaps.xlsx` or run the pipeline) still rank lower here: they're real distances of several
miles, while several GTC/Georgia-Power pairs above sit at 0.0-2.0 mi with matching in-service windows,
outranking them under the same distance + schedule scoring.

## How to run it

```
pip install -r requirements.txt
python run_all.py "path/to/Project Listings"     # folder holding "Dominion Energy/" and "Georgia Power/" PDFs
```

Only 2 PDFs are needed: GTC, MEAG and Dalton Utilities are sponsor codes already inside the Georgia
Power PDF's ITS Ten-Year Plan filing (Table 2's sponsor column), split into their own companies by
`parse_projects.py` rather than requiring a separate source document.

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
| `overlaps.py` | Centre = midpoint of the two located end points; haversine distance; overlap if < 25 mi; time gap in days; score = 70 % distance + 30 % schedule; rough shared-corridor / shared-site value; merges duplicates into opportunities. Checks every pair of the companies present in the data (`itertools.combinations`), so a 6th company needs no changes here. |
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

The four Georgia-filing companies' costs are REDACTED in the IRP, so estimates use whichever side of a
pair actually published a cost as a floor &mdash; in practice, always the Dominion side today. A pair is a
*shared corridor* (lines run within 3 mi of each other), a *shared site* (end points within 3.5 mi),
or just *nearby*. Savings = 5-12 % of the shared cost, faded to zero as the in-service gap
reaches 3 years. Right-of-way land savings are counted only when a project is a new build.
All assumptions are listed in `overlaps.py` (`ASSUMPTIONS`), in the workbook's `assumptions`
sheet, and under every estimate in the map. These are order-of-magnitude figures, not quotes.

## Location guard: implausible spans

A project's two end points are matched by name, and a name can match the wrong place: "GRADY" is both a
substation and a county 200 miles away. `geocode.py` already guarded against this by throwing away an end
point when the resulting "line" spanned more than `MAX_LINE_MI` (60 miles) — but only when exactly one of
the two ends was a weak, place-level match:

```python
weak = [i for i, r in enumerate(result) if r["how"] != "osm_name"]
if span > MAX_LINE_MI and len(weak) == 1:       # before
```

The two worst locations in the dataset had **both** ends place-level, so `len(weak)` was 2 and the check
skipped them — the exact cases it exists to catch walked straight through:

| Project | Span | What went wrong |
|---|---|---|
| GPC_170 GTC: POND FORK - MIDWAY 115KV LINE | 219 mi | Pond Fork in north Georgia, Midway on the coast |
| GPC_70 GRADY-WEST END 115KV REBUILD | 198 mi | Grady County in far south Georgia, West End in Atlanta |

The guard now fires whenever any end is weak. With one weak end, that end is dropped. With two, the span
proves at least one is wrong but not which, so both are dropped:

```python
if span > MAX_LINE_MI and weak:                 # after
    for w in weak:
        result[w] = {... "how": "discarded_implausible_span"}
```

An unlocated project is better than a 200-mile phantom line, because a phantom line has two wrong end
points that can each invent overlaps.

**Before and after, on the real filings** (pair/opportunity counts are for Dominion x Georgia Power,
the two companies this guard was tested against before the other three were split out):

| | Before | After |
|---|---|---|
| Projects located | 226 | 224 |
| Guard fired | 10 end points | 14 end points |
| Projects spanning > 100 mi | 2 | **0** |
| Overlapping pairs (Dominion x Georgia Power) | 55 | 55 |
| Distinct opportunities (Dominion x Georgia Power) | 7 | 7 |

The headline numbers do not move: those two projects were never close enough to a Dominion project to
form a pair, so they were drawing fiction on the map without affecting the ranking. The two projects lost
are now reported honestly as unlocated rather than placed 200 miles wrong.

Checked by `test_gridlock.py`, which asserts no located project spans more than 120 miles.

## Limits to keep in mind

* **Most overlaps involve dates that have already passed.** The source plans are 2024-2025 vintage, and
  most pairs' in-service dates are already behind the current date. There is no "upcoming only" filter yet.
* Locations are matched by **name**, not surveyed. The map and workbook show each pair's confidence
  (high / medium / low) so this is visible rather than hidden.
* Projects are drawn as **straight lines** between their two substations; real routes are longer.
* Two projects are dropped by the implausible-span guard above rather than placed wrongly; they count
  among the unlocated.
* 28 of the 252 parsed projects could not be located at all (18 Georgia Power, 7 GTC, 2 Dominion, 1 MEAG).
  "Rice Hope" is close to Savannah but has no public coordinates, so it is left unlocated instead of guessed.
* Georgia dates are the plan's *need date*; Dominion dates are *planned in-service*.
* GTC, MEAG and Dalton Utilities overlap Georgia Power and each other frequently (they all build within
  Georgia), but none of them overlap a Dominion project &mdash; Dominion's only cross-company neighbor is
  Georgia Power.
* Only public filings were used.

## To do / ideas for later

* **A genuinely new PDF source**, not just splitting sponsor codes already in the Georgia filing: Santee
  Cooper and Duke Energy Carolinas/Progress both publish public integrated resource plans with a
  transmission-planning section and are geographically adjacent to Dominion's SC territory, so they're
  the most likely candidates to produce real new overlaps rather than just more Georgia-internal ones.
* **A 6th+ company shouldn't need UI changes** beyond `build_map.py`'s `COMPANY_STYLE` registry (color +
  short name + centre-badge letter) and a parser emitting the standard project schema; worth confirming
  once a 6th real source is added.
