import datetime as dt
import unittest
from pathlib import Path

from demobuilder.roster import build_roster
from demobuilder.spec import SpecError, load_spec, parse_spec
from demobuilder.staffing import ChannelTargets, Variables, contacts_for_required, erlang_agents, erlang_c, required_agents, service_level
from demobuilder.volume import handle_times, materialize, plan_demand, seeded, self_check

EXAMPLE = Path(__file__).resolve().parent.parent / "examples" / "acme_mobile.toml"
END = dt.datetime(2026, 10, 19, tzinfo=dt.timezone.utc)


class ErlangTest(unittest.TestCase):
    def test_textbook_case(self):
        self.assertAlmostEqual(erlang_c(28, 24), 0.3331, places=4)
        self.assertAlmostEqual(service_level(28, 24, 240, 20), 0.7613, places=4)
        self.assertEqual(erlang_agents(180, 1800, 240, 20, 0.8), 29)

    def test_erlang_c_bounds(self):
        self.assertEqual(erlang_c(10, 10), 1.0)
        self.assertTrue(0 < erlang_c(30, 24) < 1)
        self.assertAlmostEqual(service_level(0, 0, 240, 20), 1.0)

    def test_more_agents_never_lower_service(self):
        levels = [service_level(n, 24, 240, 20) for n in range(25, 40)]
        self.assertEqual(levels, sorted(levels))


class InverseTest(unittest.TestCase):
    def test_async_inverse_is_exact(self):
        targets, variables = ChannelTargets("email", 300), Variables(shrinkage_percent=25)
        contacts = contacts_for_required(12, 1800, targets, variables)
        self.assertAlmostEqual(required_agents(contacts, 1800, targets, variables), 12)

    def test_realtime_inverse_reaches_target(self):
        targets, variables = ChannelTargets("phone", 420, 60, 0.8), Variables(shrinkage_percent=30)
        contacts = contacts_for_required(20, 1800, targets, variables)
        self.assertGreaterEqual(required_agents(contacts, 1800, targets, variables), 20)
        self.assertLess(required_agents(contacts * 0.97, 1800, targets, variables), 21)


class SpecTest(unittest.TestCase):
    def test_example_loads(self):
        spec = load_spec(EXAMPLE)
        self.assertEqual(len(spec.queues), 4)
        self.assertEqual(spec.email_domain, "acmemobile.example.com")

    def test_rejects_bad_interval_and_unknown_event_queue(self):
        base = {"company": "X", "queues": [{"name": "Q", "channel": "email", "headcount": 1, "aht_seconds": 60}]}
        with self.assertRaises(SpecError):
            parse_spec(base | {"interval_minutes": 20})
        with self.assertRaises(SpecError):
            parse_spec(base | {"story": {"events": [{"queue": "Nope", "date": "2026-01-01", "multiplier": 2}]}})


class VolumeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = load_spec(EXAMPLE)
        cls.demand = plan_demand(cls.spec, END)

    def test_story_has_both_over_and_under_staffing(self):
        for queue, row in self_check(self.demand).items():
            self.assertGreater(row["under"], 0, queue)
            self.assertGreater(row["over"], 0, queue)
            self.assertGreater(row["closed"], 0, queue)

    def test_deterministic(self):
        again = plan_demand(self.spec, END)
        self.assertEqual([d.contacts for d in again], [d.contacts for d in self.demand])

    def test_handle_times_preserve_aht(self):
        times = handle_times(seeded(1), 500, 420)
        self.assertLess(abs(sum(times) / len(times) - 420), 1)

    def test_cases_match_planned_contacts(self):
        roster = build_roster(self.spec)
        sample = [d for d in self.demand if d.contacts][:50]
        cases = list(materialize(self.spec, sample, roster, END))
        self.assertEqual(len(cases), sum(d.contacts for d in sample))
        self.assertEqual(len({c.import_id for c in cases}), len(cases))

    def test_roster_matches_headcount(self):
        roster = build_roster(self.spec)
        self.assertEqual(len(roster), sum(q.headcount for q in self.spec.queues))
        self.assertTrue(all(a.email.endswith("@acmemobile.example.com") for a in roster))


if __name__ == "__main__":
    unittest.main()
