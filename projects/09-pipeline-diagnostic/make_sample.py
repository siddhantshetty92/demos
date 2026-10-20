#!/usr/bin/env python3
"""Writes made-up CRM opportunities for two quarters, with a deliberate Q3 slowdown in mid-market."""
import csv
import datetime as dt
import random
import sys

STAGES = ["Discovery", "Evaluation", "Proposal", "Negotiation", "Closed Won", "Closed Lost"]
REASONS = ["No decision / timing", "Budget", "Chose competitor", "Missing feature", "Price", "Champion left"]
SEGMENTS = {"Enterprise": (90_000, 400_000), "Mid-Market": (25_000, 120_000), "SMB": (6_000, 30_000)}
EXPORT_DATE = dt.date(2026, 10, 15)
SOURCES = ["Inbound", "Outbound", "Partner", "Event"]
PREFIXES = ["Alder", "Birch", "Cobalt", "Delta", "Ember", "Fjord", "Garnet", "Harbor", "Iris", "Jasper", "Kite", "Lumen", "Maple", "Nimbus", "Onyx", "Pine", "Quartz", "Ridge", "Sable", "Tundra"]
SUFFIXES = ["Logistics", "Health", "Retail", "Energy", "Travel", "Finance", "Games", "Telecom", "Foods", "Labs"]


def main(path: str = "examples/opportunities.csv") -> None:
    rng = random.Random(21)
    rows = []
    for quarter, start, volume in (("Q2", dt.date(2026, 4, 1), 150), ("Q3", dt.date(2026, 7, 1), 128)):
        for i in range(volume):
            segment = rng.choices(list(SEGMENTS), weights=[2, 5 if quarter == "Q2" else 3, 4])[0]
            created = start + dt.timedelta(days=rng.randrange(91))
            amount = round(rng.uniform(*SEGMENTS[segment]), -3)
            depth = rng.choices(range(6), weights=[3, 3, 2, 2, 2, 3])[0]
            win = rng.random() < (0.32 if quarter == "Q2" else 0.24)
            if depth < 4:
                stage, reason, closed = STAGES[depth], "", ""
            else:
                stage = "Closed Won" if win else "Closed Lost"
                weights = [3, 2, 2, 2 if quarter == "Q2" else 5, 1, 1]
                reason = "" if win else rng.choices(REASONS, weights=weights)[0]
                close_date = created + dt.timedelta(days=rng.randint(25, 140))
                closed = close_date.isoformat()
                if close_date > EXPORT_DATE:
                    stage, reason, closed = "Negotiation", "", ""
            rows.append({
                "id": f"OPP-{quarter}-{i:04d}",
                "account": f"{rng.choice(PREFIXES)} {rng.choice(SUFFIXES)}",
                "segment": segment,
                "source": rng.choice(SOURCES),
                "created": created.isoformat(),
                "amount": int(amount),
                "furthest_stage": rng.choices(STAGES[:4], weights=[2, 3, 3, 2])[0] if stage == "Closed Lost" else stage,
                "stage": stage,
                "loss_reason": reason,
                "closed": closed,
            })
    with open(path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main(*sys.argv[1:])
