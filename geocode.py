"""
GridLock - fill in missing coordinates from OpenStreetMap

What it does (Part 1 of the sponsor's Finding_Real_Locations_Guide):
  1. ONE Overpass query PER STATE downloads every substation / power plant
     inside that state's official boundary and caches it (so you never
     re-download). Querying by boundary, not by bounding box, means a
     Florida substation can never be offered as a match for an SC project.
  2. For each project endpoint with no coordinates, find the OSM feature
     whose name matches, restricted to that project's own state and
     preferring substations run by the right company
  3. Writes projects.csv back with lat/lon filled in, plus a match_a /
     match_b column recording HOW each endpoint was located, and writes
     geocode_review.csv so you can check every auto-match (Part 2)

It never overwrites rows marked sponsor_verified or manually_verified.

Re-running is safe: each endpoint remembers how it was located, so a second
run cannot downgrade a row it already solved, and the review file accumulates
rather than being replaced.

Run:  pip install pandas requests
      python geocode.py
"""

import argparse
import difflib
import json
import math
import os
import re
import time
from datetime import datetime

import pandas as pd
import requests

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
# Overpass rejects the default python-requests User-Agent with 406 Not Acceptable
HEADERS = {"User-Agent": "GridLock/1.0 (Sperry Tech hackathon project)"}
CACHE = "osm_substations.json"
CACHE_VERSION = 3                  # bumped when the query changes; old caches are refetched
REVIEW = "geocode_review.csv"
STATES = {"GA": "US-GA", "SC": "US-SC"}
FUZZY_CUTOFF = 0.88                # how similar a name must be to auto-accept
RETRIES = 4                        # Overpass returns a transient 504 fairly often
CROSS_BORDER_MI = 50               # how close a cross-state match must sit to the other endpoint

OPERATORS = {  # operator tags that count as "the right company" per state
    "SC": ["dominion", "sce&g", "south carolina electric", "desc"],
    "GA": ["georgia power", "southern company", "georgia transmission", "meag",
           "savannah electric", "dalton"],
}
FILLER = r"\b(SUB|SUBSTATION|SS|TS|DS|SWITCHING STATION|SWITCHYARD|PRIMARY|TIE|JCT|JUNCTION|TAP|PLANT|DAM)\b"
UNIT = r"#\s*\d+"                 # 'THURMOND DAM #6' -> 'THURMOND'; \b cannot match before '#'

# How trustworthy each way of locating an endpoint is, worst first. A project's
# location_confidence is the WEAKEST of its located endpoints.
SEVERITY = ["not_found", "auto_ambiguous", "auto_fuzzy", "auto_exact", "preexisting"]
VERIFIED = ("sponsor_verified", "manually_verified")


def normalize(name):
    """'Stevens Creek Sub' and 'STEVENS CREEK' both become 'STEVENS CREEK'."""
    s = str(name).upper().replace("ST.", "SAINT")
    s = re.sub(r"\bST\b", "SAINT", s)      # 'St George' == 'Saint George Substation'
    s = re.sub(r"\bFT\b", "FORT", s)       # word boundary: 'Kraft' is not 'Kraport'
    s = re.sub(UNIT, " ", s)
    s = re.sub(FILLER, " ", s)
    s = re.sub(r"\(.*?\)|[^A-Z0-9 ]", " ", s)
    return " ".join(s.split())


def overpass(query):
    """POST to Overpass, retrying the transient 504s the public server throws."""
    for attempt in range(1, RETRIES + 1):
        r = requests.post(OVERPASS_URL, data={"data": query}, headers=HEADERS, timeout=360)
        if r.status_code == 200:
            return r.json()
        if r.status_code in (429, 504) and attempt < RETRIES:
            wait = 15 * attempt
            print(f"  Overpass returned {r.status_code}; retrying in {wait}s "
                  f"(attempt {attempt}/{RETRIES})...")
            time.sleep(wait)
            continue
        r.raise_for_status()
    raise RuntimeError("Overpass kept failing; try again in a few minutes")


def download_osm():
    if os.path.exists(CACHE):
        cached = json.load(open(CACHE))
        if isinstance(cached, dict) and cached.get("version") == CACHE_VERSION:
            return cached["features"]
        print(f"{CACHE} is from an older query; re-downloading...")

    feats = []
    for state, iso in STATES.items():
        query = f"""
        [out:json][timeout:300];
        area["ISO3166-2"="{iso}"][admin_level=4]->.st;
        nwr["power"~"^(substation|plant)$"](area.st);
        out center tags;
        """
        print(f"Downloading {state} substations from Overpass (~1 min)...")
        before = len(feats)
        for el in overpass(query)["elements"]:
            tags = el.get("tags", {})
            name = tags.get("name")
            spot = el.get("center", el)
            if name and "lat" in spot:
                feats.append({"name": name, "norm": normalize(name), "state": state,
                              "lat": spot["lat"], "lon": spot["lon"],
                              "operator": tags.get("operator", ""),
                              "osm": f"{el['type']}/{el['id']}"})
        print(f"  {len(feats) - before} named features in {state}")

    json.dump({"version": CACHE_VERSION, "features": feats}, open(CACHE, "w"))
    print(f"Cached {len(feats)} named features to {CACHE}")
    return feats


def miles(lat1, lon1, lat2, lon2):
    r = 3958.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def best_match(endpoint, state, feats):
    target = normalize(endpoint)
    if not target:
        return None, "not_found"
    # Only ever consider the project's own state here. Cross-border endpoints are
    # real, but they are handled by cross_border_match() below, which demands
    # corroboration -- otherwise SC's Summerville silently becomes Georgia's.
    in_state = [f for f in feats if f["state"] == state]
    groups = [[f for f in in_state if any(o in f["operator"].lower() for o in OPERATORS[state])],
              in_state]

    for group in groups:
        exact = [f for f in group if f["norm"] == target]
        if len(exact) == 1:
            return exact[0], "auto_exact"
        if len(exact) > 1:                               # same name in several places
            return exact[0], "auto_ambiguous"
    for group in groups:
        names = [f["norm"] for f in group]
        close = difflib.get_close_matches(target, names, n=1, cutoff=FUZZY_CUTOFF)
        if close:
            return group[names.index(close[0])], "auto_fuzzy"
    return None, "not_found"


def cross_border_match(endpoint, state, feats, sibling):
    """
    A Georgia Power line really can end at Thurmond Dam SC, so an out-of-state
    match is allowed -- but only when the project's OTHER endpoint vouches for it
    by sitting within CROSS_BORDER_MI. Without that corroboration a name like
    'Summerville' matches the wrong state's substation 250 miles away.
    """
    target = normalize(endpoint)
    if not target or sibling is None:
        return None, "not_found"
    slat, slon = sibling
    near = [f for f in feats
            if f["state"] != state and miles(f["lat"], f["lon"], slat, slon) <= CROSS_BORDER_MI]
    exact = [f for f in near if f["norm"] == target]
    if len(exact) == 1:
        return exact[0], "auto_exact"
    if len(exact) > 1:
        return min(exact, key=lambda f: miles(f["lat"], f["lon"], slat, slon)), "auto_exact"
    names = [f["norm"] for f in near]
    close = difflib.get_close_matches(target, names, n=1, cutoff=FUZZY_CUTOFF)
    if close:
        return near[names.index(close[0])], "auto_fuzzy"
    return None, "not_found"


def disambiguate(endpoint, state, feats, sibling):
    """
    When a name matches several substations, prefer the one nearest the project's
    OTHER endpoint. A transmission line joins two nearby stations, so 'GOSHEN' on
    a line to KRAFT (Savannah) is the Savannah Goshen, not the Augusta one.
    Returns None when there is nothing to choose between.
    """
    target = normalize(endpoint)
    cands = [f for f in feats if f["norm"] == target]
    if len(cands) < 2 or sibling is None:
        return None
    slat, slon = sibling
    return min(cands, key=lambda f: (f["lat"] - slat) ** 2 + (f["lon"] - slon) ** 2)


def label_for(matches):
    """Weakest result among the endpoints we located; _partial if one is still missing."""
    located = [m for m in matches if m != "not_found"]
    if not located:
        return "not_found"
    worst = min(located, key=SEVERITY.index)
    if worst == "preexisting":                 # had coordinates before we ever ran
        worst = "auto_exact"
    return worst + ("_partial" if len(located) < len(matches) else "")


def load_previous_review():
    """Past match details, keyed by (project_id, endpoint), so a re-run can't erase them."""
    if not os.path.exists(REVIEW):
        return {}
    old = pd.read_csv(REVIEW)
    return {(r.project_id, r.endpoint): r.to_dict() for _, r in old.iterrows()}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--redo", action="store_true",
                    help="re-match endpoints that were already auto-located "
                         "(verified rows are still never touched)")
    args = ap.parse_args()

    feats = download_osm()
    df = pd.read_csv("projects.csv")
    for col in ("match_a", "match_b"):
        if col not in df.columns:
            df[col] = ""
    df[["match_a", "match_b"]] = df[["match_a", "match_b"]].fillna("")

    review = load_previous_review()
    for i, row in df.iterrows():
        if row["location_confidence"] in VERIFIED:
            continue
        matches = []
        for end in ("a", "b"):
            name = row[f"name_{end}"]
            if pd.isna(name):                            # this project has only one endpoint
                df.at[i, f"match_{end}"] = ""
                continue
            prior = str(row[f"match_{end}"] or "")
            keep = pd.notna(row[f"lat_{end}"]) and not (args.redo and prior != "preexisting")
            if keep:
                # Already located. Remember HOW, so re-running cannot downgrade the row.
                how = prior if prior in SEVERITY else "preexisting"
                df.at[i, f"match_{end}"] = how
                matches.append(how)
                continue

            feat, how = best_match(name, row["state"], feats)
            df.at[i, f"match_{end}"] = how
            matches.append(how)
            review[(row.project_id, end)] = {
                "project_id": row.project_id, "endpoint": end, "looked_for": name,
                "matched_osm_name": feat["name"] if feat else "", "how": how,
                "lat": feat["lat"] if feat else "", "lon": feat["lon"] if feat else "",
                "operator": feat["operator"] if feat else "",
                "matched_state": feat["state"] if feat else "",
                "osm_link": f"https://www.openstreetmap.org/{feat['osm']}" if feat else "",
                "checked_on": datetime.now().strftime("%Y-%m-%d %H:%M"),
            }
            if feat:
                df.at[i, f"lat_{end}"], df.at[i, f"lon_{end}"] = feat["lat"], feat["lon"]
            else:
                # --redo re-matched this endpoint and failed. Drop the old coordinates:
                # keeping them would leave a rejected match silently feeding overlaps.py.
                df.at[i, f"lat_{end}"], df.at[i, f"lon_{end}"] = pd.NA, pd.NA
        if matches:
            df.at[i, "location_confidence"] = label_for(matches)

    # Second pass: retry endpoints we could not find in their own state, allowing a
    # cross-border match only where the sibling endpoint corroborates it.
    for i, row in df.iterrows():
        if row["location_confidence"] in VERIFIED:
            continue
        for end, other in (("a", "b"), ("b", "a")):
            if df.at[i, f"match_{end}"] != "not_found":
                continue
            olat, olon = df.at[i, f"lat_{other}"], df.at[i, f"lon_{other}"]
            if pd.isna(olat) or pd.isna(olon):
                continue
            feat, how = cross_border_match(row[f"name_{end}"], row["state"], feats, (olat, olon))
            if feat is None:
                continue
            df.at[i, f"lat_{end}"], df.at[i, f"lon_{end}"] = feat["lat"], feat["lon"]
            df.at[i, f"match_{end}"] = how
            print(f"  {row.project_id} {end}: '{row[f'name_{end}']}' -> {feat['name']} "
                  f"({feat['state']}, {miles(feat['lat'], feat['lon'], olat, olon):.1f} mi from endpoint {other})")
            review[(row.project_id, end)] = {
                "project_id": row.project_id, "endpoint": end, "looked_for": row[f"name_{end}"],
                "matched_osm_name": feat["name"], "how": how, "lat": feat["lat"], "lon": feat["lon"],
                "operator": feat["operator"], "matched_state": feat["state"],
                "osm_link": f"https://www.openstreetmap.org/{feat['osm']}",
                "checked_on": datetime.now().strftime("%Y-%m-%d %H:%M")}
        matches = [df.at[i, f"match_{e}"] for e in ("a", "b") if df.at[i, f"match_{e}"]]
        if matches:
            df.at[i, "location_confidence"] = label_for(matches)

    # Third pass: resolve auto_ambiguous endpoints using the sibling endpoint's
    # location, now that every endpoint that could be matched has been.
    for i, row in df.iterrows():
        if row["location_confidence"] in VERIFIED:
            continue
        for end, other in (("a", "b"), ("b", "a")):
            if df.at[i, f"match_{end}"] != "auto_ambiguous":
                continue
            olat, olon = df.at[i, f"lat_{other}"], df.at[i, f"lon_{other}"]
            if pd.isna(olat) or pd.isna(olon):
                continue
            feat = disambiguate(row[f"name_{end}"], row["state"], feats, (olat, olon))
            if feat is None or (feat["lat"] == df.at[i, f"lat_{end}"]
                                and feat["lon"] == df.at[i, f"lon_{end}"]):
                continue
            df.at[i, f"lat_{end}"], df.at[i, f"lon_{end}"] = feat["lat"], feat["lon"]
            df.at[i, f"match_{end}"] = "auto_exact"
            print(f"  {row.project_id} {end}: '{row[f'name_{end}']}' -> {feat['name']} "
                  f"({feat['lat']:.4f},{feat['lon']:.4f}), nearest to endpoint {other}")
            key = (row.project_id, end)
            if key in review:
                review[key].update({
                    "matched_osm_name": feat["name"], "how": "auto_exact",
                    "lat": feat["lat"], "lon": feat["lon"], "operator": feat["operator"],
                    "matched_state": feat["state"],
                    "osm_link": f"https://www.openstreetmap.org/{feat['osm']}"})
        matches = [df.at[i, f"match_{e}"] for e in ("a", "b") if df.at[i, f"match_{e}"]]
        if matches:
            df.at[i, "location_confidence"] = label_for(matches)

    df.to_csv("projects.csv", index=False)

    review_df = pd.DataFrame(review.values()).sort_values(["project_id", "endpoint"])
    review_df.to_csv(REVIEW, index=False)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    review_df.to_csv(f"geocode_review_{stamp}.csv", index=False)

    print()
    print(df["location_confidence"].value_counts().to_string())
    print(f"\nWrote {REVIEW} ({len(review_df)} endpoints) and a snapshot "
          f"geocode_review_{stamp}.csv")
    print("Next: check the matches (especially auto_fuzzy / auto_ambiguous).")
    print("Fix wrong ones by hand in projects.csv and set location_confidence = manually_verified.")
