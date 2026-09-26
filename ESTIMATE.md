# Coordination opportunity — illustrative estimate

**Pair #1 (OVL_1): DESC_23 × GPC_20277** — the top-ranked overlap, verified on both sides.

> **This is an illustrative estimate, not a claimed savings figure.** Every number
> below that is not measured from the project data is an assumption, labelled A1–A4.
> No cost figure for either project was available to us (see "What we don't know").
> Treat the output as an order of magnitude that justifies a conversation between
> the two utilities, not as a number to put in a budget.

---

## The pair

| | DESC_23 | GPC_20277 |
|---|---|---|
| Project | Jasper – Okatie 230 kV #2: Construct | SAV: MCINTOSH – PURRYSBURG 230 kV Reactors |
| Utility | Dominion Energy South Carolina | Georgia Power |
| In service | 2025-12-31 | 2026-06-01 |
| Status | In Progress | Planned |
| Source | DESC Planned Transmission Projects $2M+ (2024-2028), entry 06367 D-G | GA 2025 IRP Vol. 3, Table 2, TEAMS #20277 |

**Measured from the data (not assumed):**

- Project centres are **5.65 miles** apart.
- In-service dates are **152 days** apart.
- DESC_23's two endpoints are **5.65 miles** apart, from sponsor-verified coordinates.
- Both are **230 kV** jobs.

Two 230 kV projects, six miles apart, five months apart, run by two different
utilities that do not coordinate schedules. That is the opportunity.

---

## What we don't know

- **DESC_23's actual cost.** The source document is titled *"Planned Transmission
  Projects **$2M+**"*, so the only hard fact is that it exceeds **$2 million**.
  The PDF itself was not available to us, so the per-project figure could not be read.
- **GPC_20277's cost.** Georgia Power's 2025 IRP redacts per-project costs, so
  there is no public figure at all for the Georgia side.

Everything below therefore rests on a cost *basis* we assumed. If you have the real
DESC figure from the PDF, substitute it at step 1 and the rest of the math follows
unchanged.

---

## The math, step by step

### Step 1 — Cost basis for DESC_23  *(assumption A1)*

We know the line is 5.65 miles and 230 kV. New 230 kV transmission line
construction is commonly quoted in the range **$1.5M–$3.5M per mile** depending on
terrain, access and whether structures are steel or wood.

> **A1 (assumption):** $1.5M–$3.5M per mile for 230 kV construction.

```
Low   5.65 mi  ×  $1.5M/mi  =  $8.5M
High  5.65 mi  ×  $3.5M/mi  =  $19.8M
```

**Cost basis: roughly $9M to $20M.** This is consistent with the one fact we do
have — it is comfortably above the $2M threshold of the source document.

### Step 2 — Which costs two neighbouring projects could share  *(assumption A2)*

Not all of a project's cost can be shared. Conductor, structures and labour hours
are specific to each line. What *can* overlap between two jobs six miles apart:

> **A2 (assumption):** the shareable share of total project cost is —
>
> | Category | Share of project cost |
> |---|---|
> | Crew mobilisation and demobilisation | 3% – 6% |
> | Equipment staging / laydown yard | 1% – 3% |
> | ROW access, survey, environmental and permitting fieldwork | 2% – 4% |
> | **Total shareable pool** | **6% – 13%** |

```
Low   $8.5M   ×  6%   =  $0.51M
High  $19.8M  ×  13%  =  $2.57M
```

### Step 3 — How much of that pool coordination actually captures  *(assumption A3)*

Sharing a laydown yard does not make it free — it makes one yard serve two jobs
instead of two yards serving one each. Both utilities still run their own crews for
the actual construction.

> **A3 (assumption):** coordination avoids **25%–50%** of the shareable pool.

```
Low   $0.51M  ×  25%  =  $0.13M   ≈  $130,000
High  $2.57M  ×  50%  =  $1.29M   ≈  $1,300,000
```

**→ DESC side alone: roughly $130K to $1.3M.**

### Step 4 — The Georgia Power side  *(assumption A4)*

GPC_20277 is a reactor installation at existing substations, which is a smaller
scope than building a new line. Its cost is redacted, so it cannot be estimated
independently.

> **A4 (assumption):** Georgia Power's share of the savings is **50%–100%** of the
> DESC side's, reflecting a smaller but real scope.

```
Low   $130,000    ×  1.5  =  ~$190,000
High  $1,300,000  ×  2.0  =  ~$2,600,000
```

---

## Result

| | Low | High |
|---|---|---|
| DESC_23 side | $130,000 | $1.3M |
| **Both utilities combined** | **~$190,000** | **~$2.6M** |

**Roughly $0.19M to $2.6M for this one pair, as an illustrative order of magnitude.**

The range is wide on purpose. It spans a factor of thirteen because the cost basis
is assumed rather than known. Narrowing it requires one input: DESC_23's actual
budget from the source PDF.

---

## What would make this real, or make it zero

- **The 152-day gap is the catch.** These savings only exist if the two jobs are
  actually in the field at the same time. DESC_23 is already *In Progress* with a
  2025-12-31 in-service date; GPC_20277 is *Planned* for 2026-06-01. If neither
  schedule can move, the shared-mobilisation savings are **$0** and only the
  right-of-way and survey sharing survives.
- **Nothing here accounts for the cost of coordinating** — joint planning meetings,
  contract and liability structuring between two utilities, and schedule risk each
  absorbs by waiting on the other. For a pair this size that overhead is plausibly
  a six-figure item on its own, and it is not subtracted above.
- **The ranking, not the dollar figure, is the deliverable.** GridLock's value is
  finding that these two projects are six miles and five months apart at all.
  Whether the number is $190K or $2.6M, it is worth one phone call to find out.

---

*Generated for the Sperry Tech GridLock challenge. Distances and dates are computed
from the project data; all dollar figures are assumptions as labelled.*
