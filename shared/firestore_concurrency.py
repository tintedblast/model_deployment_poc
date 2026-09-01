"""
Firestore-based replacements for the Redis DistributedSemaphore and
GlobalTokenManager - since Cloud Run can't reach a laptop-hosted Redis,
and Memorystore has real ongoing cost + needs a VPC connector, this
keeps the whole pipeline on Firestore, which you're already using.

Same interface as before: `async with semaphore:` and `await
token_manager.acquire(tokens)` - summariser_agent's code barely changes.
"""

import time
import asyncio
from google.cloud import firestore
from google.cloud.firestore_v1 import AsyncTransaction

db = firestore.AsyncClient()


class FirestoreSemaphore:
    """
    Caps global concurrent Gemini calls across ALL Cloud Run instances,
    using a Firestore document's counter field + a transaction for
    atomic increment/decrement (Firestore transactions retry on
    contention automatically, similar guarantee to Redis's INCR).
    """

    def __init__(self, doc_path: str = "concurrency/gemini_semaphore", max_count: int = 10, poll_interval: float = 0.3):
        self.doc_ref = db.document(doc_path)
        self.max_count = max_count
        self.poll_interval = poll_interval

    async def acquire(self):
        while True:
            acquired = await self._try_acquire_once()
            if acquired:
                return
            await asyncio.sleep(self.poll_interval)

    @firestore.async_transactional
    async def _try_acquire_once_txn(self, transaction: AsyncTransaction) -> bool:
        snapshot = await self.doc_ref.get(transaction=transaction)
        current = snapshot.get("count") if snapshot.exists else 0
        current = current or 0

        if current >= self.max_count:
            return False

        transaction.set(self.doc_ref, {"count": current + 1}, merge=True)
        return True

    async def _try_acquire_once(self) -> bool:
        transaction = db.transaction()
        return await self._try_acquire_once_txn(transaction)

    async def release(self):
        @firestore.async_transactional
        async def _release_txn(transaction: AsyncTransaction):
            snapshot = await self.doc_ref.get(transaction=transaction)
            current = snapshot.get("count") if snapshot.exists else 0
            current = current or 0
            transaction.set(self.doc_ref, {"count": max(0, current - 1)}, merge=True)

        transaction = db.transaction()
        await _release_txn(transaction)

    async def __aenter__(self):
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.release()


class FirestoreTokenManager:
    """
    Sliding-window token budget (e.g. N tokens per trailing 3 seconds).
    Each usage is a document in a collection, timestamped. Sum documents
    within the trailing window, same concept as the Redis sorted-set
    version, using Firestore queries instead.
    """

    def __init__(self, collection_path: str = "concurrency/gemini_tokens/usage", max_tokens_per_window: int = 100_000, window_seconds: float = 3.0, poll_interval: float = 0.3):
        self.collection_ref = db.collection(collection_path)
        self.max_tokens = max_tokens_per_window
        self.window = window_seconds
        self.poll_interval = poll_interval

    async def acquire(self, tokens: int):
        while True:
            now = time.time()
            window_start = now - self.window

            query = self.collection_ref.where("timestamp", ">=", window_start)
            docs = [doc async for doc in query.stream()]
            current_total = sum(doc.get("tokens") for doc in docs)

            if current_total + tokens <= self.max_tokens:
                await self.collection_ref.add({"timestamp": now, "tokens": tokens})
                # Best-effort cleanup of old entries (not blocking the acquire)
                asyncio.create_task(self._cleanup_old(window_start))
                return

            await asyncio.sleep(self.poll_interval)

    async def _cleanup_old(self, window_start: float):
        query = self.collection_ref.where("timestamp", "<", window_start)
        async for doc in query.stream():
            await doc.reference.delete()


def build_firestore_semaphore(max_count: int = 10) -> FirestoreSemaphore:
    return FirestoreSemaphore(max_count=max_count)


def build_firestore_token_manager(max_tokens: int = 100_000) -> FirestoreTokenManager:
    return FirestoreTokenManager(max_tokens_per_window=max_tokens, window_seconds=3.0)