# Agent State Simulator

**Streams realistic live agent presence (on call, available, on break) from a weekly schedule, with a rotating handful of agents out of adherence.**

## Problem

Real-time adherence dashboards are the most compelling screen in a workforce-management demo, and the hardest to fake. They compare what each agent *should* be doing (the schedule) with what their phone, chat and ticketing systems *say* they are doing, live. A demo environment has schedules but no live presence feed, so the screen sits empty.

## What I built

A small service that, every tick:

1. **Resolves who is on shift** from a schedule CSV collapsed into a *weekly repeating pattern* (minute of week, Monday 00:00 = 0). Any week's export works forever. Shifts that cross Sunday midnight are split so they wrap. Timezones and DST are handled by converting "now" into the schedule's local minute of week.
2. **Keeps a pool of N agents out of adherence.** Each stint lasts 15–90 minutes; agents who leave shift drop out; the pool refills from on-shift agents. The dashboard always shows a few red rows, never the same ones for long.
3. **Picks a concrete state per platform.** Productive blocks cycle through productive states (`Available → On Call → After Call Work`) in 15–35 minute segments. Breaks, lunches and out-of-adherence agents get non-productive states. Segments are seeded by agent, block and platform, so a given minute always yields the same state and successive ticks look continuous rather than random.
4. **Emits one batch per platform**, to stdout or a webhook.

```
$ node cli.js --at 2026-10-21T15:30:00Z --once
2026-10-21T15:30:00.000Z  on shift: 8  out of adherence: ines@…, chloe@…, jon@…
telephony  T101       Available        Phones
telephony  T107       After Call Work  Phones
telephony  T109       Not Ready        OUT OF ADHERENCE
chat       C206       Away             Lunch
…
```

**Mock data:** [`examples/people.csv`](examples/people.csv) (12 agents with telephony, chat and ticketing ids) and [`examples/schedule.csv`](examples/schedule.csv) (a week of shifts with breaks, lunch and coaching) → [`sample-output/ticks.json`](sample-output/ticks.json): 16 half-hourly ticks across one day, showing every emitted state and who was out of adherence.

## Run it

```bash
node cli.js                                    # tick every 60 s to stdout
node cli.js --webhook https://… --ooa 5        # post batches; WEBHOOK_TOKEN adds a bearer header
npm test                                       # 7 tests
```

Node 20+, no dependencies.

## Design choices

- **Deterministic randomness everywhere** (seeded PRNG keyed by agent and block). Restarts don't make every agent jump state, and bugs are reproducible.
- **Out of adherence only applies to productive time.** An agent on lunch showing "Lunch" is in adherence. Picking OOA agents only from productive on-shift agents keeps the red rows believable.
- **Platform vocabularies are data.** Adding a platform is a new entry in `lib/states.js` plus an id column in the people CSV.

In the original setting this ran as a hosted service streaming roughly 85 agents across nine source systems into several demo environments at once, with a small control UI to upload rosters and start or stop each stream.
