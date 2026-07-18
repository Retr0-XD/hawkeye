# Hawkeye — Security Notes (from 2026-07-17 audit)

## Fixed this session
- **CORS**: API `main.py` changed from `allow_origins=["*"]` to an explicit
  allow-list of the two Hawkeye frontends. Deployed (api rev 00015).
- **Public + multi-tenant**: App is now open to ANY verified Google account
  (`HAWKEYE_ALLOWED_EMAILS` cleared on the API, rev 00017). Each logged-in user
  sees THEIR OWN GCP data via their Google access token (Cloud Asset API /
  Resource Manager) — the owner's shared Firestore/BigQuery dataset is no longer
  read by the user console. New backend: `gcp_user.py` + `gcp_user_router.py`
  (`/api/user/gcp/projects|resources|compliance`, require id token + `X-Gcp-Token`).
  Frontend: `auth.ts` requests `cloud-platform.read-only` scope and stores the
  access token; `App.tsx` loads per-user projects/resources/compliance.
- **Approvals UX**: added per-row busy/error state + 401→session-expiry handling
  so the Approve/Reject buttons give feedback instead of appearing dead.
  (frontend-user rev 00017)

## OPEN / KNOWN EXPOSURES (action required by user)
1. **OAuth client secret in the SPA** — `frontend-user/.env` contains
   `VITE_GOOGLE_CLIENT_SECRET=GOCSPX-...` which is bundled into the public JS
   (`auth.ts` sends it to Google's token endpoint). Any visitor can extract it.
   The current OAuth client is a "confidential" Web client that REQUIRES the
   secret, so removing it breaks login. Proper fix: create a **public** OAuth
   client (or use a PKCE-only flow that doesn't need a secret) in Google Cloud
   Console, then drop the secret from the SPA. Until then, the secret is
   effectively public — rotate it if the client is ever compromised.
   NOTE: a client secret in a browser SPA is low-risk for a *confidential* web
   client because Google still validates the redirect URI + issues only an
   id_token (not offline refresh tokens); the main risk is token-exchange abuse
   from unauthorized origins, which the CORS allow-list now contains.

2. **Bring-your-own-cloud (service account) — NO restricted OAuth scope needed.**
   The user console now uses ONLY basic Google sign-in (`openid email profile`),
   which needs no verification and has no user cap. To see their cloud, each user
   pastes THEIR OWN GCP service-account JSON (Viewer role). It is encrypted with
   `HAWKEYE_CREDS_KEY` (Fernet) and stored per-user in Firestore
   (`user_gcp_credentials/{email}`); the plaintext is never returned to the
   client and is only used server-side to read that user's own projects. This
   removes the Google verification / 100-test-user limit entirely and avoids
   logging anyone's email on a consent screen. Each user sees only their cloud.

3. **Firestore security rules not deployed** — `firestore.rules` exists but was
   never deployed (gcloud version lacked the subcommand). Relies on
   service-account-only writes. Deploy via Firebase CLI/console.

2. **Firestore security rules not deployed** — `firestore.rules` exists but was
   never deployed (gcloud version lacked the subcommand). Relies on
   service-account-only writes. Deploy via Firebase CLI/console.

3. **No API rate limiting** — doc-deferred; add before production.

4. **Automation dry_run=True** — safe by default; approvals log intent but do
   NOT mutate GCP. Flip to false only after review + Firestore rules deployed.

## Safe by design
- Services use Application Default Credentials (Cloud Run SA), not user creds.
- `verify_id_token` fails closed (requires configured `oauth_client_id`).
- User endpoints require a valid Google ID token (verified 401 without token).
- Censoring applied in the public demo; user console shows real (authorized) data.
