import assert from "node:assert/strict";
import { createServer } from "node:http";
import { after, before, test } from "node:test";
import { createApp } from "../lib/app.js";
import { SESSION_COOKIE, STATE_COOKIE, createSession, verifySession } from "../lib/session.js";

const secret = "x".repeat(40);
const issues = [{ id: "G-1", title: "Area → Sub → Feature", labels: ["High impact"], description: "### Acme | $10k" }];
let server;
let base;

const fakeIdp = async (url) => {
  if (String(url).includes("token")) return new Response(JSON.stringify({ access_token: "t" }), { status: 200 });
  return new Response(JSON.stringify({ email: "eve@evil.test", email_verified: true }), { status: 200 });
};

before(async () => {
  const oidc = { ok: true, authorizeUrl: "https://idp.test/auth", tokenUrl: "https://idp.test/token", userinfoUrl: "https://idp.test/userinfo", clientId: "c", clientSecret: "s" };
  server = createServer((req, res) => createApp({
    secret, allowedDomains: ["example.com"], oidc, secureCookies: false, baseUrl: "http://localhost",
    loadIssues: async () => issues, fetchImpl: fakeIdp,
  })(req, res));
  await new Promise((resolve) => server.listen(0, resolve));
  base = `http://localhost:${server.address().port}`;
});

after(() => server.close());

const get = (path, cookie) => fetch(base + path, { redirect: "manual", headers: cookie ? { cookie } : {} });

test("dashboard and data redirect or 401 without a session", async () => {
  assert.equal((await get("/")).status, 302);
  assert.equal((await get("/api/gaps")).status, 401);
});

test("source files are never served by path", async () => {
  for (const path of ["/public/dashboard.html", "/data/sample-issues.json", "/data/preview.js","/lib/session.js", "/server.js"]) {
    assert.equal((await get(path)).status, 404, path);
  }
});

test("a valid session sees the data", async () => {
  const res = await get("/api/gaps", `${SESSION_COOKIE}=${createSession("ann@example.com", secret)}`);
  assert.equal(res.status, 200);
  const body = await res.json();
  assert.equal(body.gaps[0].arrAtRisk, 10_000);
});

test("tampered and expired sessions are rejected", async () => {
  const token = createSession("ann@example.com", secret);
  assert.equal((await get("/api/gaps", `${SESSION_COOKIE}=${token}x`)).status, 401);
  const expired = createSession("ann@example.com", secret, { now: Date.now() - 9 * 3600_000 });
  assert.equal(verifySession(expired, secret), null);
});

test("callback rejects a state mismatch", async () => {
  const res = await get("/auth/callback?code=c&state=wrong", `${STATE_COOKIE}=right`);
  assert.equal(res.status, 400);
});

test("callback denies identities outside the allowed domain", async () => {
  const res = await get("/auth/callback?code=c&state=s1", `${STATE_COOKIE}=s1`);
  assert.equal(res.status, 403);
});

test("demo login is disabled unless demo mode is on", async () => {
  const res = await fetch(`${base}/auth/demo`, { method: "POST", body: "email=ann@example.com", headers: { "content-type": "application/x-www-form-urlencoded" }, redirect: "manual" });
  assert.equal(res.status, 404);
});
