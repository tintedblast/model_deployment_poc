terraform {
  backend "gcs" {
    bucket = "gen-lang-client-0002160432-tfstate"
    prefix = "pubsub-pipeline"
  }
}

provider "google" {
  project = "gen-lang-client-0002160432"
  region  = "us-central1"
}

locals {
  project_id = "gen-lang-client-0002160432"
  region     = "us-central1"
}

# Reference EXISTING Cloud Run services (deployed by GitHub Actions'
# deploy.yml) - Terraform does NOT create/manage these, just reads
# their URIs so subscriptions can point at them.
data "google_cloud_run_v2_service" "triage_agent" {
  name     = "triage-agent"
  location = local.region
}

data "google_cloud_run_v2_service" "summariser_agent" {
  name     = "summariser-agent"
  location = local.region
}

data "google_cloud_run_v2_service" "rectification_agent" {
  name     = "rectification-agent"
  location = local.region
}

resource "google_pubsub_topic" "topic_1" {
  name = "topic-1"
}

resource "google_pubsub_topic" "summariser_agent_topic" {
  name = "summariser-agent-topic"
}

resource "google_pubsub_topic" "rectification_agent_topic" {
  name = "rectification-agent-topic"
}

resource "google_pubsub_topic" "dlq" {
  name = "pipeline-dlq-topic"
}

resource "google_service_account" "pubsub_invoker" {
  account_id   = "pubsub-invoker"
  display_name = "Identity Pub/Sub uses to invoke private Cloud Run services"
}

resource "google_cloud_run_v2_service_iam_member" "triage_invoker" {
  name     = data.google_cloud_run_v2_service.triage_agent.name
  location = local.region
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.pubsub_invoker.email}"
}

resource "google_cloud_run_v2_service_iam_member" "summariser_invoker" {
  name     = data.google_cloud_run_v2_service.summariser_agent.name
  location = local.region
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.pubsub_invoker.email}"
}

resource "google_cloud_run_v2_service_iam_member" "rectification_invoker" {
  name     = data.google_cloud_run_v2_service.rectification_agent.name
  location = local.region
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.pubsub_invoker.email}"
}

resource "google_pubsub_subscription" "triage_sub" {
  name  = "triage-sub"
  topic = google_pubsub_topic.topic_1.name

  push_config {
    push_endpoint = data.google_cloud_run_v2_service.triage_agent.uri
    oidc_token {
      service_account_email = google_service_account.pubsub_invoker.email
    }
  }

  ack_deadline_seconds = 60
  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }
  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.dlq.id
    max_delivery_attempts = 5
  }
}

resource "google_pubsub_subscription" "summariser_sub" {
  name  = "summariser-sub"
  topic = google_pubsub_topic.summariser_agent_topic.name

  push_config {
    push_endpoint = data.google_cloud_run_v2_service.summariser_agent.uri
    oidc_token {
      service_account_email = google_service_account.pubsub_invoker.email
    }
  }

  ack_deadline_seconds = 600
  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }
  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.dlq.id
    max_delivery_attempts = 3
  }
}

resource "google_pubsub_subscription" "rectification_sub" {
  name  = "rectification-sub"
  topic = google_pubsub_topic.rectification_agent_topic.name

  push_config {
    push_endpoint = data.google_cloud_run_v2_service.rectification_agent.uri
    oidc_token {
      service_account_email = google_service_account.pubsub_invoker.email
    }
  }

  ack_deadline_seconds = 60
}
