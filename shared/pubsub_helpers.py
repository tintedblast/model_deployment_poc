"""Publish helper + push-envelope parser, used by every agent."""

import os
import json
import base64
from google.cloud import pubsub_v1

PROJECT_ID = os.environ.get("GCP_PROJECT_ID")
if not PROJECT_ID:
    raise ValueError("Set GCP_PROJECT_ID in your .env file")

publisher = pubsub_v1.PublisherClient()


def publish(topic_name: str, tracking_id: str):
    topic_path = publisher.topic_path(PROJECT_ID, topic_name)
    data = json.dumps({"tracking_id": tracking_id}).encode("utf-8")
    future = publisher.publish(topic_path, data)
    return future.result()


def publish_payload(topic_name: str, payload: dict):
    """For the entry point, where no tracking_id exists yet - publishes
    the full raw payload dict instead."""
    topic_path = publisher.topic_path(PROJECT_ID, topic_name)
    data = json.dumps(payload).encode("utf-8")
    future = publisher.publish(topic_path, data)
    return future.result()


def parse_push_envelope(envelope: dict) -> dict:
    """Decode a Pub/Sub push message envelope, return the raw JSON payload."""
    message_data = envelope["message"]["data"]
    return json.loads(base64.b64decode(message_data).decode("utf-8"))