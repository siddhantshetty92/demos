import datetime as dt
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from diagnose import Opp, diagnose, funnel, kpis, load, loss_reasons, render, win_back


def opp(i, stage="Closed Lost", furthest="Proposal", reason="Budget", amount=100_000, created="2026-05-01", closed="2026-06-01", segment="Mid-Market"):
    return Opp(f"o{i}", f"Acct {i}", segment, "Inbound", dt.date.fromisoformat(created), amount, furthest, stage, reason,
               dt.date.fromisoformat(closed) if closed else None)


class DiagnoseTest(unittest.TestCase):
    def test_kpis(self):
        opps = [opp(1, stage="Closed Won", furthest="Closed Won", reason="", amount=50_000), opp(2), opp(3, stage="Discovery", furthest="Discovery", closed=None)]
        k = kpis(opps)
        self.assertEqual(k["created"], 3)
        self.assertAlmostEqual(k["win_rate"], 0.5)
        self.assertEqual(k["cycle_days"], 31)

    def test_funnel_counts_won_deals_as_reaching_every_stage(self):
        rows = funnel([opp(1, stage="Closed Won", furthest="Closed Won"), opp(2, furthest="Evaluation")])
        self.assertEqual([count for _, count, _ in rows], [2, 2, 1, 1, 1])

    def test_loss_reason_shares(self):
        shares = loss_reasons([opp(1), opp(2), opp(3, reason="Price")])
        self.assertAlmostEqual(shares["Budget"], 2 / 3)

    def test_win_back_tiers(self):
        tiers = dict((o.id, t) for t, o in win_back([
            opp(1, amount=200_000),
            opp(2, amount=10_000),
            opp(3, reason="Missing feature", furthest="Discovery"),
            opp(4, reason="Chose competitor"),
            opp(5, reason="Champion left", furthest="Discovery", amount=10_000),
        ]))
        self.assertEqual(tiers["o1"], 1)
        self.assertEqual(tiers["o2"], 2)
        self.assertEqual(tiers["o3"], 2)
        self.assertNotIn("o4", tiers)
        self.assertEqual(tiers["o5"], 3)

    def test_sample_end_to_end(self):
        result = diagnose(load(ROOT / "examples" / "opportunities.csv"), "2026 Q2", "2026 Q3")
        before, after = result["kpis"]
        self.assertGreater(before["created"], after["created"])
        page = render(result)
        self.assertIn("Pipeline Diagnostic — 2026 Q2 vs 2026 Q3", page)
        self.assertIn("Tier 1", page)

    def test_missing_period_is_an_error(self):
        with self.assertRaises(ValueError):
            diagnose([opp(1)], "2026 Q2", "2026 Q4")


if __name__ == "__main__":
    unittest.main()
