#!/usr/bin/env python3
"""Build a demo environment from a spec: config, roster, and calibrated case volume."""
from __future__ import annotations

import argparse
import datetime as dt
import os
import sys

from demobuilder.roster import build_roster
from demobuilder.sinks import PUSH_ORDER, CsvSink, HttpSink
from demobuilder.spec import SpecError, load_spec
from demobuilder.volume import materialize, plan_demand, self_check


def config_resources(spec):
    return {
        "sites": [{"name": s} for s in spec.sites],
        "teams": [{"name": t} for t in spec.teams],
        "skills": [{"name": s} for s in spec.skills],
        "queues": [{"name": q.name, "channel": q.channel, "team": q.team} for q in spec.queues],
    }


def print_self_check(report):
    print(f"{'queue':<22}{'contacts':>10}{'under':>8}{'ok':>6}{'over':>6}{'closed':>8}")
    for queue, row in report.items():
        open_intervals = row["under"] + row["ok"] + row["over"] or 1
        print(f"{queue:<22}{row['contacts']:>10}{row['under']:>8}{row['ok']:>6}{row['over']:>6}{row['closed']:>8}"
              f"   ({row['under'] / open_intervals:.0%} under, {row['over'] / open_intervals:.0%} over)")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", required=True)
    parser.add_argument("--dry-run", action="store_true", help="validate and print the self-check; write nothing")
    parser.add_argument("--out", default="out", help="CSV output directory (default sink)")
    parser.add_argument("--api-url", help="push to a JSON bulk API instead of CSV (key from DEMO_API_KEY)")
    parser.add_argument("--only", default=",".join(PUSH_ORDER), help=f"subset of {','.join(PUSH_ORDER)}")
    parser.add_argument("--end", help="end of history window, ISO-8601 (default: now)")
    args = parser.parse_args(argv)

    try:
        spec = load_spec(args.spec)
    except SpecError as err:
        print(f"spec error: {err}", file=sys.stderr)
        return 2

    end = dt.datetime.fromisoformat(args.end) if args.end else dt.datetime.now(dt.timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=dt.timezone.utc)
    roster = build_roster(spec)
    demand = plan_demand(spec, end)
    print(f"{spec.company}: {len(spec.queues)} queues, {len(roster)} agents, {spec.weeks_back} weeks of {spec.interval_minutes}-minute intervals\n")
    print_self_check(self_check(demand))
    if args.dry_run:
        return 0

    if args.api_url:
        key = os.environ.get("DEMO_API_KEY")
        if not key:
            print("DEMO_API_KEY is not set", file=sys.stderr)
            return 2
        sink = HttpSink(args.api_url, key)
    else:
        sink = CsvSink(args.out)

    wanted = set(args.only.split(","))
    resources = config_resources(spec) | {"people": roster, "cases": materialize(spec, demand, roster, end)}
    print()
    for name in PUSH_ORDER:
        if name in wanted:
            print(f"{name:<8} {sink.push(name, resources[name]):>8} rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
