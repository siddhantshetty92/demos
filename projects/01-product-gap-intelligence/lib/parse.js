const IMPACT_LABELS = ["Deal breaker", "High impact", "Medium impact", "Low impact", "Roadmap"];
const PRIORITY_NAMES = { 0: "None", 1: "Urgent", 2: "High", 3: "Medium", 4: "Low" };
const TITLE_SEPARATOR = /\s*(?:→|->)\s*/;
const ACCOUNT_HEADING = /^###\s+(.+)$/gm;

export function parseTitle(title) {
  const parts = title.split(TITLE_SEPARATOR).map((p) => p.trim()).filter(Boolean);
  if (parts.length >= 3) return { area: parts[0], subArea: parts[1], feature: parts.slice(2).join(" → ") };
  if (parts.length === 2) return { area: parts[0], subArea: "", feature: parts[1] };
  return { area: "Uncategorized", subArea: "", feature: title.trim() };
}

export function parseMoney(text) {
  const match = String(text).replace(/,/g, "").match(/\$?\s*([\d.]+)\s*([kKmM]?)/);
  if (!match) return 0;
  const multiplier = { k: 1e3, m: 1e6 }[match[2].toLowerCase()] ?? 1;
  return Math.round(Number(match[1]) * multiplier);
}

export function parseAccounts(description) {
  const accounts = [];
  for (const [, heading] of String(description ?? "").matchAll(ACCOUNT_HEADING)) {
    const [name, arr, segment = "", stage = ""] = heading.split("|").map((s) => s.trim());
    if (!name) continue;
    accounts.push({ name, arr: parseMoney(arr ?? ""), segment, stage });
  }
  return accounts;
}

export function impactFromLabels(labels) {
  const names = new Set(labels.map((l) => l.toLowerCase()));
  return IMPACT_LABELS.find((label) => names.has(label.toLowerCase())) ?? "Unrated";
}

export function parseIssue(issue) {
  const labels = (issue.labels ?? []).map(String);
  const accounts = parseAccounts(issue.description);
  return {
    id: issue.id,
    url: issue.url ?? null,
    ...parseTitle(issue.title),
    impact: impactFromLabels(labels),
    priority: PRIORITY_NAMES[issue.priority] ?? "None",
    status: issue.status ?? "Backlog",
    createdAt: issue.createdAt ?? null,
    accounts,
    arrAtRisk: accounts.reduce((sum, a) => sum + a.arr, 0),
  };
}

export { IMPACT_LABELS };
