"""
Claim-check pattern, keyed by (tracking_id, agent_id).
Structure: complaints/{tracking_id}/agents/{agent_id}
"""

from google.cloud import firestore

db = firestore.AsyncClient()

# Fixed per agent, not per request
AGENT_ID_TRIAGE = "triage_agent"
AGENT_ID_SUMMARIZER = "summarizer_agent"
AGENT_ID_RECTIFICATION = "rectification_agent"


async def save_agent_data(tracking_id: str, agent_id: str, data: dict):
    doc_ref = (
        db.collection("complaints")
        .document(tracking_id)
        .collection("agents")
        .document(agent_id)
    )
    await doc_ref.set(data, merge=True)


async def get_agent_data(tracking_id: str, agent_id: str) -> dict:
    doc_ref = (
        db.collection("complaints")
        .document(tracking_id)
        .collection("agents")
        .document(agent_id)
    )
    doc = await doc_ref.get()
    return doc.to_dict() or {}