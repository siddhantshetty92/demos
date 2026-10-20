# Demo Environment Builder

**One spec file in, a believable customer-support operation out: org config, a staffed roster, and months of contact history calibrated so the staffing story is the one you want to tell.**

## Problem

Workforce-management software demos fall flat on empty or random data. A prospect wants to see *their* shape of operation (their queues, channels, sites, headcount) and a staffing picture with real tension: some intervals under-staffed, some over, a spike on a known date. Building that by hand took days per prospect, and random volume produced requirement curves that looked fake, because the platform derives staffing requirements from volume with Erlang C math the random data ignored.

## What I built

A CLI that takes a TOML spec (`examples/acme_mobile.toml`) and:

1. **Synthesizes config and a roster**: sites, teams, skills with coverage and proficiency, queues, and one agent per seat, all deterministic from a seed.
2. **Plans demand backwards from headcount.** For every queue and interval it computes the capacity the roster provides, applies a slow wave, noise and named events to get a *target requirement*, then **inverts the staffing formula** to find the contact volume that produces exactly that requirement.
3. **Materializes individual cases** with log-normal handle times rescaled so the mean equals the queue's AHT exactly. The platform infers AHT from those cases, so its own requirement math lands where the plan said it would.
4. **Self-checks before pushing anything**: it recomputes the requirement from the generated contacts and reports the under/ok/over split per queue.
5. **Pushes in dependency order** (sites → teams → skills → queues → people → cases) to CSV for review, or to any JSON bulk API with batching, rate limiting and retry on 429/5xx. Every record has a stable import id, so re-running is a safe upsert that also resumes an interrupted seed.

```
$ python3 cli.py --spec examples/acme_mobile.toml --dry-run
Acme Mobile: 4 queues, 95 agents, 4 weeks of 30-minute intervals

queue                   contacts   under    ok  over  closed
Billing Phone              30777     262   180   342     560   (33% under, 44% over)
Tech Support Chat          14789     272   172   340     560   (35% under, 43% over)
Returns Email              22282     302   149   333     560   (39% under, 42% over)
Back Office Review          5125     314   146   324     560   (40% under, 41% over)
```

**Mock data:** spec [`examples/acme_mobile.toml`](examples/acme_mobile.toml) → output in [`sample-output/`](sample-output): `people.csv` (95 agents), `demand.csv` (every queue × 30-minute interval with capacity, contacts, derived requirement and under/ok/over state), the 2,000 most recent rows of `cases.csv` (the full run is ~73k), and the config CSVs.

## The math

- **Realtime channels (phone, chat):** Erlang C. `staffing.py` implements it from first principles: Erlang B by the stable recurrence, Erlang C from B, service level `1 − C·e^(−(N−A)·T/AHT)`, then the smallest N that meets target. The tests pin it to textbook values (24 Erlangs, 240 s AHT, 80/20 → 29 agents).
- **Async channels (email, back office):** linear workload, `contacts × AHT / interval`.
- Both are divided by productive time (1 − shrinkage) × concurrency.
- **Inverse:** exact algebra for async; bisection for Erlang C, which is monotone in volume.

## Run it

```bash
python3 cli.py --spec examples/acme_mobile.toml --dry-run          # plan + self-check only
python3 cli.py --spec examples/acme_mobile.toml --out out/          # write CSVs
DEMO_API_KEY=… python3 cli.py --spec … --api-url https://sandbox.example.com/v1
python3 -m unittest discover -s tests                               # 12 tests
```

Python 3.11+, standard library only.

## What this changed

In the original setting, standing up a tailored demo went from days of manual setup to editing a spec and running one command. Pushing hundreds of agents and months of case history dropped from about three hours to about fifteen minutes once batches ran concurrently under the API's rate limit. Because the volume is derived from the requirement and not the other way round, a solutions engineer can ask for "a bit more under-staffing on Tuesdays" and get exactly that.

## How AI helped

I built it with a coding agent, writing the staffing math and its tests against textbook values before trusting the calibration. A companion AI skill turns a prospect's requirements (an email, call notes, a deck) into a first-draft spec and applies plain-language tweaks like "add 50 agents to the EU team" or "make email 30% of volume", so the human step is review, not authoring.
