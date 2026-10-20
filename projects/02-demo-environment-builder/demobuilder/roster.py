from __future__ import annotations

import random
from dataclasses import dataclass

from .spec import Spec

FIRST_NAMES = ["Ava", "Ben", "Chloe", "Dev", "Elif", "Femi", "Gia", "Hiro", "Ines", "Jon", "Kaia", "Luca", "Mina", "Nils", "Omar", "Pia", "Quinn", "Ravi", "Sana", "Tomas", "Uma", "Vik", "Wen", "Yara", "Zed"]
LAST_NAMES = ["Abara", "Brandt", "Costa", "Dube", "Eriksen", "Fujita", "Garcia", "Haddad", "Ivanova", "Jensen", "Kim", "Laine", "Mensah", "Novak", "Okafor", "Patel", "Rossi", "Silva", "Tanaka", "Varga"]


@dataclass(frozen=True)
class Agent:
    imported_id: str
    first_name: str
    last_name: str
    email: str
    team: str
    site: str
    queues: tuple[str, ...]
    skills: tuple[tuple[str, int], ...]


def build_roster(spec: Spec) -> list[Agent]:
    rng = random.Random(spec.story.seed)
    agents: list[Agent] = []
    for queue in spec.queues:
        for _ in range(queue.headcount):
            n = len(agents) + 1
            first, last = rng.choice(FIRST_NAMES), rng.choice(LAST_NAMES)
            skills = tuple(
                (skill, rng.choices([1, 2, 3, 4, 5], weights=[1, 2, 4, 2, 1])[0])
                for skill, coverage in spec.skills.items()
                if rng.random() < coverage
            )
            agents.append(Agent(
                imported_id=f"AGT-{n:05d}",
                first_name=first,
                last_name=last,
                email=f"{first}.{last}.{n}@{spec.email_domain}".lower(),
                team=queue.team,
                site=spec.sites[n % len(spec.sites)],
                queues=(queue.name,),
                skills=skills,
            ))
    return agents
