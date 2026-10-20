#!/usr/bin/env python3
"""Interval actuals in, case-level records out, with every interval metric preserved.

Input CSV columns: interval_start, contact_type, offered, abandoned, aht_seconds,
service_level, asa_seconds, sl_threshold_seconds, interval_minutes.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import random
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import fmean

MIN_EXCESS_WAIT = 1.0
MIN_WITHIN_SHARE = 0.02


@dataclass(frozen=True)
class Interval:
    start: dt.datetime
    contact_type: str
    offered: int
    abandoned: int
    aht_seconds: float | None
    service_level: float | None
    asa_seconds: float | None
    sl_threshold_seconds: float
    minutes: int

    @property
    def handled(self) -> int:
        return self.offered - self.abandoned


@dataclass(frozen=True)
class Case:
    case_id: str
    contact_type: str
    status: str
    created_at: str
    first_response_at: str | None
    solved_at: str
    wait_seconds: float | None
    handle_seconds: float | None


def _opt_float(value: str) -> float | None:
    value = (value or "").strip()
    return float(value) if value else None


def read_intervals(path: Path) -> list[Interval]:
    with path.open(newline="") as fh:
        rows = list(csv.DictReader(fh))
    intervals = []
    for row in rows:
        offered = max(0, round(float(row["offered"] or 0)))
        intervals.append(Interval(
            start=dt.datetime.fromisoformat(row["interval_start"]).replace(tzinfo=dt.timezone.utc),
            contact_type=row["contact_type"],
            offered=offered,
            abandoned=min(offered, max(0, round(float(row["abandoned"] or 0)))),
            aht_seconds=_opt_float(row.get("aht_seconds")),
            service_level=_opt_float(row.get("service_level")),
            asa_seconds=_opt_float(row.get("asa_seconds")),
            sl_threshold_seconds=float(row["sl_threshold_seconds"]),
            minutes=int(row.get("interval_minutes") or 15),
        ))
    return intervals


def fill_missing_aht(intervals: list[Interval]) -> list[Interval]:
    daily: dict[tuple[str, dt.date], list[float]] = defaultdict(list)
    for i in intervals:
        if i.aht_seconds:
            daily[(i.contact_type, i.start.date())].append(i.aht_seconds)
    filled = []
    for i in intervals:
        if not i.aht_seconds and i.handled:
            fallback = daily.get((i.contact_type, i.start.date()))
            i = Interval(**{**asdict(i), "aht_seconds": fmean(fallback) if fallback else 300.0})
        filled.append(i)
    return filled


def rng_for(*parts) -> random.Random:
    return random.Random(int.from_bytes(hashlib.sha256("|".join(map(str, parts)).encode()).digest()[:8], "big"))


def handle_times(rng: random.Random, n: int, aht: float, sigma: float = 0.6) -> list[float]:
    if n == 0:
        return []
    draws = [rng.lognormvariate(0, sigma) for _ in range(n)]
    scale = aht * n / sum(draws)
    return [d * scale for d in draws]


def wait_times(rng: random.Random, n: int, threshold: float, sl: float | None, asa: float | None) -> list[float]:
    """Waits whose share under `threshold` equals `sl` and whose mean approaches `asa`. SL wins on conflict."""
    if n == 0:
        return []
    sl = 0.8 if sl is None else min(max(sl, 0.0), 1.0)
    within = round(sl * n)
    above = n - within
    target_asa = threshold / 2 if asa is None else asa
    within_mean = min(target_asa, threshold / 2)
    if above and within:
        room = (target_asa * n - (threshold + MIN_EXCESS_WAIT) * above) / within
        within_mean = min(max(room, threshold * MIN_WITHIN_SHARE), within_mean)
    waits =[min(w, threshold) for w in rescaled([rng.random() for _ in range(within)], within_mean)]
    if above:
        excess = max((target_asa * n - within_mean * within) / above - threshold, MIN_EXCESS_WAIT)
        waits += [threshold + 0.001 + e for e in rescaled([rng.expovariate(1.0) for _ in range(above)], excess)]
    rng.shuffle(waits)
    return waits


def rescaled(draws: list[float], mean: float) -> list[float]:
    total = sum(draws)
    if not draws or total == 0:
        return [mean] * len(draws)
    return [d * mean * len(draws) / total for d in draws]


def generate(intervals: list[Interval]):
    for interval in fill_missing_aht(intervals):
        rng = rng_for(interval.contact_type, interval.start.isoformat())
        seconds = interval.minutes * 60
        prefix = f"{interval.contact_type}-{interval.start:%Y%m%d%H%M}"
        handles = handle_times(rng, interval.handled, interval.aht_seconds or 0)
        waits = wait_times(rng, interval.handled, interval.sl_threshold_seconds, interval.service_level, interval.asa_seconds)
        for n, (handle, wait) in enumerate(zip(handles, waits)):
            created = interval.start + dt.timedelta(seconds=rng.uniform(0, seconds - 1))
            responded = created + dt.timedelta(seconds=wait)
            yield Case(f"{prefix}-H{n:04d}", interval.contact_type, "solved", created.isoformat(), responded.isoformat(),
                       (responded + dt.timedelta(seconds=handle)).isoformat(), round(wait, 3), round(handle, 3))
        for n in range(interval.abandoned):
            created = interval.start + dt.timedelta(seconds=rng.uniform(0, seconds - 1))
            gave_up = created + dt.timedelta(seconds=rng.uniform(5, 2 * interval.sl_threshold_seconds))
            yield Case(f"{prefix}-A{n:04d}", interval.contact_type, "abandoned", created.isoformat(), None, gave_up.isoformat(), None, None)


def reconcile(intervals: list[Interval], cases: list[Case], minutes: int = 15) -> list[dict]:
    buckets: dict[tuple[str, str], list[Case]] = defaultdict(list)
    for case in cases:
        created = dt.datetime.fromisoformat(case.created_at)
        floored = created.replace(minute=created.minute - created.minute % minutes, second=0, microsecond=0)
        buckets[(case.contact_type, floored.isoformat())].append(case)
    rows = []
    for interval in fill_missing_aht(intervals):
        got = buckets.get((interval.contact_type, interval.start.isoformat()), [])
        handled = [c for c in got if c.status == "solved"]
        waits = [c.wait_seconds for c in handled]
        rows.append({
            "contact_type": interval.contact_type,
            "interval_start": interval.start.isoformat(),
            "offered_src": interval.offered, "offered_gen": len(got),
            "abandoned_src": interval.abandoned, "abandoned_gen": len(got) - len(handled),
            "aht_src": interval.aht_seconds if interval.handled else None,
            "aht_gen": fmean(c.handle_seconds for c in handled) if handled else None,
            "sl_src": interval.service_level,
            "sl_gen": sum(w <= interval.sl_threshold_seconds for w in waits) / len(waits) if waits else None,
            "asa_src": interval.asa_seconds,
            "asa_gen": fmean(waits) if waits else None,
        })
    return rows


def summarize(rows: list[dict]) -> dict:
    def max_abs(a, b):
        diffs = [abs(r[a] - r[b]) for r in rows if r[a] is not None and r[b] is not None]
        return round(max(diffs), 4) if diffs else 0.0
    def weighted(src, gen):
        pairs = [(r[src], r[gen], r["offered_gen"] - r["abandoned_gen"]) for r in rows if r[src] is not None and r[gen] is not None]
        weight = sum(w for _, _, w in pairs)
        if not weight:
            return 0.0
        return round(abs(sum(s * w for s, _, w in pairs) - sum(g * w for _, g, w in pairs)) / weight, 4)
    return {
        "intervals": len(rows),
        "offered_mismatches": sum(r["offered_src"] != r["offered_gen"] for r in rows),
        "abandoned_mismatches": sum(r["abandoned_src"] != r["abandoned_gen"] for r in rows),
        "max_aht_error_seconds": max_abs("aht_src", "aht_gen"),
        "overall_sl_error": weighted("sl_src", "sl_gen"),
        "max_interval_sl_error": max_abs("sl_src", "sl_gen"),
        "overall_asa_error_seconds": weighted("asa_src", "asa_gen"),
    }


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("intervals", type=Path)
    parser.add_argument("--out", type=Path, default=Path("out"))
    args = parser.parse_args(argv)

    intervals = read_intervals(args.intervals)
    cases = list(generate(intervals))
    for contact_type in sorted({c.contact_type for c in cases}):
        write_csv(args.out / f"cases_{contact_type}.csv", [asdict(c) for c in cases if c.contact_type == contact_type])
    rows = reconcile(intervals, cases, intervals[0].minutes if intervals else 15)
    write_csv(args.out / "reconcile.csv", rows)
    summary = summarize(rows)
    (args.out / "reconcile_summary.json").write_text(json.dumps(summary, indent=2))
    print(f"{len(cases)} cases from {len(intervals)} intervals")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
