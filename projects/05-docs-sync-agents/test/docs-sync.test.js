import assert from "node:assert/strict";
import { mkdtempSync, readFileSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import { anthropicProvider, heuristicProvider } from "../lib/classifier.js";
import { firstJsonObject, parseEnvelope } from "../lib/envelope.js";
import { runGates } from "../lib/gates.js";
import { JobStore, sync } from "../lib/pipeline.js";
import { classifySpecs } from "../lib/spec-diff.js";

const here = path.dirname(fileURLToPath(import.meta.url));
const scenario = (name, file) => JSON.parse(readFileSync(path.join(here, "..", "evals", "scenarios", name, file), "utf8"));
const repo = path.join(here, "..", "fixtures", "repo");

test("spec diff detects optional additions, new required fields and version cutovers", () => {
  const before = scenario("additive-optional-field", "before.json");
  assert.equal(classifySpecs(before, before).classification, "skip");
  assert.equal(classifySpecs(before, scenario("additive-optional-field", "after.json")).classification, "additive");
  const required = classifySpecs(before, scenario("breaking-new-required-field", "after.json"));
  assert.equal(required.classification, "breaking");
  assert.match(required.reasons.join(), /site_id/);
  assert.match(classifySpecs(before, scenario("breaking-v2-cutover", "after.json")).reasons.join(), /new API version surface/);
});

test("removed operations and type changes are breaking", () => {
  const before = scenario("additive-optional-field", "before.json");
  const after = structuredClone(before);
  delete after.paths["/v1/shifts"].get;
  after.components.schemas.Shift.properties.start.type = "integer";
  const { classification, reasons } = classifySpecs(before, after);
  assert.equal(classification, "breaking");
  assert.ok(reasons.some((r) => r.includes("removed operation GET /v1/shifts")));
  assert.ok(reasons.some((r) => r.includes("changed type")));
});

test("envelope parsing tolerates prose around the JSON and rejects bad enums", () => {
  assert.equal(firstJsonObject('noise {"a":"}"} trailing }'), '{"a":"}"}');
  assert.equal(parseEnvelope('Here: {"spec":"skip","runbook":"update","files":[],"rationale":"x"}').runbook, "update");
  assert.throws(() => parseEnvelope('{"spec":"maybe","runbook":"skip"}'), /invalid spec/);
});

test("anthropic provider runs the diff_specs tool loop and parses the structured answer", async () => {
  const calls = [];
  const client = {
    messages: {
      create: async (request) => {
        calls.push(request);
        if (calls.length === 1) return { stop_reason: "tool_use", content: [{ type: "tool_use", id: "t1", name: "diff_specs", input: {} }] };
        return { stop_reason: "end_turn", content: [{ type: "text", text: '{"spec":"breaking","runbook":"new","files":["runbooks/"],"rationale":"v2 cutover"}' }] };
      },
    },
  };
  const before = scenario("breaking-v2-cutover", "before.json");
  const result = await anthropicProvider({ client }).classify({ diff: "+x", specs: { before, after: scenario("breaking-v2-cutover", "after.json") } });
  assert.deepEqual([result.spec, result.runbook], ["breaking", "new"]);
  assert.equal(calls[0].model, "claude-opus-5-5");
  const toolResult = calls[1].messages.at(-1).content[0];
  assert.equal(toolResult.tool_use_id, "t1");
  assert.equal(JSON.parse(toolResult.content).classification, "breaking");
});

test("pipeline skips no-op merges and gates writers behind approval", async () => {
  const store = new JobStore(mkdtempSync(path.join(os.tmpdir(), "jobs-")));
  const before = scenario("ops-only-backoff", "before.json");
  const skipped = await sync({ sha: "a1", subject: "rename", diff: "+function x() {}", specs: { before, after: before }, provider: heuristicProvider(), store });
  assert.equal(skipped.state, "skipped");
  const waiting = await sync({ sha: "b2", subject: "backoff", diff: "+const RETRY_DELAYS_MS = [1]", specs: { before, after: before }, provider: heuristicProvider(), store });
  assert.equal(waiting.state, "awaiting_approval");
  assert.deepEqual(waiting.briefs.map((b) => b.writer), ["runbook"]);
  assert.throws(() => store.transition("b2", "pr_opened"), /cannot move/);
  assert.equal(store.transition("b2", "writing").state, "writing");
});

test("gates pass on a well-formed runbook and catch scope drift", () => {
  const ok = runGates({ root: repo, changedFiles: ["runbooks/publish-job-failures.md"], envelope: { spec: "skip", runbook: "update" } });
  assert.ok(ok.every((g) => g.pass), JSON.stringify(ok));
  const drift = runGates({ root: repo, changedFiles: ["openapi/openapi.json"], envelope: { spec: "skip", runbook: "skip" } });
  assert.equal(drift.find((g) => g.gate === "scope").pass, false);
});
