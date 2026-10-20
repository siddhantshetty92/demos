# Rotation Eligibility

**Enforces a labor rule ("anyone who worked the last three Sundays must have the next one off") by keeping exactly one eligibility tag on every person, so the scheduler can't break it.**

## Problem

Some labor regulations limit consecutive Sunday work. A scheduling engine that optimizes coverage doesn't know the rule, so every week a planner had to check each agent's last three Sundays by hand and fix the schedule afterwards. Mistakes are compliance issues, not just inconveniences.

## How it works

Rather than teach the scheduler a new rule, the tool turns the rule into data the scheduler already respects: a pair of mutually exclusive tags.

1. For a target Sunday, look at the previous N Sundays **in the site's local timezone** (a 23:30 Saturday shift is not Sunday work).
2. Count only **productive** scheduled time. Training or an all-day meeting doesn't count as working.
3. Worked all N → `must-rest-next-sunday`; otherwise → `can-work-next-sunday`.
4. Guarantee **exactly one** of the two tags per person. Anyone holding both (a data error) is corrected.
5. **Preview by default.** `--apply` writes only the people whose tags change, and a second run is a no-op.

```
$ python3 rotation.py --demo --sunday 2026-10-25 --tz Europe/Madrid
Target Sunday 2026-10-25; checking 2026-10-18, 2026-10-11, 2026-10-04

MUST REST (4)
  Ada Brennan  WWW   +must-rest-next-sunday -can-work-next-sunday
  Dana Ruiz    WWW   -can-work-next-sunday
  …
CAN WORK (8)
  Eli Haddad   ---   +can-work-next-sunday -must-rest-next-sunday
  Ivy Mensah   WW-   no change        <- third Sunday was training only
  Lea Novak    W-W   no change        <- shift ended 23:59 Saturday
  …
4 people would change (preview only; pass --apply to write)
```

**Mock data:** [`examples/demo_workforce.json`](examples/demo_workforce.json) (12 agents, 3 Sundays of activity, including a training-only Sunday, a late-Saturday shift and someone holding both tags) · output in [`sample-output/preview.txt`](sample-output/preview.txt).

## Run it

```bash
python3 rotation.py --demo --sunday 2026-10-25 --tz Europe/Madrid   # fixture data, no network
WORKFORCE_API_TOKEN=… python3 rotation.py --api-url https://… --sunday 2026-10-25 --apply
python3 -m unittest discover -s tests                              # 6 tests
```

Python 3.9+, standard library only. `JsonApiWorkforce` is a thin adapter; point it at any API with people, activities and tag updates.

## Design choices

- **Encode the rule as data the existing system already enforces** instead of building a parallel scheduler.
- **Idempotent and minimal writes.** Safe to run on a schedule every week, and the audit log only shows real changes.
- **Planner-friendly.** The original was a local web app with a preview table and a single "update" button; non-technical planners run it weekly. A demo mode with fixture data let them rehearse safely.
