#!/usr/bin/env python3
"""Writes a week of made-up 15-minute interval actuals for two contact types."""
import csv
import datetime as dt
import math
import random
import sys

TYPES = {
    "phone": {"peak": 60, "aht": 380, "threshold": 180, "sl": 0.82, "asa": 75, "abandon": 0.05},
    "messaging": {"peak": 35, "aht": 720, "threshold": 900, "sl": 0.9, "asa": None, "abandon": 0.02},
}


def main(path: str = "examples/intervals.csv") -> None:
    rng = random.Random(11)
    start = dt.datetime(2026, 9, 7)
    with open(path, "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["interval_start", "contact_type", "offered", "abandoned", "aht_seconds",
                         "service_level", "asa_seconds", "sl_threshold_seconds", "interval_minutes"])
        for step in range(7 * 96):
            ts = start + dt.timedelta(minutes=15 * step)
            hour = ts.hour + ts.minute / 60
            shape = max(0.0, math.sin(math.pi * (hour - 6) / 16)) if 6 <= hour < 22 else 0.0
            weekday = 0.5 if ts.weekday() >= 5 else 1.0
            for name, t in TYPES.items():
                offered = round(t["peak"] * shape * weekday * rng.uniform(0.85, 1.15))
                if offered == 0:
                    continue
                abandoned = round(offered * t["abandon"] * rng.uniform(0.5, 1.5))
                aht = "" if rng.random() < 0.03 else round(t["aht"] * rng.uniform(0.85, 1.15))
                sl = round(min(1.0, t["sl"] * rng.uniform(0.9, 1.08)), 3)
                asa = "" if t["asa"] is None else round(t["asa"] * rng.uniform(0.7, 1.3))
                writer.writerow([ts.isoformat(), name, offered, abandoned, aht, sl, asa, t["threshold"], 15])


if __name__ == "__main__":
    main(*sys.argv[1:])
