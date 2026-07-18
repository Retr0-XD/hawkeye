# Hawkeye — Cloud Resource Intelligence Platform

Hawkeye is a unified cloud resource intelligence platform (GCP-only MVP). It
ingests your GCP resources, correlates them, surfaces cost/security/performance
recommendations, runs ML anomaly/failure/cost predictions, and lets users approve
automated remediations — all on the GCP free tier (serverless, scale-to-0).

## Architecture

```
Ingestion (Cloud Run) ──Pub/Sub──▶ Processing (Cloud Run)
                                          │
                                          ├─▶ Firestore (resources, recs, alerts, graph, approvals)
                                          ├─▶ BigQuery  (metrics, billing, audit_logs, lifecycle)
                                          │
        API (Cloud Run, REST) ◀──────────┘
          │            │
   Demo Dashboard   User Console (+ Google OAuth)
   (Cloud Run)      (Cloud Run)
          │
        ML Service (Cloud Run) ── predictions
          │
   Automation (Cloud Run) ── executes APPROVED recommendations (dry-run by default)
          │
   Budget Guard (Cloud Run) ── suspends everything if MTD cost > $0.10
```

## Services (all deployed, scale-to-0, free tier)

| Service            | URL                                                                 | Purpose |
|--------------------|---------------------------------------------------------------------|---------|
| ingestion          | https://hawkeye-ingestion-78803747777.us-central1.run.app          | Collect resources/metrics/billing/audit |
| processing         | https://hawkeye-processing-78803747777.us-central1.run.app         | Correlate, recommend, alert, graph |
| api                | https://hawkeye-api-78803747777.us-central1.run.app                | REST query API (CORS-enabled) |
| ml                 | https://hawkeye-ml-78803747777.us-central1.run.app                 | Anomaly / failure / cost ML |
| budget-guard       | https://budget-guard-78803747777.us-central1.run.app               | Free-tier cost safety net |
| automation         | https://hawkeye-automation-78803747777.us-central1.run.app         | Execute approved remediations |
| frontend-demo      | https://hawkeye-frontend-demo-78803747777.us-central1.run.app     | Public demo dashboard |
| frontend-user      | https://hawkeye-frontend-user-78803747777.us-central1.run.app     | User console (Google login + approvals) |

## Local development

Each service under `hawkeye/services/<name>` is independent:

```powershell
cd hawkeye/services/api
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8080
```

Frontends (React + Vite):

```powershell
cd hawkeye/services/frontend-demo
npm install
npm run dev
```

## Deployment

Images are built remotely with Cloud Build (Docker is not required locally):

```powershell
$env:PATH = "C:\Users\Sakthi Harish\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin;$env:PATH"
$env:CLOUDSDK_PYTHON = "C:\Python313\python.exe"
cd hawkeye/services/api
gcloud builds submit --config cloudbuild.yaml --project dice-master-the-platform .
gcloud run deploy hawkeye-api --image us-central1-docker.pkg.dev/dice-master-the-platform/hawkeye/api:latest --region us-central1 --allow-unauthenticated
```

## Free-tier safety net

`budget-guard` checks month-to-date cost every minute. If it exceeds **$0.10**,
it suspends all 13 Cloud Run services and the 4 scheduler jobs, and resumes them
at the start of the next month. Current MTD cost: **$0.00**.

## Optional / deferred items

See [`HAWKEYE_OPTIONAL_ITEMS.md`](./HAWKEYE_OPTIONAL_ITEMS.md) for the full list
of intentionally deferred items per stage (billing/audit exports, GraphQL,
Vercel deploy, real ML training signal, mutating automation actions, etc.).
