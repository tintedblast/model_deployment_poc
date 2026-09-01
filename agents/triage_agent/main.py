# ============================================
# SERVICE: TRIAGE AGENT
# Firestore agent_id: "triage_agent"
# Receives raw payload from topic-1, generates tracking_id, creates the
# Firestore record (claim-check setup), runs deterministic continue/drop
# check, publishes tracking_id to summarizer_agent's topic if continuing.
# ============================================
from dotenv import load_dotenv
load_dotenv()

import uuid
import logging
from fastapi import FastAPI, Request

from shared.pubsub_helpers import publish, parse_push_envelope
from shared.firestore_client import save_agent_data, AGENT_ID_TRIAGE

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()


def should_continue(interactions: list[dict]) -> bool:
    """Dummy deterministic rule - drop if fewer than 2 interactions."""
    return len(interactions) >= 2


@app.post("/")
async def handle_push(request: Request):
    envelope = await request.json()
    payload = parse_push_envelope(envelope)

    tracking_id = str(uuid.uuid4())
    logger.info("Triage agent creating tracking_id=%s", tracking_id)

    decision = should_continue(payload["interactions"])

    await save_agent_data(tracking_id, AGENT_ID_TRIAGE, {
        "customer_id": payload["customer_id"],
        "summary_type": payload["summary_type"],
        "raw_interactions": payload["interactions"],
        "decision": decision,
        "status": "done",
    })

    if decision:
        publish("summariser-agent-topic", tracking_id)

    return {"status": "ok"}