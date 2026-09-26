"""
GridLock - build the interactive map

Reads the two CSVs produced by the pipeline and writes ONE self-contained
HTML file. Everything -- the project rows, the overlap rows, the CSS and the
JavaScript -- is embedded in that file, so gridlock_map.html works by
double-clicking it. Nothing is loaded from disk at view time; only Leaflet
itself comes from a CDN, so the map tiles need an internet connection.

Input : projects_with_overlaps.csv   (from overlaps.py)
        overlaps.csv                 (from overlaps.py)
Output: gridlock_map.html

Run:  python build_map.py
"""

import json
import math

import pandas as pd

# ---------------------------------------------------------------------------
# Coordination estimate (bonus deliverable). Keyed by the two project ids, so
# the note only ever attaches to the pair it was written for.
#
# ILLUSTRATIVE. The cost basis is real -- DESC_23's $23,787,423 is published in
# the DESC PDF and now lives in projects.csv under the `cost` column -- but the
# savings percentages applied to it are assumptions, documented step by step in
# ESTIMATE.md. Georgia Power redacts per-project costs in its public IRP, so the
# range counts the DESC side only and the true total is higher by an unknown
# amount. Keyed on both project ids so it attaches to that pair alone.
# ---------------------------------------------------------------------------
ESTIMATES = {
    ("DESC_23", "GPC_20277"): {
        "range": "~$360K - $1.5M",
        "basis": "DESC_23 cost $23,787,423 (published, $3.66M/mi over 6.5 mi)",
        "note": ("Two 230 kV jobs 5.65 mi apart with in-service dates 152 days "
                 "apart. One crew mobilisation, one laydown yard and one set of "
                 "right-of-way and survey visits could serve both instead of two."),
        "caveat": ("DESC side only - Georgia Power redacts its project costs, so its "
                   "share is real but not quantifiable. Savings percentages are "
                   "assumptions; see ESTIMATE.md."),
        "retro": ("Retrospective: DESC_23's 2025-12-31 in-service date has passed. "
                  "Our tool would have flagged this pair before construction."),
    },
}

PROJECTS_CSV = "projects_with_overlaps.csv"
OVERLAPS_CSV = "overlaps.csv"
OUT = "gridlock_map.html"

# The whole point of the analysis is the GA/SC border, so open the map on the
# Savannah River between Augusta and Savannah.
MAP_CENTER = [33.0, -81.5]
MAP_ZOOM = 8

# Pairs whose midpoints are within this many miles form one hotspot circle.
CLUSTER_MI = 25

# One colour per utility. The Georgia list also carries Georgia Power's ITS
# partners (GTC, MEAG, Dalton), which are a third group rather than a fourth,
# fifth and sixth colour.
def utility_group(utility):
    u = str(utility)
    if "Dominion" in u:
        return "DESC"
    if u == "Georgia Power":
        return "GPC"
    return "ITS"


def miles(lat1, lon1, lat2, lon2):
    r = 3958.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def cluster_overlaps(overlaps, threshold_mi=CLUSTER_MI):
    """
    Group overlapping pairs into geographic hotspots.

    Drawing all 37 pairs as centre-to-centre lines produces a knot around
    Savannah that cannot be read at state zoom. Instead we cluster the pairs by
    the midpoint of each pair and let the map show one circle per cluster, sized
    by how many pairs it holds.

    Single-linkage: two pairs join the same cluster if their midpoints are within
    threshold_mi of each other, and clusters merge transitively. That matches how
    the eye groups them -- a corridor of nearby work becomes one hotspot.
    """
    mids = [((o["a_center"][0] + o["b_center"][0]) / 2,
             (o["a_center"][1] + o["b_center"][1]) / 2) for o in overlaps]

    parent = list(range(len(overlaps)))          # union-find
    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    def union(i, j):
        parent[find(i)] = find(j)

    for i in range(len(overlaps)):
        for j in range(i + 1, len(overlaps)):
            if miles(*mids[i], *mids[j]) <= threshold_mi:
                union(i, j)

    # number clusters by size, largest first, so cluster 0 is the main hotspot
    groups = {}
    for i in range(len(overlaps)):
        groups.setdefault(find(i), []).append(i)
    order = sorted(groups.values(), key=len, reverse=True)
    for cid, members in enumerate(order):
        for i in members:
            overlaps[i]["cluster"] = cid
    return len(order)


def clean(value):
    """NaN -> None, so it lands in the JSON as null instead of the string 'nan'."""
    return None if pd.isna(value) else value


def build_projects(df):
    """One JSON record per project: its geometry plus everything a popup needs."""
    out = []
    for _, r in df.iterrows():
        has_a = pd.notna(r.lat_a) and pd.notna(r.lon_a)
        has_b = pd.notna(r.lat_b) and pd.notna(r.lon_b)
        if not (has_a or has_b):
            continue                      # never located, so nothing to draw
        out.append({
            "id": r.project_id,
            "name": clean(r.project_name),
            "utility": clean(r.utility),
            "group": utility_group(r.utility),
            "state": clean(r.state),
            "date": clean(r.in_service_date),
            "status": clean(r.status),
            "confidence": clean(r.location_confidence),
            # DESC publishes per-project costs; Georgia Power redacts them in the
            # public IRP, so a null here is a known redaction, not missing data.
            "cost": int(r.cost) if pd.notna(r.cost) else None,
            "cost_note": clean(r.cost_note),
            "cost_redacted": pd.isna(r.cost) and str(r.sponsor) != "DESC",
            "source": clean(r.source),
            "source_id": clean(r.source_id),
            # endpoint names and coordinates; b is null for single-ended projects
            "name_a": clean(r.name_a), "name_b": clean(r.name_b),
            "a": [r.lat_a, r.lon_a] if has_a else None,
            "b": [r.lat_b, r.lon_b] if has_b else None,
            "center": [r.lat_center, r.lon_center],
            "overlaps": int(r.overlap_count) if pd.notna(r.overlap_count) else 0,
        })
    return out


def build_overlaps(df, centers):
    """One JSON record per overlapping pair, carrying both project centres."""
    out = []
    for _, r in df.iterrows():
        a, b = centers.get(r.project_id_a), centers.get(r.project_id_b)
        if a is None or b is None:
            continue
        out.append({
            "rank": int(r["rank"]),
            "id": r.overlap_id,
            "miles": float(r.distance_mi),
            "gap_days": int(r["time_gap (day)"]),
            "score": float(r.score),
            "confidence": r.confidence,          # 'verified' or 'needs_check'
            "a_id": r.project_id_a, "a_name": r.project_name_a,
            "a_util": r.utility_a, "a_date": r.in_service_a,
            "b_id": r.project_id_b, "b_name": r.project_name_b,
            "b_util": r.utility_b, "b_date": r.in_service_b,
            "a_center": a, "b_center": b,
            # present only on the pair we costed; the popup hides the block otherwise
            "estimate": ESTIMATES.get((r.project_id_a, r.project_id_b)),
        })
    return out


if __name__ == "__main__":
    projects_df = pd.read_csv(PROJECTS_CSV)
    overlaps_df = pd.read_csv(OVERLAPS_CSV)

    projects = build_projects(projects_df)
    centers = {p["id"]: p["center"] for p in projects}
    overlaps = build_overlaps(overlaps_df, centers)
    n_clusters = cluster_overlaps(overlaps)

    # The slider can only filter pairs that overlaps.py already found, and it
    # only kept pairs under its 25 mi rule -- so that is the top of the range.
    max_miles = max([o["miles"] for o in overlaps], default=25)

    payload = json.dumps({"projects": projects, "overlaps": overlaps,
                          "center": MAP_CENTER, "zoom": MAP_ZOOM,
                          "maxMiles": 25, "clusters": n_clusters}, allow_nan=False)
    # A literal </script> inside the JSON would close the tag early.
    payload = payload.replace("</", "<\\/")

    html = open("map_template.html").read().replace("/*__DATA__*/", payload)
    open(OUT, "w").write(html)

    sizes = {}
    for o in overlaps:
        sizes[o["cluster"]] = sizes.get(o["cluster"], 0) + 1
    print(f"{n_clusters} hotspot cluster(s): " +
          ", ".join(f"{n} pairs" for _, n in sorted(sizes.items())))
    costed = sum(1 for o in overlaps if o["estimate"])
    print(f"{costed} pair(s) carry a coordination estimate")
    verified = sum(1 for o in overlaps if o["confidence"] == "verified")
    print(f"{len(projects)} projects drawn, {len(overlaps)} overlap pairs "
          f"({verified} verified), longest {max_miles:.1f} mi")
    print(f"Wrote {OUT} ({len(html) / 1024:.0f} KB) - open it by double-clicking")
