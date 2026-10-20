"""Turns a headcount into case-level volume whose derived staffing requirement tells a story.

Per queue and interval:
  capacity        = headcount x coverage x intraday/weekday profile
  target_required = capacity x (1 + slow wave + noise) x event multiplier
  contacts        = the inverse of the staffing formula for target_required
The platform recomputes the requirement from the cases, so it lands on the
intended mix of over- and under-staffed intervals.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import math
import random
from dataclasses import dataclass
from zoneinfo import ZoneInfo

from .roster import Agent
from .spec import Queue, Spec
from .staffing import contacts_for_required, required_agents

WAVE_PERIOD_HOURS = 7.5 * 24
UNDER_THRESHOLD = 1.1
OVER_THRESHOLD = 0.9


def seeded(*parts) -> random.Random:
    digest = hashlib.sha256("|".join(map(str, parts)).encode()).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))


@dataclass(frozen=True)
class IntervalDemand:
    queue: str
    channel: str
    start: dt.datetime
    capacity: float
    contacts: int
    required: float

    @property
    def state(self) -> str:
        if self.capacity <= 0:
            return "closed"
        if self.required > self.capacity * UNDER_THRESHOLD:
            return "under"
        if self.required < self.capacity * OVER_THRESHOLD:
            return "over"
        return "ok"


@dataclass(frozen=True)
class Case:
    import_id: str
    queue: str
    channel: str
    created_at: dt.datetime
    handle_time_seconds: int
    status: str
    assignee_import_id: str | None


def intraday_profile(local: dt.datetime, spec: Spec) -> float:
    hour = local.hour + local.minute / 60
    if not spec.open_hour <= hour < spec.close_hour:
        return 0.0
    span = spec.close_hour - spec.open_hour
    x = (hour - spec.open_hour) / span
    shape = 0.55 + 0.45 * (math.exp(-((x - 0.3) ** 2) / 0.02) + 0.8 * math.exp(-((x - 0.7) ** 2) / 0.03))
    weekday_weight = spec.weekend_weight if local.weekday() >= 5 else 1.0
    return min(shape, 1.0) * weekday_weight


def interval_starts(spec: Spec, end: dt.datetime) -> list[dt.datetime]:
    step = dt.timedelta(minutes=spec.interval_minutes)
    start = (end - dt.timedelta(weeks=spec.weeks_back)).replace(minute=0, second=0, microsecond=0)
    starts, cursor = [], start
    while cursor + step <= end:
        starts.append(cursor)
        cursor += step
    return starts


def event_multiplier(spec: Spec, queue: Queue, local: dt.datetime) -> float:
    for event in spec.story.events:
        if event.queue == queue.name and event.date == local.date().isoformat():
            return event.multiplier
    return 1.0


def plan_demand(spec: Spec, end: dt.datetime) -> list[IntervalDemand]:
    tz = ZoneInfo(spec.timezone)
    story = spec.story
    demand = []
    for queue in spec.queues:
        phase = seeded(story.seed, queue.name, "phase").random() * 2 * math.pi
        for start in interval_starts(spec, end):
            local = start.astimezone(tz)
            capacity = queue.headcount * story.coverage * intraday_profile(local, spec)
            if capacity <= 0:
                demand.append(IntervalDemand(queue.name, queue.channel, start, 0.0, 0, 0.0))
                continue
            rng = seeded(story.seed, queue.name, start.isoformat())
            hours = start.timestamp() / 3600
            wave = story.swing * math.sin(2 * math.pi * hours / WAVE_PERIOD_HOURS + phase)
            noise = rng.gauss(0, story.noise)
            target = max(capacity * (1 + wave + noise) * event_multiplier(spec, queue, local), 0.0)
            exact = contacts_for_required(target, spec.interval_seconds, queue.targets, spec.variables)
            contacts = math.floor(exact) + (1 if rng.random() < exact - math.floor(exact) else 0)
            required = required_agents(contacts, spec.interval_seconds, queue.targets, spec.variables)
            demand.append(IntervalDemand(queue.name, queue.channel, start, capacity, contacts, required))
    return demand


def handle_times(rng: random.Random, n: int, aht: float, sigma: float = 0.5) -> list[int]:
    if n == 0:
        return []
    draws = [rng.lognormvariate(0, sigma) for _ in range(n)]
    scale = aht * n / sum(draws)
    return [max(1, round(d * scale)) for d in draws]


def materialize(spec: Spec, demand: list[IntervalDemand], roster: list[Agent], end: dt.datetime, open_recency_days: int = 3):
    by_queue: dict[str, list[Agent]] = {}
    for agent in roster:
        for queue in agent.queues:
            by_queue.setdefault(queue, []).append(agent)
    queues = {q.name: q for q in spec.queues}
    for interval in demand:
        if interval.contacts == 0:
            continue
        queue = queues[interval.queue]
        rng = seeded(spec.story.seed, "cases", queue.name, interval.start.isoformat())
        recent = (end - interval.start).days < open_recency_days
        for i, seconds in enumerate(handle_times(rng, interval.contacts, queue.aht_seconds)):
            is_open = rng.random() < (0.5 if recent else 0.03)
            agents = by_queue.get(queue.name, [])
            yield Case(
                import_id=f"{queue.name[:3].upper()}-{int(interval.start.timestamp())}-{i:04d}",
                queue=queue.name,
                channel=queue.channel,
                created_at=interval.start + dt.timedelta(seconds=rng.randrange(spec.interval_seconds)),
                handle_time_seconds=seconds,
                status="open" if is_open else "solved",
                assignee_import_id=None if is_open or not agents else rng.choice(agents).imported_id,
            )


def self_check(demand: list[IntervalDemand]) -> dict[str, dict[str, float]]:
    report: dict[str, dict[str, float]] = {}
    for interval in demand:
        row = report.setdefault(interval.queue, {"under": 0, "ok": 0, "over": 0, "closed": 0, "contacts": 0})
        row[interval.state] += 1
        row["contacts"] += interval.contacts
    return report
