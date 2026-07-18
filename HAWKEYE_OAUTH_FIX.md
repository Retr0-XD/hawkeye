# Hawkeye — OAuth Login Fix (403 / invalid_client)

**Date**: 2026-07-15
**Console**: https://console.cloud.google.com/apis/credentials?project=dice-master-the-platform

---

## Root cause (definitive)

The user console login fails with **"Error 401: invalid_client — The OAuth
client was not found"** at `accounts.google.com`.

The project's ONLY OAuth client is a **GCP IAM OAuthClient**:

```
name:     projects/dice-master-the-platform/locations/global/oauthClients/hawkeye-user-console
clientId: ad955ccc7-1998-4237-bec2-adebd8f8ea27
type:    CONFIDENTIAL_CLIENT  (AUTHORIZATION_CODE_GRANT)
state:   ACTIVE
```

`accounts.google.com/o/oauth2/v2/auth` (and the GIS One Tap flow) only accept
**standard Google OAuth 2.0 Web Client IDs** — the `*.apps.googleusercontent.com`
format tied to an **OAuth consent screen**. A GCP IAM OAuthClient is a
different product (workload identity / service-to-service) and is NOT recognized
by `accounts.google.com`. That is why BOTH the original GIS flow (403) and the
new authorization-code flow (invalid_client) fail.

## What was already fixed in code

- `frontend-user/src/auth.ts` rewritten to use the **OAuth 2.0 Authorization
  Code flow with PKCE** (the correct flow for a standard web client ID). It
  redirects to Google, exchanges `?code=` for an `id_token`, and calls
  `/api/user/me`. The API already verifies any Google `id_token` whose audience
  matches `HAWKEYE_OAUTH_CLIENT_ID`.
- `frontend-user/src/App.tsx` now calls `handleRedirect()` on mount to complete
  the login after Google redirects back.
- `frontend-user` migrated to the same shadcn "Observatory" theme as the demo
  (matching color scheme + graph styling).
- Both services rebuilt and redeployed (demo rev `00008`, user rev `00003`).

## The ONE remaining step (Cloud Console UI — cannot be done via gcloud/script)

A standard Web OAuth Client ID must be created in the Google Cloud Console.
`gcloud iam oauth-clients` creates the WRONG product type, and the
`clientsecret.googleapis.com` REST API is not reachable from this environment.

### Do this (≈2 minutes):

1. Open **APIs & Services → OAuth consent screen**
   (https://console.cloud.google.com/apis/credentials/consent?project=dice-master-the-platform)
   - User type: **External**
   - App name: `Hawkeye`
   - User support / developer email: `sakthiharish705@gmail.com`
   - Save and continue; add scope `.../auth/userinfo.email` + `userinfo.profile`
     + `openid`; leave test users as your email.

2. Open **APIs & Services → Credentials → Create Credentials → OAuth client ID**
   (https://console.cloud.google.com/apis/credentials?project=dice-master-the-platform)
   - Application type: **Web application**
   - Name: `Hawkeye User Console`
   - **Authorized redirect URIs**: add
     `https://hawkeye-frontend-user-78803747777.us-central1.run.app`
   - Create → copy the new **Client ID** (looks like
     `123456789-abc.apps.googleusercontent.com`).

3. Set that new Client ID in TWO places:
   - **frontend-user build**: create `hawkeye/services/frontend-user/.env`
     with `VITE_GOOGLE_CLIENT_ID=<new-id>` (and optionally
     `VITE_REDIRECT_URI=https://hawkeye-frontend-user-78803747777.us-central1.run.app`),
     then rebuild + redeploy frontend-user.
   - **API**: update the env var so the API accepts the token's audience:
     ```
     gcloud run services update hawkeye-api --region=us-central1 \
       --project=dice-master-the-platform \
       --set-env-vars="HAWKEYE_OAUTH_CLIENT_ID=<new-id>"
     ```

After step 3, clicking **Sign in with Google** will complete the OAuth flow
and land on the recommendations console. No further code changes are needed —
the flow is already correct.

## Verification done

- [x] Demo dashboard: interactive data-table (sort/select/paginate/row-actions),
      real KPIs (22 resources, 13 anomalies, 1 public exposure), theme-consistent
      graph. Deployed rev `00008`.
- [x] User console: renders with matching theme; "Sign in with Google" triggers
      Google consent (reaches `accounts.google.com` with the client_id).
- [x] API `/api/user/me` correctly returns 401 without a token (auth gating works).
- [ ] User console full login — BLOCKED on the console step above (needs a
      standard Web OAuth Client ID, which requires a Cloud Console UI action).
