import { readFileSync, writeFileSync } from "node:fs";
import { summarize } from "./lib/aggregate.js";
import { parseIssue } from "./lib/parse.js";

export function previewPayload(issues) {
  const gaps = issues.map(parseIssue);
  return { viewer: "static preview", generatedAt: "2026-10-20T09:00:00.000Z", preview: true, gaps, summary: summarize(gaps) };
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const issues = JSON.parse(readFileSync(new URL("./data/sample-issues.json", import.meta.url), "utf8"));
  writeFileSync(new URL("./data/preview.js", import.meta.url), `globalThis.GAP_PREVIEW = ${JSON.stringify(previewPayload(issues), null, 1)};\n`);
  console.log("wrote data/preview.js");
}
