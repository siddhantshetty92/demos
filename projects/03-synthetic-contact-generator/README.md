# Synthetic Contact Generator

**Turns a prospect's interval-level actuals into individual contact records that re-aggregate to the same numbers.**

## Problem

In a proof of concept, a prospect shares a spreadsheet of 15-minute interval actuals: contacts offered, abandoned, average handle time, service level and average speed of answer. The software being evaluated ingests *individual contacts*, not interval summaries. To load the prospect's real operation, every interval has to become a set of cases whose timestamps, waits and handle times reproduce that interval's metrics. If they don't, the forecast the prospect is judging is built on the wrong history.

## What I built

`synth.py` reads an interval CSV and generates one record per contact:

- **Counts are exact.** Offered becomes that many records; abandoned is rounded and capped at offered; handled = offered − abandoned.
- **AHT is exact.** Handle times are log-normal (realistic right skew) and rescaled so the interval total equals handled × AHT to the millisecond. Missing AHT falls back to that day's mean for the contact type.
- **Service level is exact; ASA is matched when it can be.** `round(SL × handled)` waits fall under the threshold and the rest above it. The two groups' means are solved so the overall mean hits ASA. When the source SL and ASA contradict each other (for example, a low ASA with a low SL), service level wins and the conflict is visible in reconciliation, not hidden.
- **Abandoned contacts** have no response or handle time and end a plausible few seconds to minutes after arrival.
- **Deterministic.** Seeds come from a hash of contact type and interval, so re-runs produce identical ids and values.

It then **reconciles**: it re-buckets the generated cases into intervals and diffs every metric against the source.

```
$ python3 make_sample.py && python3 synth.py examples/intervals.csv
23185 cases from 882 intervals
{
  "offered_mismatches": 0,
  "abandoned_mismatches": 0,
  "max_aht_error_seconds": 0.0003,
  "overall_sl_error": 0.0004,
  "max_interval_sl_error": 0.259,
  "overall_asa_error_seconds": 0.0099
}
```

`max_interval_sl_error` is a property of small numbers, not a bug: an interval with three handled contacts and an 82% SL target can only score 67% or 100%. Overall SL across the dataset is within 0.04 points.

**Mock data:** input [`examples/intervals.csv`](examples/intervals.csv) (a week of phone and messaging intervals, with gaps such as missing AHT and missing ASA) → output in [`sample-output/`](sample-output): the first 500 cases per contact type, the full per-interval `reconcile.csv`, and `reconcile_summary.json`.

## Run it

```bash
python3 make_sample.py                         # a week of made-up phone + messaging intervals
python3 synth.py examples/intervals.csv --out out/
python3 -m unittest discover -s tests          # 7 tests
```

## Why it matters

Prospects trust a proof of concept when the first chart they see matches the spreadsheet they sent. Reconciliation turns "trust me, the data loaded" into a per-interval diff the prospect's own analyst can check.

## How AI helped

The data rules (which column is the source of truth, what happens when SL and ASA disagree, how to treat a sheet whose columns are shifted by one) were negotiated with the prospect in plain language. I kept those rules as a written spec and had a coding agent implement and test against it, then used the reconciliation report as the acceptance test instead of eyeballing charts.
