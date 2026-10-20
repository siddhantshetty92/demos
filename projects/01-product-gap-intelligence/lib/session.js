import { createHmac, randomBytes, timingSafeEqual } from "node:crypto";

export const SESSION_COOKIE = "gap_session";
export const STATE_COOKIE = "gap_oauth_state";
const DEFAULT_TTL_SECONDS = 8 * 60 * 60;

function b64url(input) {
  return Buffer.from(input).toString("base64url");
}

function sign(payload, secret) {
  return createHmac("sha256", secret).update(payload).digest("base64url");
}

export function createSession(email, secret, { now = Date.now(), ttlSeconds = DEFAULT_TTL_SECONDS } = {}) {
  if (!secret || secret.length < 32) throw new Error("SESSION_SECRET must be at least 32 characters");
  const payload = b64url(JSON.stringify({ email, exp: Math.floor(now / 1000) + ttlSeconds }));
  return `${payload}.${sign(payload, secret)}`;
}

export function verifySession(token, secret, { now = Date.now() } = {}) {
  if (!token || !secret) return null;
  const [payload, signature] = token.split(".");
  if (!payload || !signature) return null;
  const expected = Buffer.from(sign(payload, secret));
  const actual = Buffer.from(signature);
  if (expected.length !== actual.length || !timingSafeEqual(expected, actual)) return null;
  try {
    const data = JSON.parse(Buffer.from(payload, "base64url").toString("utf8"));
    if (typeof data.email !== "string" || typeof data.exp !== "number") return null;
    if (data.exp * 1000 <= now) return null;
    return data;
  } catch {
    return null;
  }
}

export function newState() {
  return randomBytes(24).toString("base64url");
}

export function parseCookies(header) {
  const cookies = {};
  for (const part of String(header ?? "").split(";")) {
    const index = part.indexOf("=");
    if (index < 0) continue;
    cookies[part.slice(0, index).trim()] = decodeURIComponent(part.slice(index + 1).trim());
  }
  return cookies;
}

export function cookie(name, value, { maxAge, secure = true } = {}) {
  const parts = [`${name}=${encodeURIComponent(value)}`, "Path=/", "HttpOnly", "SameSite=Lax"];
  if (secure) parts.push("Secure");
  if (maxAge !== undefined) parts.push(`Max-Age=${maxAge}`);
  return parts.join("; ");
}
