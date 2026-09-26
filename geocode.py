"""Part 1 - give every project coordinates.

For each project we pull the two named end points out of the project name
("Stevens Creek - Hooks 115 kV ..." -> Stevens Creek, Hooks), then look each one up:

  1. OpenStreetMap substations / power plants (data/osm_power.json, one bulk Overpass query)
  2. Nominatim place search (towns, dams, plants) for anything OSM has no substation for

Ambiguous names (two "Goshen" substations) are resolved by picking the pair of end points that
form a plausible line (close together, right state, right operator).

Every located end point carries a `source` (osm_substation / osm_plant / nominatim) and each
project gets a `confidence`:
    high    both end points (or the single named one) are OSM substations/plants with a strong name match
    medium  a substation match on one end and a place-level match on the other, or a fuzzy name match
    low     place-level only (town centre, not the actual substation)
    none    could not be located

Called by run_all.py: geocode_projects(desc, gpc) returns the projects with coordinates.
"""
import difflib
import itertools
import json
import math
import os
import re
import time

import pandas as pd
import requests

OSM_FILE = "data/osm_power.json"
NOM_CACHE = "data/nominatim_cache.json"
UA = {"User-Agent": "gridlock-hackathon/1.0 (sperry tech shell hacks 2026)"}

BORDERS_FILE = "data/state_borders.json"
_RINGS = None


def _rings():
    global _RINGS
    if _RINGS is None:
        _RINGS = json.load(open(BORDERS_FILE)) if os.path.exists(BORDERS_FILE) else {}
    return _RINGS


def _inside(ring, lat, lon):
    """Ray-casting point-in-polygon; ring is a list of [lon, lat]."""
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def side_of_border(lat, lon):
    """'GA' / 'SC' for a point, from the real state outlines (None if in neither)."""
    rings = _rings()
    for code in ("GA", "SC"):
        for ring in rings.get(code, [])[:3]:
            if _inside(ring, lat, lon):
                return code
    return None


_DIST_CACHE = {}


def dist_to_state(lat, lon, state):
    """Miles from a point to the state's territory (0 if inside; 0 if the outline is unavailable).
    Facilities on the Savannah River itself (dams, plants) sit within a mile of both states."""
    key = (round(lat, 4), round(lon, 4), state)
    if key in _DIST_CACHE:
        return _DIST_CACHE[key]
    rings = _rings().get(state, [])[:3]
    if not rings or any(_inside(r, lat, lon) for r in rings):
        d = 0.0
    else:
        k = math.cos(math.radians(lat)) * 69.17
        d = min(math.hypot((x - lon) * k, (y - lat) * 69.0) for r in rings for x, y in r)
    _DIST_CACHE[key] = d
    return d


IN_STATE_MI, CROSS_BORDER_MI = 2.0, 12.0
SAVANNAH = (32.0809, -81.0912)
MAX_LINE_MI = 60.0          # a transmission line project rarely spans more than this


def haversine_miles(lat1, lon1, lat2, lon2):
    r = 3958.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


# --------------------------------------------------------------------------- end points
PREFIX = re.compile(r"^\s*(?:(?:SAV|GTC|MEAG|DU|CC|GRID)\s*[:\-]\s*)+", re.I)
CUT = re.compile(
    r"(?:\b\d{2,3}(?:\.\d+)?(?:\s*[-/]\s*\d{2,3}(?:\.\d+)?)?\s*k\s*v\b|\bkv\b|:|,| & | AND | / |"
    r"\b(?:rebuild|rebld|reconductor|relay|upgrade|reactors?|capacitor|breaker|new|line|substation|sub|"
    r"tap|fold-in|construct|replace|install|installation|modernization|area|project|switching|"
    r"transformer|statcom|dual|series|add|loop)\b)", re.I)
STOP_NAMES = {"georgia", "south", "carolina", "north", "east", "west", "central", "county", "power"}
GENERIC = {"substation", "sub", "station", "primary", "pri", "switching", "tie", "plant", "generating",
           "facility", "the", "of", "line", "powerhouse", "power", "energy", "electric", "steam"}
ABBREV = {"st": "saint", "ft": "fort", "mt": "mount", "jct": "junction", "junct": "junction",
          "pri": "primary", "n": "north", "s": "south", "e": "east", "w": "west"}
# names the utilities abbreviate that OSM spells out (documented so they can be audited)
ALIASES = {
    "vcs1": "V C Summer", "vcs2": "V C Summer", "vc summer": "V C Summer",
    "am williams": "A M Williams", "sw house": "",
}


def norm_tokens(s):
    s = s.lower().replace("&", " and ")
    s = re.sub(r"\(.*?\)|#\d+|['’.]", " ", s)
    toks = [ABBREV.get(t, t) for t in re.findall(r"[a-z0-9]+", s)]
    return [t for t in toks if t not in GENERIC]


def extract_endpoints(name):
    """Project name -> list of cleaned end point names (first and last if a line has >2)."""
    s = PREFIX.sub("", name.replace("–", "-"))
    s = re.sub(r"\([^)]*\)", " ", s)          # (SAV), (USA), (APC) are annotations, not places
    m = CUT.search(s)
    head = s[:m.start()] if m and m.start() > 0 else s
    parts = [p.strip(" -") for p in re.split(r"\s*-\s*", head) if p.strip(" -")]
    parts = [re.sub(r"\s+", " ", re.sub(r"\(.*?\)|#\s*\d+", "", p)).strip() for p in parts]
    parts = [p for p in parts if p and not re.fullmatch(r"\d+", p)]
    if len(parts) > 2:
        parts = [parts[0], parts[-1]]
    return parts


# --------------------------------------------------------------------------- OSM index
class OSMIndex:
    def __init__(self, path=OSM_FILE):
        els = json.load(open(path, encoding="utf-8"))["elements"]
        self.items = []
        self.subs = []          # every substation incl. unnamed ones, for voltage-matched snapping
        for e in els:
            t = e.get("tags", {})
            name = t.get("name")
            lat = e.get("lat", e.get("center", {}).get("lat"))
            lon = e.get("lon", e.get("center", {}).get("lon"))
            if lat is None:
                continue
            if t.get("power") == "substation":
                self.subs.append({"name": name or "", "lat": lat, "lon": lon,
                                  "operator": t.get("operator", ""), "voltage": t.get("voltage", ""),
                                  "type": t.get("substation", ""), "id": f"{e['type']}/{e['id']}"})
            if not name:
                continue
            self.items.append({
                "name": name, "kind": t.get("power"), "operator": t.get("operator", ""),
                "lat": lat, "lon": lon, "toks": norm_tokens(name), "id": f"{e['type']}/{e['id']}",
            })
        self.by_token = {}
        for i, it in enumerate(self.items):
            for tk in set(it["toks"]):
                self.by_token.setdefault(tk, []).append(i)

    def candidates(self, ep, utility_state, sponsor=""):
        """All OSM features whose name matches end point `ep`, best first."""
        alias = ALIASES.get(ep.lower(), ep)
        qt = norm_tokens(alias)
        if not qt:
            return []
        pool = set()
        for tk in qt:
            pool.update(self.by_token.get(tk, []))
        out = []
        for i in pool:
            it = self.items[i]
            a, b = set(qt), set(it["toks"])
            if not b:
                continue
            if a == b:
                q = 1.0
            elif a <= b:                       # query name fully inside the OSM name
                q = max(0.62, 0.9 - 0.08 * (len(b) - len(a)))
            elif b <= a and not b <= STOP_NAMES:   # OSM name fully inside the query
                q = max(0.62, 0.85 - 0.08 * (len(a) - len(b)))
            else:
                r = difflib.SequenceMatcher(None, " ".join(qt), " ".join(it["toks"])).ratio()
                q = r if r >= 0.88 else 0
            if q < 0.6:
                continue
            if it["kind"] != "substation" and GENERATING_NOISE.search(it["name"])                     and not GENERATING_NOISE.search(ep):
                continue
            bonus = 0.0
            op = it["operator"].lower()
            if it["kind"] == "substation":
                bonus += 0.05
            if utility_state == "SC" and re.search(r"dominion|sce&g|south carolina|santee", op):
                bonus += 0.1
            if utility_state == "GA" and re.search(r"georgia|oglethorpe|meag", op):
                bonus += 0.1
            if sponsor == "SAV":        # Savannah Electric territory: pick the Savannah-area namesake
                bonus += 0.12 if haversine_miles(it["lat"], it["lon"], *SAVANNAH) <= 45 else -0.12
            d_state = dist_to_state(it["lat"], it["lon"], utility_state)
            if d_state > CROSS_BORDER_MI:
                continue           # a Dominion project is in SC, a Georgia Power one in GA
            if d_state > IN_STATE_MI:
                bonus -= 0.15      # tie lines can cross the river, but prefer the in-state match
            out.append({**it, "q": q + bonus})
        out.sort(key=lambda c: -c["q"])
        return out[:6]


# --------------------------------------------------------------------------- Nominatim
STATE_NAME = {"SC": "South Carolina", "GA": "Georgia"}
PLACE_CATS = {"place", "boundary", "power", "man_made", "natural", "waterway", "landuse"}
GENERATING_NOISE = re.compile(r"solar|battery|storage|wind farm|landfill", re.I)


def valid_place(hit, state):
    """A usable Nominatim hit is a place-like feature that really is in the utility's state
    (the bounded viewbox alone lets North Carolina / Florida towns of the same name through)."""
    return bool(hit) and hit.get("cls") in PLACE_CATS and f", {STATE_NAME[state]}," in hit.get("name", "") + ","


class Nominatim:
    """Place lookups (towns, dams, plants) with a polite 1 request/second and an on-disk cache.
    The cache keeps the raw top results so the validity rules can change without re-querying."""
    VIEWBOX = {"SC": "-83.4,35.3,-78.4,32.0", "GA": "-85.7,35.1,-80.8,30.3"}

    def __init__(self, path=NOM_CACHE):
        self.path = path
        self.cache = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}
        self.last = 0.0

    def _raw(self, query, state):
        key = f"v2|{query}|{state}"
        if key in self.cache:
            return self.cache[key]
        old = self.cache.get(f"{query}|{state}", "missing")     # first-generation cache entry
        if old is None:
            self.cache[key] = []
            return []
        if old != "missing" and valid_place(old, state):
            self.cache[key] = [old]
            return [old]
        wait = 1.1 - (time.time() - self.last)
        if wait > 0:
            time.sleep(wait)
        params = {"q": query, "format": "jsonv2", "limit": 5, "countrycodes": "us",
                  "viewbox": self.VIEWBOX[state], "bounded": 1}
        try:
            r = requests.get("https://nominatim.openstreetmap.org/search", params=params,
                             headers=UA, timeout=30)
            res = r.json() if r.ok else None
        except Exception:
            res = None
        self.last = time.time()
        if res is None:                       # network hiccup: don't cache, don't guess
            return []
        raw = [{"name": x.get("display_name", "")[:200], "lat": float(x["lat"]), "lon": float(x["lon"]),
                "type": x.get("type", ""), "cls": x.get("category", x.get("class", ""))} for x in res]
        self.cache[key] = raw
        json.dump(self.cache, open(self.path, "w", encoding="utf-8"))
        return raw

    def search(self, query, state):
        for hit in self._raw(query, state):
            if valid_place(hit, state) and dist_to_state(hit["lat"], hit["lon"], state) <= IN_STATE_MI:
                return hit
        return None


# --------------------------------------------------------------------------- resolve
def voltages_in(name):
    """kV values mentioned in a project name, e.g. '230/115KV' -> {230, 115}."""
    return {int(v) for v in re.findall(r"\b(500|230|115|46|161|138|69)\s*(?:/|-)?\s*(?:k\s*v)?", name, re.I)}


def snap_to_unnamed_substation(osm, lat, lon, state, volts, radius=6.0):
    """Nearest substation (named or not) around a place-level point that has the project's voltage
    and an operator compatible with the utility. This is how a human would match 'Okatie' to the
    unlabelled 230 kV switching station next to the town."""
    best, best_d = None, radius
    want = {str(v * 1000) for v in volts}
    for s in osm.subs:
        if abs(s["lat"] - lat) > radius / 69 or abs(s["lon"] - lon) > radius / 55:
            continue
        d = haversine_miles(lat, lon, s["lat"], s["lon"])
        if d >= best_d:
            continue
        if want and not (want & set(re.split(r"[;,\s]+", s["voltage"]))):
            continue
        op = s["operator"].lower()
        if state == "SC" and op and not re.search(r"dominion|sce&g|south carolina|santee", op):
            continue
        if state == "GA" and op and not re.search(r"georgia|oglethorpe|meag", op):
            continue
        if dist_to_state(s["lat"], s["lon"], state) > IN_STATE_MI:
            continue
        best, best_d = s, d
    return best, best_d


def locate_one(ep, state, volts, osm, nom, cs):
    if cs:
        c = cs[0]
        return {**c, "kind": c["kind"], "q": c["q"], "how": "osm_name"}
    hit = nom.search(f"{ep} substation", state) or nom.search(ep, state)
    if not hit:
        return {"name": ep, "lat": None, "lon": None, "kind": "none", "q": 0, "how": "none"}
    snap, d = snap_to_unnamed_substation(osm, hit["lat"], hit["lon"], state, volts)
    if snap:
        return {"name": f"{ep} (unlabelled {'/'.join(map(str, sorted(volts)))} kV substation, {d:.1f} mi from town)",
                "lat": snap["lat"], "lon": snap["lon"], "kind": "osm_unnamed_substation", "q": 0.55,
                "operator": snap["operator"], "nom": hit["name"],
                "how": "nominatim+snap" if d <= 3.0 else "nominatim+snap_far"}
    return {"name": ep, "lat": hit["lat"], "lon": hit["lon"], "kind": "place", "q": 0.4,
            "operator": "", "how": "nominatim_place", "nom": hit["name"]}


def resolve_project(name, state, osm, nom, sponsor=""):
    eps = extract_endpoints(name)
    volts = voltages_in(name)
    cands = [osm.candidates(ep, state, sponsor) for ep in eps]
    result = []
    if len(eps) == 2 and cands[0] and cands[1]:
        # choose the pair that best forms a plausible line (short span, high name quality)
        best, best_score = None, -1e9
        for a, b in itertools.product(cands[0][:4], cands[1][:4]):
            span = haversine_miles(a["lat"], a["lon"], b["lat"], b["lon"])
            score = a["q"] + b["q"] - (0.02 * max(0, span - 30))
            if score > best_score:
                best, best_score = (a, b), score
        result = [{**best[0], "how": "osm_name"}, {**best[1], "how": "osm_name"}]
    else:
        result = [locate_one(ep, state, volts, osm, nom, cs) for ep, cs in zip(eps, cands)]
    if len(result) == 2 and all(r["lat"] is not None for r in result):
        span = haversine_miles(result[0]["lat"], result[0]["lon"], result[1]["lat"], result[1]["lon"])
        weak = [i for i, r in enumerate(result) if r["how"] != "osm_name"]
        if span > MAX_LINE_MI and len(weak) == 1:      # e.g. a town of the same name 180 mi away
            w = weak[0]
            result[w] = {"name": result[w]["name"], "lat": None, "lon": None, "kind": "none", "q": 0,
                         "how": "discarded_implausible_span"}
    return eps, result


def geocode_projects(desc, gpc):
    """Add coordinates to the two project tables from parse_projects; returns one table."""
    osm, nom = OSMIndex(), Nominatim()
    rows = []
    for df in (desc, gpc):
        for _, p in df.iterrows():
            eps, res = resolve_project(p["project_name"], p["state"], osm, nom, p.get("sponsor") or "")
            rec = p.to_dict()
            rec["endpoints_parsed"] = " | ".join(eps)
            for k, tag in enumerate(("a", "b")):
                r = res[k] if k < len(res) else None
                rec[f"name_{tag}"] = r["name"] if r else None
                rec[f"lat_{tag}"] = r["lat"] if r else None
                rec[f"lon_{tag}"] = r["lon"] if r else None
                rec[f"kind_{tag}"] = r["kind"] if r else None
                rec[f"how_{tag}"] = r.get("how") if r else None
                rec[f"osm_operator_{tag}"] = r.get("operator") if r else None
                rec[f"q_{tag}"] = round(r["q"], 2) if r else None
            rows.append(rec)
    return pd.DataFrame(rows)
