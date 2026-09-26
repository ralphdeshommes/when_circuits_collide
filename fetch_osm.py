"""Pull every substation / power plant in the GA + SC region from OpenStreetMap (Overpass API).

One bulk query (as the guide recommends) instead of one lookup per project. Names are
matched against project endpoints later in geocode.py.

Run:  python fetch_osm.py      ->  data/osm_power.json
"""
import json
import sys
import time

import requests

# south, west, north, east: covers Georgia + South Carolina
BBOX = "30.3,-85.7,35.3,-78.4"
QUERY = f"""
[out:json][timeout:240];
(
  nwr["power"="substation"]({BBOX});
  nwr["power"="plant"]({BBOX});
  nwr["power"="generator"]["name"]({BBOX});
);
out tags center;
"""
ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]


def main(out_path="data/osm_power.json"):
    for url in ENDPOINTS:
        try:
            print("querying", url, flush=True)
            r = requests.post(url, data={"data": QUERY}, timeout=300,
                              headers={"User-Agent": "gridlock-hackathon/1.0"})
            r.raise_for_status()
            data = r.json()
            els = data.get("elements", [])
            print("got", len(els), "elements")
            if els:
                with open(out_path, "w", encoding="utf-8") as f:
                    json.dump(data, f)
                return 0
        except Exception as e:  # try the next mirror
            print("failed:", e, file=sys.stderr)
            time.sleep(3)
    return 1


if __name__ == "__main__":
    sys.exit(main())
