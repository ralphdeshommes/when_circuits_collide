"""Regression tests for the Gridlock pipeline and the interactive map.

    python test_gridlock.py            # everything
    python test_gridlock.py --pipeline # PDFs -> locations -> overlaps only
    python test_gridlock.py --map      # the built gridlock_map.html only

The pipeline tests run the real thing end to end from the two utility PDFs, so
they need the same GRIDLOCK_SRC folder run_all.py needs. The map tests drive the
built gridlock_map.html in headless Chrome and click its real controls. Anything
that cannot run (no PDFs, no Chrome) is reported as SKIP, never as a pass.

Most checks exist because the failure they guard against is easy to reintroduce
and silent: a name that stops matching, a point that drifts into the wrong state,
a filter that stops filtering. A wrong answer here still looks like an answer.
"""
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import warnings

warnings.filterwarnings("ignore")

PASS, FAIL, SKIP = [], [], []


def check(name, condition, detail=""):
    (PASS if condition else FAIL).append(name)
    print(("  ok   " if condition else "  FAIL ") + name + (("  -- " + str(detail)) if detail and not condition else ""))
    return condition


def skip(name, why):
    SKIP.append(name)
    print("  skip " + name + "  -- " + why)


def section(title):
    print("\n" + title)


# --------------------------------------------------------------------------
# pipeline
# --------------------------------------------------------------------------
def run_pipeline():
    """Run parse -> geocode -> verify -> overlaps once and hand back the frames."""
    from parse_projects import DESC_PDF, GPC_PDF, parse_desc, parse_gpc
    if not (os.path.isfile(DESC_PDF) and os.path.isfile(GPC_PDF)):
        return None
    import geocode
    import overlaps
    import verify
    desc, gpc = parse_desc(), parse_gpc()
    projects = verify.verify_projects(geocode.geocode_projects(desc, gpc))
    pairs, partners, opps, projects = overlaps.compute(projects)
    return dict(desc=desc, gpc=gpc, projects=projects, pairs=pairs, opps=opps)


def miles(a, b, c, d):
    r = 3958.8
    p1, p2 = math.radians(a), math.radians(c)
    dp, dl = math.radians(c - a), math.radians(d - b)
    x = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(x))


def test_pipeline():
    import pandas as pd
    out = run_pipeline()
    if out is None:
        section("PARSING / GEOCODING / OVERLAPS")
        skip("whole pipeline", "utility PDFs not found; set GRIDLOCK_SRC")
        return
    desc, gpc = out["desc"], out["gpc"]
    projects, pairs, opps = out["projects"], out["pairs"], out["opps"]
    dsc = projects[projects.utility.str.startswith("Dominion")]

    section("PARSING")
    check("44 Dominion projects parsed", len(desc) == 44, len(desc))
    check("208 Georgia projects parsed", len(gpc) == 208, len(gpc))
    check("every project has an in-service date",
          projects.in_service_date.notna().all(),
          int(projects.in_service_date.isna().sum()))
    # The cost column is what the bonus estimate rests on, so pin a known value.
    d23 = projects[projects.project_id == "DESC_23"]
    check("DESC_23 cost read as $23,787,423",
          not d23.empty and int(d23.total_cost_usd.iloc[0]) == 23_787_423,
          None if d23.empty else d23.total_cost_usd.iloc[0])
    # Georgia costs are REDACTED in the public IRP. A number appearing here would
    # mean the parser invented one.
    ga = projects[~projects.utility.str.startswith("Dominion")]
    check("no Georgia project has a cost (redacted in the IRP)",
          ga.total_cost_usd.isna().all() | (ga.total_cost_usd.fillna(0) == 0).all(),
          int(ga.total_cost_usd.notna().sum()))
    check("every Dominion project has a cost",
          dsc.total_cost_usd.notna().all(), int(dsc.total_cost_usd.isna().sum()))

    section("GEOCODING")
    import geocode
    located = projects[projects.lat_center.notna()]
    check("most projects located (>= 200 of 252)", len(located) >= 200, len(located))

    # Endpoints may sit just outside GA/SC -- Georgia Power interconnects with
    # Alabama Power and FPL across the line, and those projects say so in their
    # names (OPELIKA, ROANOKE, (APC), (FPL)). What must never happen is an
    # endpoint hundreds of miles away because a name matched the wrong place.
    OUT_OF_STATE_MI = 40
    strays = []
    for _, r in located.iterrows():
        for e in ("a", "b"):
            lat, lon = r.get("lat_" + e), r.get("lon_" + e)
            if pd.isna(lat) or pd.isna(lon):
                continue
            out = min(geocode.dist_to_state(lat, lon, "GA"),
                      geocode.dist_to_state(lat, lon, "SC"))
            if out > OUT_OF_STATE_MI:
                strays.append((r.project_id, e, round(out), round(lat, 3), round(lon, 3)))
    check("no endpoint more than %d mi outside GA/SC" % OUT_OF_STATE_MI, not strays, strays[:4])

    # A transmission line joins two nearby stations. A huge span means one end
    # matched the wrong place -- the same shape as a Savannah name matching an
    # Augusta substation.
    spans = []
    for _, r in located.iterrows():
        if pd.notna(r.lat_a) and pd.notna(r.lat_b):
            d = miles(r.lat_a, r.lon_a, r.lat_b, r.lon_b)
            if d > 120:
                spans.append((r.project_id, round(d), r.confidence))
    # A 200-mile "line" means at least one end matched the wrong town. The span
    # guard drops the weak end, or both ends when it cannot tell which is wrong,
    # so no located project should span implausibly far at all.
    check("no project spans more than 120 mi end to end", not spans, spans[:4])

    def endpoints_of(pid):
        row = projects[projects.project_id == pid]
        return None if row.empty else row.iloc[0]

    # Names that have historically broken string normalisation.
    for pid, label in [("DESC_43", "Urquhart"), ("DESC_35", "Urquhart/Toolebeck")]:
        r = endpoints_of(pid)
        if r is None:
            skip(pid + " located", "project id not present")
        else:
            check(pid + " (" + label + ") located in SC near Augusta",
                  pd.notna(r.lat_a) and 33.2 < r.lat_a < 33.7 and -82.3 < r.lon_a < -81.6,
                  (r.lat_a, r.lon_a))

    # 'Kraft' is mangled by a naive "FT " -> "FORT " replacement.
    kraft = projects[projects.project_name.str.contains("KRAFT", case=False, na=False)]
    check("a KRAFT project exists and is located",
          not kraft.empty and kraft.lat_center.notna().any(), len(kraft))
    if not kraft.empty:
        k = kraft.iloc[0]
        # Kraft is on the Savannah River north of the city.
        check("KRAFT project sits near Savannah, not Augusta",
              pd.notna(k.lat_center) and 31.9 < k.lat_center < 32.5,
              (k.lat_center, k.lon_center))

    # '#6' survives a regex that assumes a word boundary before '#'.
    t6 = projects[projects.project_name.str.contains(r"THURMOND DAM.*#\s*6", case=False,
                                                     na=False, regex=True)]
    check("THURMOND DAM #6 project is located",
          not t6.empty and t6.lat_center.notna().all(), len(t6))

    # Two Georgia Power substations are called Goshen, ~90 mi apart. The Savannah
    # project must take the Savannah one.
    sav_goshen = projects[projects.project_name.str.contains("GOSHEN", case=False, na=False)
                          & projects.project_name.str.contains("SAV", case=False, na=False)]
    if sav_goshen.empty:
        skip("SAV Goshen disambiguation", "no SAV Goshen project found")
    else:
        g = sav_goshen.iloc[0]
        check("SAV Goshen project resolves to the Savannah Goshen",
              pd.notna(g.lat_center) and g.lat_center < 33.0, (g.lat_center, g.lon_center))

    section("OVERLAPS")
    import overlaps as ov
    check("every pair is closer than the 25 mi rule",
          (pairs.distance_mi < ov.MAX_MILES).all(), float(pairs.distance_mi.max()))
    check("pairs always join the two different utilities",
          (pairs.utility_a.str.startswith("Dominion")
           & ~pairs.utility_b.str.startswith("Dominion")).all())
    check("no project is paired with itself",
          (pairs.project_id_a != pairs.project_id_b).all())
    key = pairs.apply(lambda r: tuple(sorted((r.project_id_a, r.project_id_b))), axis=1)
    check("no duplicate pair", key.duplicated().sum() == 0, int(key.duplicated().sum()))
    check("55 pairs", len(pairs) == 55, len(pairs))
    check("7 de-duplicated opportunities", len(opps) == 7, len(opps))
    check("opportunities are a subset of the pairs",
          set(opps.overlap_id) <= set(pairs.overlap_id))

    # centre = midpoint of the two endpoints (or the single located one)
    bad = []
    for _, r in located.iterrows():
        la = [r["lat_" + e] for e in "ab" if pd.notna(r["lat_" + e])]
        lo = [r["lon_" + e] for e in "ab" if pd.notna(r["lon_" + e])]
        if la and (abs(sum(la) / len(la) - r.lat_center) > 1e-6
                   or abs(sum(lo) / len(lo) - r.lon_center) > 1e-6):
            bad.append(r.project_id)
    check("centre is the midpoint of the endpoints", not bad, bad[:4])

    # score = 0.7 * distance + 0.3 * schedule, per the sponsor's weighting
    worst = 0
    for _, r in pairs.iterrows():
        geo = 1 - r.distance_mi / ov.MAX_MILES
        tim = 1 - min(r["time_gap (day)"], ov.TIME_SCALE_DAYS) / ov.TIME_SCALE_DAYS
        worst = max(worst, abs(ov.GEO_WEIGHT * geo + ov.TIME_WEIGHT * tim - r.score))
    # tolerance covers the 2dp rounding of the stored distance
    check("score matches the 70/30 distance-schedule weighting", worst < 2e-3, worst)
    check("pairs are ranked best score first",
          list(pairs.sort_values("rank").rank_score) == sorted(pairs.rank_score, reverse=True))

    section("COORDINATION ESTIMATE")
    have = pairs[pairs.est_savings_low_usd.notna()]
    check("an estimate is produced for at least one pair", len(have) > 0, len(have))
    check("low estimate never exceeds high",
          (have.est_savings_low_usd <= have.est_savings_high_usd).all())
    # Georgia costs are redacted, so a figure can only come from the Dominion side.
    check("no estimate without a Dominion cost to base it on",
          have.project_id_a.isin(dsc[dsc.total_cost_usd.notna()].project_id).all())
    check("schedule fit is a fraction", ((pairs.schedule_fit >= 0)
                                         & (pairs.schedule_fit <= 1)).all())
    far = pairs[pairs["time_gap (day)"] > 3 * 365]
    check("projects years apart cannot share a mobilisation",
          far.empty or (far.schedule_fit == 0).all(), int((far.schedule_fit > 0).sum()))

    section("DETERMINISM")
    again = run_pipeline()
    check("a second run gives the identical pairs",
          again is not None and list(again["pairs"].overlap_id) == list(pairs.overlap_id)
          and [round(x, 6) for x in again["pairs"].distance_mi] == [round(x, 6) for x in pairs.distance_mi])


# --------------------------------------------------------------------------
# map
# --------------------------------------------------------------------------
CHROME_PATHS = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    shutil.which("google-chrome") or "", shutil.which("chromium") or "",
]

PROBE = r"""
<script>
const out = {};
const SELECTED_ON_LOAD = (typeof selected !== 'undefined' && selected) ? String(selected) : '';
const fire = el => el.dispatchEvent(new Event('input', {bubbles: true}));
const cards = () => document.querySelectorAll('.card').length;
const el = id => document.getElementById(id);
try {
  out.cards_default = cards();
  out.count_default = el('listcount').textContent.trim();
  out.paths = document.querySelectorAll('path').length;

  // Type: identifiers in mono, and a system fallback so the page still reads
  // the same when the font cannot be fetched.
  const bodyFont = getComputedStyle(document.body).fontFamily;
  out.type_body_stack = bodyFont;
  out.type_has_fallback = /system-ui|-apple-system|sans-serif/.test(bodyFont);
  const idEl = document.querySelector('.rank') || document.querySelector('.mono');
  out.type_id_is_mono = idEl ? /mono/i.test(getComputedStyle(idEl).fontFamily) : null;
  out.type_tabular = getComputedStyle(document.body).fontVariantNumeric;

  // The ranked list must be reachable without scrolling past the map key.
  const topOf = sel => Math.round(document.querySelector(sel).getBoundingClientRect().top);
  out.side_list_top = topOf('#listhead');
  out.side_key_top = topOf('#mapkey');
  out.side_list_above_key = topOf('#listhead') < topOf('#mapkey');
  out.side_key_collapsed = !el('mapkey').open;
  out.side_cards_in_view = [...document.querySelectorAll('.card')]
    .filter(c => c.getBoundingClientRect().bottom <= window.innerHeight).length;
  el('mapkey').open = true;
  out.side_key_expands = !!document.querySelector('#mapkey .legend');
  el('mapkey').open = false;

  const g = el('group');
  out.top_merged_cards = cards();
  out.top_merged_title = el('listtitle').textContent.trim();
  g.checked = false; fire(g);
  out.cards_unmerged = cards();                 // capped at the top ten
  out.top_title = el('listtitle').textContent.trim();
  out.top_count = el('listcount').textContent.trim();
  out.top_more_label = (el('morebtn') || {}).textContent;
  out.top_first_rank = document.querySelector('.card .rank').textContent.trim();
  el('morebtn').click();
  out.top_expanded = cards();
  out.top_expanded_label = (el('morebtn') || {}).textContent;
  el('morebtn').click();
  out.top_recollapsed = cards();
  g.checked = true;  fire(g); out.cards_remerged = cards();

  const mi = el('miles');
  mi.value = 10; fire(mi); out.cards_10mi = cards();
  mi.value = 25; fire(mi); out.cards_back = cards();

  const gap = el('gap');
  gap.value = '365'; fire(gap); out.cards_gap1yr = cards();
  gap.value = '99999'; fire(gap);

  const cf = el('conf');
  cf.value = '3'; fire(cf); out.cards_highonly = cards();
  cf.value = '1'; fire(cf); out.cards_confback = cards();

  // The page auto-selects the top opportunity, and that selection draws extra
  // geometry. A filter that hides the selected pair clears it, so re-select
  // before measuring or the comparison is against a different baseline.
  document.querySelector('.card').click();
  const ra = el('radii');
  out.paths_baseline = document.querySelectorAll('path').length;
  ra.checked = true; fire(ra); out.paths_allradii = document.querySelectorAll('path').length;
  ra.checked = false; fire(ra);

  const pa = el('partners');
  pa.checked = true; fire(pa); out.cards_partners = cards();
  pa.checked = false; fire(pa); out.cards_nopartners = cards();

  const sa = el('showall');
  sa.checked = false; fire(sa); out.paths_overlaponly = document.querySelectorAll('path').length;
  sa.checked = true; fire(sa);

  document.querySelector('.card').click();
  out.detail = (document.querySelector('#detail') || document.body).textContent.slice(0, 600);
  out.selected_on_load = SELECTED_ON_LOAD;

  // ---- click any project to re-centre the 25-mile circle (his feature) ----
  const gpc = DATA.projects.find(p => p.c && p.util === 'Georgia Power');
  const dom = DATA.projects.find(p => p.c && p.util.startsWith('Dominion'));
  selectProject(gpc.id, false);
  out.recentre_gpc_panel = el('detail').textContent.slice(0, 200);
  out.recentre_gpc_drawn = layerSel.getLayers().length > 0;
  out.recentre_gpc_ring = rings.some(r => r.kind === 'sel' && r.p.id === gpc.id);
  selectProject(dom.id, false);
  out.recentre_dom_ring = rings.some(r => r.kind === 'sel' && r.p.id === dom.id);
  out.recentre_dom_panel = el('detail').textContent.slice(0, 200);
  // a project with two located end points draws as a line, one end point as a marker
  const twoEnds = DATA.projects.find(p => p.a && p.b);
  const oneEnd = DATA.projects.find(p => p.c && !(p.a && p.b));
  out.geom_two_ends = !!twoEnds; out.geom_one_end = !!oneEnd;
  document.querySelector('.card').click();

  // ---- the detail card folds away without losing the selection ----
  const dc = el('detail');
  out.fold_open_on_load = dc.style.display !== 'none';
  // One control only. It must really be painted, not merely present in the DOM:
  // a previous version had it covered by an absolutely positioned close button,
  // which every behavioural test passed straight through.
  const fb = dc.querySelector('.fold').getBoundingClientRect();
  out.fold_btn_size = [Math.round(fb.width), Math.round(fb.height)];
  out.fold_btn_visible = getComputedStyle(dc.querySelector('.fold')).display !== 'none'
                         && fb.width > 0 && fb.height > 0;
  out.no_close_button = !dc.querySelector('.x');
  out.fold_btn_glyph_open = dc.querySelector('.fold').textContent.trim();
  // nothing else in the bar may sit on top of it
  out.fold_btn_on_top = (() => {
    const c = document.elementFromPoint((fb.left + fb.right) / 2, (fb.top + fb.bottom) / 2);
    return !!(c && c.closest('.fold'));
  })();
  out.dim_open = getComputedStyle(map.getPane('overlaps')).opacity;
  out.fold_h_open = Math.round(dc.getBoundingClientRect().height);
  out.fold_layers_open = layerSel.getLayers().length;
  dc.querySelector('.fold').click();
  out.fold_class = dc.classList.contains('folded');
  out.fold_h_folded = Math.round(dc.getBoundingClientRect().height);
  out.fold_body_hidden = getComputedStyle(dc.querySelector('.dbody')).display === 'none';
  out.fold_title = dc.querySelector('h3').textContent.trim();
  out.fold_layers_kept = layerSel.getLayers().length;
  out.fold_still_selected = String(selected);
  out.fold_btn_glyph_folded = dc.querySelector('.fold').textContent.trim();
  out.dim_folded = getComputedStyle(map.getPane('overlaps')).opacity;
  dc.click();                                   // clicking the folded bar reopens it
  out.fold_reexpanded = !dc.classList.contains('folded');
  dc.querySelector('.fold').click();            // fold, then pick another pair
  document.querySelectorAll('.card')[1].click();
  out.fold_reopens_on_pick = !dc.classList.contains('folded');
  out.fold_pick_shows_body = getComputedStyle(dc.querySelector('.dbody')).display !== 'none';
  out.fold_new_title = dc.querySelector('h3').textContent.trim();
  out.fold_new_drawn = layerSel.getLayers().length > 0;
  setFold(false);

  // ---- hover readout over the 25-mile circles ----
  const box = el('hoverinfo');
  out.hover_box_exists = !!box;
  if (box) {
    const rr = el('radii'); rr.checked = true; fire(rr);
    out.hover_rings = rings.length;
    clearHover();
    out.hover_hidden_at_rest = box.hidden;

    // the midpoint of the two closest circle centres is inside both
    let best = null;
    for (let i = 0; i < rings.length; i++) for (let j = i + 1; j < rings.length; j++) {
      const d = map.distance(L.latLng(rings[i].p.c), L.latLng(rings[j].p.c));
      if (d < 2 * RADIUS_MI * MILE_M && (!best || d < best.d)) best = {i, j, d};
    }
    out.hover_has_intersection = !!best;
    if (best) {
      const a = rings[best.i].p.c, b = rings[best.j].p.c;
      const mid = L.latLng((a[0] + b[0]) / 2, (a[1] + b[1]) / 2);
      const hits = ringsUnder(mid);
      out.hover_hits_multi = hits.length;
      renderHover(hits);
      out.hover_shown_multi = !box.hidden;
      out.hover_multi_class = box.classList.contains('two');
      out.hover_multi_text = box.textContent.replace(/\s+/g, ' ').trim().slice(0, 120);
      out.hover_highlighted = rings.filter(r => r.layer.options.weight > r.base.weight).length;
      out.hover_no_thinning = rings.every(r => r.layer.options.weight >= r.base.weight);
      out.hover_weights = rings.map(r => [r.base.weight, r.layer.options.weight]);
      // every Georgia project the panel counts must really be in range of all hits
      const shared = sharedProjects(hits).list;
      out.hover_shared_ok = shared.every(g =>
        hits.every(r => map.distance(L.latLng(g.c), L.latLng(r.p.c)) <= RADIUS_MI * MILE_M));
      out.hover_shared_n = shared.length;
      // cost block: spend must be the sum of the hovered projects' own costs
      out.hover_spend_sum = hits.map(r => r.p.cost).filter(c => c).reduce((s, c) => s + c, 0);
      out.hover_costs_present = hits.filter(r => r.p.cost).length;
    }
    // a point inside exactly one circle
    let solo = null;
    for (let dx = 0; dx < 0.5 && !solo; dx += 0.01) {
      const pt = L.latLng(rings[0].p.c[0], rings[0].p.c[1] + dx);
      if (ringsUnder(pt).length === 1) solo = pt;
    }
    if (solo) {
      renderHover(ringsUnder(solo));
      out.hover_solo_text = box.textContent.replace(/\s+/g, ' ').trim().slice(0, 60);
      out.hover_solo_class = box.classList.contains('two');
    }
    // a circle that owns an overlap carrying an estimate must quote it
    const withEst = DATA.overlaps.find(o => o.lo != null && o.lo > 0);
    const ringEst = withEst && rings.find(r => r.p.id === withEst.a);
    if (ringEst) {
      renderHover([ringEst]);
      const t = box.textContent.replace(/\s+/g, ' ').trim();
      out.hover_cost_text = t;
      out.hover_quotes_saving = t.includes('rough saving if coordinated');
      out.hover_quotes_overlap_id = t.includes(withEst.id);
      out.hover_quotes_spend = t.includes('planned Dominion spend');
      out.hover_est_lo = withEst.lo; out.hover_est_hi = withEst.hi;
      out.hover_proj_cost = ringEst.p.cost;
    }
    // a circle with no estimated overlap must say so rather than show nothing
    const ringNo = rings.find(r => !visible.some(o => o.a === r.p.id && o.lo != null && o.lo > 0));
    if (ringNo) {
      renderHover([ringNo]);
      out.hover_noest_text = box.textContent.replace(/\s+/g, ' ').trim();
    }
    clearHover();
    out.hover_hidden_after = box.hidden;
    out.hover_styles_restored = rings.every(r => r.layer.options.weight === r.base.weight);
    rr.checked = false; fire(rr);
  }
} catch (e) { out.error = e.message; }
const d = document.createElement('div'); d.id = 'PROBE';
d.textContent = JSON.stringify(out); document.body.appendChild(d);
</script>
"""


def test_map():
    section("MAP (headless Chrome)")
    chrome = next((p for p in CHROME_PATHS if p and os.path.exists(p)), None)
    if not chrome:
        skip("map tests", "no Chrome or Chromium found")
        return
    if not os.path.exists("gridlock_map.html"):
        skip("map tests", "gridlock_map.html not built; run run_all.py first")
        return

    html = open("gridlock_map.html").read().replace("</body>", PROBE + "\n</body>")
    tmp = tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, dir=os.getcwd())
    tmp.write(html)
    tmp.close()
    try:
        dom = subprocess.run(
            [chrome, "--headless", "--disable-gpu", "--no-sandbox",
             "--window-size=1400,900", "--virtual-time-budget=15000",
             "--dump-dom", "file://" + tmp.name],
            capture_output=True, text=True, timeout=180).stdout
    finally:
        os.unlink(tmp.name)

    m = re.search(r'<div id="PROBE">(.*?)</div>', dom, re.S)
    if not m:
        check("map page executed its JavaScript", False, "no probe output")
        return
    r = json.loads(m.group(1))
    if r.get("error"):
        check("map page ran without a JavaScript error", False, r["error"])
        return

    check("map renders project geometry", r["paths"] > 100, r["paths"])
    check("opportunity list is populated", r["cards_default"] == 7, r["cards_default"])
    check("list header reports the de-duplication",
          "from 55 pairs" in r["count_default"], r["count_default"])
    # The ranked list is the deliverable, so it must be visible in the sidebar
    # without scrolling past the map key, which is long and read once.
    check("identifiers are set in a monospace face", r.get("type_id_is_mono"),
          r.get("type_body_stack"))
    check("the type stack falls back to the system font",
          r.get("type_has_fallback"), r.get("type_body_stack"))
    check("figures are tabular so columns line up",
          "tabular-nums" in (r.get("type_tabular") or ""), r.get("type_tabular"))

    check("the ranked list sits above the map key", r.get("side_list_above_key"),
          (r.get("side_list_top"), r.get("side_key_top")))
    check("the map key is folded away by default", r.get("side_key_collapsed"))
    check("the map key still expands", r.get("side_key_expands"))
    check("at least one ranked card is visible without scrolling",
          r.get("side_cards_in_view", 0) >= 1, r.get("side_cards_in_view"))

    # The deliverable is a ranked top ten. With duplicates merged there are only
    # seven distinct opportunities, so the cap only bites on the raw pair list.
    check("the ranked list is capped at ten", r.get("cards_unmerged") == 10,
          r.get("cards_unmerged"))
    check("the heading says Top 10 when capped",
          "Top 10" in (r.get("top_title") or ""), r.get("top_title"))
    check("the count shows what is hidden",
          "of 55" in (r.get("top_count") or ""), r.get("top_count"))
    check("the list is ranked best first", r.get("top_first_rank") == "#1",
          r.get("top_first_rank"))
    check("show-all reveals every pair", r.get("top_expanded") == 55,
          r.get("top_expanded"))
    check("the control offers to collapse again",
          "top 10" in (r.get("top_expanded_label") or "").lower(),
          r.get("top_expanded_label"))
    check("collapsing returns to ten", r.get("top_recollapsed") == 10,
          r.get("top_recollapsed"))
    check("merged view shows all seven distinct opportunities uncapped",
          r.get("top_merged_cards") == 7, r.get("top_merged_cards"))
    check("re-ticking it returns to 7", r["cards_remerged"] == 7, r["cards_remerged"])
    check("distance slider narrows the list",
          r["cards_10mi"] < r["cards_default"], (r["cards_10mi"], r["cards_default"]))
    check("distance slider restores", r["cards_back"] == 7, r["cards_back"])
    check("time-gap filter narrows the list",
          r["cards_gap1yr"] < r["cards_default"], r["cards_gap1yr"])
    check("location-quality 'high only' narrows the list",
          r["cards_highonly"] < r["cards_default"], r["cards_highonly"])
    check("location-quality restores", r["cards_confback"] == 7, r["cards_confback"])
    check("'circle for every project' draws more geometry",
          r["paths_allradii"] > r["paths_baseline"],
          (r["paths_allradii"], r["paths_baseline"]))
    check("ITS partner toggle changes the result",
          r["cards_partners"] != r["cards_nopartners"] or r["cards_partners"] >= 7,
          (r["cards_partners"], r["cards_nopartners"]))
    check("hiding non-overlapping projects removes geometry",
          r["paths_overlaponly"] < r["paths"], (r["paths_overlaponly"], r["paths"]))
    d = r.get("detail", "")
    check("clicking a card opens a detail panel", len(d) > 50, len(d))
    check("detail panel explains the 25-mile radius test", "25-mile" in d or "25 mi" in d)
    check("detail panel shows a cost figure", "$" in d)
    check("top opportunity is selected on load",
          bool(r.get("selected_on_load")), r.get("selected_on_load"))

    # Hovering the 25-mile circles. Leaflet's own mouseover reports only the
    # topmost shape, so intersecting circles are exactly the case that breaks;
    # containment is computed from the cursor instead.
    # The detail card sits over the map, so it must be foldable without losing
    # the selection drawn underneath it.
    # His click-to-recentre: the 25-mile test runs from either company's project,
    # not only from a Dominion one.
    check("clicking a Georgia Power project re-centres the circle on it",
          r.get("recentre_gpc_ring") and r.get("recentre_gpc_drawn"))
    check("clicking a Dominion project re-centres the circle on it",
          r.get("recentre_dom_ring"))
    check("the re-centred panel names the circle it drew",
          "25-mile circle" in (r.get("recentre_gpc_panel") or ""),
          (r.get("recentre_gpc_panel") or "")[:80])
    check("both a two-endpoint and a single-endpoint project exist to draw",
          r.get("geom_two_ends") and r.get("geom_one_end"))

    check("the collapse button is visible with a usable hit target",
          r.get("fold_btn_visible") and min(r.get("fold_btn_size", [0, 0])) > 12,
          r.get("fold_btn_size"))
    check("nothing is painted on top of the collapse button",
          r.get("fold_btn_on_top"), "something covers it")
    check("there is no close button", r.get("no_close_button"))
    check("the control reads as minus when open and plus when collapsed",
          r.get("fold_btn_glyph_open") in ("\u2212", "-")
          and r.get("fold_btn_glyph_folded") in ("+",),
          (r.get("fold_btn_glyph_open"), r.get("fold_btn_glyph_folded")))
    check("collapsing undims the rest of the map",
          float(r.get("dim_folded", 0)) > float(r.get("dim_open", 1)),
          (r.get("dim_open"), r.get("dim_folded")))
    check("detail card folds to a title bar",
          r.get("fold_class") and r.get("fold_h_folded", 999) < 80,
          r.get("fold_h_folded"))
    check("folding frees most of the map",
          r.get("fold_h_folded", 999) < r.get("fold_h_open", 0) / 3,
          (r.get("fold_h_folded"), r.get("fold_h_open")))
    check("folded card hides its body", r.get("fold_body_hidden"))
    check("folded card still names the pair",
          "OVL" in (r.get("fold_title") or ""), r.get("fold_title"))
    check("folding keeps the pair selected and drawn",
          r.get("fold_layers_kept") == r.get("fold_layers_open")
          and r.get("fold_still_selected", "null") != "null",
          (r.get("fold_layers_kept"), r.get("fold_layers_open")))
    check("clicking the folded bar reopens it", r.get("fold_reexpanded"))
    # Folding must not swallow the next selection: picking an item is a request
    # to read it, so the card reopens rather than staying a title bar.
    check("picking another pair reopens the folded card",
          r.get("fold_reopens_on_pick"))
    check("and its details are actually shown", r.get("fold_pick_shows_body"))
    check("a pair picked while folded is still drawn on the map", r.get("fold_new_drawn"))
    check("hover readout panel exists", r.get("hover_box_exists"))
    check("hover panel hidden until the cursor is over a circle",
          r.get("hover_hidden_at_rest") is True)
    check("circles are registered for hover", r.get("hover_rings", 0) > 1, r.get("hover_rings"))
    check("the map has intersecting circles to hover", r.get("hover_has_intersection"))
    check("a point in the intersection reports every circle it is inside",
          r.get("hover_hits_multi", 0) >= 2, r.get("hover_hits_multi"))
    check("hovering an intersection shows the panel", r.get("hover_shown_multi"))
    check("intersection is styled differently from a single circle",
          r.get("hover_multi_class"))
    check("panel names how many circles overlap",
          "overlap here" in (r.get("hover_multi_text") or ""), r.get("hover_multi_text"))
    check("hover thickens each circle relative to its own weight, never thins it",
          r.get("hover_no_thinning"), r.get("hover_weights"))
    check("every circle under the cursor is highlighted",
          r.get("hover_highlighted") == r.get("hover_hits_multi"),
          (r.get("hover_highlighted"), r.get("hover_hits_multi")))
    check("projects counted are inside all hovered circles",
          r.get("hover_shared_ok"), r.get("hover_shared_n"))
    if r.get("hover_solo_text"):
        check("a single circle reads as one, not as an intersection",
              "Inside 1 circle" in r["hover_solo_text"] and not r.get("hover_solo_class"),
              r.get("hover_solo_text"))
    else:
        skip("single-circle hover wording", "no point found inside exactly one circle")
    # Cost on hover. Two separate figures: published Dominion spend, and the
    # saving from the best-ranked overlap. They must never be added together.
    check("hover panel states the planned Dominion spend", r.get("hover_quotes_spend"))
    check("hover panel quotes a coordination saving where one exists",
          r.get("hover_quotes_saving"), r.get("hover_cost_text"))
    check("the saving names the overlap it came from", r.get("hover_quotes_overlap_id"))
    check("spend shown is the sum of the hovered projects' own costs",
          r.get("hover_spend_sum", 0) > 0 and r.get("hover_costs_present", 0) > 0,
          (r.get("hover_spend_sum"), r.get("hover_costs_present")))
    check("spend and saving are different figures, not one added to the other",
          r.get("hover_proj_cost", 0) > r.get("hover_est_hi", 0),
          (r.get("hover_proj_cost"), r.get("hover_est_hi")))
    if r.get("hover_noest_text"):
        check("a circle with no estimate says so rather than showing nothing",
              "no cost saving estimated" in r["hover_noest_text"]
              or "rough saving" in r["hover_noest_text"],
              r["hover_noest_text"][:90])
    else:
        skip("no-estimate hover wording", "every circle owns an estimated overlap")
    check("leaving the circles hides the panel", r.get("hover_hidden_after"))
    check("leaving the circles restores the circle styling",
          r.get("hover_styles_restored"))


if __name__ == "__main__":
    only = [a for a in sys.argv[1:] if a.startswith("--")]
    if not only or "--pipeline" in only:
        test_pipeline()
    if not only or "--map" in only:
        test_map()
    print("\n%d passed, %d failed, %d skipped" % (len(PASS), len(FAIL), len(SKIP)))
    if FAIL:
        print("failed:\n  " + "\n  ".join(FAIL))
    sys.exit(1 if FAIL else 0)
