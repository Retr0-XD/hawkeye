# Hawkeye - Ingestion Service infrastructure (free tier).
# Creates the 4 Pub/Sub topics and the Cloud Run service.
# Requires: gcloud auth application-default login (for Terraform)
#           and billing enabled on the project.

terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

variable "project_id" {
  type    = string
  default = "dice-master-the-platform"
}

variable "region" {
  type    = string
  default = "us-central1"
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# --- Pub/Sub topics (Layer 1 publish targets) -------------------------------
resource "google_pubsub_topic" "resources" {
  name = "hawkeye-resources"
}
resource "google_pubsub_topic" "metrics" {
  name = "hawkeye-metrics"
}
resource "google_pubsub_topic" "billing" {
  name = "hawkeye-billing"
}
resource "google_pubsub_topic" "audit" {
  name = "hawkeye-audit"
}

# --- Artifact Registry for the container image ------------------------------
resource "google_artifact_registry_repository" "hawkeye" {
  location      = var.region
  repository_id = "hawkeye"
  description   = "Hawkeye container images"
  format        = "DOCKER"
}

# --- Cloud Run service (Ingestion) ------------------------------------------
resource "google_cloud_run_v2_service" "ingestion" {
  name     = "hawkeye-ingestion"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    scaling {
      min_instance_count = 0
      max_instance_count = 1
    }
    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/hawkeye/ingestion:latest"
      ports {
        container_port = 8080
      }
      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }
      env {
        name  = "HAWKEYE_GCP_PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "HAWKEYE_INGEST_INTERVAL_SECONDS"
        value = "300"
      }
    }
  }
}

# Allow unauthenticated health/read access (demo dashboard reads via API later).
resource "google_cloud_run_v2_service_iam_member" "ingestion_public" {
  name     = google_cloud_run_v2_service.ingestion.name
  location = google_cloud_run_v2_service.ingestion.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}

output "ingestion_url" {
  value = google_cloud_run_v2_service.ingestion.uri
}
