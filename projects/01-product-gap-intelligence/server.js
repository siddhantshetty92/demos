import { readFile } from "node:fs/promises";
import { createServer } from "node:http";
import { randomBytes } from "node:crypto";
import { oidcConfigFromEnv } from "./lib/auth.js";
import { createApp } from "./lib/app.js";

const port = Number(process.env.PORT ?? 8787);
const demoAuth = process.argv.includes("--demo") || process.env.DEMO_AUTH === "1";
const secret = process.env.SESSION_SECRET ?? (demoAuth ? randomBytes(32).toString("hex") : undefined);
if (!secret) {
  console.error("Set SESSION_SECRET (32+ chars), or run with --demo.");
  process.exit(1);
}

const issuesFile = process.env.ISSUES_FILE ?? new URL("./data/sample-issues.json", import.meta.url);

const handle = createApp({
  secret,
  allowedDomains: (process.env.ALLOWED_DOMAINS ?? "example.com").split(",").map((d) => d.trim()),
  oidc: oidcConfigFromEnv(process.env),
  demoAuth,
  secureCookies: !demoAuth,
  baseUrl: process.env.BASE_URL ?? `http://localhost:${port}`,
  loadIssues: async () => JSON.parse(await readFile(issuesFile, "utf8")),
});

createServer((req, res) => handle(req, res).catch((err) => {
  console.error(err);
  res.writeHead(500).end("Internal error");
})).listen(port, () => {
  console.log(`Product gap dashboard on http://localhost:${port}${demoAuth ? "  (demo sign-in; use any @example.com address)" : ""}`);
});
