"""Fetch the real Georgia and South Carolina outlines (OpenStreetMap via Nominatim) so 'which
state / which side of the Savannah River is this point on?' is answered from data rather than a
hand-drawn line.

Run:  python fetch_border.py   ->  data/state_borders.json  ({"GA": rings, "SC": rings}, [lon, lat])
"""
import time
import json
import sys

import requests

URL = "https://nominatim.openstreetmap.org/search"
QUERY = {"GA": "Georgia, United States", "SC": "South Carolina, United States"}


def fetch(name):
    params = {"q": name, "featureType": "state", "countrycodes": "us", "format": "jsonv2",
              "polygon_geojson": 1, "polygon_threshold": 0.0004, "limit": 1}
    r = requests.get(URL, params=params, timeout=60,
                     headers={"User-Agent": "gridlock-hackathon/1.0 (sperry tech shell hacks 2026)"})
    r.raise_for_status()
    res = r.json()[0]
    geo = res["geojson"]
    polys = geo["coordinates"] if geo["type"] == "MultiPolygon" else [geo["coordinates"]]
    rings = sorted((p[0] for p in polys), key=len, reverse=True)      # outer ring of each polygon
    print(res["display_name"], "| polygons:", len(rings), "| mainland points:", len(rings[0]))
    return rings


def main(out="data/state_borders.json"):
    borders = {}
    for code, name in QUERY.items():
        borders[code] = fetch(name)
        time.sleep(1.2)
    json.dump(borders, open(out, "w"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
