#!/usr/bin/env python3
"""Weekend-rest rotation: anyone who worked the last N Sundays must rest the next one.

For each person it guarantees exactly one of two tags, MUST_REST or CAN_WORK, so a
scheduler that filters on tags can never place someone who is owed a rest day.
Preview by default; --apply writes only the people whose tags actually change.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from zoneinfo import ZoneInfo

MUST_REST = "must-rest-next-sunday"
CAN_WORK = "can-work-next-sunday"


@dataclass
class Person:
    id: str
    name: str
    tags: set[str] = field(default_factory=set)


@dataclass(frozen=True)
class Activity:
    person_id: str
    start: dt.datetime
    end: dt.datetime
    productive: bool


@dataclass(frozen=True)
class Plan:
    person: Person
    worked: tuple[bool, ...]
    target_tag: str
    add: frozenset[str]
    remove: frozenset[str]

    @property
    def changes(self) -> bool:
        return bool(self.add or self.remove)


def previous_weekdays(target: dt.date, count: int) -> list[dt.date]:
    return [target - dt.timedelta(weeks=n) for n in range(1, count + 1)]


def day_bounds(day: dt.date, tz: ZoneInfo) -> tuple[dt.datetime, dt.datetime]:
    start = dt.datetime.combine(day, dt.time(), tz)
    return start, dt.datetime.combine(day + dt.timedelta(days=1), dt.time(), tz)


def worked_on(day: dt.date, tz: ZoneInfo, activities: list[Activity]) -> set[str]:
    start, end = day_bounds(day, tz)
    return {a.person_id for a in activities if a.productive and a.start < end and a.end > start}


def plan_rotation(people: list[Person], activities: list[Activity], target: dt.date, tz: ZoneInfo, streak: int = 3) -> list[Plan]:
    if target.weekday() != 6:
        raise ValueError(f"{target} is not a Sunday")
    days = previous_weekdays(target, streak)
    worked_by_day = [worked_on(day, tz, activities) for day in days]
    plans = []
    for person in people:
        worked = tuple(person.id in ids for ids in worked_by_day)
        target_tag = MUST_REST if all(worked) else CAN_WORK
        other = CAN_WORK if target_tag == MUST_REST else MUST_REST
        plans.append(Plan(
            person=person,
            worked=worked,
            target_tag=target_tag,
            add=frozenset({target_tag} - person.tags),
            remove=frozenset({other} & person.tags),
        ))
    return plans


class InMemoryWorkforce:
    def __init__(self, people: list[Person], activities: list[Activity]):
        self.people = {p.id: p for p in people}
        self.activities = activities
        self.writes = 0

    def list_people(self) -> list[Person]:
        return list(self.people.values())

    def list_activities(self, start: dt.datetime, end: dt.datetime) -> list[Activity]:
        return [a for a in self.activities if a.start < end and a.end > start]

    def set_tags(self, person_id: str, tags: set[str]) -> None:
        self.people[person_id].tags = set(tags)
        self.writes += 1


class JsonApiWorkforce:
    """Adapter for a REST API with /people, /activities?start=&end= and PATCH /people/{id} {"tags": [...]}."""

    def __init__(self, base_url: str, token: str):
        self.base_url = base_url.rstrip("/")
        self.token = token

    def _request(self, method: str, path: str, body: dict | None = None):
        request = urllib.request.Request(
            self.base_url + path,
            data=json.dumps(body).encode() if body is not None else None,
            headers={"authorization": f"Bearer {self.token}", "content-type": "application/json"},
            method=method,
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)

    def list_people(self) -> list[Person]:
        return [Person(p["id"], p["name"], set(p.get("tags", []))) for p in self._request("GET", "/people")]

    def list_activities(self, start: dt.datetime, end: dt.datetime) -> list[Activity]:
        rows = self._request("GET", f"/activities?start={int(start.timestamp())}&end={int(end.timestamp())}")
        return [Activity(r["person_id"], dt.datetime.fromtimestamp(r["start"], dt.timezone.utc),
                         dt.datetime.fromtimestamp(r["end"], dt.timezone.utc), bool(r["productive"])) for r in rows]

    def set_tags(self, person_id: str, tags: set[str]) -> None:
        self._request("PATCH", f"/people/{person_id}", {"tags": sorted(tags)})


def run(workforce, target: dt.date, tz: ZoneInfo, streak: int, apply: bool) -> list[Plan]:
    days = previous_weekdays(target, streak)
    window_start, _ = day_bounds(min(days), tz)
    _, window_end = day_bounds(max(days), tz)
    plans = plan_rotation(workforce.list_people(), workforce.list_activities(window_start, window_end), target, tz, streak)
    if apply:
        for plan in plans:
            if plan.changes:
                workforce.set_tags(plan.person.id, (plan.person.tags - plan.remove) | plan.add)
    return plans


DEMO_DATA = Path(__file__).resolve().parent / "examples" / "demo_workforce.json"


def demo_workforce(path: Path = DEMO_DATA) -> InMemoryWorkforce:
    data = json.loads(path.read_text())
    people = [Person(p["id"], p["name"], set(p["tags"])) for p in data["people"]]
    activities = [Activity(a["person_id"], dt.datetime.fromisoformat(a["start"]), dt.datetime.fromisoformat(a["end"]), a["productive"])
                  for a in data["activities"]]
    return InMemoryWorkforce(people, activities)


def print_plans(plans: list[Plan], target: dt.date, streak: int, applied: bool) -> None:
    days = ", ".join(d.isoformat() for d in previous_weekdays(target, streak))
    print(f"Target Sunday {target}; checking {days}\n")
    for title, group in (("MUST REST", [p for p in plans if p.target_tag == MUST_REST]), ("CAN WORK", [p for p in plans if p.target_tag == CAN_WORK])):
        print(f"{title} ({len(group)})")
        for plan in group:
            marks = "".join("W" if w else "-" for w in plan.worked)
            change = " ".join([*(f"+{t}" for t in sorted(plan.add)), *(f"-{t}" for t in sorted(plan.remove))]) or "no change"
            print(f"  {plan.person.name:<12} {marks}   {change}")
        print()
    changed = sum(p.changes for p in plans)
    print(f"{changed} people {'updated' if applied else 'would change'}{'' if applied else ' (preview only; pass --apply to write)'}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sunday", required=True, help="target Sunday, YYYY-MM-DD")
    parser.add_argument("--tz", default="UTC")
    parser.add_argument("--streak", type=int, default=3)
    parser.add_argument("--api-url")
    parser.add_argument("--demo", action="store_true", help="use examples/demo_workforce.json; nothing leaves this process")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)

    target, tz = dt.date.fromisoformat(args.sunday), ZoneInfo(args.tz)
    if args.demo:
        workforce = demo_workforce()
    elif args.api_url:
        import os
        token = os.environ.get("WORKFORCE_API_TOKEN")
        if not token:
            print("WORKFORCE_API_TOKEN is not set", file=sys.stderr)
            return 2
        workforce = JsonApiWorkforce(args.api_url, token)
    else:
        parser.error("pass --demo or --api-url")
    try:
        plans = run(workforce, target, tz, args.streak, args.apply)
    except ValueError as err:
        print(err, file=sys.stderr)
        return 2
    print_plans(plans, target, args.streak, args.apply)
    return 0


if __name__ == "__main__":
    sys.exit(main())
