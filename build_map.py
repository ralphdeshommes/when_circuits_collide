"""Build the interactive map -> gridlock_map.html (self-contained; all data is embedded in the page).

The page needs internet only for the Leaflet library and the base-map tiles.

Called by run_all.py: build_map(projects, pairs, its_partner_pairs).
"""
import json
import math
import os

import pandas as pd

from overlaps import ASSUMPTIONS


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
        "dist": o["distance_mi"], "gap": int(o["time_gap (day)"]), "conf": o["confidence"],
        "score": o["score"], "rscore": o["rank_score"], "why": o["why"],
        "groupA": o["group_a"], "groupB": o["group_b"], "membersA": o["members_a"].split(";"),
        "membersB": o["members_b"].split(";"),
        "ctype": o["coordination_type"], "sched": o["schedule_fit"],
        "shared": o["shared_corridor_mi"], "minsep": o["min_separation_mi"], "sepAcres": o["acres_separate"],
        "sharedAcres": o["acres_shared"], "acres": o["acres_saved"],
        "lo": clean(o["est_savings_low_usd"]), "hi": clean(o["est_savings_high_usd"]),
    }


def build_map(projects, gp, partners, out="gridlock_map.html"):
    projects = projects[projects["lat_center"].notna()]
    data = {
        "projects": [project_json(p) for _, p in projects.iterrows()],
        "overlaps": [overlap_json(o) for _, o in gp.iterrows()],
        "partners": [overlap_json(o) for _, o in partners.iterrows()],
        "assumptions": {"rowWidth": ASSUMPTIONS["row_width_ft"], "extra": ASSUMPTIONS["second_line_extra_width"],
                        "buffer": ASSUMPTIONS["corridor_buffer_mi"], "lowPct": ASSUMPTIONS["savings_low_pct"],
                        "highPct": ASSUMPTIONS["savings_high_pct"], "siteMi": ASSUMPTIONS["site_mi"],
                        "siteShare": ASSUMPTIONS["site_share_of_cost"], "taper": ASSUMPTIONS["schedule_taper_days"]},
    }
    template = os.path.join(os.path.dirname(os.path.abspath(__file__)), "map_template.html")
    html = open(template, encoding="utf-8").read()
    html = html.replace("/*DATA*/", json.dumps(data, ensure_ascii=False, allow_nan=False).replace("</", "<\\/"))
    open(out, "w", encoding="utf-8").write(html)
    print(f"{out}: {len(data['projects'])} located projects, {len(data['overlaps'])} overlapping pairs")
