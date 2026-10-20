#!/usr/bin/env node
import { execFileSync } from "node:child_process";
import { parseArgs } from "node:util";
import { providerFromName } from "./lib/classifier.js";
import { JobStore, sync } from "./lib/pipeline.js";

const { values } = parseArgs({
  options: {
    repo: { type: "string", default: "." },
    sha: { type: "string", default: "HEAD" },
    spec: { type: "string", default: "openapi/openapi.json" },
    provider: { type: "string", default: "heuristic" },
    jobs: { type: "string", default: "jobs" },
    approve: { type: "boolean", default: false },
  },
});

const git = (...args) => execFileSync("git", ["-C", values.repo, ...args], { encoding: "utf8", maxBuffer: 20_000_000 });
const specAt = (rev) => {
  try {
    return JSON.parse(git("show", `${rev}:${values.spec}`));
  } catch {
    return null;
  }
};

const sha = git("rev-parse", values.sha).trim();
const store = new JobStore(values.jobs);

if (values.approve) {
  const job = store.transition(sha, "writing", { note: "approved by reviewer" });
  console.log(`approved ${sha.slice(0, 8)}; hand these briefs to your coding agent:\n`);
  for (const brief of job.briefs) console.log(`--- ${brief.writer} writer ---\n${brief.instructions}\n`);
} else {
  const job = await sync({
    sha,
    subject: git("log", "-1", "--format=%s", sha).trim(),
    diff: git("show", "--format=", sha),
    specs: { before: specAt(`${sha}^`), after: specAt(sha) },
    provider: providerFromName(values.provider),
    store,
  });
  console.log(JSON.stringify({ sha: job.sha, state: job.state, envelope: job.envelope }, null, 2));
  if (job.state === "awaiting_approval") console.log(`\nReview, then run: node sync.js --repo ${values.repo} --sha ${sha.slice(0, 8)} --approve`);
}
