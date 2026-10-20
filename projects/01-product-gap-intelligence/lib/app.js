import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { summarize } from "./aggregate.js";
import { authorizeRedirect, exchangeCode, isAllowed } from "./auth.js";
import { parseIssue } from "./parse.js";
import { SESSION_COOKIE, STATE_COOKIE, cookie, createSession, newState, parseCookies, verifySession } from "./session.js";

const DASHBOARD_PATH = fileURLToPath(new URL("../public/dashboard.html", import.meta.url));

function send(res, status, body, headers = {}) {
  res.writeHead(status, { "cache-control": "no-store", "x-robots-tag": "noindex", ...headers });
  res.end(body);
}

function page(title, body) {
  return `<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${title}</title>
<style>body{font:15px system-ui,sans-serif;max-width:420px;margin:15vh auto;padding:0 16px;color:#1a1a18;background:#f8f7f4}
@media (prefers-color-scheme:dark){body{color:#eee;background:#141413}}a,button{font:inherit}input{font:inherit;padding:8px;width:100%;box-sizing:border-box;margin:8px 0}</style>
${body}`;
}

function escapeHtml(text) {
  return String(text).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}

async function readBody(req) {
  const chunks = [];
  for await (const chunk of req) chunks.push(chunk);
  return new URLSearchParams(Buffer.concat(chunks).toString("utf8"));
}

export function createApp({ secret, allowedDomains, oidc, demoAuth = false, secureCookies = true, loadIssues, baseUrl, fetchImpl = fetch }) {
  const redirectUri = `${baseUrl}/auth/callback`;

  function currentUser(req) {
    return verifySession(parseCookies(req.headers.cookie)[SESSION_COOKIE], secret);
  }

  function startSession(res, email) {
    send(res, 302, "", {
      location: "/",
      "set-cookie": cookie(SESSION_COOKIE, createSession(email, secret), { secure: secureCookies }),
    });
  }

  const routes = {
    "GET /auth/login": async (req, res) => {
      if (demoAuth) {
        return send(res, 200, page("Sign in", `<h1>Sign in (demo mode)</h1>
<p>Demo mode skips the identity provider but still enforces the domain allowlist: <b>${escapeHtml(allowedDomains.join(", "))}</b>.</p>
<form method="post" action="/auth/demo"><input name="email" type="email" placeholder="you@example.com" required><button>Continue</button></form>`), { "content-type": "text/html; charset=utf-8" });
      }
      if (!oidc?.ok) return send(res, 500, page("Not configured", "<h1>Sign-in is not configured</h1>"), { "content-type": "text/html; charset=utf-8" });
      const state = newState();
      send(res, 302, "", {
        location: authorizeRedirect(oidc, { redirectUri, state }),
        "set-cookie": cookie(STATE_COOKIE, state, { maxAge: 600, secure: secureCookies }),
      });
    },
    "POST /auth/demo": async (req, res) => {
      if (!demoAuth) return send(res, 404, "Not found");
      const email = (await readBody(req)).get("email") ?? "";
      if (!isAllowed({ email, email_verified: true }, allowedDomains)) {
        return send(res, 403, page("Denied", `<h1>Access denied</h1><p>${escapeHtml(email)} is not on an allowed domain.</p>`), { "content-type": "text/html; charset=utf-8" });
      }
      startSession(res, email);
    },
    "GET /auth/callback": async (req, res, url) => {
      const expectedState = parseCookies(req.headers.cookie)[STATE_COOKIE];
      if (!expectedState || url.searchParams.get("state") !== expectedState) return send(res, 400, page("Error", "<h1>Sign-in expired. Try again.</h1>"), { "content-type": "text/html; charset=utf-8" });
      try {
        const identity = await exchangeCode(oidc, { code: url.searchParams.get("code"), redirectUri, fetchImpl });
        if (!isAllowed(identity, allowedDomains)) return send(res, 403, page("Denied", "<h1>Access denied</h1>"), { "content-type": "text/html; charset=utf-8" });
        startSession(res, identity.email);
      } catch {
        send(res, 502, page("Error", "<h1>Sign-in failed</h1>"), { "content-type": "text/html; charset=utf-8" });
      }
    },
    "GET /auth/logout": async (req, res) => {
      send(res, 302, "", { location: "/auth/login", "set-cookie": cookie(SESSION_COOKIE, "", { maxAge: 0, secure: secureCookies }) });
    },
    "GET /": async (req, res, url, user) => {
      if (!user) return send(res, 302, "", { location: "/auth/login" });
      send(res, 200, await readFile(DASHBOARD_PATH), { "content-type": "text/html; charset=utf-8" });
    },
    "GET /api/gaps": async (req, res, url, user) => {
      if (!user) return send(res, 401, JSON.stringify({ error: "unauthenticated" }), { "content-type": "application/json" });
      const gaps = (await loadIssues()).map(parseIssue);
      send(res, 200, JSON.stringify({ viewer: user.email, generatedAt: new Date().toISOString(), gaps, summary: summarize(gaps) }), { "content-type": "application/json" });
    },
  };

  return async function handle(req, res) {
    const url = new URL(req.url, baseUrl);
    const route = routes[`${req.method} ${url.pathname}`];
    if (!route) return send(res, 404, "Not found");
    await route(req, res, url, currentUser(req));
  };
}
