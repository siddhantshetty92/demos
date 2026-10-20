import { mkdirSync, readFileSync, writeFileSync, existsSync } from "node:fs";
import path from "node:path";

export const STATES = ["classified", "skipped", "awaiting_approval", "writing", "pr_opened", "writer_failed", "rejected"];

const TRANSITIONS = {
  classified: ["skipped", "awaiting_approval"],
  awaiting_approval: ["writing", "rejected"],
  writing: ["pr_opened", "writer_failed"],
  writer_failed: ["writing"],
};

export function writerBriefs(envelope, { sha, subject }) {
  const briefs = [];
  if (envelope.spec !== "skip") {
    briefs.push({
      writer: "spec",
      instructions: [
        `Merge ${sha} ("${subject}") was classified spec=${envelope.spec}.`,
        "Edit openapi/openapi.json so it matches the merged code exactly. Do not invent endpoints or fields that the diff does not show.",
        envelope.spec === "breaking" ? "Keep /v1 untouched and describe the new behavior under /v2." : "Stay on the existing version path.",
        "Open a pull request titled 'docs(spec): …' and include the classifier rationale in the description.",
      ].join("\n"),
    });
  }
  if (envelope.runbook !== "skip") {
    briefs.push({
      writer: "runbook",
      instructions: [
        `Merge ${sha} ("${subject}") was classified runbook=${envelope.runbook}.`,
        envelope.runbook === "new" ? "Create one new runbook under runbooks/ and add it to docs/manifest.json." : "Update the runbook mapped to the changed code path in docs/manifest.json.",
        "Every runbook keeps the required frontmatter and sections. Only reference commands that exist in this repository.",
        "Append a dated Changelog entry naming this merge.",
      ].join("\n"),
    });
  }
  return briefs;
}

export class JobStore {
  constructor(dir) {
    this.dir = dir;
    mkdirSync(dir, { recursive: true });
  }

  file(sha) {
    return path.join(this.dir, `${sha}.json`);
  }

  get(sha) {
    return existsSync(this.file(sha)) ? JSON.parse(readFileSync(this.file(sha), "utf8")) : null;
  }

  create(sha, fields) {
    const job = { sha, state: "classified", history: [{ state: "classified", at: new Date().toISOString() }], ...fields };
    writeFileSync(this.file(sha), JSON.stringify(job, null, 2));
    return job;
  }

  transition(sha, next, patch = {}) {
    const job = this.get(sha);
    if (!job) throw new Error(`no job for ${sha}`);
    if (!(TRANSITIONS[job.state] ?? []).includes(next)) throw new Error(`cannot move ${sha} from ${job.state} to ${next}`);
    Object.assign(job, patch, { state: next });
    job.history.push({ state: next, at: new Date().toISOString(), ...(patch.note ? { note: patch.note } : {}) });
    writeFileSync(this.file(sha), JSON.stringify(job, null, 2));
    return job;
  }
}

export async function sync({ sha, subject, diff, specs, provider, store }) {
  const envelope = await provider.classify({ diff, specs });
  store.create(sha, { subject, provider: provider.name, envelope });
  if (envelope.spec === "skip" && envelope.runbook === "skip") return store.transition(sha, "skipped", { note: envelope.rationale });
  return store.transition(sha, "awaiting_approval", { briefs: writerBriefs(envelope, { sha, subject }) });
}
