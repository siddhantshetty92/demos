"""Staffing requirement math: Erlang C for realtime channels, linear workload for async ones."""
from __future__ import annotations

import math
from dataclasses import dataclass

REALTIME_CHANNELS = {"phone", "chat", "voice"}


def is_realtime(channel: str) -> bool:
    return channel.lower() in REALTIME_CHANNELS


@dataclass(frozen=True)
class Variables:
    shrinkage_percent: float = 0.0
    concurrency: float = 1.0
    minimum_staffing: float = 0.0

    @property
    def productive_fraction(self) -> float:
        fraction = 1.0 - self.shrinkage_percent / 100.0
        if fraction <= 0:
            raise ValueError(f"shrinkage {self.shrinkage_percent}% leaves no productive time")
        return fraction * self.concurrency


def traffic_erlangs(contacts: float, interval_seconds: float, aht_seconds: float) -> float:
    return contacts * aht_seconds / interval_seconds


def erlang_b(agents: int, traffic: float) -> float:
    blocking = 1.0
    for n in range(1, agents + 1):
        blocking = traffic * blocking / (n + traffic * blocking)
    return blocking


def erlang_c(agents: int, traffic: float) -> float:
    if agents <= traffic:
        return 1.0
    b = erlang_b(agents, traffic)
    return agents * b / (agents - traffic * (1 - b))


def service_level(agents: int, traffic: float, aht_seconds: float, threshold_seconds: float) -> float:
    if traffic <= 0:
        return 1.0
    if agents <= traffic:
        return 0.0
    wait_probability = erlang_c(agents, traffic)
    return 1.0 - wait_probability * math.exp(-(agents - traffic) * threshold_seconds / aht_seconds)


def erlang_agents(contacts: float, interval_seconds: float, aht_seconds: float, threshold_seconds: float, target_sl: float) -> int:
    traffic = traffic_erlangs(contacts, interval_seconds, aht_seconds)
    if traffic <= 0:
        return 0
    agents = max(1, math.floor(traffic))
    while service_level(agents, traffic, aht_seconds, threshold_seconds) < target_sl:
        agents += 1
    return agents


@dataclass(frozen=True)
class ChannelTargets:
    channel: str
    aht_seconds: float
    sl_threshold_seconds: float = 0.0
    sl_target: float = 0.8


def required_agents(contacts: float, interval_seconds: float, targets: ChannelTargets, variables: Variables) -> float:
    if contacts <= 0:
        return 0.0
    if is_realtime(targets.channel):
        raw = erlang_agents(contacts, interval_seconds, targets.aht_seconds, targets.sl_threshold_seconds, targets.sl_target)
    else:
        raw = traffic_erlangs(contacts, interval_seconds, targets.aht_seconds)
    return max(raw / variables.productive_fraction, variables.minimum_staffing)


def contacts_for_required(required: float, interval_seconds: float, targets: ChannelTargets, variables: Variables) -> float:
    if required <= 0 or targets.aht_seconds <= 0:
        return 0.0
    if not is_realtime(targets.channel):
        return required * variables.productive_fraction * interval_seconds / targets.aht_seconds
    lo, hi = 0.0, 1.0
    while required_agents(hi, interval_seconds, targets, variables) < required:
        hi *= 2
    for _ in range(50):
        mid = (lo + hi) / 2
        if required_agents(mid, interval_seconds, targets, variables) >= required:
            hi = mid
        else:
            lo = mid
    return hi
