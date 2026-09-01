# ============================================
# SERVICE: RECTIFICATION AGENT
# Firestore agent_id: "rectification_agent"
# Dummy for now - final stage, just marks the pipeline complete.
# ============================================
from dotenv import load_dotenv
load_dotenv()

import logging
from fastapi import FastAPI, Request

from shared.pubsub_helpers import parse_push_envelope
from shared.firestore_client import save_agent_data, AGENT_ID_RECTIFICATION

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()


@app.post("/")
async def handle_push(request: Request):
    envelope = await request.json()
    tracking_id = parse_push_envelope(envelope)["tracking_id"]
    logger.info("Rectification agent received tracking_id=%s", tracking_id)

    await save_agent_data(tracking_id, AGENT_ID_RECTIFICATION, {"status": "done"})

    return {"status": "ok"}