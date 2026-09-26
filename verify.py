"""Part 2 - confirm matches and grade every project's location confidence.

Takes the geocoded projects (automatic name matching) and returns the verified project table.

Automatic checks (a similarly-named substation in the wrong place is the common false match):
  * a Dominion project's centre must be in (or within 6 mi of) South Carolina and a Georgia Power
    project's in Georgia, using the real state outlines (data/state_borders.json)
  * a two-end-point line whose located ends are > 60 mi apart is treated as a probable mismatch
  * Georgia Power lists a transmission ZONE for every project (Table 2); a match that lands
    > 120 mi from where the rest of that zone's confidently-located projects sit is rejected
    (this catches same-named places, e.g. a "Riverside" in Savannah for a project in the Atlanta zone)
  * place-level matches (a town centre, not the substation) are always 'low'

Manual overrides (OVERRIDES below) are for matches re-read against the utility's PDF text;
each one carries the evidence for the change. They are applied first and marked 'verified'.

confidence:  high    every named end point is an OSM substation/plant with a strong name match
             medium  a good match on at least one end, or one end could not be located
             low     place-level only, or a sanity check failed
             none    not located (excluded from overlaps)

Called by run_all.py: verify_projects(geocoded) returns the verified project table.
"""
import re

import pandas as pd

from geocode import CROSS_BORDER_MI, dist_to_state, haversine_miles

ZONE_MI = 120

RANK = {"none": 0, "low": 1, "medium": 2, "high": 3}


def strength(how, q):
    if how == "override":
        return "strong"
    if how == "override_place":          # evidence-backed, but a street / nearby-site level point
        return "weak"
    if how == "osm_name":
        return "strong" if (q or 0) >= 0.95 else "good"
    if how == "nominatim+snap":
        return "good"
    if how in ("nominatim_place", "nominatim+snap_far"):
        return "weak"
    return None


def grade(p):
    notes = []
    eps = [s for s in (p["endpoints_parsed"] or "").split(" | ") if s] if isinstance(p["endpoints_parsed"], str) else []
    n_parsed = max(len(eps), 1)
    st = [strength(p.get(f"how_{t}"), p.get(f"q_{t}")) for t in ("a", "b") if pd.notna(p.get(f"lat_{t}"))]
    if not st:
        return "none", ["no end point could be located"]
    if all(s == "strong" for s in st) and len(st) == n_parsed:
        conf = "high"
    elif all(s == "weak" for s in st):
        conf, notes = "low", notes + ["place-level match only (town centre, not the substation)"]
    else:
        conf = "medium"
    if len(st) < n_parsed:
        conf = min(conf, "medium", key=RANK.get)
        notes.append("only one end point located; centre = that point")
    if re.match(r"^\s*(?:SAV\s*:\s*)?CC", p["project_name"]):
        conf = min(conf, "low", key=RANK.get)
        notes.append("customer-connection project (named after a customer site, so the substation match is a guess)")
    lat_c = p["lat_center"]
    want = p["state"]
    if pd.notna(lat_c):
        away = dist_to_state(lat_c, p["lon_center"], want)
        if away > CROSS_BORDER_MI / 2:
            conf = "low"
            notes.append(f"centre is {away:.0f} mi outside {want} - probable wrong-place match")
    if pd.notna(p["lat_a"]) and pd.notna(p["lat_b"]):
        span = haversine_miles(p["lat_a"], p["lon_a"], p["lat_b"], p["lon_b"])
        if span > 60:
            conf = "low"
            notes.append(f"end points {span:.0f} mi apart - probable name mismatch")
    return conf, notes


# Matches re-read against the PDF text (Part 2). Each carries the quote / evidence that justifies it.
OVERRIDES = [
    {"project_id": "GPC_45", "endpoint": "a", "name": "Fenwick St (Augusta GA, street-level)",
     "lat": 33.4718, "lon": -81.9754, "how": "override_place",
     "evidence": "PDF description: 'Reconductor approximately 2.72 miles of transmission line from Fenwick St to East "
                 "Augusta Jct' (zone 215 = Augusta area). Nominatim: Fenwick Street, Augusta, Richmond County, GA - "
                 "a street, not the substation itself"},
    {"project_id": "GPC_45", "endpoint": "b", "name": "East Augusta Jct (near Sand Bar Ferry Rd, Augusta GA)",
     "lat": 33.4602, "lon": -81.936, "how": "override_place",
     "evidence": "Project name pairs Fenwick St with Sand Bar Ferry; the two street points are ~2.3 mi apart, "
                 "consistent with the 2.72 mi in the PDF description"},
    {"project_id": "GPC_62", "endpoint": "a", "name": "Big Ogeechee (new sub near Little Ogeechee Sub)",
     "lat": 32.0068, "lon": -81.2532, "how": "override_place",
     "evidence": "PDF description: 'Construct a new substation near Little Ogeechee, adjacent to the 500kV and 230kV "
                 "shared right of way'. Coordinates = OSM Little Ogeechee Substation (Georgia Power)"},
]


def apply_overrides(df):
    for o in OVERRIDES:
        i = df.index[df["project_id"] == o["project_id"]]
        if len(i) == 0:
            continue
        t = o["endpoint"]
        df.loc[i, [f"name_{t}", f"lat_{t}", f"lon_{t}", f"how_{t}", f"q_{t}"]] = [
            o["name"], o["lat"], o["lon"], o["how"], 1.0]
        df.loc[i, "override_evidence"] = o["evidence"]
    return df


def centers(df):
    def c(r):
        pts = [(r["lat_a"], r["lon_a"]), (r["lat_b"], r["lon_b"])]
        pts = [(a, b) for a, b in pts if pd.notna(a) and pd.notna(b)]
        if not pts:
            return pd.Series([None, None])
        return pd.Series([sum(x[0] for x in pts) / len(pts), sum(x[1] for x in pts) / len(pts)])
    df[["lat_center", "lon_center"]] = df.apply(c, axis=1)
    return df


def zone_check(df):
    """Reject matches that contradict the project's own transmission zone."""
    ok = df[df["zone"].notna() & df["confidence"].isin(["high", "medium"]) & df["lat_center"].notna()]
    med = ok.groupby("zone").agg(n=("project_id", "size"), lat=("lat_center", "median"), lon=("lon_center", "median"))
    for i, r in df[df["zone"].notna() & df["lat_center"].notna() & (df["confidence"] != "none")].iterrows():
        m = med.loc[r["zone"]] if r["zone"] in med.index else None
        if m is None or m["n"] < 4:
            continue
        d = haversine_miles(r["lat_center"], r["lon_center"], m["lat"], m["lon"])
        if d > ZONE_MI:
            df.at[i, "confidence"] = "none"
            df.at[i, "geo_notes"] = (f"rejected: match is {d:.0f} mi from where zone {r['zone']} projects sit "
                                     f"(likely a same-named place); " + str(df.at[i, "geo_notes"]))
    return df


def verify_projects(geocoded):
    df = geocoded.copy()
    df["zone"] = df["zone"].replace("", float("nan"))
    df["override_evidence"] = None
    df = apply_overrides(df)
    df = centers(df)
    res = df.apply(grade, axis=1)
    df["confidence"] = [r[0] for r in res]
    df["geo_notes"] = ["; ".join(r[1]) for r in res]
    df.loc[df["override_evidence"].notna(), "geo_notes"] = df["geo_notes"] + " | verified: " + df["override_evidence"].fillna("")
    df = zone_check(df)
    cols = ["project_id", "utility", "state", "project_name", "name_a", "lat_a", "lon_a", "name_b", "lat_b",
            "lon_b", "lat_center", "lon_center", "in_service_date", "sponsor", "zone", "source_id", "status",
            "total_cost_usd", "confidence", "geo_notes", "how_a", "how_b", "endpoints_parsed", "description"]
    for c in cols:
        if c not in df:
            df[c] = None
    return df[cols]
