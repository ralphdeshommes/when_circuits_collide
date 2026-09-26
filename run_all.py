"""Run the whole Gridlock pipeline: PDFs -> locations -> overlaps -> interactive map + workbook.

    pip install -r requirements.txt
    python run_all.py "path/to/Project Listings"     # folder that holds the two utility PDFs
    python run_all.py --refresh                      # also re-download the OpenStreetMap data

The folder must contain  Dominion Energy/<pdf>  and  Georgia Power/<pdf>  (the challenge package
layout). Instead of passing the path you can set the GRIDLOCK_SRC environment variable.

Everything happens in memory - no intermediate files. data/ only holds saved copies of the
OpenStreetMap downloads, so a normal run takes seconds and gives the same answer every time.
Anything missing there is downloaded automatically.
"""
import os
import subprocess
import sys

PY = sys.executable
DATA = [("data/osm_power.json", "download substations from OpenStreetMap", "fetch_osm.py"),
        ("data/state_borders.json", "download state outlines", "fetch_border.py")]


def main(argv):
    refresh = "--refresh" in argv
    paths = [a for a in argv if not a.startswith("--")]
    if paths:
        os.environ["GRIDLOCK_SRC"] = paths[0]
    from parse_projects import DESC_PDF, GPC_PDF, parse_desc, parse_gpc      # reads GRIDLOCK_SRC
    missing = [p for p in (DESC_PDF, GPC_PDF) if not os.path.isfile(p)]
    if missing:
        sys.exit("Could not find the utility PDFs:\n  " + "\n  ".join(missing) +
                 "\nPass the 'Project Listings' folder:  python run_all.py \"path/to/Project Listings\"")
    os.makedirs("data", exist_ok=True)
    for path, label, script in DATA:
        if refresh or not os.path.exists(path):
            print("\n== " + label, flush=True)
            if subprocess.run([PY, script]).returncode:
                sys.exit("step failed: " + label)

    import build_map
    import export_xlsx
    import geocode
    import overlaps
    import verify

    print("\n== parse the two PDFs", flush=True)
    desc, gpc = parse_desc(), parse_gpc()
    print("   %d Dominion + %d Georgia projects" % (len(desc), len(gpc)))
    print("\n== find a location for every project", flush=True)
    geocoded = geocode.geocode_projects(desc, gpc)
    print("\n== verify matches and grade confidence", flush=True)
    projects = verify.verify_projects(geocoded)
    print(projects.groupby(["utility", "confidence"]).size().unstack(fill_value=0).to_string())
    print("\n== find overlaps, rank them, estimate value", flush=True)
    pairs, partners, opps, projects = overlaps.compute(projects)
    print("   %d overlapping pairs (< %d mi) -> %d distinct opportunities" % (len(pairs), overlaps.MAX_MILES, len(opps)))
    print("\n== build the interactive map and the workbook", flush=True)
    build_map.build_map(projects, pairs, partners)
    export_xlsx.export_xlsx(projects, pairs, opps)

    print("\nTop coordination opportunities:")
    for _, r in opps.iterrows():
        print("  #%d  %5.1f mi  %5d days  [%s]  %s  <->  %s" % (
            r["opportunity_rank"], r["distance_mi"], r["time_gap (day)"], r["confidence"],
            r["project_name_a"][:44], r["project_name_b"][:44]))
    print("\nOpen gridlock_map.html in a browser (interactive map). Tables: Projects_Overlaps.xlsx")


if __name__ == "__main__":
    main(sys.argv[1:])
