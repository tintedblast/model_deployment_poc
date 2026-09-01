# ============================================
# SERVICE: ENTRY POINT
# Accepts the initial request, publishes raw payload to "topic-1".
# No Firestore write here - triage_agent creates the tracking_id + record.
# ============================================
from dotenv import load_dotenv
load_dotenv()

import logging
from fastapi import FastAPI
from pydantic import BaseModel

from shared.pubsub_helpers import publish_payload

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()


class ComplaintRequest(BaseModel):
    customer_id: str
    summary_type: str  # "call" | "email" | "message" | "complaint"
    interactions: list[dict]


@app.post("/submit")
async def submit(payload: ComplaintRequest):
    logger.info("Publishing raw request for customer_id=%s", payload.customer_id)
    message_id = publish_payload("topic-1", payload.model_dump())
    return {"message_id": message_id, "status": "published"}