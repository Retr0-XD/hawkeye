// Google OAuth 2.0 Authorization Code flow (PKCE) for the Hawkeye user console.
//
// The Hawkeye OAuth client (ad955ccc7-...) is a CONFIDENTIAL_CLIENT that only
// allows the AUTHORIZATION_CODE_GRANT with a single registered redirect URI.
// The Google Identity Services "One Tap" id_token flow is NOT compatible with
// that client type and returns a 403. So we use the standard redirect flow,
// which returns an id_token (JWT) that the API already verifies.
//
// Token is stored in localStorage. PKCE is used so the flow is safe from the
// browser without a client secret.

const CLIENT_ID =
  (import.meta.env.VITE_GOOGLE_CLIENT_ID as string | undefined) || "";
// A standard "Web application" OAuth client is treated by Google as a
// confidential client, so the token exchange REQUIRES the client_secret.
// (Google does not offer a secret-less web client type; the secret is bundled
// into the SPA by nature of the flow. It is only used for the code→token
// exchange with Google and is never sent to the Hawkeye API.)
const CLIENT_SECRET =
  (import.meta.env.VITE_GOOGLE_CLIENT_SECRET as string | undefined) || "";
const REDIRECT_URI =
  (import.meta.env.VITE_REDIRECT_URI as string | undefined) ||
  (typeof window !== "undefined" ? window.location.origin : "");
const AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth";
// Basic identity only — NO restricted GCP scope. Each user connects their OWN
// GCP project via a service-account key (bring-your-own-cloud), so the app
// stays fully public without Google verification.
const SCOPES = "openid email profile";

const TOKEN_KEY = "hawkeye_id_token";
const ACCESS_TOKEN_KEY = "hawkeye_access_token";
const VERIFIER_KEY = "hawkeye_pkce_verifier";

function randomString(len: number): string {
  const chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~";
  const out: string[] = [];
  const buf = new Uint8Array(len);
  crypto.getRandomValues(buf);
  for (let i = 0; i < len; i++) out.push(chars[buf[i] % chars.length]);
  return out.join("");
}

function base64UrlEncode(bytes: Uint8Array): string {
  let str = "";
  bytes.forEach((b) => (str += String.fromCharCode(b)));
  return btoa(str).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

async function sha256(s: string): Promise<string> {
  const data = new TextEncoder().encode(s);
  const digest = await crypto.subtle.digest("SHA-256", data);
  return base64UrlEncode(new Uint8Array(digest));
}

export function getStoredToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setStoredToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function getStoredAccessToken(): string | null {
  return localStorage.getItem(ACCESS_TOKEN_KEY);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(VERIFIER_KEY);
}

export async function initGoogle(): Promise<void> {
  if (!CLIENT_ID) throw new Error("VITE_GOOGLE_CLIENT_ID is not configured");
}

// A standard Google OAuth Web Client ID looks like "123-abc.apps.googleusercontent.com".
// A GCP IAM OAuthClient (e.g. "ad955ccc7-...") is a DIFFERENT product and is NOT
// accepted by accounts.google.com — using it causes 403 / invalid_client.
export function clientIdLooksValid(): boolean {
  return /^[\w-]+\.apps\.googleusercontent\.com$/.test(CLIENT_ID);
}

// Begin the authorization-code (PKCE) flow by redirecting to Google.
export async function signIn(): Promise<string> {
  if (!CLIENT_ID) throw new Error("VITE_GOOGLE_CLIENT_ID is not configured");
  if (!clientIdLooksValid()) {
    throw new Error(
      "OAuth client is misconfigured. The dashboard .env must use a STANDARD Web OAuth Client ID " +
        "(*.apps.googleusercontent.com) created in APIs & Services → Credentials, not a GCP IAM OAuthClient."
    );
  }
  const verifier = randomString(64);
  localStorage.setItem(VERIFIER_KEY, verifier);
  const challenge = await sha256(verifier);
  const params = new URLSearchParams({
    client_id: CLIENT_ID,
    redirect_uri: REDIRECT_URI,
    response_type: "code",
    scope: SCOPES,
    code_challenge: challenge,
    code_challenge_method: "S256",
    access_type: "offline",
    prompt: "select_account",
  });
  window.location.href = `${AUTH_ENDPOINT}?${params.toString()}`;
  // Never resolves — the page navigates away.
  return new Promise<string>(() => {});
}

// Exchange the authorization code (from the redirect) for an id_token.
export async function handleRedirect(): Promise<string | null> {
  if (typeof window === "undefined") return null;
  const url = new URL(window.location.href);
  const code = url.searchParams.get("code");
  const err = url.searchParams.get("error");
  const errDesc = url.searchParams.get("error_description");
  // Clean the URL so refresh doesn't re-trigger.
  window.history.replaceState({}, document.title, window.location.pathname);
  if (err) {
    // Google rejected the authorization (e.g. consent screen "Testing" mode
    // without the user added as a test user, or a redirect_uri mismatch).
    // Surface it loudly instead of failing silently.
    throw new Error(
      `Google authorization failed: ${err}${errDesc ? ` — ${errDesc}` : ""}. ` +
        `If this is "access_denied", add this Google account as a Test User on ` +
        `the OAuth consent screen (APIs & Services → OAuth consent screen), or publish the app.`
    );
  }
  if (!code) return null;
  const verifier = localStorage.getItem(VERIFIER_KEY) ?? "";
  const body = new URLSearchParams({
    client_id: CLIENT_ID,
    code,
    code_verifier: verifier,
    grant_type: "authorization_code",
    redirect_uri: REDIRECT_URI,
  });
  // Confidential (Web) client: Google's token endpoint requires the secret.
  if (CLIENT_SECRET) body.set("client_secret", CLIENT_SECRET);
  const res = await fetch("https://oauth2.googleapis.com/token", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: body.toString(),
  });
  if (!res.ok) {
    const txt = await res.text();
    throw new Error(`Token exchange failed: ${res.status} ${txt}`);
  }
  const data = (await res.json()) as { id_token?: string; access_token?: string };
  if (!data.id_token) throw new Error("No id_token in token response");
  setStoredToken(data.id_token);
  // Store the access token so the app can read the user's OWN GCP data.
  if (data.access_token) localStorage.setItem(ACCESS_TOKEN_KEY, data.access_token);
  return data.id_token;
}

export function renderButton(
  element: HTMLElement,
  onSuccess: (token: string) => void
): void {
  element.innerHTML = "";
  const btn = document.createElement("button");
  btn.textContent = "Sign in with Google";
  btn.className =
    "rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90";
  btn.onclick = () => {
    void signIn().then(onSuccess).catch(() => {});
  };
  element.appendChild(btn);
}
