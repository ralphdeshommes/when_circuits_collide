"""Part 0 - turn the two utility PDFs into project tables (no coordinates yet).

  Dominion Energy SC : "2024-2028 $2M and above project descriptions"  (44 one-page projects)
  Georgia Power      : 2025 IRP Volume 3, "2024 GA ITS Ten-Year Plan (2025-2034)" detail sections
                       (name / TEAMS # / need date / description), plus the Table 2 project list
                       for the project sponsor column (GPC, SAV, GTC, MEAG, DU).

Only public filings are used. Anything marked REDACTED (costs) stays empty.

Run:  python parse_projects.py
Out:  data/desc_raw.csv, data/gpc_raw.csv
"""
import os
import re
from datetime import datetime

import fitz  # PyMuPDF
import pandas as pd

SRC = os.environ.get(
    "GRIDLOCK_SRC", os.path.expanduser("~/Downloads/Sperry-Tech-Challenge/Project Listings"))
DESC_PDF = os.path.join(SRC, "Dominion Energy", "2024-2028-2million-and-above-project-descriptions.pdf")
GPC_PDF = os.path.join(SRC, "Georgia Power", "2025 IRP Volume 3 PUBLIC DISCLOSURE.pdf")
ITS_FIRST_PAGE, ITS_LAST_PAGE = 171, 425      # 1-indexed pages of the Georgia ITS Ten-Year Plan
TABLE2_PAGES = range(177, 193)                # 1-indexed pages holding "Table 2 ... Project List"


def clean(s):
    return re.sub(r"\s+", " ", s.replace("–", "-").replace("—", "-")).strip()


def parse_date(s):
    """First m/d/y date found in s -> datetime (2-digit years are 20xx)."""
    m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{2,4})", s or "")
    if not m:
        return None
    mo, d, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
    y += 2000 if y < 100 else 0
    return datetime(y, mo, d)


# --------------------------------------------------------------------------- Dominion
def parse_desc():
    doc = fitz.open(DESC_PDF)
    rows = []
    for page in doc:
        t = page.get_text()
        m = re.search(r"5 Year Budget\s*(.*?)\s*Project ID\s*(.*?)\s*Project Description\s*(.*?)\s*"
                      r"Project Need\s*(.*?)\s*Project Status\s*(.*?)\s*Planned In-Service Date\s*(.*?)\s*"
                      r"Estimated Project Cost(.*?)(?:\*Total Estimated|$)", t, re.S)
        if not m:
            print("  ! could not parse a Dominion page:", t[:80].replace("\n", " "))
            continue
        name, src_id, desc, need, status, date_txt, cost_txt = [clean(x) for x in m.groups()]
        costs = [int(c.replace(",", "")) for c in re.findall(r"\$([\d,]+)", cost_txt)]
        rows.append({
            "project_name": name,
            "source_id": src_id,
            "description": desc,
            "project_need": need,
            "status": status,
            "in_service_text": date_txt,
            "in_service_date": parse_date(date_txt),
            "total_cost_usd": max(costs) if costs else None,   # last column "Total*" is the largest
        })
    df = pd.DataFrame(rows)
    df.insert(0, "project_id", [f"DESC_{i}" for i in range(1, len(df) + 1)])
    df.insert(1, "utility", "Dominion Energy South Carolina")
    df.insert(2, "state", "SC")
    return df


# --------------------------------------------------------------------------- Georgia Power
def _page_lines(page, gap=17.0):
    """Text lines of one page in reading order (words grouped by baseline), with a blank line
    wherever the vertical gap is larger than a normal line. Same result as `pdftotext -layout`
    for these pages (checked on all 208 projects), without needing poppler installed."""
    words = page.get_text("words")
    words.sort(key=lambda w: ((w[1] + w[3]) / 2, w[0]))
    rows, cur, cy = [], [], None
    for w in words:
        yc = (w[1] + w[3]) / 2
        if cy is None or abs(yc - cy) <= 3:
            cur.append(w)
            cy = yc if cy is None else sum((x[1] + x[3]) / 2 for x in cur) / len(cur)
        else:
            rows.append((cy, cur))
            cur, cy = [w], yc
    if cur:
        rows.append((cy, cur))
    out, prev = [], None
    for cy, ws in rows:
        if prev is not None and cy - prev > gap:
            out.append("")
        out.append(" ".join(x[4] for x in sorted(ws, key=lambda x: x[0])))
        prev = cy
    return out


def layout_text(first, last):
    doc = fitz.open(GPC_PDF)
    pages = [chr(10).join(_page_lines(doc[p - 1])) for p in range(first, last + 1)]
    return (chr(10) * 2).join(pages)


SKIP_LINE = re.compile(r"CRITICAL ENERGY|be aware that|notification\.|policy, should|employees\.|"
                       r"PUBLIC DISCLOSURE|GA ITS Ten-Year Plan|^\s*Page \d+ of")


def parse_gpc_details():
    text = layout_text(ITS_FIRST_PAGE, ITS_LAST_PAGE)
    lines = text.splitlines()
    rows = []
    for i, ln in enumerate(lines):
        m = re.match(r"\s*Teams #\s*(\d+)", ln)
        if not m:
            continue
        # project name = the non-boilerplate lines directly above the "Teams #" line
        name_parts, j = [], i - 1
        while j >= 0 and len(name_parts) < 4:
            s = lines[j].strip()
            if not s:
                if name_parts:
                    break
            elif SKIP_LINE.search(s):
                break
            else:
                name_parts.insert(0, s)
            j -= 1
        # need / start date is on the next non-empty line
        k = i + 1
        while k < len(lines) and not lines[k].strip():
            k += 1
        dm = re.search(r"Need Date\s*(\S+)\s*Start Date\s*(\S+)", lines[k])
        # description = text between "Description" and "Supporting Statement"
        d0 = next((x for x in range(k, min(k + 12, len(lines))) if lines[x].strip() == "Description"), None)
        desc = ""
        if d0 is not None:
            buf = []
            for x in range(d0 + 1, min(d0 + 40, len(lines))):
                s = lines[x].strip()
                if s.startswith("Supporting Statement") or SKIP_LINE.search(s):
                    break
                buf.append(s)
            desc = clean(" ".join(buf))
        rows.append({
            "project_name": clean(" ".join(name_parts)),
            "source_id": m.group(1),
            "need_text": dm.group(1) if dm else "",
            "in_service_date": parse_date(dm.group(1)) if dm else None,
            "start_date": parse_date(dm.group(2)) if dm else None,
            "description": desc,
        })
    return pd.DataFrame(rows)


def parse_gpc_sponsors():
    """TEAMS number -> (zone, sponsor) from Table 2, using word positions (the table's
    multi-line cells make plain text extraction unreliable)."""
    doc = fitz.open(GPC_PDF)
    out, last_hdr = {}, None
    for pno in TABLE2_PAGES:
        page = doc[pno - 1]
        words = page.get_text("words")
        hdr = {w[4]: w for w in words if w[4] in ("Zone", "TEAMS", "Sponsor", "Need")}
        if "TEAMS" in hdr and "Sponsor" in hdr:
            last_hdr = hdr                    # column positions repeat on every page
        if last_hdr is None:
            continue
        hdr = last_hdr
        x_teams0, x_spon0 = hdr["TEAMS"][0] - 6, hdr["Sponsor"][0] - 8
        x_teams1, x_spon1 = hdr["TEAMS"][0] + 40, hdr["Sponsor"][0] + 45
        zone_x1 = hdr["Zone"][0] + 30
        for w in words:
            if re.fullmatch(r"\d{5}", w[4]) and x_teams0 <= w[0] <= x_teams1:
                yc = (w[1] + w[3]) / 2
                spon = [s[4] for s in words if s[4] in ("GPC", "SAV", "GTC", "MEAG", "DU")
                        and x_spon0 <= s[0] <= x_spon1 and abs((s[1] + s[3]) / 2 - yc) < 5]
                zone = [z[4] for z in words if re.fullmatch(r"2\d\d", z[4]) and z[0] < zone_x1
                        and abs((z[1] + z[3]) / 2 - yc) < 5]
                out[w[4]] = (zone[0] if zone else "", spon[0] if spon else "")
    return out


PREFIX_SPONSOR = {"SAV": "SAV", "GTC": "GTC", "MEAG": "MEAG", "DU": "DU"}


def parse_gpc():
    df = parse_gpc_details()
    spons = parse_gpc_sponsors()
    df["zone"] = df["source_id"].map(lambda s: spons.get(s, ("", ""))[0])
    df["sponsor"] = df["source_id"].map(lambda s: spons.get(s, ("", ""))[1])

    def guess(row):                      # fall back to the name prefix ("GTC: ...", "DU: ...")
        if row["sponsor"]:
            return row["sponsor"]
        m = re.match(r"(SAV|GTC|MEAG|DU)\b\s*[:\-]", row["project_name"])
        return PREFIX_SPONSOR[m.group(1)] if m else "GPC"
    df["sponsor"] = df.apply(guess, axis=1)
    df = df.drop_duplicates("source_id").reset_index(drop=True)
    df.insert(0, "project_id", [f"GPC_{i}" for i in range(1, len(df) + 1)])
    df.insert(1, "utility", "Georgia Power")
    df.insert(2, "state", "GA")
    return df


if __name__ == "__main__":
    os.makedirs("data", exist_ok=True)
    d = parse_desc()
    print(f"Dominion: {len(d)} projects, {d['in_service_date'].notna().sum()} with dates")
    d.to_csv("data/desc_raw.csv", index=False)
    g = parse_gpc()
    print(f"Georgia : {len(g)} projects, {g['in_service_date'].notna().sum()} with dates")
    print(g["sponsor"].value_counts().to_dict())
    g.to_csv("data/gpc_raw.csv", index=False)
