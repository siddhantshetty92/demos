import { ENVELOPE_SCHEMA, parseEnvelope } from "./envelope.js";
import { classifySpecs } from "./spec-diff.js";

export const CLASSIFIER_PROMPT = `You are a docs-sync classifier for a public HTTP API. You see one merged git diff and decide whether the public API contract and/or the on-call runbooks must change.

Call the diff_specs tool before choosing "spec". It compares the OpenAPI document before and after this merge and returns skip | additive | breaking with reasons.
- If it reports additive or breaking, use that.
- If it reports skip, the spec file may not have been edited yet (code often lands first). Decide from the code diff instead.

spec:
- skip: no public HTTP contract change
- additive: optional fields, optional query params, new non-breaking paths on the same version
- breaking: removed or renamed fields, new required request fields, removed paths, type changes, or a new /v2 surface next to /v1

runbook:
- skip: no operational procedure change
- update: an existing failure mode, job, retry, or alert behavior changed
- new: a new failure mode, or a version cutover on-call has no procedure for

Easy to miss: adding /v2 while /v1 stays is a cutover (spec=breaking, runbook=new). Deprecation or Sunset headers also need a cutover runbook. Internal renames are skip/skip. Retry or backoff changes with no HTTP change are spec=skip, runbook=update.

"files" lists the docs paths writers should edit (openapi/, runbooks/). "rationale" is one or two sentences for a human reviewer: name the diff_specs result and why you chose the runbook decision.`;

const DIFF_SPECS_TOOL = {
  name: "diff_specs",
  description: "Compare the OpenAPI document at this merge against its parent. Returns skip, additive, or breaking plus reasons. Read-only.",
  input_schema: { type: "object", properties: {}, required: [], additionalProperties: false },
};

export function heuristicProvider() {
  return {
    name: "heuristic",
    async classify({ diff, specs }) {
      const tool = classifySpecs(specs.before, specs.after);
      const added = diff.split("\n").filter((l) => l.startsWith("+") && !l.startsWith("+++")).join("\n");
      const touchesHttp = /\b(app|router|server)\.(get|post|put|patch|delete)\(|reply\.header|Sunset|Deprecation/.test(added);
      const opsChange = /retry|backoff|timeout|queue|alert|circuit/i.test(added);
      const cutover = /\/v[2-9]\//.test(added) || /Sunset|Deprecation/.test(added);
      let spec = tool.classification;
      if (spec === "skip" && touchesHttp) spec = cutover ? "breaking" : "additive";
      const runbook = cutover ? "new" : opsChange ? "update" : "skip";
      const files = [...(spec !== "skip" ? ["openapi/openapi.json"] : []), ...(runbook !== "skip" ? ["runbooks/"] : [])];
      return { spec, runbook, files, rationale: `diff_specs=${tool.classification} (${tool.reasons[0]}); runbook=${runbook} from keyword scan.` };
    },
  };
}

export function anthropicProvider({ model = "claude-opus-5-5", client } = {}) {
  return {
    name: `anthropic:${model}`,
    async classify({ diff, specs }) {
      const anthropic = client ?? new (await import("@anthropic-ai/sdk")).default();
      const messages = [{ role: "user", content: `Diff:\n${diff}` }];
      for (let turn = 0; turn < 4; turn++) {
        const response = await anthropic.messages.create({
          model,
          max_tokens: 4096,
          system: CLASSIFIER_PROMPT,
          tools: [DIFF_SPECS_TOOL],
          output_config: { effort: "low", format: { type: "json_schema", schema: ENVELOPE_SCHEMA } },
          messages,
        });
        if (response.stop_reason === "refusal") throw new Error("classifier refused the request");
        if (response.stop_reason !== "tool_use") {
          const text = response.content.find((b) => b.type === "text")?.text ?? "";
          return parseEnvelope(text);
        }
        messages.push({ role: "assistant", content: response.content });
        const results = response.content
          .filter((b) => b.type === "tool_use")
          .map((b) => ({ type: "tool_result", tool_use_id: b.id, content: JSON.stringify(classifySpecs(specs.before, specs.after)) }));
        messages.push({ role: "user", content: results });
      }
      throw new Error("classifier did not finish within 4 turns");
    },
  };
}

export function providerFromName(name) {
  if (name === "heuristic") return heuristicProvider();
  if (name === "anthropic" || name?.startsWith("anthropic:")) return anthropicProvider({ model: name.split(":")[1] });
  throw new Error(`unknown provider '${name}' (use heuristic or anthropic[:model])`);
}
