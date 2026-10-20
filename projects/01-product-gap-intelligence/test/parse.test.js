import assert from "node:assert/strict";
import { test } from "node:test";
import { summarize } from "../lib/aggregate.js";
import { parseAccounts, parseIssue, parseMoney, parseTitle } from "../lib/parse.js";

test("title splits into area, sub-area and feature with either arrow", () => {
  assert.deepEqual(parseTitle("Scheduling → Rules → Weekend rest"), { area: "Scheduling", subArea: "Rules", feature: "Weekend rest" });
  assert.deepEqual(parseTitle("Reporting -> Exports"), { area: "Reporting", subArea: "", feature: "Exports" });
  assert.deepEqual(parseTitle("Just a title"), { area: "Uncategorized", subArea: "", feature: "Just a title" });
});

test("money parses k and M suffixes and commas", () => {
  assert.equal(parseMoney("$340k"), 340_000);
  assert.equal(parseMoney("$1.2M"), 1_200_000);
  assert.equal(parseMoney("$85,000"), 85_000);
  assert.equal(parseMoney("n/a"), 0);
});

test("accounts come from ### headings in the description", () => {
  const accounts = parseAccounts("intro\n### Acme | $90k | SMB | Proposal\n* link\n### Globex | $1M | Enterprise | Renewal");
  assert.deepEqual(accounts, [
    { name: "Acme", arr: 90_000, segment: "SMB", stage: "Proposal" },
    { name: "Globex", arr: 1_000_000, segment: "Enterprise", stage: "Renewal" },
  ]);
});

test("issue gets impact from labels and sums ARR", () => {
  const gap = parseIssue({ id: "G-1", title: "A → B → C", labels: ["deal breaker"], priority: 1, description: "### X | $10k\n### Y | $5k" });
  assert.equal(gap.impact, "Deal breaker");
  assert.equal(gap.priority, "Urgent");
  assert.equal(gap.arrAtRisk, 15_000);
});

test("unique ARR counts an account once even when it appears on several gaps", () => {
  const gaps = [
    parseIssue({ id: "1", title: "A → x", labels: [], description: "### Acme | $100k" }),
    parseIssue({ id: "2", title: "B → y", labels: [], description: "### Acme | $100k\n### Globex | $50k" }),
  ];
  const { totals } = summarize(gaps);
  assert.equal(totals.accountsAffected, 2);
  assert.equal(totals.uniqueArrAtRisk, 150_000);
});

test("static preview data matches the sample issues", async () => {
  const { readFileSync } = await import("node:fs");
  const { previewPayload } = await import("../build-preview.js");
  const issues = JSON.parse(readFileSync(new URL("../data/sample-issues.json", import.meta.url), "utf8"));
  const committed = readFileSync(new URL("../data/preview.js", import.meta.url), "utf8");
  assert.equal(committed, `globalThis.GAP_PREVIEW = ${JSON.stringify(previewPayload(issues), null, 1)};\n`, "run `node build-preview.js`");
});
