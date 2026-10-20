#!/usr/bin/env node
import { readdirSync, readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { parseArgs } from "node:util";
import { providerFromName } from "./lib/classifier.js";

const { values } = parseArgs({ options: { provider: { type: "string", default: "heuristic" } } });
const root = path.join(path.dirname(fileURLToPath(import.meta.url)), "evals", "scenarios");
const provider = providerFromName(values.provider);
const read = (dir, file) => readFileSync(path.join(root, dir, file), "utf8");

let correct = 0;
const scenarios = readdirSync(root).sort();
console.log(`provider: ${provider.name}\n`);
console.log(`${"scenario".padEnd(30)}${"expected".padEnd(20)}${"got".padEnd(20)}`);
for (const name of scenarios) {
  const expected = JSON.parse(read(name, "expected.json"));
  const got = await provider.classify({
    diff: read(name, "diff.patch"),
    specs: { before: JSON.parse(read(name, "before.json")), after: JSON.parse(read(name, "after.json")) },
  });
  const pass = got.spec === expected.spec && got.runbook === expected.runbook;
  if (pass) correct++;
  console.log(`${name.padEnd(30)}${`${expected.spec}/${expected.runbook}`.padEnd(20)}${`${got.spec}/${got.runbook}`.padEnd(20)}${pass ? "✓" : "✗"}`);
}
console.log(`\n${correct}/${scenarios.length} correct`);
process.exitCode = correct === scenarios.length ? 0 : 1;
