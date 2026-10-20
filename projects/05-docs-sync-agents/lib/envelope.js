export const SPEC_DECISIONS = ["skip", "additive", "breaking"];
export const RUNBOOK_DECISIONS = ["skip", "update", "new"];

export const ENVELOPE_SCHEMA = {
  type: "object",
  properties: {
    spec: { type: "string", enum: SPEC_DECISIONS },
    runbook: { type: "string", enum: RUNBOOK_DECISIONS },
    files: { type: "array", items: { type: "string" } },
    rationale: { type: "string" },
  },
  required: ["spec", "runbook", "files", "rationale"],
  additionalProperties: false,
};

export function firstJsonObject(text) {
  const start = text.indexOf("{");
  if (start < 0) return null;
  let depth = 0;
  let inString = false;
  let escaped = false;
  for (let i = start; i < text.length; i++) {
    const c = text[i];
    if (inString) {
      if (escaped) escaped = false;
      else if (c === "\\") escaped = true;
      else if (c === '"') inString = false;
    } else if (c === '"') inString = true;
    else if (c === "{") depth++;
    else if (c === "}" && --depth === 0) return text.slice(start, i + 1);
  }
  return null;
}

export function parseEnvelope(text) {
  const json = firstJsonObject(text);
  if (!json) throw new Error("classifier returned no JSON object");
  const parsed = JSON.parse(json);
  if (!SPEC_DECISIONS.includes(parsed.spec)) throw new Error(`invalid spec decision '${parsed.spec}'`);
  if (!RUNBOOK_DECISIONS.includes(parsed.runbook)) throw new Error(`invalid runbook decision '${parsed.runbook}'`);
  return {
    spec: parsed.spec,
    runbook: parsed.runbook,
    files: Array.isArray(parsed.files) ? parsed.files.map(String) : [],
    rationale: String(parsed.rationale ?? ""),
  };
}
