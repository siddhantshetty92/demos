import { IMPACT_LABELS } from "./parse.js";

function groupSum(gaps, keyOf) {
  const groups = new Map();
  for (const gap of gaps) {
    const key = keyOf(gap);
    const group = groups.get(key) ?? { key, count: 0, arrAtRisk: 0 };
    group.count += 1;
    group.arrAtRisk += gap.arrAtRisk;
    groups.set(key, group);
  }
  return [...groups.values()].sort((a, b) => b.arrAtRisk - a.arrAtRisk || b.count - a.count);
}

export function uniqueAccountArr(gaps) {
  const byName = new Map();
  for (const gap of gaps) {
    for (const account of gap.accounts) {
      byName.set(account.name, Math.max(byName.get(account.name) ?? 0, account.arr));
    }
  }
  return { accounts: byName.size, arr: [...byName.values()].reduce((s, v) => s + v, 0) };
}

export function summarize(gaps) {
  const impactOrder = [...IMPACT_LABELS, "Unrated"];
  const unique = uniqueAccountArr(gaps);
  return {
    totals: {
      gaps: gaps.length,
      dealBreakers: gaps.filter((g) => g.impact === "Deal breaker").length,
      accountsAffected: unique.accounts,
      uniqueArrAtRisk: unique.arr,
    },
    byArea: groupSum(gaps, (g) => g.area),
    byImpact: groupSum(gaps, (g) => g.impact).sort(
      (a, b) => impactOrder.indexOf(a.key) - impactOrder.indexOf(b.key),
    ),
    topGaps: [...gaps].sort((a, b) => b.arrAtRisk - a.arrAtRisk).slice(0, 10),
  };
}
