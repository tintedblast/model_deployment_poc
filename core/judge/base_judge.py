"""
BaseJudge - default LLM-as-Judge functionality with built-in retry policy
for JUDGE ERRORS (API failure, malformed response) - NOT for low scores.
Low-score handling (quality retry, regenerate + rejudge) lives one layer
above, in whatever calls the judge (e.g. a quality-retry loop around
SummarizerAgent + BaseJudge together).
"""

import json
import logging
import asyncio

logger = logging.getLogger(__name__)


class JudgeFailedError(Exception):
    """The judge call itself errored out after all retries (not a low score)."""
    pass


class BaseJudge:
    """
    Default judge skeleton:
        pre_hook() -> call_llm() -> parse_score() -> post_hook()

    Retry policy is built in, for judge ERRORS only. Override judge_prompt_template
    or parse_score for a different judge prompt/response format.
    """

    judge_prompt_template = (
        "Rate the SUMMARY below for faithfulness to the SOURCE on a 0.0-1.0 scale. "
        "Faithfulness means the summary does not contain claims unsupported by the "
        "source, and does not omit critical facts. Respond ONLY as JSON: "
        "{{\"score\": <float>, \"reason\": \"...\"}}\n\n"
        "SOURCE:\n{source}\n\n"
        "SUMMARY:\n{summary}"
    )

    def __init__(
        self,
        gemini_client,
        semaphore,
        token_manager,
        max_retries: int = 3,
        acquire_timeout: float = 30.0,
        backoff_base: float = 2.0,
    ):
        self.gemini_client = gemini_client
        self.semaphore = semaphore
        self.token_manager = token_manager
        self.max_retries = max_retries
        self.acquire_timeout = acquire_timeout
        self.backoff_base = backoff_base

    def estimate_tokens(self, text: str) -> int:
        return max(1, len(text) // 4)

    def build_judge_prompt(self, source: str, summary: str) -> str:
        return self.judge_prompt_template.format(source=source, summary=summary)

    def parse_score(self, judge_response: str) -> float:
        """
        Default: expects JSON with a 'score' key. Gemini often wraps JSON in
        markdown code fences (```json ... ```) or adds surrounding text, so
        strip fences and extract the {...} block before parsing.
        """
        text = judge_response.strip()

        if text.startswith("```"):
            text = text.strip("`")
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()

        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            text = text[start:end + 1]

        data = json.loads(text)
        return float(data["score"])

    async def pre_hook(self, source: str, summary: str) -> None:
        async with asyncio.timeout(self.acquire_timeout):
            await self.semaphore.acquire()
            await self.token_manager.acquire(self.estimate_tokens(source + summary))

    async def post_hook(self, source: str, summary: str, score: float, duration: float) -> None:
        logger.info("judge=%s score=%.2f duration=%.2fs", self.__class__.__name__, score, duration)
        await self.semaphore.release()

    async def _call_judge_once(self, source: str, summary: str) -> float:
        await self.pre_hook(source, summary)
        prompt = self.build_judge_prompt(source, summary)
        response = await self.gemini_client.generate(prompt)
        # print(response)
        return self.parse_score(response)

    async def judge(self, source: str, summary: str) -> float:
        """
        Judge the summary against its source for faithfulness, retrying on
        ERROR (not low score) up to max_retries times with exponential backoff.
        Raises JudgeFailedError if all attempts fail.
        """
        import time
        start = time.monotonic()
        last_error = None

        for attempt in range(self.max_retries):
            try:
                score = await self._call_judge_once(source, summary)
                await self.post_hook(source, summary, score, time.monotonic() - start)
                return score
            except Exception as e:
                last_error = e
                logger.warning("Judge attempt %d/%d failed: %s", attempt + 1, self.max_retries, e)
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.backoff_base ** attempt)

        raise JudgeFailedError(f"Judge failed after {self.max_retries} attempts: {last_error}")


class FaithfulnessJudge(BaseJudge):
    """Concrete judge - default prompt/parsing from BaseJudge is already sufficient."""
    pass