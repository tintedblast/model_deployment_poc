"""
BaseAgent - default hooks any agent gets for free. Prompt is just an
attribute, not something subclasses need to implement via abstract methods.
Subclasses override hooks only if their behavior actually differs.
"""

import logging
import asyncio

logger = logging.getLogger(__name__)


class BaseAgent:
    """
    Default agent skeleton:
        pre_hook() -> execute() -> post_hook()

    - prompt: plain attribute, set at init or by a subclass
    - pre_hook: default checks token/semaphore budget before calling the LLM
    - post_hook: default logs prompt, tokens used, tool calls, timing (audit)
    """

    def __init__(
        self,
        gemini_client,
        semaphore,
        token_manager,
        prompt: str = "",
        acquire_timeout: float = 30.0,
    ):
        self.gemini_client = gemini_client
        self.semaphore = semaphore
        self.token_manager = token_manager
        self.prompt = prompt
        self.acquire_timeout = acquire_timeout

    def estimate_tokens(self, text: str) -> int:
        return max(1, len(text) // 4)

    async def pre_hook(self, input_text: str) -> None:
        """Default: acquire semaphore slot + token budget before calling the LLM."""
        async with asyncio.timeout(self.acquire_timeout):
            await self.semaphore.acquire()
            await self.token_manager.acquire(self.estimate_tokens(self.prompt + input_text))

    async def post_hook(self, input_text: str, output_text: str, duration: float) -> None:
        """Default: audit log. Override to capture tool calls, richer metadata, etc."""
        logger.info(
            "agent=%s duration=%.2fs prompt_tokens=%d input_tokens=%d",
            self.__class__.__name__,
            duration,
            self.estimate_tokens(self.prompt),
            self.estimate_tokens(input_text),
        )
        await self.semaphore.release()

    async def call_llm(self, full_prompt: str) -> str:
        """The actual LLM call. Override only if the call mechanics differ."""
        return await self.gemini_client.generate(full_prompt)

    def build_full_prompt(self, input_text: str) -> str:
        """Combine the agent's prompt attribute with the input. Override for custom formatting."""
        return f"{self.prompt}\n\n{input_text}"

    async def execute(self, input_text: str) -> str:
        """Template method: pre_hook -> call_llm -> post_hook. Do not override."""
        import time
        start = time.monotonic()

        await self.pre_hook(input_text)
        full_prompt = self.build_full_prompt(input_text)
        output = await self.call_llm(full_prompt)
        duration = time.monotonic() - start
        await self.post_hook(input_text, output, duration)

        return output
