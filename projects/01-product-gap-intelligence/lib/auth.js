export function isAllowed(identity, allowedDomains) {
  if (!identity?.email || identity.email_verified === false) return false;
  const domain = identity.email.split("@").pop().toLowerCase();
  return allowedDomains.map((d) => d.toLowerCase()).includes(domain);
}

export function oidcConfigFromEnv(env) {
  const required = ["OIDC_AUTHORIZE_URL", "OIDC_TOKEN_URL", "OIDC_USERINFO_URL", "OIDC_CLIENT_ID", "OIDC_CLIENT_SECRET"];
  const missing = required.filter((key) => !env[key]);
  if (missing.length) return { ok: false, missing };
  return {
    ok: true,
    authorizeUrl: env.OIDC_AUTHORIZE_URL,
    tokenUrl: env.OIDC_TOKEN_URL,
    userinfoUrl: env.OIDC_USERINFO_URL,
    clientId: env.OIDC_CLIENT_ID,
    clientSecret: env.OIDC_CLIENT_SECRET,
  };
}

export function authorizeRedirect(config, { redirectUri, state }) {
  const url = new URL(config.authorizeUrl);
  url.searchParams.set("response_type", "code");
  url.searchParams.set("client_id", config.clientId);
  url.searchParams.set("redirect_uri", redirectUri);
  url.searchParams.set("scope", "openid email");
  url.searchParams.set("state", state);
  return url.toString();
}

export async function exchangeCode(config, { code, redirectUri, fetchImpl = fetch }) {
  const tokenResponse = await fetchImpl(config.tokenUrl, {
    method: "POST",
    headers: { "content-type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      grant_type: "authorization_code",
      code,
      redirect_uri: redirectUri,
      client_id: config.clientId,
      client_secret: config.clientSecret,
    }),
  });
  if (!tokenResponse.ok) throw new Error(`token exchange failed: ${tokenResponse.status}`);
  const { access_token: accessToken } = await tokenResponse.json();
  const userinfoResponse = await fetchImpl(config.userinfoUrl, {
    headers: { authorization: `Bearer ${accessToken}` },
  });
  if (!userinfoResponse.ok) throw new Error(`userinfo failed: ${userinfoResponse.status}`);
  return userinfoResponse.json();
}
