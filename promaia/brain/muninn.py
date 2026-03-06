"""
MuninnDB REST client for zBrain cognitive memory sidecar.

Wraps MuninnDB's REST API (port 8475) using async httpx. The Python SDK
(muninndb / muninn-python) is broken on Python 3.14 due to a packaging bug
that installs zero code files. Direct REST calls via httpx are reliable and
httpx is already a project dependency.

MuninnDB handles embedding generation server-side via MUNINN_GOOGLE_KEY.
This client sends text only -- no client-side embedding generation.

Usage:
    from promaia.brain.muninn import get_muninn

    muninn = await get_muninn()
    if muninn:
        await muninn.write(concept="short label", content="full text")
        results = await muninn.activate(context=["what am I thinking about?"])
"""

import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


class MuninnClient:
    """Async REST client for MuninnDB cognitive memory database."""

    def __init__(
        self,
        base_url: str = "http://localhost:8475",
        vault: str = "zbrain-vault",
        timeout: float = 5.0,
    ):
        self._vault = vault
        self._client = httpx.AsyncClient(
            base_url=base_url,
            timeout=timeout,
        )

    async def health(self) -> bool:
        """Check if MuninnDB is reachable. GET /api/health."""
        try:
            r = await self._client.get("/api/health")
            return r.status_code == 200
        except Exception:
            return False

    async def write(
        self,
        concept: str,
        content: str,
        tags: list[str] | None = None,
        confidence: float = 0.9,
    ) -> str | None:
        """Write a single engram. Returns ULID id on success, None on failure.

        POST /api/engrams. Logs warning on failure but does NOT raise --
        callers use this in best-effort dual-write paths.
        """
        try:
            r = await self._client.post("/api/engrams", json={
                "vault": self._vault,
                "concept": concept,
                "content": content,
                "tags": tags or [],
                "confidence": confidence,
            })
            r.raise_for_status()
            return r.json().get("id")
        except Exception as e:
            logger.warning(f"MuninnDB write failed: {e}")
            return None

    async def write_batch(self, engrams: list[dict]) -> list[dict]:
        """Write multiple engrams. Returns list of result dicts.

        Uses individual POST /api/engrams calls because the batch endpoint
        (/api/engrams/batch) ignores the vault field and always writes to
        the default vault (MuninnDB v0.3.6-alpha bug).

        Each engram dict should have keys: concept, content, tags, confidence.
        Raises on failure -- batch is used for seeding, not in hot path.
        """
        results = []
        for i, engram in enumerate(engrams):
            r = await self._client.post("/api/engrams", json={
                "vault": self._vault,
                "concept": engram.get("concept", ""),
                "content": engram.get("content", ""),
                "tags": engram.get("tags", []),
                "confidence": engram.get("confidence", 0.9),
            })
            r.raise_for_status()
            data = r.json()
            results.append({
                "index": i,
                "id": data.get("id", ""),
                "status": "ok",
            })
        return results

    async def activate(
        self,
        context: list[str],
        max_results: int = 10,
        threshold: float = 0.1,
    ) -> dict:
        """Run ACTIVATE cognitive retrieval pipeline.

        POST /api/activate. Returns full response dict containing:
        query_id, total_found, activations, latency_ms, brief.

        Raises on failure.
        """
        r = await self._client.post("/api/activate", json={
            "vault": self._vault,
            "context": context,
            "max_results": max_results,
            "threshold": threshold,
        })
        r.raise_for_status()
        return r.json()

    async def stats(self) -> dict:
        """Get vault statistics. GET /api/stats?vault={vault}.

        Useful for verifying embedder config (check index_size > 0).
        """
        r = await self._client.get("/api/stats", params={"vault": self._vault})
        r.raise_for_status()
        return r.json()

    async def close(self) -> None:
        """Close the underlying httpx client."""
        await self._client.aclose()


# ---------------------------------------------------------------------------
# Module-level lazy singleton
# ---------------------------------------------------------------------------

_muninn: MuninnClient | None = None
_muninn_checked: bool = False


async def get_muninn() -> Optional[MuninnClient]:
    """Return MuninnDB client singleton, or None if unavailable.

    Checks health once on first call. If MuninnDB is unreachable,
    caches None to avoid repeated connection attempts. All callers
    are async handlers so the await is fine.
    """
    global _muninn, _muninn_checked
    if not _muninn_checked:
        _muninn_checked = True
        client = MuninnClient()
        if await client.health():
            _muninn = client
            logger.info("MuninnDB connected (zbrain-vault)")
        else:
            logger.warning(
                "MuninnDB unreachable at localhost:8475 "
                "-- cognitive memory disabled"
            )
            await client.close()
    return _muninn
