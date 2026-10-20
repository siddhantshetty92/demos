#!/usr/bin/env python3
"""Period-over-period pipeline diagnostic from a CRM opportunity export, rendered as one HTML page."""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import html
import statistics
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

FUNNEL = ["Discovery", "Evaluation", "Proposal", "Negotiation", "Closed Won"]
RECOVERABLE = {"No decision / timing", "Budget", "Missing feature", "Champion left"}
TIER_ONE_REASONS = {"No decision / timing", "Budget"}


@dataclass(frozen=True)
class Opp:
    id: str
    account: str
    segment: str
    source: str
    created: dt.date
    amount: int
    furthest_stage: str
    stage: str
    loss_reason: str
    closed: dt.date | None

    @property
    def period(self) -> str:
        return f"{self.created.year} Q{(self.created.month - 1) // 3 + 1}"

    @property
    def won(self) -> bool:
        return self.stage == "Closed Won"

    @property
    def lost(self) -> bool:
        return self.stage == "Closed Lost"

    def reached(self, stage: str) -> bool:
        return self.won or FUNNEL.index(self.furthest_stage) >= FUNNEL.index(stage)


def load(path: Path) -> list[Opp]:
    with path.open(newline="") as fh:
        return [Opp(r["id"], r["account"], r["segment"], r["source"], dt.date.fromisoformat(r["created"]), int(r["amount"]),
                    r["furthest_stage"], r["stage"], r["loss_reason"], dt.date.fromisoformat(r["closed"]) if r["closed"] else None)
                for r in csv.DictReader(fh)]


def kpis(opps: list[Opp]) -> dict:
    closed = [o for o in opps if o.won or o.lost]
    won = [o for o in closed if o.won]
    return {
        "created": len(opps),
        "pipeline": sum(o.amount for o in opps),
        "win_rate": len(won) / len(closed) if closed else 0.0,
        "avg_deal": statistics.fmean(o.amount for o in won) if won else 0.0,
        "cycle_days": statistics.median((o.closed - o.created).days for o in won) if won else 0.0,
    }


def funnel(opps: list[Opp]) -> list[tuple[str, int, float]]:
    rows, previous = [], None
    for stage in FUNNEL:
        count = sum(o.reached(stage) for o in opps)
        rows.append((stage, count, count / previous if previous else 1.0))
        previous = count or None
    return rows


def by_segment(opps: list[Opp]) -> dict[str, int]:
    return dict(Counter(o.segment for o in opps))


def loss_reasons(opps: list[Opp]) -> dict[str, float]:
    lost = [o for o in opps if o.lost]
    counts = Counter(o.loss_reason or "Unspecified" for o in lost)
    return {reason: n / len(lost) for reason, n in counts.most_common()} if lost else {}


def win_back(opps: list[Opp]) -> list[tuple[int, Opp]]:
    medians = {seg: statistics.median(o.amount for o in opps if o.segment == seg) for seg in {o.segment for o in opps}}
    tiers = []
    for o in opps:
        if not o.lost or o.loss_reason not in RECOVERABLE:
            continue
        deep = FUNNEL.index(o.furthest_stage) >= FUNNEL.index("Proposal")
        if o.loss_reason in TIER_ONE_REASONS and deep and o.amount >= medians[o.segment]:
            tiers.append((1, o))
        elif deep or o.loss_reason == "Missing feature":
            tiers.append((2, o))
        else:
            tiers.append((3, o))
    return sorted(tiers, key=lambda t: (t[0], -t[1].amount))


def diagnose(opps: list[Opp], before: str, after: str) -> dict:
    groups = defaultdict(list)
    for o in opps:
        groups[o.period].append(o)
    a, b = groups[before], groups[after]
    if not a or not b:
        raise ValueError(f"need opportunities in both {before} and {after}; found {sorted(groups)}")
    return {
        "periods": (before, after),
        "kpis": (kpis(a), kpis(b)),
        "funnel": (funnel(a), funnel(b)),
        "segments": (by_segment(a), by_segment(b)),
        "losses": (loss_reasons(a), loss_reasons(b)),
        "win_back": win_back(a + b),
    }


def money(n: float) -> str:
    return f"${n / 1e6:.1f}M" if n >= 1e6 else f"${n / 1e3:.0f}k"


def delta(a: float, b: float, pct: bool = False, lower_is_better: bool = False) -> str:
    if pct:
        d = (b - a) * 100
        text = f"{d:+.1f} pts"
    elif a:
        d = (b - a) / a * 100
        text = f"{d:+.0f}%"
    else:
        return ""
    good = d <= 0 if lower_is_better else d >= 0
    return f'<span class="{"up" if good else "down"}">{text}</span>'


def bars(rows: list[tuple[str, float, float]], fmt) -> str:
    peak = max([max(x, y) for _, x, y in rows] + [1e-9])
    out = []
    for label, x, y in rows:
        out.append(f'<div class="bar-row"><span>{html.escape(label)}</span>'
                   f'<span class="track"><i class="a" style="width:{x / peak * 100:.1f}%"></i><i class="b" style="width:{y / peak * 100:.1f}%"></i></span>'
                   f'<span class="num">{fmt(x)} → {fmt(y)}</span></div>')
    return "".join(out)


def render(result: dict) -> str:
    p1, p2 = result["periods"]
    k1, k2 = result["kpis"]
    tiles = [
        ("Opportunities created", f"{k2['created']}", delta(k1["created"], k2["created"])),
        ("Pipeline created", money(k2["pipeline"]), delta(k1["pipeline"], k2["pipeline"])),
        ("Win rate", f"{k2['win_rate']:.0%}", delta(k1["win_rate"], k2["win_rate"], pct=True)),
        ("Average won deal", money(k2["avg_deal"]), delta(k1["avg_deal"], k2["avg_deal"])),
        ("Median cycle", f"{k2['cycle_days']:.0f} days", delta(k1["cycle_days"], k2["cycle_days"], lower_is_better=True)),
    ]
    f1, f2 = result["funnel"]
    s1, s2 = result["segments"]
    l1, l2 = result["losses"]
    reasons = sorted(set(l1) | set(l2), key=lambda r: -(l2.get(r, 0)))
    biggest = max(reasons, key=lambda r: l2.get(r, 0) - l1.get(r, 0)) if reasons else None
    tier_rows = "".join(
        f"<tr><td>Tier {tier}</td><td>{html.escape(o.account)}</td><td>{html.escape(o.segment)}</td><td>{html.escape(o.loss_reason)}</td>"
        f"<td>{html.escape(o.furthest_stage)}</td><td class='num'>{money(o.amount)}</td><td>{o.closed}</td></tr>"
        for tier, o in result["win_back"][:25])
    tier_counts = Counter(t for t, _ in result["win_back"])
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Pipeline Diagnostic</title><style>
:root{{--bg:#f9f9f7;--surface:#fff;--text:#111;--muted:#62615c;--line:rgba(0,0,0,.1);--a:#9ec5f4;--b:#2a78d6;--up:#16803c;--down:#c0392b}}
@media (prefers-color-scheme:dark){{:root{{--bg:#0f0f0e;--surface:#1b1b19;--text:#f2f1ec;--muted:#a5a49c;--line:rgba(255,255,255,.12);--a:#2f4f78;--b:#5b95ea;--up:#3fbf68;--down:#ef6b5b}}}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);font:14px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}}
.wrap{{max-width:1100px;margin:0 auto;padding:28px 16px 64px}}h1{{font-size:22px;margin:0}}.sub{{color:var(--muted);margin:4px 0 18px;font-size:13px}}
html{{background:var(--bg)}}.tiles{{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px}}.tiles.tiers{{grid-template-columns:repeat(3,1fr)}}.tile,.card{{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:14px 16px}}
.tile .l{{font-size:11.5px;color:var(--muted);text-transform:uppercase;letter-spacing:.05em}}.tile .v{{font-size:26px;font-weight:650}}.up{{color:var(--up)}}.down{{color:var(--down)}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:14px}}@media (max-width:760px){{.grid{{grid-template-columns:1fr}}}}
.card h2{{font-size:14px;margin:0 0 4px}}.note{{color:var(--muted);font-size:12.5px;margin:0 0 10px}}
.bar-row{{display:grid;grid-template-columns:150px 1fr 120px;gap:8px;align-items:center;font-size:12.5px;padding:3px 0}}
.track{{display:grid;gap:2px}}.track i{{display:block;height:7px;border-radius:4px}}.track .a{{background:var(--a)}}.track .b{{background:var(--b)}}
.num{{text-align:right;font-variant-numeric:tabular-nums}}.legend{{font-size:12px;color:var(--muted);margin-bottom:8px}}.legend i{{display:inline-block;width:10px;height:10px;border-radius:2px;margin:0 4px 0 10px;vertical-align:-1px}}
table{{width:100%;border-collapse:collapse;font-size:12.5px}}th{{text-align:left;color:var(--muted);font-weight:600;border-bottom:1px solid var(--line);padding:6px}}td{{padding:6px;border-bottom:1px solid var(--line)}}
.table{{margin-top:14px;overflow-x:auto}}</style></head><body><div class="wrap">
<h1>Pipeline Diagnostic — {p1} vs {p2}</h1>
<p class="sub">New-business opportunities from a CRM export. Every figure compares {p2} with {p1}.</p>
<div class="tiles">{"".join(f'<div class="tile"><div class="l">{l}</div><div class="v">{v}</div><div>{d}</div></div>' for l, v, d in tiles)}</div>
<p class="note" style="margin-top:10px">Win rate and cycle length count closed deals only. {p2} has had less time to close long deals, so its cycle length skews short until those deals resolve.</p>
<div class="legend" style="margin-top:14px"><i style="background:var(--a)"></i>{p1}<i style="background:var(--b)"></i>{p2}</div>
<div class="grid">
<div class="card"><h2>Where creation changed</h2><p class="note">Opportunities created by segment.</p>{bars([(s, s1.get(s, 0), s2.get(s, 0)) for s in sorted(set(s1) | set(s2))], lambda x: f"{x:.0f}")}</div>
<div class="card"><h2>Funnel progression</h2><p class="note">Share of the previous stage that reached each stage.</p>{bars([(st, a[2], b[2]) for st, a, b in zip(FUNNEL, f1, f2)][1:], lambda x: f"{x:.0%}")}</div>
<div class="card"><h2>Why deals were lost</h2><p class="note">Share of closed-lost deals. Largest increase: <b>{html.escape(biggest or "n/a")}</b>.</p>{bars([(r, l1.get(r, 0), l2.get(r, 0)) for r in reasons], lambda x: f"{x:.0%}")}</div>
<div class="card"><h2>Win-back list</h2><p class="note">Lost for recoverable reasons. Tier 1: timing or budget, reached Proposal, at or above segment median size.</p>
<div class="tiles tiers">{"".join(f'<div class="tile"><div class="l">Tier {t}</div><div class="v">{tier_counts.get(t, 0)}</div></div>' for t in (1, 2, 3))}</div></div>
</div>
<div class="card table"><h2>Top of the win-back list</h2><table><thead><tr><th>Tier</th><th>Account</th><th>Segment</th><th>Loss reason</th><th>Furthest stage</th><th class="num">Amount</th><th>Closed</th></tr></thead><tbody>{tier_rows}</tbody></table></div>
</div></body></html>"""


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("export", type=Path)
    parser.add_argument("--before", required=True, help='period label, e.g. "2026 Q2"')
    parser.add_argument("--after", required=True)
    parser.add_argument("--out", type=Path, default=Path("pipeline-diagnostic.html"))
    args = parser.parse_args(argv)
    try:
        result = diagnose(load(args.export), args.before, args.after)
    except ValueError as err:
        print(err, file=sys.stderr)
        return 2
    args.out.write_text(render(result))
    k1, k2 = result["kpis"]
    print(f"{args.before} → {args.after}: created {k1['created']} → {k2['created']}, win rate {k1['win_rate']:.0%} → {k2['win_rate']:.0%}; "
          f"{len(result['win_back'])} win-back candidates -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
