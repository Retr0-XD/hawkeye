# Hawkeye Deployment Guide

All services run on Cloud Run (serverless, scale-to-0) in project
`dice-master-the-platform`, region `us-central1`. Images are built with Cloud
Build (no local Docker needed).

## Prerequisites

```powershell
# gcloud SDK is NOT on PATH by default; prepend it each session:
$env:PATH = "C:\Users\Sakthi Harish\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin;$env:PATH"
# The gcloud PowerShell wrapper needs a real python3 (MS Store stub fails):
$env:CLOUDSDK_PYTHON = "C:\Python313\python.exe"
# Authenticate (quota project = dice-master-the-platform):
gcloud auth application-default login
```

## Build + deploy a Python service

```powershell
cd hawkeye/services/<service>
gcloud builds submit --config cloudbuild.yaml --project dice-master-the-platform .
gcloud run deploy hawkeye-<service> `
  --image us-central1-docker.pkg.dev/dice-master-the-platform/hawkeye/<service>:latest `
  --region us-central1 --project dice-master-the-platform --allow-unauthenticated
```

## Build + deploy a frontend (static SPA on Cloud Run)

```powershell
cd hawkeye/services/frontend-demo   # or frontend-user
npm install
npm run build                        # outputs dist/
gcloud builds submit --config cloudbuild.yaml --project dice-master-the-platform .
gcloud run deploy hawkeye-frontend-demo `
  --image us-central1-docker.pkg.dev/dice-master-the-platform/hawkeye/frontend-demo:latest `
  --region us-central1 --project dice-master-the-platform --allow-unauthenticated --port 8080
```

The frontend Dockerfile builds the SPA and serves `dist/` with a tiny Node
static server on `:8080` (no nginx). Set `VITE_API_BASE` / `VITE_GOOGLE_CLIENT_ID`
in a `.env` before `npm run build` to point at the API / OAuth client.

## Schedulers (Cloud Scheduler)

| Job               | Schedule      | Target |
|-------------------|---------------|--------|
| ingestion-tick    | `*/5 * * * *` | POST /ingest/run |
| processing-tick   | `*/5 * * * *` | POST /process/run |
| budget-guard-tick | `* * * * *`   | POST /guard/run |
| automation-tick   | `*/10 * * * *`| POST /automation/run |

## Environment variables

- **api**: `HAWKEYE_OAUTH_CLIENT_ID` (Google OAuth web client id)
- **automation**: `HAWKEYE_DRY_RUN` (default `true` — logs intent, no mutation)
- **ml / processing / ingestion**: GCP project auto-detected; billing/audit
  exports are optional (collectors skip gracefully if not configured).

## Budget guard

`budget-guard` reads Cloud Billing `getBillingInfo` and suspends all services +
schedulers if MTD cost > `$0.10`. Verify with:

```powershell
Invoke-RestMethod https://budget-guard-78803747777.us-central1.run.app/guard/status
```
