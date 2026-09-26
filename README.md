# GridLock

Interactive map of transmission projects and potential coordination opportunities
across Georgia and South Carolina. Open `gridlock_map.html` in a browser; an
internet connection is required for Leaflet and OpenStreetMap tiles.

## Run locally

From this project directory, with Python 3.10 or newer:

```sh
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python overlaps.py
python build_map.py
```

Edit `map_template.html` to change the interface, then run `build_map.py` to
regenerate `gridlock_map.html`. Project data is embedded in the generated HTML.
Click a hotspot to expand its pairs, or select a ranked pair to inspect it.
The list supports Tab and Enter/Space. Filters control distance and verification.

## Data pipeline

- `projects.csv`: source project records, coordinates and verification status.
- `geocode.py`: optional OSM matching; updates `projects.csv` and writes review
  CSVs. Run `python geocode.py` from this directory. `--redo` retries automatic
  matches; sponsor-verified and manually verified rows are preserved.
- `overlaps.py`: compares Dominion SC with Georgia Power using project centers,
  retaining pairs strictly under 25 miles and ranking geography (70%) and
  in-service timing (30%). ITS partners are excluded by default.
- `build_map.py`: builds the map from `projects_with_overlaps.csv` and `overlaps.csv`.

Centers use complete, valid endpoint coordinates. One located endpoint is enough;
projects without a usable endpoint are omitted from the map. In-service dates
are required for ranking. Automatic location matches still need human review.
Lines depict straight connections between endpoints, not surveyed routes.
Coordination savings are illustrative; see `ESTIMATE.md` for assumptions.

## Checks

```sh
python -m unittest discover -s tests -v
```
