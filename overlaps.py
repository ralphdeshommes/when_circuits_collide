"""
GridLock - overlap finder (follows the Sperry Tech challenge rules)

Rules from ShellHacks_Challenge_Gridlock.docx + Finding_Real_Locations_Guide.docx:
  - Each project's CENTER = midpoint of its two named endpoints
    (or the one point, if only one endpoint has coordinates)
  - Distance = straight-line (haversine) miles between the two centers
  - Pair counts as an overlap if distance < 25 miles   (PRIMARY signal)
  - Record the time gap between in-service dates in DAYS (SECONDARY signal)

Input : projects.csv   (one row per project, both utilities)
Output: overlaps.csv   (one row per overlapping pair, ranked best-first)
        projects_with_overlaps.csv (projects.csv + overlap_count, overlap_1..3)

Run:  python overlaps.py
"""

import math
from pathlib import Path

import pandas as pd

# ---- Settings ----
MAX_MILES = 25              # sponsor's rule: under 25 miles = overlap
TIME_SCALE_DAYS = 5 * 365   # a gap this big (or bigger) earns 0 timing points
GEO_WEIGHT = 0.7            # geography is the primary signal...
TIME_WEIGHT = 0.3           # ...timing is the secondary signal
UTILITY_A = "Dominion Energy South Carolina"
UTILITY_B = "Georgia Power"
# The Georgia list also has projects owned by Georgia Power's ITS partners
# (GTC, MEAG, Dalton Utilities). Set True to include them as "Georgia side".
INCLUDE_GA_ITS_PARTNERS = False


def haversine_miles(lat1, lon1, lat2, lon2):
    """Straight-line distance in miles between two GPS points."""
    r = 3958.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def add_centers(df):
    """Center = average of endpoint A and B; if only one exists, use that one."""
    valid_a = df.lat_a.between(-90, 90) & df.lon_a.between(-180, 180)
    valid_b = df.lat_b.between(-90, 90) & df.lon_b.between(-180, 180)
    for axis in ("lat", "lon"):
        endpoints = pd.concat([df[f"{axis}_a"].where(valid_a),
                               df[f"{axis}_b"].where(valid_b)], axis=1)
        df[f"{axis}_center"] = endpoints.mean(axis=1, skipna=True)
    return df


def score(miles, gap_days):
    geo = 1 - miles / MAX_MILES                        # 0 miles -> 1.0, 25 miles -> 0
    time = max(0.0, 1 - gap_days / TIME_SCALE_DAYS)    # same day -> 1.0, 5+ yrs -> 0
    return round(GEO_WEIGHT * geo + TIME_WEIGHT * time, 3)


def find_overlaps(projects):
    projects = add_centers(projects.copy())
    projects["in_service_date"] = pd.to_datetime(projects["in_service_date"])
    if projects["in_service_date"].isna().any():
        raise ValueError("Every project needs an in_service_date to rank overlaps.")
    located = projects.dropna(subset=["lat_center", "lon_center"])

    side_a = located[located["utility"] == UTILITY_A]
    if INCLUDE_GA_ITS_PARTNERS:
        side_b = located[located["state"] == "GA"]
    else:
        side_b = located[located["utility"] == UTILITY_B]

    rows = []
    for _, a in side_a.iterrows():          # compare every A project...
        for _, b in side_b.iterrows():      # ...with every B project
            miles = haversine_miles(a.lat_center, a.lon_center, b.lat_center, b.lon_center)
            if miles >= MAX_MILES:
                continue
            gap = abs((b.in_service_date - a.in_service_date).days)
            rows.append({
                "distance_mi": round(miles, 2),
                "time_gap (day)": gap,
                "score": score(miles, gap),
                "utility_a": a.utility, "project_id_a": a.project_id, "project_name_a": a.project_name,
                "in_service_a": a.in_service_date.date(),
                "utility_b": b.utility, "project_id_b": b.project_id, "project_name_b": b.project_name,
                "in_service_b": b.in_service_date.date(),
                "confidence": "verified" if {a.location_confidence, b.location_confidence}
                              <= {"sponsor_verified", "manually_verified"} else "needs_check",
            })

    columns = ["distance_mi", "time_gap (day)", "score", "utility_a",
               "project_id_a", "project_name_a", "in_service_a", "utility_b",
               "project_id_b", "project_name_b", "in_service_b", "confidence"]
    overlaps = pd.DataFrame(rows, columns=columns)
    overlaps = overlaps.sort_values(["score", "distance_mi"], ascending=[False, True]).reset_index(drop=True)
    overlaps.insert(0, "rank", overlaps.index + 1)
    overlaps.insert(1, "overlap_id", [f"OVL_{i}" for i in overlaps["rank"]])

    # overlap_count / overlap_1..3 columns, like the sponsor's projects sheet
    partners = {}
    for _, o in overlaps.iterrows():
        partners.setdefault(o.project_id_a, []).append(o.project_id_b)
        partners.setdefault(o.project_id_b, []).append(o.project_id_a)
    projects["overlap_count"] = projects["project_id"].map(lambda p: len(partners.get(p, [])))
    for i in range(3):
        projects[f"overlap_{i + 1}"] = projects["project_id"].map(
            lambda p: partners.get(p, [])[i] if len(partners.get(p, [])) > i else "")
    return overlaps, projects


if __name__ == "__main__":
    base = Path(__file__).resolve().parent
    projects = pd.read_csv(base / "projects.csv")
    overlaps, projects = find_overlaps(projects)
    overlaps.to_csv(base / "overlaps.csv", index=False)
    projects.to_csv(base / "projects_with_overlaps.csv", index=False)

    n_loc = projects["lat_center"].notna().sum()
    print(f"{len(projects)} projects, {n_loc} with coordinates, {len(overlaps)} overlapping pairs\n")
    pd.set_option("display.width", 220)
    if not overlaps.empty:
        print(overlaps[["rank", "distance_mi", "time_gap (day)", "score",
                        "project_id_a", "project_id_b", "project_name_b"]].to_string(index=False))
