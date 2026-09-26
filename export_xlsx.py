"""Write Projects_Overlaps.xlsx in the same layout as the starter workbook.

Sheets:  projects  (starter columns first, then confidence / source columns)
         overlaps  (starter columns first, then rank, score, corridor and cost/impact estimate)
         top_opportunities  (ranked coordination list with the reason each pair matters)
         assumptions  (the numbers behind the rough cost / land estimates)

Called by run_all.py: export_xlsx(projects, pairs, opportunities).
"""
import pandas as pd
from openpyxl.utils import get_column_letter

from overlaps import ASSUMPTIONS

PROJECT_COLS = ["project_id", "utility", "state", "project_name", "name_a", "lat_a", "lon_a", "name_b", "lat_b",
                "lon_b", "lat_center", "lon_center", "in_service_date", "overlap_count", "overlap_1", "overlap_2",
                "overlap_3", "confidence", "sponsor", "source_id", "status", "total_cost_usd", "geo_notes"]
OVERLAP_COLS = ["overlap_id", "distance_mi", "time_gap (day)", "utility_a", "project_id_a", "project_name_a",
                "utility_b", "project_id_b", "project_name_b", "rank", "score", "confidence", "sponsor_b",
                "in_service_a", "in_service_b", "coordination_type", "min_separation_mi", "shared_corridor_mi",
                "schedule_fit", "acres_saved",
                "est_savings_low_usd", "est_savings_high_usd", "why"]


def widths(ws, df):
    for i, col in enumerate(df.columns, 1):
        longest = max([len(str(col))] + [len(str(v)) for v in df[col].head(200)])
        ws.column_dimensions[get_column_letter(i)].width = min(max(10, longest + 2), 60)
    ws.freeze_panes = "A2"


def export_xlsx(projects, ov, opps, out="Projects_Overlaps.xlsx"):
    proj = projects[projects["sponsor"].isna() | projects["sponsor"].isin(["GPC", "SAV"]) | (projects["utility"] != "Georgia Power")]
    top = opps.head(10)[["opportunity_rank", "overlap_id", "distance_mi", "time_gap (day)", "confidence",
                         "project_name_a", "project_name_b", "why", "coordination_type", "est_savings_low_usd",
                         "est_savings_high_usd", "same_corridor_projects", "other_nearby_pairs",
                         "other_nearby_examples"]]
    assume = pd.DataFrame([
        ("Right-of-way width (ft) by voltage", ", ".join(f"{k} kV = {v}" for k, v in ASSUMPTIONS["row_width_ft"].items())),
        ("Second line beside an existing one", f"adds {ASSUMPTIONS['second_line_extra_width']:.0%} of its own width"),
        ("Corridor 'shared' when lines are within", f"{ASSUMPTIONS['corridor_buffer_mi']} mi along their length"),
        ("Cost avoided by joint delivery", f"{ASSUMPTIONS['savings_low_pct']:.0%} (low) - {ASSUMPTIONS['savings_high_pct']:.0%} (high) of the "
                                           "Dominion construction cost on the shared stretch; Georgia costs are REDACTED in the IRP"),
        ("Shared site", f"an end point of each project within {ASSUMPTIONS['site_mi']} mi; "
                        f"{ASSUMPTIONS['site_share_of_cost']:.0%} of the Dominion project cost is treated as tied to the shared terminal"),
        ("Schedule fit", f"savings scale linearly to zero as the in-service gap grows to {ASSUMPTIONS['schedule_taper_days']} days"),
        ("Land savings counted only when", "at least one project is a new-build (a rebuild reuses its own corridor)"),
        ("Line geometry", "straight segment between the two named substations (actual routes are longer)"),
        ("Overlap rule", "haversine distance between project centres < 25 mi; centre = midpoint of the two located end points"),
        ("Top opportunities", "duplicates removed: sibling projects (same utility, identical end points and location) "
                              "are merged into one corridor and each corridor appears in at most one opportunity, best pair "
                              "first; the other nearby pairs are counted in other_nearby_pairs. The overlaps sheet keeps every pair."),
        ("Georgia side", "Georgia Power (GPC, SAV) projects; GTC / MEAG / DU ITS-partner projects are left out (none overlap a Dominion project)"),
    ], columns=["assumption", "value"])
    with pd.ExcelWriter(out, engine="openpyxl", datetime_format="m/d/yyyy") as xw:
        for name, df in (("projects", proj[PROJECT_COLS]), ("overlaps", ov[OVERLAP_COLS]),
                         ("top_opportunities", top), ("assumptions", assume)):
            df.to_excel(xw, sheet_name=name, index=False)
            widths(xw.sheets[name], df)
    print(f"wrote {out}: {len(proj)} projects, {len(ov)} overlaps")
