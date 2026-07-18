# Hawkeye — Per-Stage Optional / Deferred Items

> Tracking file for optional items that were intentionally deferred (not bugs, not stubs).
> Each item notes: stage, what it is, why deferred, and how to complete it later.
> Status legend: ⬜ not started · 🟡 partial · ✅ done

---

## Stage 1-2: Ingestion (DONE, deployed)
- ⬜ **Billing BigQuery export** — `HAWKEYE_BILLING_BQ_*` not configured by user.
  Collector skips gracefully. To complete: enable Cloud Billing Export → BigQuery
  (dataset `hawkeye`, table `billing`), set env vars on ingestion + processing.
- ⬜ **Audit Logs BigQuery export** — `HAWKEYE_AUDIT_BQ_*` not configured by user.
  Collector skips gracefully. To complete: export Cloud Audit Logs → BigQuery,
  set env vars. Enables audit_logs collection + security insights.
- ⬜ **Terraform IaC** — doc specifies `terraform/` for all infra. We deployed via
  `gcloud` directly (Terraform not installed). To complete: author `terraform/`
  with cloud_run.tf, firestore.tf, pubsub.tf, iam.tf, bigquery.tf.
- ⬜ **CI/CD GitHub Actions** — `.github/workflows/deploy.yaml` not created.
  Deploys are manual `gcloud builds submit` + `gcloud run deploy`. To complete:
  add workflow that builds + deploys each service on push to main.
- ⬜ **Multi-project ingestion** — currently single project `dice-master-the-platform`.
  Doc supports listing all projects user owns. To complete: read project list from
  Firestore / Resource Manager, loop ingest across projects.

## Stage 2: Storage & Schema (DONE)
- 🟡 **Firestore composite indexes** — `firestore.indexes.json` written but NOT
  deployed (gcloud/ADC quirk: `gcloud firestore indexes composite create` returns
  "Invalid value"; Admin API returns 403). Indexes auto-create on first query that
  needs them, or deploy via Firebase console. Not a blocker.
- ⬜ **Firestore security rules deploy** — `firestore.rules` written but not deployed
  (gcloud `firestore rules deploy` subcommand unavailable in this gcloud version).
  Deploy via Firebase CLI/console. Currently relies on default rules + service-only writes.
- ⬜ **Redis cache** — doc lists Redis for real-time. Avoided (costs $36/mo, exceeds
  free tier). Using in-memory Cloud Run caching instead. Acceptable for MVP.

## Stage 3: Processing (DONE, deployed)
- 🟡 **Deletion detection** — per-batch only flags `new` (in batch, not in Firestore).
  True deletions need full-snapshot reconciliation (ingestion publishes full set each
  cycle). Not done per partial batch (would false-flag deletions). To complete:
  reconcile against full snapshot, emit `deleted` alerts.
- ⬜ **Blast-radius / dependency graph enrichment** — graph built from resource
  relationships but not yet computing blast radius or cycle detection in storage.
  `build_graph` exists; enrichment is optional polish.
- ⬜ **Anomaly alerts from metrics** — doc wants metric-anomaly alerts (CPU spike etc).
  Currently only lifecycle-change alerts. To complete: add metric-threshold/anomaly
  alert generation in orchestrator.

## Stage 4: ML Service (DONE, deployed — https://hawkeye-ml-78803747777.us-central1.run.app)
- ✅ Anomaly detection (Isolation Forest, contamination=auto) — `/ml/predict/{id}` + `/ml/predict/all`
- ✅ Failure prediction (Gradient Boosting, self-supervised label heuristic)
- ✅ Cost forecasting (ARIMA(1,1,1)) — returns None when <7 days history / no billing
- ✅ Model serving endpoint + 1h in-memory cache + startup warmup (auto-train on cold start)
- ✅ Model monitoring (`/ml/monitoring`) + manual `/ml/retrain`
- ✅ **Explainable ML (added)** — `ml/app/explain.py` blends model score with structural
  risk signals (public DB/storage, unencrypted, no backups, no audit logging, orphaned)
  and returns `risk_score`, `risk_level`, ranked `drivers`, and a human `reason` per
  resource. Training guard skips the anomaly model when telemetry is all-zero (avoids the
  degenerate "everything is anomalous at 0.8667" output). Every prediction now carries an
  `explanation` and `/ml/predict/all` ranks by blended risk + returns `high_risk`.
- ✅ **Smart Insights endpoint (added)** — `api/app/queries.py::smart_insights` aggregates
  recommendations + ML risk ranking + compliance + graph blast-radius into a prioritized,
  explainable payload served at `GET /api/insights`.
- ⬜ **Real training signal** — idle serverless services report ~0% CPU/metrics, so all
  feature vectors are ~0 → anomaly model is intentionally NOT trained (guard skips it) and
  returns neutral. Not a code bug; data-reality issue. Resolves once services have real
  traffic/billing (then the model trains and explains real anomalies).
- ⬜ **Failure predictor needs labels** — current label is a heuristic (high error + high
  variance + aged). Needs real incident labels to be meaningful. Until then it trains but
  is low-signal.

## Stage 5-6: API / Frontend / UI (DONE, deployed)
- ✅ REST API (resources, recommendations, alerts, graph, metrics, cost-trend, dashboard,
  cost-breakdown, compliance, predictions, insights)
- ✅ shadcn/ui dashboard (zinc/neutral + blue primary, no green), 7 tabs + new Smart Insights
- ✅ **Smart Insights tab (added)** — prioritized insight cards with "why" drivers + risk
  ranking; consumes `/api/insights`.
- ✅ **Resource drill-down modal (added)** — click any resource row (or insight) to open a
  detail modal with cost/metrics/risk explanation; fetches `/api/resources/{id}`.
- ✅ **Data censoring for public demo (added)** — `frontend-demo/src/lib/censor.ts` masks
  resource IDs, names, and emails (deterministic hash) so the unauthenticated demo shows
  original structure but censored identifiers. Applied in ResourceTable, RecommendationsPanel,
  AlertsPanel, SmartInsights, ResourceDetail.
- ✅ **Expanded recommendation engine (added)** — processing `insights.py` now emits
  SECURITY (public DB/storage), RELIABILITY (no backups), GOVERNANCE (audit logging,
  ownership tagging), PERFORMANCE (error-rate), and COST recommendations.
- ✅ **Firestore recommendation-id bug fix** — recommendation ids embed `/` (resource id),
  which is an invalid Firestore document key. `storage.write_firestore` now sanitizes rec
  ids via `_safe_id` (same as resources). Previously caused a 400 and 0 stored recommendations.
- 🟡 **Graph interactivity** — DependencyGraph renders statically (pan/zoom/click pending).
- 🟡 **Cost visualization** — CostTrend/CostDashboard show "no billing data" until Billing
  Export is enabled; donut + breakdown work on structural data.
- ⬜ **Cost forecasting needs billing export** — blocked on Stage 1-2 Billing BQ export.
  Returns null until billing data flows.
- ⬜ **Model persistence across restarts** — models saved to ephemeral Cloud Run disk
  (lost on scale-to-0). Mitigated by startup warmup (auto-train if missing). For durable
  persistence, store joblib in GCS bucket instead of local `models/`.
- ⬜ **Recommendation engine (ML-based)** — beyond current rules-based insights in processing.
  To complete: train a model that suggests optimizations from feature vectors + insights.
- ⬜ **Automated scheduled retraining** — `/ml/retrain` is manual. Add Cloud Scheduler job
  (e.g. daily) to call `/ml/retrain` so models refresh as data grows.
- ⬜ **/ml/predict/all latency** — iterates 18 resources sequentially (~1s each warm, cold
  BigQuery pull). On cold instance can exceed 120s. Mitigated by feature-matrix cache (300s).
  For scale, parallelize predictions or precompute in a batch job.

## Stage 5: API (DONE as REST, deviation from doc)
- 🟡 **GraphQL vs REST** — doc specifies GraphQL (Apollo Server). We built REST
  (FastAPI) mirroring the doc's query shapes. REST is simpler for MVP + immediate
  frontend use. To complete GraphQL: add Apollo Server, schema, resolvers, subscriptions.
- ⬜ **Authentication / Authorization** — doc wants OAuth JWT validation + row-level
  access control. Current API is open (demo mode). To complete: add auth middleware,
  JWT validation, per-user project filtering.
- ⬜ **Rate limiting** — doc wants 1000 req/user/hour. Not implemented. To complete:
  add rate-limit middleware (e.g., via API Gateway or in-app).
- ⬜ **Real-time subscriptions (WebSocket)** — doc wants GraphQL subscriptions for
  live updates. Not implemented (REST only). To complete with GraphQL layer.
- ⬜ **Caching (Redis 1h TTL)** — using in-memory only. Optional.

## Stage 4: ML Service (BUILT & DEPLOYED 2026-07-14)
- 🟡 **Real training signal** — demo project's Cloud Run services are idle
  (scale-to-0, no traffic) so `cpu_percent` etc. are 0.0 in BigQuery. The
  Isolation Forest therefore sees near-zero-variance features and cannot
  separate resources. Code degrades gracefully (returns neutral score 0.0,
  not flagged). To get real value: drive load / wire billing export so
  features have variance. Models retrain weekly (or via /ml/retrain).
- 🟡 **Age-driven anomalies (observed)** — with idle metrics, the only feature
  with variance is `age_days`. The Isolation Forest flags the 5 newest Hawkeye
  platform services (age=1.0) as anomalies (score ~0.99) vs the 13 older DICE
  services (age=0.0). Legitimate separation, not a bug, but "anomaly" currently
  ≈ "recently created". Resolves once cpu/network/cost features have variance.
- 🟡 **Failure predictor** — needs labeled incidents OR cost data to build a
  supervised label. Currently cannot train (billing=0, no incident history).
  Falls back to rules-based recommendations in Processing. To complete:
  accumulate cost history + incident labels, then Gradient Boosting trains.
- 🟡 **Cost forecasting (ARIMA)** — implemented but returns None until billing
  export is configured (needs ≥7 days of daily cost rows). Wire Billing
  BigQuery export (Stage 1-2 item) to activate.
- 🟡 **Model persistence across restarts** — models saved to local joblib on
  the Cloud Run ephemeral disk; lost on cold start. Retrain on first use or
  via /ml/retrain (or store in GCS later). Acceptable for MVP.
- 🟡 **`/ml/predict/all` latency** — iterates all resources sequentially with
  a cold BigQuery feature pull; can exceed 120s on a cold instance. Single
  `/ml/predict/{id}` is fast (~3.6s warm). Optimize later: batch feature
  fetch once, parallelize, or precompute in Processing.
- ⬜ **API /api/predictions** — added; calls ML /ml/predict/all. Degrades to
  empty if ML service unreachable. Consider caching results in Firestore.

## Stage 6: Frontend — Demo Dashboard (DONE, deployed)
- ✅ React + Vite + TS + Tailwind SPA (services/frontend-demo)
- ✅ Tabs: Overview (KPIs, cost trend, recs, alerts), Resources, ML, Graph
- ✅ Reads existing REST API (CORS added to API service for cross-origin)
- ✅ Deployed to Cloud Run (hawkeye-frontend-demo) — free tier, scale-to-0
- ✅ URL: https://hawkeye-frontend-demo-78803747777.us-central1.run.app
- ⬜ **Deploy to Vercel** — doc specifies Vercel. We deployed to Cloud Run instead
  (no external account needed; stays in GCP free tier). To use Vercel: connect repo,
  set VITE_API_BASE to the API URL, `npm run build`, static deploy of `dist/`.
- ⬜ **Cost pie / metrics charts** — KPIs + inline SVG cost-trend line chart only.
  No pie chart or per-resource metric time-series charts yet. To complete: add a
  donut for byType and a metrics sparkline per resource (from /api/metrics).
- ⬜ **Real-time WebSocket updates** — doc wants live push. Current dashboard polls
  every 60s. Acceptable for demo; WebSocket needs API/GraphQL subscription layer.
- ⬜ **Resource detail drill-down** — clicking a resource doesn't open a detail view
  yet. /api/resources/{id} exists; wire a modal/route to show costs+metrics+deps.
- ⬜ **Graph interactivity** — dependency graph is read-only SVG (no zoom/pan/click).
  For richer UX, use a lib (e.g. react-flow) or add pan/zoom.

## Stage 7: Frontend — User Dashboard + Auth (DONE, deployed)
- ✅ Google OAuth (Google Identity Services) — ID-token verification in API auth.py
- ✅ API endpoints /api/user/me, /api/user/recommendations, approve/reject (protected)
- ✅ User console SPA (services/frontend-user) with Google sign-in + approval UI
- ✅ Deployed: https://hawkeye-frontend-user-78803747777.us-central1.run.app
- ✅ OAuth client created (confidential-client, client id ad955ccc7-...-adebd8f8ea27)
- ⬜ **Admin panel** — teams, budgets, members, audit log UI not built. To complete:
  add /api/admin/* endpoints + admin SPA (or tab in user console).
- ⬜ **User-specific data scoping** — current approvals are global (any user can
  approve any rec). For multi-tenant, scope recs/approvals by user's projects/teams.
- ⬜ **Refresh token / session expiry** — ID token cached in localStorage; on 401 the
  UI clears it and prompts re-login. No silent refresh. Acceptable for MVP.
- ⬜ **OAuth consent screen** — if the Google Cloud OAuth consent screen is not yet
  "published", only test users can sign in. Publish/verify in Cloud Console if needed.

## Stage 8: Automation Service (DONE, deployed)
- ✅ Automation executor (services/automation) consumes APPROVED recommendations
- ✅ /automation/run processes approvals; /automation/log shows audit trail
- ✅ Deployed: https://hawkeye-automation-78803747777.us-central1.run.app
- ✅ dry_run=True by default (logs intent, executes nothing) — safe for MVP
- ✅ Verified: seeded test approval -> dry_run logged correctly
- ⬜ **Real mutating actions** — handlers currently evaluate + log but do not
  mutate GCP resources (conservative). To complete: call Run Admin API to
  downsize/set min-instances, enable encryption, etc. Flip dry_run=false after review.
- ⬜ **Pub/Sub trigger** — automation is invoked via /automation/run (or scheduler).
  Doc wants a Pub/Sub consumer on approval events. To complete: subscribe to a
  topic and trigger run_automation() on new approvals.
- ⬜ **Scheduler job** — add a Cloud Scheduler job (e.g. hourly) to call
  /automation/run so approvals are acted on automatically.
- ⬜ **Delete-unused / destructive actions** — not implemented (high risk). Gated
  behind explicit approval + dry_run; add with safety backups before enabling.

## Stage 9: Polish / Testing / Docs (DONE — core; advanced items deferred)
- ✅ README.md (architecture, service table, local dev, deploy, free-tier net)
- ✅ DEPLOYMENT.md (exact gcloud commands, schedulers, env vars, budget guard)
- ✅ Unit tests: ingestion 6, processing 6, api 3, budget-guard 3, ml 6, automation 4 (28 total)
- ✅ All 8 services deployed + livez verified; pipeline coherent (18 resources,
  13 scored by ML, 5 age-driven anomalies, 0 MTD cost)
- ✅ automation-tick scheduler added (every 10 min) to act on approvals
- ⬜ **Integration / E2E tests** — no cross-service automated tests yet. Manual
  verification done per stage. To complete: pytest hitting live endpoints in a
  staging project, or contract tests per service boundary.
- ⬜ **Load testing** — not performed (free-tier quotas: 2M invocations/mo).
  To complete: a small loader (e.g. locust) against /api/dashboard + /ml/predict/all.
- ⬜ **Security tests** — auth bypass / injection not auto-tested. Manual review:
  API CORS=*, user endpoints require Google ID token (verified 401 without token).
  Tighten CORS to known origins + add rate limiting before production.
- ⬜ **API.md / SECURITY.md / CONTRIBUTING.md** — README + DEPLOYMENT cover the
  essentials; formal per-endpoint API docs + security model doc deferred.
- ⬜ **Demo data scripts** — no seed script for fake resources/metrics. Optional.
- ⬜ **Perf pass** — indexes not deployed (Stage 2), /ml/predict/all slow cold.
  Acceptable for MVP scale (18 resources). Optimize if resource count grows.

---

## Quick "complete later" checklist (highest value first)
1. Wire Billing + Audit BigQuery exports (unlocks cost/security insights) — Stage 1-2
2. Build Frontend Demo Dashboard (makes the platform visible/shareable) — Stage 6
3. Build ML Service (anomaly/failure/cost predictions) — Stage 4
4. Deploy Firestore rules + indexes (security + query perf) — Stage 2
5. Add API auth + rate limiting (production readiness) — Stage 5
6. Build Automation Service (one-click remediation) — Stage 8
7. Terraform IaC + CI/CD — Stage 1-2 / 9
8. User Dashboard + OAuth — Stage 7
9. GraphQL layer + WebSocket subscriptions — Stage 5
10. Full test suite + docs — Stage 9
