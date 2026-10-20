from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from .staffing import ChannelTargets, Variables

VALID_INTERVALS = {15, 30, 60}


class SpecError(ValueError):
    pass


@dataclass(frozen=True)
class Queue:
    name: str
    channel: str
    team: str
    headcount: int
    aht_seconds: float
    sl_threshold_seconds: float = 0.0
    sl_target: float = 0.8

    @property
    def targets(self) -> ChannelTargets:
        return ChannelTargets(self.channel, self.aht_seconds, self.sl_threshold_seconds, self.sl_target)


@dataclass(frozen=True)
class Event:
    queue: str
    date: str
    multiplier: float


@dataclass(frozen=True)
class Story:
    swing: float = 0.3
    coverage: float = 0.7
    noise: float = 0.08
    seed: int = 1
    events: tuple[Event, ...] = ()


@dataclass(frozen=True)
class Spec:
    company: str
    email_domain: str
    timezone: str
    interval_minutes: int
    weeks_back: int
    open_hour: int
    close_hour: int
    weekend_weight: float
    variables: Variables
    sites: tuple[str, ...]
    skills: dict[str, float]
    queues: tuple[Queue, ...]
    story: Story = field(default_factory=Story)

    @property
    def interval_seconds(self) -> int:
        return self.interval_minutes * 60

    @property
    def teams(self) -> list[str]:
        return sorted({q.team for q in self.queues})


def _require(data: dict, key: str, where: str):
    if key not in data:
        raise SpecError(f"{where}: missing '{key}'")
    return data[key]


def parse_spec(data: dict) -> Spec:
    interval = int(data.get("interval_minutes", 30))
    if interval not in VALID_INTERVALS:
        raise SpecError(f"interval_minutes must be one of {sorted(VALID_INTERVALS)}")
    hours = data.get("business_hours", {})
    open_hour, close_hour = int(hours.get("open", 8)), int(hours.get("close", 20))
    if not 0 <= open_hour < close_hour <= 24:
        raise SpecError("business_hours: open must be before close, both within 0-24")

    queues = []
    for i, raw in enumerate(_require(data, "queues", "spec")):
        where = f"queues[{i}]"
        queue = Queue(
            name=_require(raw, "name", where),
            channel=_require(raw, "channel", where),
            team=raw.get("team", raw["name"]),
            headcount=int(_require(raw, "headcount", where)),
            aht_seconds=float(_require(raw, "aht_seconds", where)),
            sl_threshold_seconds=float(raw.get("sl_threshold_seconds", 0)),
            sl_target=float(raw.get("sl_target", 0.8)),
        )
        if queue.headcount <= 0 or queue.aht_seconds <= 0:
            raise SpecError(f"{where}: headcount and aht_seconds must be positive")
        queues.append(queue)
    names = [q.name for q in queues]
    if len(names) != len(set(names)):
        raise SpecError("queue names must be unique")

    story_raw = data.get("story", {})
    events = tuple(Event(e["queue"], e["date"], float(e["multiplier"])) for e in story_raw.get("events", []))
    for event in events:
        if event.queue not in names:
            raise SpecError(f"story event references unknown queue '{event.queue}'")

    company = _require(data, "company", "spec")
    variables_raw = data.get("variables", {})
    return Spec(
        company=company,
        email_domain=data.get("email_domain", f"{company.lower().replace(' ', '')}.example.com"),
        timezone=data.get("timezone", "UTC"),
        interval_minutes=interval,
        weeks_back=int(data.get("weeks_back", 4)),
        open_hour=open_hour,
        close_hour=close_hour,
        weekend_weight=float(hours.get("weekend_weight", 0.4)),
        variables=Variables(
            shrinkage_percent=float(variables_raw.get("shrinkage_percent", 0)),
            concurrency=float(variables_raw.get("concurrency", 1)),
            minimum_staffing=float(variables_raw.get("minimum_staffing", 0)),
        ),
        sites=tuple(data.get("sites", ["Main"])),
        skills={k: float(v) for k, v in data.get("skills", {}).items()},
        queues=tuple(queues),
        story=Story(
            swing=float(story_raw.get("swing", 0.3)),
            coverage=float(story_raw.get("coverage", 0.7)),
            noise=float(story_raw.get("noise", 0.08)),
            seed=int(story_raw.get("seed", 1)),
            events=events,
        ),
    )


def load_spec(path: str | Path) -> Spec:
    with open(path, "rb") as fh:
        return parse_spec(tomllib.load(fh))
