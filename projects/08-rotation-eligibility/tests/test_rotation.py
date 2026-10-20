import datetime as dt
import sys
import unittest
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rotation import CAN_WORK, MUST_REST, Activity, Person, demo_workforce, plan_rotation, run

TZ = ZoneInfo("Europe/Madrid")
TARGET = dt.date(2026, 10, 25)


def shift(person_id, day, start_hour=9, hours=8, productive=True):
    start = dt.datetime.combine(day, dt.time(start_hour), TZ)
    return Activity(person_id, start, start + dt.timedelta(hours=hours), productive)


class RotationTest(unittest.TestCase):
    def test_three_sundays_in_a_row_means_rest(self):
        people = [Person("a", "A"), Person("b", "B")]
        sundays = [TARGET - dt.timedelta(weeks=n) for n in (1, 2, 3)]
        activities = [shift("a", d) for d in sundays] + [shift("b", d) for d in sundays[:2]]
        plans = {p.person.id: p for p in plan_rotation(people, activities, TARGET, TZ)}
        self.assertEqual(plans["a"].target_tag, MUST_REST)
        self.assertEqual(plans["b"].target_tag, CAN_WORK)

    def test_non_productive_time_does_not_count(self):
        sundays = [TARGET - dt.timedelta(weeks=n) for n in (1, 2, 3)]
        activities = [shift("a", d, productive=False) for d in sundays]
        [plan] = plan_rotation([Person("a", "A")], activities, TARGET, TZ)
        self.assertEqual(plan.target_tag, CAN_WORK)

    def test_local_day_boundaries(self):
        late_saturday = dt.datetime.combine(TARGET - dt.timedelta(days=8), dt.time(23, 30), TZ)
        activities = [Activity("a", late_saturday, late_saturday + dt.timedelta(minutes=20), True)]
        [plan] = plan_rotation([Person("a", "A")], activities, TARGET, TZ)
        self.assertEqual(plan.worked, (False, False, False))

    def test_holding_both_tags_is_corrected_to_exactly_one(self):
        [plan] = plan_rotation([Person("a", "A", {MUST_REST, CAN_WORK})], [], TARGET, TZ)
        self.assertEqual(plan.remove, {MUST_REST})
        self.assertEqual(plan.add, frozenset())

    def test_rejects_non_sunday(self):
        with self.assertRaises(ValueError):
            plan_rotation([], [], TARGET - dt.timedelta(days=1), TZ)

    def test_apply_writes_only_changes_and_is_idempotent(self):
        workforce = demo_workforce()
        run(workforce, TARGET, TZ, 3, apply=False)
        self.assertEqual(workforce.writes, 0)
        first = run(workforce, TARGET, TZ, 3, apply=True)
        self.assertEqual(workforce.writes, sum(p.changes for p in first))
        writes = workforce.writes
        second = run(workforce, TARGET, TZ, 3, apply=True)
        self.assertFalse(any(p.changes for p in second))
        self.assertEqual(workforce.writes, writes)
        for person in workforce.list_people():
            self.assertEqual(len(person.tags & {MUST_REST, CAN_WORK}), 1)


if __name__ == "__main__":
    unittest.main()
