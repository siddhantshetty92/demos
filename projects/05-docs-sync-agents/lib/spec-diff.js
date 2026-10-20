const METHODS = ["get", "put", "post", "delete", "patch", "head", "options"];

function operations(doc) {
  const ops = new Map();
  for (const [path, item] of Object.entries(doc?.paths ?? {})) {
    for (const method of METHODS) if (item[method]) ops.set(`${method.toUpperCase()} ${path}`, item[method]);
  }
  return ops;
}

function versionOf(operationKey) {
  return operationKey.match(/^\w+ \/(v\d+)\//)?.[1] ?? null;
}

function resolve(doc, schema) {
  const ref = schema?.$ref;
  if (!ref) return schema ?? {};
  return ref.replace(/^#\//, "").split("/").reduce((node, key) => node?.[key], doc) ?? {};
}

function requestSchema(doc, op) {
  return resolve(doc, op?.requestBody?.content?.["application/json"]?.schema);
}

function responseSchema(doc, op) {
  const ok = op?.responses?.["200"] ?? op?.responses?.["201"];
  return resolve(doc, ok?.content?.["application/json"]?.schema);
}

function compareObject(label, before, after, { request }) {
  const breaking = [];
  const additive = [];
  const beforeProps = before.properties ?? {};
  const afterProps = after.properties ?? {};
  const beforeRequired = new Set(before.required ?? []);
  const afterRequired = new Set(after.required ?? []);
  for (const [name, prop] of Object.entries(beforeProps)) {
    if (!(name in afterProps)) breaking.push(`${label}: removed field '${name}'`);
    else if ((prop.type ?? null) !== (afterProps[name].type ?? null)) breaking.push(`${label}: '${name}' changed type ${prop.type} → ${afterProps[name].type}`);
  }
  for (const name of Object.keys(afterProps)) {
    if (name in beforeProps) continue;
    if (request && afterRequired.has(name)) breaking.push(`${label}: new required request field '${name}'`);
    else additive.push(`${label}: new optional field '${name}'`);
  }
  if (request) {
    for (const name of afterRequired) {
      if (name in beforeProps && !beforeRequired.has(name)) breaking.push(`${label}: '${name}' became required`);
    }
  }
  return { breaking, additive };
}

export function classifySpecs(before, after) {
  if (!before && !after) return { classification: "skip", reasons: ["no spec at either revision"] };
  if (!before) return { classification: "additive", reasons: ["spec added"] };
  if (!after) return { classification: "breaking", reasons: ["spec removed"] };
  if (JSON.stringify(before) === JSON.stringify(after)) return { classification: "skip", reasons: ["spec unchanged"] };

  const breaking = [];
  const additive = [];
  const beforeOps = operations(before);
  const afterOps = operations(after);
  for (const key of beforeOps.keys()) if (!afterOps.has(key)) breaking.push(`removed operation ${key}`);
  const knownVersions = new Set([...beforeOps.keys()].map(versionOf));
  for (const [key, op] of afterOps) {
    if (!beforeOps.has(key)) {
      const version = versionOf(key);
      if (version && !knownVersions.has(version)) breaking.push(`new API version surface ${key}`);
      else additive.push(`new operation ${key}`);
      continue;
    }
    const previous = beforeOps.get(key);
    for (const side of ["request", "response"]) {
      const pick = side === "request" ? requestSchema : responseSchema;
      const result = compareObject(`${key} ${side}`, pick(before, previous), pick(after, op), { request: side === "request" });
      breaking.push(...result.breaking);
      additive.push(...result.additive);
    }
  }
  if (breaking.length) return { classification: "breaking", reasons: breaking };
  if (additive.length) return { classification: "additive", reasons: additive };
  return { classification: "additive", reasons: ["spec changed without contract-level differences (descriptions, examples)"] };
}
