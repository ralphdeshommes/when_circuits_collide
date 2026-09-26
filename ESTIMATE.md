# Coordination opportunity — illustrative estimate

**Pair #1 (OVL_1): DESC_23 × GPC_20277** — the top-ranked overlap, verified on both sides.

> **This is an illustrative estimate, not a claimed savings figure.** The cost
> basis is now a real published number, but the savings percentages applied to it
> are assumptions, labelled A2 and A3. Treat the output as an order of magnitude
> that justifies a conversation between the two utilities, not as a number to put
> in a budget.

> **Retrospective example.** DESC_23's planned in-service date of **2025-12-31 has
> passed**, and both projects come from 2024–2025 filings. This is not a live
> opportunity — it is a demonstration that *our tool would have flagged this pair
> before construction*, when coordinating was still possible. That is the point of
> the exercise: the same scan run against current filings surfaces the pairs that
> are still actionable.

---

## The pair

| | DESC_23 | GPC_20277 |
|---|---|---|
| Project | Jasper – Okatie 230 kV #2: Construct | SAV: MCINTOSH – PURRYSBURG 230 kV Reactors |
| Utility | Dominion Energy South Carolina | Georgia Power |
| Scope | New 230 kV line, ~6.5 miles | Reactor installation at existing substations |
| Cost | **$23,787,423** (published) | **Redacted** |
| In service | 2025-12-31 *(passed)* | 2026-06-01 |
| Status | In Progress | Planned |
| Source | DESC Planned Transmission Projects $2M+ (2024–2028), project 23 of 44 | GA 2025 IRP Vol. 3, Table 2, TEAMS #20277 |

**Measured from the project data (not assumed):**

- Project centres are **5.65 miles** apart.
- In-service dates are **152 days** apart.
- DESC_23's two endpoints are **5.65 miles** apart straight-line, from
  sponsor-verified coordinates. The PDF gives the built line as **6.5 miles**,
  a routing factor of 1.15 — consistent, since a line follows a right-of-way
  rather than the crow-flies path.
- Both are **230 kV**.

Two 230 kV projects, six miles apart, five months apart, run by two different
utilities that do not coordinate schedules. That is the opportunity.

---

## The math, step by step

### Step 1 — Cost basis for DESC_23  *(published figure, not an assumption)*

> **Source:** DESC Planned Transmission Projects $2M+ (2024–2028), project 23 of 44.

```
Total estimated cost      $23,787,423
Line length (per the PDF)         6.5 miles
                          -----------------
Unit cost                 ~$3.66M per mile
```

$3.66M/mile is a plausible figure for new 230 kV construction, which is a useful
check that we have read the document correctly.

All 44 DESC project costs from the PDF are now stored in `projects.csv` under the
`cost` column ($699,613,389 in total), so future estimates can use real figures
rather than assumed ones. Georgia Power's remain blank because they are redacted
in the public IRP. Two DESC entries carry a `cost_note`: DESC_26, whose stated
$30M total exceeds the $20M its yearly columns sum to, and DESC_40 at $1.1M,
below the $2M threshold in the document's own title. Both are recorded as the
PDF prints them.

### Step 2 — Which costs two neighbouring projects could share  *(assumption A2)*

Not all of a project's cost can be shared. Conductor, structures and labour hours
are specific to each job. What *can* overlap between two projects six miles apart:

> **A2 (assumption):** the shareable share of total project cost is —
>
> | Category | Share of project cost |
> |---|---|
> | Crew mobilisation and demobilisation | 3% – 6% |
> | Equipment staging / laydown yard | 1% – 3% |
> | ROW access, survey, environmental and permitting fieldwork | 2% – 4% |
> | **Total shareable pool** | **6% – 13%** |

```
Low   $23,787,423  ×  6%   =  $1,427,245
High  $23,787,423  ×  13%  =  $3,092,364
```

### Step 3 — How much of that pool coordination actually captures  *(assumption A3)*

Sharing a laydown yard does not make it free — it makes one yard serve two jobs
instead of two yards serving one each. Both utilities still run their own crews for
the actual construction.

> **A3 (assumption):** coordination avoids **25%–50%** of the shareable pool.

```
Low   $1,427,245  ×  25%  =  $356,811
High  $3,092,364  ×  50%  =  $1,546,182
```

### Step 4 — The Georgia Power side  *(described, not counted)*

**Georgia Power redacts per-project costs in its public 2025 IRP**, so there is no
figure to work from. GPC_20277 is also a different kind of job — reactor
installation inside existing substations, not line construction — so its cost
structure does not resemble DESC_23's, and scaling the DESC number by some
percentage would be inventing data twice over.

**So the dollar range below counts the DESC side only.** Qualitatively, the Georgia
side would see:

- **Shared mobilisation** — reactor installation still requires crews, cranes and
  heavy haul to reach a substation six miles from the DESC work.
- **Shared staging** — one laydown yard serving both jobs rather than two.
- **Shared outage coordination** — the larger and harder-to-price benefit. Both
  projects touch the same 230 kV corridor near the Savannah River. Two utilities
  taking separate outages on an interconnected corridor costs more in congestion
  and redispatch than one jointly planned outage window.

**The real total is therefore higher than the figure below, by an unknown amount.**
Stating that honestly is better than multiplying by a made-up factor.

---

## Result

| | Low | High |
|---|---|---|
| **DESC_23 side (published cost basis)** | **~$360,000** | **~$1.5M** |
| Georgia Power side | not quantifiable — costs redacted | |
| Combined | greater than the DESC figure, by an unknown amount | |

**Roughly $360K to $1.5M on the DESC side alone, as an illustrative order of magnitude.**

The range spans a factor of about four, down from thirteen in the first draft.
That narrowing came entirely from replacing an assumed cost basis with the
published one — the remaining spread is the genuine uncertainty in assumptions
A2 and A3, not uncertainty about the project itself.

---

## What would make this real, or make it zero

- **The 152-day gap is the catch.** These savings only exist if the two jobs are
  actually in the field at the same time. If neither schedule can move, the
  shared-mobilisation savings are **$0** and only the right-of-way and survey
  sharing survives.
- **Nothing here accounts for the cost of coordinating** — joint planning, contract
  and liability structuring between two utilities, and the schedule risk each
  absorbs by waiting on the other. For a pair this size that overhead is plausibly
  a six-figure item on its own, and it is not subtracted above.
- **A2 and A3 are still assumptions.** They are ordinary planning heuristics, not
  figures from either utility. Replacing them with real mobilisation and staging
  line items from a project budget would narrow the range much further.
- **The ranking, not the dollar figure, is the deliverable.** GridLock's value is
  finding that these two projects are six miles and five months apart at all —
  and flagging it while the schedules can still move.

---

*Generated for the Sperry Tech GridLock challenge. Distances and dates are computed
from the project data. DESC_23's cost is published; the savings percentages applied
to it are assumptions, labelled above.*
