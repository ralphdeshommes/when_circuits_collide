"""Part 3 - find where the two utilities' planned projects overlap.

Rules (from the Gridlock challenge + the Finding Real Locations guide):
  * a project's centre = midpoint of its two named end points (or the one located point)
  * distance = straight-line (haversine) miles between the two centres
  * distance < 25 mi  -> overlap (PRIMARY signal), one row per pair
  * time gap = days between the two in-service dates (SECONDARY signal)

Ranking: score = 0.7 * closeness + 0.3 * schedule-closeness, then weighted by how sure we are
about the two locations (high 1.0, medium 0.9, low 0.7).

Bonus - rough coordination value: for line projects whose corridors run close together we
estimate the shared corridor length, the right-of-way land two separate builds would take
versus one shared corridor, and a range for the cost avoided. Assumptions are in ASSUMPTIONS
and are shown next to every estimate in the map.

Called by run_all.py: compute(projects) returns (pairs, its_partner_pairs, opportunities, projects).
"""
import math
import re

import pandas as pd

MAX_MILES = 25
TIME_SCALE_DAYS = 5 * 365
GEO_WEIGHT, TIME_WEIGHT = 0.7, 0.3
CONF_WEIGHT = {"high": 1.0, "medium": 0.9, "low": 0.7}
CONF_RANK = {"high": 3, "medium": 2, "low": 1}
UTIL_A, UTIL_B = "Dominion Energy South Carolina", "Georgia Power"
GEORGIA_POWER_SPONSORS = {"GPC", "SAV"}      # GTC / MEAG / DU are ITS partners in the same plan

ASSUMPTIONS = {
    "row_width_ft": {46: 60, 69: 60, 115: 75, 138: 85, 161: 100, 230: 125, 500: 175},
    "second_line_extra_width": 0.35,   # a second line beside an existing one needs ~35% extra width
    "corridor_buffer_mi": 3.0,         # lines within 3 mi of each other along their length "share" a corridor
    "savings_low_pct": 0.05,           # share of construction cost avoided by joint mobilisation,
    "savings_high_pct": 0.12,          # permitting, outages and crews (low / high case)
    "site_mi": 3.5,                    # end points within 3.5 mi = the two projects work in the same substation area
    "site_share_of_cost": 0.25,        # share of a project's cost tied to the shared terminal (crews, yard, outages)
    "schedule_taper_days": 1095,       # savings fade linearly to zero as the in-service gap grows to 3 years
}


def haversine_miles(lat1, lon1, lat2, lon2):
    r = 3958.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def center(p):
    pts = [(p["lat_a"], p["lon_a"]), (p["lat_b"], p["lon_b"])]
    pts = [(la, lo) for la, lo in pts if pd.notna(la) and pd.notna(lo)]
    if not pts:
        return None, None
    return sum(x[0] for x in pts) / len(pts), sum(x[1] for x in pts) / len(pts)


def seg_points(p, n=41):
    a = (p["lat_a"], p["lon_a"]) if pd.notna(p["lat_a"]) else None
    b = (p["lat_b"], p["lon_b"]) if pd.notna(p["lat_b"]) else None
    if a and b:
        return [(a[0] + (b[0] - a[0]) * i / (n - 1), a[1] + (b[1] - a[1]) * i / (n - 1)) for i in range(n)]
    return [a or b]


def seg_length(pts):
    return sum(haversine_miles(*p, *q) for p, q in zip(pts, pts[1:]))


def is_line(p):
    return pd.notna(p["lat_a"]) and pd.notna(p["lat_b"]) and \
        haversine_miles(p["lat_a"], p["lon_a"], p["lat_b"], p["lon_b"]) > 0.5


def top_kv(name):
    v = [int(x) for x in re.findall(r"\b(500|230|161|138|115|69|46)\s*(?:/\s*\d+)?\s*k\s*v", name, re.I)]
    return max(v) if v else None


def is_new_build(p):
    txt = f"{p['project_name']} {p.get('description', '')}".lower()
    return bool(re.search(r"\bconstruct|\bnew (?:\d+ ?kv )?(?:line|substation|sub|tap)|new line", txt)) \
        and "rebuild" not in p["project_name"].lower() or "construct" in p["project_name"].lower()


def coordination_estimate(pa, pb, gap_days=0):
    """Shared corridor / shared site, land and cost impact for one pair (rough, assumption-driven).

    corridor : both are lines and run within `corridor_buffer_mi` of each other for a stretch
    site     : some end point of one is within `site_mi` of the other (same terminal / yard)
    nearby   : close enough to flag, no physical sharing (scheduling and crews only)
    Savings are scaled by schedule fit: a build 8 years apart cannot share a mobilisation.
    """
    A, B = seg_points(pa), seg_points(pb)
    sep = min(haversine_miles(*a, *b) for a in A for b in B)
    sched = max(0.0, 1 - gap_days / ASSUMPTIONS["schedule_taper_days"])
    out = {"coordination_type": "nearby", "min_separation_mi": round(sep, 1), "shared_corridor_mi": 0.0,
           "acres_separate": 0.0, "acres_shared": 0.0, "acres_saved": 0.0, "schedule_fit": round(sched, 2),
           "est_savings_low_usd": None, "est_savings_high_usd": None}
    cost = pa.get("total_cost_usd")            # Georgia costs are REDACTED; use Dominion's as a floor
    has_cost = pd.notna(cost) and bool(cost)
    share_of_cost = 0.0
    if is_line(pa) and is_line(pb):
        buf = ASSUMPTIONS["corridor_buffer_mi"]
        la, lb = seg_length(A), seg_length(B)
        fa = sum(1 for a in A if min(haversine_miles(*a, *b) for b in B) <= buf) / len(A)
        fb = sum(1 for b in B if min(haversine_miles(*a, *b) for a in A) <= buf) / len(B)
        shared = min(fa * la, fb * lb)
        if shared >= 0.5:
            out["coordination_type"], out["shared_corridor_mi"] = "corridor", round(shared, 1)
            wa = ASSUMPTIONS["row_width_ft"].get(top_kv(pa["project_name"]), 75)
            wb = ASSUMPTIONS["row_width_ft"].get(top_kv(pb["project_name"]), 75)
            sep_acres = shared * 5280 * (wa + wb) / 43560
            shr_acres = shared * 5280 * (max(wa, wb) + ASSUMPTIONS["second_line_extra_width"] * min(wa, wb)) / 43560
            if is_new_build(pa) or is_new_build(pb):   # a rebuild reuses its own corridor
                out.update(acres_separate=round(sep_acres, 1), acres_shared=round(shr_acres, 1),
                           acres_saved=round(sep_acres - shr_acres, 1))
            share_of_cost = min(1.0, shared / la) if la > 0 else 0.0
    if out["coordination_type"] == "nearby" and sep <= ASSUMPTIONS["site_mi"]:
        out["coordination_type"] = "site"
        share_of_cost = ASSUMPTIONS["site_share_of_cost"]
    if has_cost and share_of_cost > 0:
        base = cost * share_of_cost * sched
        out["est_savings_low_usd"] = round(base * ASSUMPTIONS["savings_low_pct"], -3)
        out["est_savings_high_usd"] = round(base * ASSUMPTIONS["savings_high_pct"], -3)
    return out


def why(row, est):
    bits = [f"{row['distance_mi']:.1f} mi apart"]
    d = row["time_gap (day)"]
    bits.append("same in-service month" if d <= 31 else f"in service {d} days apart"
                + (f" (~{d / 365:.1f} yr)" if d > 365 else ""))
    if est["coordination_type"] == "corridor":
        bits.append(f"corridors run together for ~{est['shared_corridor_mi']:.0f} mi")
    elif est["coordination_type"] == "site":
        bits.append(f"work in the same substation area (end points {est['min_separation_mi']:.1f} mi apart)")
    return "; ".join(bits)


def find_overlaps(projects, b_filter):
    A = projects[projects["utility"] == UTIL_A]
    B = projects[projects["utility"] == UTIL_B]
    B = B[b_filter(B)]
    rows = []
    for _, a in A.iterrows():
        if a["lat_center"] != a["lat_center"] or a["confidence"] == "none":
            continue
        for _, b in B.iterrows():
            if b["lat_center"] != b["lat_center"] or b["confidence"] == "none":
                continue
            d = haversine_miles(a["lat_center"], a["lon_center"], b["lat_center"], b["lon_center"])
            if d >= MAX_MILES:
                continue
            da, db = pd.to_datetime(a["in_service_date"]), pd.to_datetime(b["in_service_date"])
            gap = abs((da - db).days)
            geo = 1 - d / MAX_MILES
            tim = 1 - min(gap, TIME_SCALE_DAYS) / TIME_SCALE_DAYS
            score = GEO_WEIGHT * geo + TIME_WEIGHT * tim
            conf = min(a["confidence"], b["confidence"], key=lambda c: CONF_RANK[c])
            row = {
                "distance_mi": round(d, 2), "time_gap (day)": gap,
                "utility_a": a["utility"], "project_id_a": a["project_id"], "project_name_a": a["project_name"],
                "utility_b": b["utility"], "project_id_b": b["project_id"], "project_name_b": b["project_name"],
                "sponsor_b": b.get("sponsor", ""),
                "group_a": a["group_id"], "group_b": b["group_id"],
                "members_a": a["group_members"], "members_b": b["group_members"], "in_service_a": da.date().isoformat(),
                "in_service_b": db.date().isoformat(), "confidence": conf,
                "score": round(score, 3), "rank_score": round(score * CONF_WEIGHT[conf], 3),
            }
            est = coordination_estimate(a, b, gap)
            row.update(est)
            row["why"] = why(row, est)
            rows.append(row)
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df = df.sort_values(["rank_score", "distance_mi"], ascending=[False, True]).reset_index(drop=True)
    df.insert(0, "rank", df.index + 1)
    df.insert(1, "overlap_id", [f"OVL_{i}" for i in df["rank"]])
    return df


def add_groups(projects):
    """Sibling projects (same utility, identical parsed end points AND the same spot on the map -
    e.g. the '#5' / '#6' circuits of one corridor, or two phases of one rebuild) form one group,
    so they are not counted as separate opportunities."""
    key = (projects["endpoints_parsed"].fillna("").str.lower().str.replace(r"\s+", " ", regex=True).str.strip()
           + "@" + projects["lat_center"].round(2).astype(str) + "," + projects["lon_center"].round(2).astype(str))
    members = {}
    for pid, util, k, ep in zip(projects["project_id"], projects["utility"], key, projects["endpoints_parsed"]):
        members.setdefault((util, k if isinstance(ep, str) and ep.strip() else pid), []).append(pid)
    gid, gmem = {}, {}
    for lst in members.values():
        for pid in lst:
            gid[pid], gmem[pid] = lst[0], ";".join(lst)
    projects["group_id"] = projects["project_id"].map(gid)
    projects["group_members"] = projects["project_id"].map(gmem)
    return projects


def build_opportunities(ov):
    """Top coordination opportunities = the overlap pairs with duplicates removed:
    walk the pairs best-first and keep a pair only if neither of its project groups already
    appears in a better opportunity. The pairs that were skipped are kept as 'related'."""
    used_a, used_b, rows = set(), set(), []
    for _, r in ov.sort_values(["rank_score", "distance_mi"], ascending=[False, True]).iterrows():
        if r["group_a"] in used_a or r["group_b"] in used_b:
            continue
        used_a.add(r["group_a"])
        used_b.add(r["group_b"])
        same_pair = (ov["group_a"] == r["group_a"]) & (ov["group_b"] == r["group_b"])
        others = ov[((ov["group_a"] == r["group_a"]) | (ov["group_b"] == r["group_b"])) & ~same_pair]
        siblings = [m for m in r["members_a"].split(";") if m != r["project_id_a"]] + \
                   [m for m in r["members_b"].split(";") if m != r["project_id_b"]]
        row = r.to_dict()
        row["same_corridor_projects"] = "; ".join(siblings)
        row["other_nearby_pairs"] = len(others)
        row["other_nearby_examples"] = "; ".join(
            f"{x.project_id_a}~{x.project_id_b} ({x.distance_mi:.1f} mi)" for x in others.head(4).itertuples())
        rows.append(row)
    opp = pd.DataFrame(rows).reset_index(drop=True)
    opp.insert(0, "opportunity_rank", opp.index + 1)
    return opp


def compute(verified):
    """verified: the project table from verify.py.
    Returns (pairs, its_partner_pairs, opportunities, projects with per-project overlap columns)."""
    projects = add_groups(verified.copy())
    gp = find_overlaps(projects, lambda B: B["sponsor"].isin(GEORGIA_POWER_SPONSORS))
    allb = find_overlaps(projects, lambda B: B["sponsor"].notna())
    opps = build_opportunities(gp)
    partners = allb[~allb["sponsor_b"].isin(GEORGIA_POWER_SPONSORS)].reset_index(drop=True)
    partners["rank"] = partners.index + 1
    partners["overlap_id"] = [f"ITS_{i}" for i in partners["rank"]]

    # per-project overlap columns (same layout as the starter workbook)
    ov = {}
    for _, r in gp.iterrows():
        ov.setdefault(r["project_id_a"], []).append((r["distance_mi"], r["project_id_b"]))
        ov.setdefault(r["project_id_b"], []).append((r["distance_mi"], r["project_id_a"]))
    projects["overlap_count"] = projects["project_id"].map(lambda i: len(ov.get(i, [])))
    for k in range(3):
        projects[f"overlap_{k + 1}"] = projects["project_id"].map(
            lambda i: sorted(ov.get(i, []))[k][1] if len(ov.get(i, [])) > k else None)
    return gp, partners, opps, projects
