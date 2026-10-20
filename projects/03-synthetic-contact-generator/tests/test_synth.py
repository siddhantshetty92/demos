import datetime as dt
import sys
import unittest
from pathlib import Path
from statistics import fmean

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from synth import Interval, generate, handle_times, reconcile, rng_for, summarize, wait_times

START = dt.datetime(2026, 9, 7, 10, tzinfo=dt.timezone.utc)


def interval(**overrides):
    base = dict(start=START, contact_type="phone", offered=80, abandoned=4, aht_seconds=400.0,
                service_level=0.8, asa_seconds=60.0, sl_threshold_seconds=180.0, minutes=15)
    return Interval(**(base | overrides))


class WaitTest(unittest.TestCase):
    def test_service_level_is_exact(self):
        waits = wait_times(rng_for("a"), 100, 180, 0.8, 60)
        self.assertEqual(sum(w <= 180 for w in waits), 80)

    def test_asa_is_met_when_feasible(self):
        waits = wait_times(rng_for("b"), 2000, 180, 0.8, 90)
        self.assertLess(abs(fmean(waits) - 90), 0.5)

    def test_service_level_wins_when_asa_is_infeasible(self):
        waits = wait_times(rng_for("c"), 100, 180, 0.5, 10)
        self.assertEqual(sum(w <= 180 for w in waits), 50)


class HandleTimeTest(unittest.TestCase):
    def test_total_handle_time_is_exact(self):
        times = handle_times(rng_for("d"), 37, 412)
        self.assertAlmostEqual(sum(times), 37 * 412, places=6)


class EndToEndTest(unittest.TestCase):
    def test_reconcile_round_trips_counts(self):
        source = [interval(), interval(start=START + dt.timedelta(minutes=15), offered=10, abandoned=0, aht_seconds=None),
                  interval(start=START + dt.timedelta(minutes=30), contact_type="messaging", sl_threshold_seconds=900,
                           asa_seconds=None, service_level=0.9)]
        cases = list(generate(source))
        summary = summarize(reconcile(source, cases))
        self.assertEqual(summary["offered_mismatches"], 0)
        self.assertEqual(summary["abandoned_mismatches"], 0)
        self.assertLess(summary["max_aht_error_seconds"], 0.01)
        self.assertLess(summary["max_interval_sl_error"], 0.02)

    def test_missing_aht_falls_back_to_daily_mean(self):
        cases = list(generate([interval(), interval(start=START + dt.timedelta(minutes=15), aht_seconds=None)]))
        later = [c for c in cases if c.created_at >= (START + dt.timedelta(minutes=15)).isoformat() and c.status == "solved"]
        self.assertAlmostEqual(fmean(c.handle_seconds for c in later), 400, delta=0.01)

    def test_deterministic_ids(self):
        first = [c.case_id for c in generate([interval()])]
        self.assertEqual(first, [c.case_id for c in generate([interval()])])
        self.assertEqual(len(first), len(set(first)))


if __name__ == "__main__":
    unittest.main()
