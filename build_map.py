"""Build the interactive map -> gridlock_map.html (self-contained; all data is embedded in the page).

The page needs internet only for the Leaflet library and the base-map tiles.

Called by run_all.py: build_map(projects, pairs, its_partner_pairs).
"""
import json
import math
import os

import pandas as pd

from overlaps import ASSUMPTIONS, COMPANY_MAX_MILES, DEFAULT_MAX_MILES

# Company -> display color / short label / centre-badge letter. Adding a 6th company
# means one more row here (plus a parser that emits its `utility` name) -- nothing
# else in the map has to change.
COMPANY_STYLE = {
    "Dominion Energy South Carolina": {"color": "#1f5fbf", "short": "Dominion", "letter": "D"},
    "Georgia Power": {"color": "#c95f00", "short": "Georgia Power", "letter": "G"},
    "Georgia Transmission Corporation": {"color": "#1a8f5a", "short": "GTC", "letter": "T"},
    "Municipal Electric Authority of Georgia": {"color": "#7b4fc9", "short": "MEAG", "letter": "M"},
    "Dalton Utilities": {"color": "#c9296b", "short": "Dalton Utilities", "letter": "U"},
}
FALLBACK_COLORS = ["#2a8f8f", "#8f6b2a", "#5a5ac9", "#a1a11a", "#c94f4f"]


def company_registry(utilities):
    """utility name -> {color, short, letter, maxMi}, in order (falls back to a generic
    palette + first letter for any company not in COMPANY_STYLE, e.g. a 6th one).
    maxMi is that company's own coordination radius (overlaps.COMPANY_MAX_MILES),
    defaulting to DEFAULT_MAX_MILES -- the map reads it to draw the right-size circle
    instead of assuming every company uses the same 25 mi."""
    out, used_letters, spare = {}, set(), iter(FALLBACK_COLORS)
    for u in utilities:
        style = COMPANY_STYLE.get(u)
        if not style:
            letter = next((c for c in u if c.isalpha() and c.upper() not in used_letters), "?").upper()
            style = {"color": next(spare, "#888888"), "short": u, "letter": letter}
        used_letters.add(style["letter"])
        out[u] = dict(style, maxMi=COMPANY_MAX_MILES.get(u, DEFAULT_MAX_MILES))
    return out


def clean(v):
    if v is None or (isinstance(v, float) and math.isnan(v)) or v is pd.NaT:
        return None
    if hasattr(v, "item"):
        v = v.item()
    return v


def pt(lat, lon, name):
    lat, lon = clean(lat), clean(lon)
    return None if lat is None or lon is None else [round(lat, 5), round(lon, 5), clean(name)]


def project_json(p):
    c = pt(p["lat_center"], p["lon_center"], None)
    date = pd.to_datetime(p["in_service_date"])
    return {
        "id": p["project_id"], "util": p["utility"], "name": p["project_name"], "sponsor": clean(p["sponsor"]),
        "a": pt(p["lat_a"], p["lon_a"], p["name_a"]), "b": pt(p["lat_b"], p["lon_b"], p["name_b"]),
        "c": c[:2] if c else None, "date": date.date().isoformat() if pd.notna(date) else None,
        "status": clean(p["status"]), "cost": clean(p["total_cost_usd"]), "conf": p["confidence"],
        "notes": clean(p["geo_notes"]) or "", "desc": (clean(p["description"]) or "")[:400],
    }


def overlap_json(o):
    return {
        "id": o["overlap_id"], "a": o["project_id_a"], "b": o["project_id_b"],
        "nameA": o["project_name_a"], "nameB": o["project_name_b"], "sponsor": clean(o["sponsor_b"]),
        "dist": o["distance_mi"], "maxMi": o["max_mi"], "gap": int(o["time_gap (day)"]), "conf": o["confidence"],
        "score": o["score"], "rscore": o["rank_score"], "why": o["why"],
        "groupA": o["group_a"], "groupB": o["group_b"], "membersA": o["members_a"].split(";"),
        "membersB": o["members_b"].split(";"),
        "ctype": o["coordination_type"], "sched": o["schedule_fit"],
        "shared": o["shared_corridor_mi"], "minsep": o["min_separation_mi"], "sepAcres": o["acres_separate"],
        "sharedAcres": o["acres_shared"], "acres": o["acres_saved"],
        "lo": clean(o["est_savings_low_usd"]), "hi": clean(o["est_savings_high_usd"]),
    }


def build_map(projects, pairs, out="gridlock_map.html"):
    projects = projects[projects["lat_center"].notna()]
    companies = company_registry(sorted(projects["utility"].dropna().unique()))
    data = {
        "projects": [project_json(p) for _, p in projects.iterrows()],
        "overlaps": [overlap_json(o) for _, o in pairs.iterrows()],
        "companies": companies,
        "assumptions": {"rowWidth": ASSUMPTIONS["row_width_ft"], "extra": ASSUMPTIONS["second_line_extra_width"],
                        "buffer": ASSUMPTIONS["corridor_buffer_mi"], "lowPct": ASSUMPTIONS["savings_low_pct"],
                        "highPct": ASSUMPTIONS["savings_high_pct"], "siteMi": ASSUMPTIONS["site_mi"],
                        "siteShare": ASSUMPTIONS["site_share_of_cost"], "taper": ASSUMPTIONS["schedule_taper_days"]},
    }
    template = os.path.join(os.path.dirname(os.path.abspath(__file__)), "map_template.html")
    html = open(template, encoding="utf-8").read()
    html = html.replace("/*DATA*/", json.dumps(data, ensure_ascii=False, allow_nan=False).replace("</", "<\\/"))
    open(out, "w", encoding="utf-8").write(html)
    print(f"{out}: {len(data['projects'])} located projects, {len(data['overlaps'])} overlapping pairs, "
          f"{len(companies)} companies")
