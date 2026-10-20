import { existsSync, readFileSync, readdirSync } from "node:fs";
import path from "node:path";

export const REQUIRED_SECTIONS = ["When to use", "Symptoms", "First 5 minutes", "Mitigation", "Verification", "Rollback", "Escalation", "Changelog"];
export const FRONTMATTER_KEYS = ["service", "title", "owner", "severity", "last_reviewed", "code_paths"];

export function parseFrontmatter(text) {
  if (!text.startsWith("---\n")) return { data: {}, body: text };
  const end = text.indexOf("\n---", 4);
  if (end < 0) return { data: {}, body: text };
  const data = {};
  let listKey = null;
  for (const line of text.slice(4, end).split("\n")) {
    const item = line.match(/^\s+-\s+(.*)$/);
    if (item && listKey) { data[listKey].push(item[1].trim()); continue; }
    const pair = line.match(/^([\w-]+):\s*(.*)$/);
    if (!pair) continue;
    listKey = pair[2] === "" ? pair[1] : null;
    data[pair[1]] = pair[2] === "" ? [] : pair[2].trim();
  }
  return { data, body: text.slice(end + 4) };
}

function runbookFiles(root) {
  const dir = path.join(root, "runbooks");
  return existsSync(dir) ? readdirSync(dir).filter((f) => f.endsWith(".md")).map((f) => path.join(dir, f)) : [];
}

export function runGates({ root, changedFiles, envelope }) {
  const problems = { frontmatter: [], sections: [], codePaths: [], scope: [] };
  for (const file of runbookFiles(root)) {
    const name = path.basename(file);
    const { data, body } = parseFrontmatter(readFileSync(file, "utf8"));
    for (const key of FRONTMATTER_KEYS) if (data[key] === undefined) problems.frontmatter.push(`${name}: missing '${key}'`);
    const headings = new Set([...body.matchAll(/^##\s+(.+)$/gm)].map((m) => m[1].trim()));
    for (const section of REQUIRED_SECTIONS) if (!headings.has(section)) problems.sections.push(`${name}: missing '## ${section}'`);
    for (const codePath of [].concat(data.code_paths ?? [])) {
      if (!existsSync(path.join(root, codePath))) problems.codePaths.push(`${name}: code path '${codePath}' does not exist`);
    }
  }
  const touchedRunbooks = changedFiles.some((f) => f.startsWith("runbooks/"));
  const touchedSpec = changedFiles.some((f) => f.startsWith("openapi/"));
  if (envelope.runbook === "skip" && touchedRunbooks) problems.scope.push("classifier said runbook=skip but the docs PR edits runbooks/");
  if (envelope.spec === "skip" && touchedSpec) problems.scope.push("classifier said spec=skip but the docs PR edits openapi/");
  if (envelope.runbook !== "skip" && !touchedRunbooks) problems.scope.push(`classifier said runbook=${envelope.runbook} but no runbook changed`);
  return Object.entries(problems).map(([gate, list]) => ({ gate, pass: list.length === 0, problems: list }));
}
