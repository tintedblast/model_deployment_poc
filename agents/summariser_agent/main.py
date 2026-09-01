# ============================================
# SERVICE: SUMMARISER AGENT
# Firestore agent_id: "summarizer_agent"
# Fetches triage_agent's data via tracking_id, runs the real
# SummarizerAgent / ComplaintSummarizerOrchestrator, saves its own
# result, publishes tracking_id to rectification_agent's topic.
# ============================================
from dotenv import load_dotenv
load_dotenv()

import logging
from fastapi import FastAPI, Request

from shared.pubsub_helpers import publish, parse_push_envelope
from shared.firestore_client import save_agent_data, get_agent_data, AGENT_ID_TRIAGE, AGENT_ID_SUMMARIZER
from shared.firestore_concurrency import build_firestore_semaphore, build_firestore_token_manager
from core.agents.summariser_agent import SummarizerAgent
from core.orchestrator import ComplaintSummarizerOrchestrator, SummarizationFailedError
from core.filter_interactions import filter_interactions
from core.llm_manager.client import GeminiClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

semaphore = build_firestore_semaphore(max_count=10)
token_manager = build_firestore_token_manager(max_tokens=100_000)
gemini_client = GeminiClient(model="gemini-2.5-pro")


def format_text(interactions: list[dict]) -> str:
    return "\n".join(f"[{i['timestamp']}] {i['speaker']}: {i['text']}" for i in interactions)


@app.post("/")
async def handle_push(request: Request):
    envelope = await request.json()
    tracking_id = parse_push_envelope(envelope)["tracking_id"]
    logger.info("Summariser agent received tracking_id=%s", tracking_id)

    triage_data = await get_agent_data(tracking_id, AGENT_ID_TRIAGE)
    interactions = triage_data.get("raw_interactions", [])
    summary_type = triage_data.get("summary_type", "complaint")

    filtered = filter_interactions(interactions, summary_type)

    try:
        if summary_type == "complaint":
            orchestrator = ComplaintSummarizerOrchestrator(
                gemini_client=gemini_client, semaphore=semaphore, token_manager=token_manager,
            )
            result = await orchestrator.run(filtered)
            summary_data = {"summary": result.summary, "overall_score": result.overall_score, "status": "done"}
        else:
            agent = SummarizerAgent(
                gemini_client=gemini_client, semaphore=semaphore, token_manager=token_manager,
                interaction_channel=summary_type,
            )
            summary = await agent.summarize(format_text(filtered))
            summary_data = {"summary": summary, "status": "done"}

        await save_agent_data(tracking_id, AGENT_ID_SUMMARIZER, summary_data)
        publish("rectification-agent-topic", tracking_id)
        return {"status": "ok"}

    except SummarizationFailedError as e:
        logger.error("Summarization failed tracking_id=%s: %s", tracking_id, e)
        return {"status": "error", "detail": str(e)}, 500