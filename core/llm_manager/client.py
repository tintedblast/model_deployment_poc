"""
Async-compatible Gemini client, adapted from your LLMRouter.
Wraps the sync generate_content() call with asyncio.to_thread so it
doesn't block the event loop - required since BaseAgent/BaseJudge
call `await self.gemini_client.generate(prompt)`.

IMPORTANT: set your API key via environment variable, not hardcoded:
    setx GEMINI_API_KEY "your-key-here"   (PowerShell, then restart terminal)
or for the current session only:
    $env:GEMINI_API_KEY = "your-key-here"
"""
from dotenv import load_dotenv
load_dotenv()

import os
import asyncio
import google.generativeai as genai


class GeminiClient:
    def __init__(self, model: str = "gemini-2.5-pro"):
        print("Key loaded:", bool(os.environ.get("GEMINI_API_KEY")))
        api_key =  os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("Set GEMINI_API_KEY environment variable before running.")
        genai.configure(api_key=api_key)
        self.client = genai.GenerativeModel(model)

    async def generate(self, prompt: str) -> str:
        # generate_content() is sync/blocking - run it in a thread so it
        # doesn't block the event loop while other coroutines are waiting.
        response = await asyncio.to_thread(self.client.generate_content, prompt)
        return response.text