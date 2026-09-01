"""
Corrected orchestration:
    1. Summarize the FULL interaction history in ONE pass (prompt instructs
       each bullet to be tagged with its date) - full context, coherent output.
    2. Parse the bullet-point output, GROUP BY DATE -> this is the chunking,
       applied to the OUTPUT, not the input.
    3. For each date-chunk of bullets, judge it against that SAME date's
       source interactions, concurrently (asyncio.gather) - localized,
       parallel faithfulness checks instead of one big judge call.
    4. If any date-chunk scores below threshold -> quality retry: regenerate
       the FULL summary again (not just that chunk), keep best overall attempt.
"""

import re
import asyncio
import logging
from dataclasses import dataclass, field
from collections import defaultdict

from core.agents.summariser_agent import SummarizerAgent
from core.judge.base_judge import FaithfulnessJudge, JudgeFailedError

logger = logging.getLogger(__name__)


class SummarizationFailedError(Exception):
    """No valid summary produced across all quality-retry attempts."""
    pass


@dataclass
class DateChunkJudgement:
    date: str
    bullets: str
    score: float


@dataclass
class ComplaintSummaryResult:
    summary: str
    per_date_scores: list[DateChunkJudgement]
    overall_score: float
    quality_attempts_used: int
    metadata: dict = field(default_factory=dict)


class ComplaintSummarizerOrchestrator:
    def __init__(
        self,
        gemini_client,
        semaphore,
        token_manager,
        judge_max_retries: int = 3,
        quality_max_attempts: int = 3,
        quality_score_threshold: float = 0.85,
    ):
        self.gemini_client = gemini_client
        self.semaphore = semaphore
        self.token_manager = token_manager
        self.judge_max_retries = judge_max_retries
        self.quality_max_attempts = quality_max_attempts
        self.quality_score_threshold = quality_score_threshold

    # =========================================================
    # Source grouping - raw interactions by date (for judge reference)
    # =========================================================
    def _source_by_date(self, interactions: list[dict]) -> dict[str, str]:
        buckets: dict[str, list[str]] = defaultdict(list)
        for i in interactions:
            date_key = i["timestamp"][:10]
            buckets[date_key].append(f"[{i['timestamp']}] [{i['channel']}] {i['speaker']}: {i['text']}")
        return {date: "\n".join(lines) for date, lines in buckets.items()}

    # =========================================================
    # Output chunking - parse bullets, group by their [YYYY-MM-DD] tag
    # =========================================================
    def _chunk_summary_by_date(self, summary: str) -> dict[str, list[str]]:
        buckets: dict[str, list[str]] = defaultdict(list)
        pattern = re.compile(r"^\[(\d{4}-\d{2}-\d{2})\]")

        for line in summary.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            match = pattern.match(line)
            date_key = match.group(1) if match else "unknown"
            buckets[date_key].append(line)

        return buckets

    # =========================================================
    # One full summarization pass (single call, full context)
    # =========================================================
    async def _summarize_full(self, interactions: list[dict]) -> str:
        source_text = "\n".join(
            f"[{i['timestamp']}] [{i['channel']}] {i['speaker']}: {i['text']}"
            for i in interactions
        )
        agent = SummarizerAgent(
            gemini_client=self.gemini_client,
            semaphore=self.semaphore,
            token_manager=self.token_manager,
            interaction_channel="complaint",
        )
        return await agent.summarize(source_text)

    # =========================================================
    # Judge each date-chunk of the OUTPUT concurrently, against
    # that same date's source interactions
    # =========================================================
    async def _judge_by_date_chunk(
        self, summary_buckets: dict[str, list[str]], source_by_date: dict[str, str]
    ) -> list[DateChunkJudgement]:
        judge = FaithfulnessJudge(
            gemini_client=self.gemini_client,
            semaphore=self.semaphore,
            token_manager=self.token_manager,
            max_retries=self.judge_max_retries,
        )

        async def judge_one(date: str, bullets: list[str]) -> DateChunkJudgement:
            bullet_text = "\n".join(bullets)
            source_text = source_by_date.get(date, "")
            try:
                score = await judge.judge(source_text, bullet_text)
            except JudgeFailedError as e:
                logger.warning("Judge failed for date %s: %s", date, e)
                score = 0.0  # treat as failed judgement, will drag overall down
            return DateChunkJudgement(date=date, bullets=bullet_text, score=score)

        return await asyncio.gather(
            *[judge_one(date, bullets) for date, bullets in summary_buckets.items()]
        )

    # =========================================================
    # Full run: summarize once -> chunk output by date -> judge
    # each date-chunk concurrently -> quality retry on low scores
    # =========================================================
    async def run(self, interactions: list[dict]) -> ComplaintSummaryResult:
        source_by_date = self._source_by_date(interactions)

        best_summary = None
        best_judgements: list[DateChunkJudgement] = []
        best_overall = -1.0
        attempts_used = 0

        for attempt in range(self.quality_max_attempts):
            attempts_used = attempt + 1

            summary = await self._summarize_full(interactions)
            summary_buckets = self._chunk_summary_by_date(summary)
            judgements = await self._judge_by_date_chunk(summary_buckets, source_by_date)

            overall = sum(j.score for j in judgements) / len(judgements) if judgements else 0.0

            if overall > best_overall:
                best_summary, best_judgements, best_overall = summary, judgements, overall

            if overall >= self.quality_score_threshold:
                break

        if best_summary is None:
            raise SummarizationFailedError("No valid summary produced across all quality-retry attempts")

        return ComplaintSummaryResult(
            summary=best_summary,
            per_date_scores=best_judgements,
            overall_score=best_overall,
            quality_attempts_used=attempts_used,
        )