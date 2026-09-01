from core.agents.base_agent import BaseAgent
from core.prompt_mapper import PROMPT_MAP


class SummarizerAgent(BaseAgent):
    """
    Prompt is now selected via interaction_channel, using PROMPT_MAP,
    instead of being passed in directly as a raw string.
    """

    def __init__(self, gemini_client, semaphore, token_manager, interaction_channel: str, acquire_timeout: float = 30.0):
        prompt = PROMPT_MAP[interaction_channel]
        super().__init__(
            gemini_client=gemini_client,
            semaphore=semaphore,
            token_manager=token_manager,
            prompt=prompt,
            acquire_timeout=acquire_timeout,
        )
        self.interaction_channel = interaction_channel

    async def summarize(self, input_text: str) -> str:
        return await self.execute(input_text)