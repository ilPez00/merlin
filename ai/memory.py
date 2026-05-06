"""
Merlin — Episodic memory via ChromaDB.
Stores observations and Q&A pairs with embeddings.
Retrieves semantically relevant past context before each query.
"""

import hashlib
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

log = logging.getLogger("merlin.memory")

MEMORY_DIR = Path.home() / ".merlin" / "memory"
COLLECTION = "merlin_episodes"
MAX_STORE_LEN = 2000   # truncate very long texts before embedding
MAX_RESULTS = 5


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


class EpisodicMemory:
    """
    Persistent semantic memory.  Uses ChromaDB with its built-in embedding
    (all-MiniLM-L6-v2 via chromadb's default).  Falls back to a no-op if
    chromadb is not installed.
    """

    def __init__(self):
        self._collection = None

    # ── Init (lazy) ──────────────────────────────────────────────────────────────

    def _init(self) -> bool:
        if self._collection is not None:
            return True
        try:
            import chromadb
            MEMORY_DIR.mkdir(parents=True, exist_ok=True)
            client = chromadb.PersistentClient(path=str(MEMORY_DIR))
            self._collection = client.get_or_create_collection(
                name=COLLECTION,
                metadata={"hnsw:space": "cosine"},
            )
            log.info("episodic memory ready (%d entries)", self._collection.count())
            return True
        except ImportError:
            log.warning("chromadb not installed: pip install chromadb")
        except Exception as e:
            log.warning("memory init failed: %s", e)
        return False

    # ── Public API ───────────────────────────────────────────────────────────────

    def store(
        self,
        text: str,
        kind: str = "observation",
        mode: str = "",
        extra: Optional[dict] = None,
    ) -> Optional[str]:
        """Store a text chunk. Returns doc_id or None on failure."""
        if not self._init() or not text.strip():
            return None
        text = text[:MAX_STORE_LEN]
        try:
            doc_id = hashlib.sha256(
                f"{time.time():.3f}{text[:40]}".encode()
            ).hexdigest()[:16]
            meta: dict = {
                "ts": time.time(),
                "ts_iso": _now_iso(),
                "kind": kind,
                "mode": mode,
            }
            if extra:
                for k, v in extra.items():
                    meta[k] = str(v)
            self._collection.add(documents=[text], ids=[doc_id], metadatas=[meta])
            return doc_id
        except Exception as e:
            log.warning("memory store error: %s", e)
            return None

    def query(self, text: str, n: int = MAX_RESULTS, kind: Optional[str] = None) -> list[str]:
        """Return up to n most semantically relevant past entries."""
        if not self._init() or not text.strip():
            return []
        try:
            count = self._collection.count()
            if count == 0:
                return []
            kwargs: dict = dict(
                query_texts=[text],
                n_results=min(n, count),
                include=["documents", "metadatas"],
            )
            if kind:
                kwargs["where"] = {"kind": kind}
            results = self._collection.query(**kwargs)
            docs = results.get("documents", [[]])[0]
            metas = results.get("metadatas", [[]])[0]
            out = []
            for doc, meta in zip(docs, metas):
                if not doc:
                    continue
                ts = meta.get("ts_iso", "")
                prefix = f"[memory {ts}]" if ts else "[memory]"
                out.append(f"{prefix} {doc}")
            return out
        except Exception as e:
            log.warning("memory query error: %s", e)
            return []

    def count(self) -> int:
        if not self._init():
            return 0
        try:
            return self._collection.count()
        except Exception:
            return 0

    def delete_before(self, days: int = 30) -> int:
        """Delete entries older than N days. Returns count deleted."""
        if not self._init():
            return 0
        cutoff = time.time() - days * 86400
        try:
            results = self._collection.get(include=["metadatas"])
            ids_to_delete = [
                doc_id
                for doc_id, meta in zip(results["ids"], results["metadatas"])
                if meta.get("ts", float("inf")) < cutoff
            ]
            if ids_to_delete:
                self._collection.delete(ids=ids_to_delete)
                log.info("pruned %d memory entries older than %d days", len(ids_to_delete), days)
            return len(ids_to_delete)
        except Exception as e:
            log.warning("memory prune error: %s", e)
            return 0


# Module-level singleton used by session.py and tools.py
_memory: Optional[EpisodicMemory] = None


def get_memory() -> EpisodicMemory:
    global _memory
    if _memory is None:
        _memory = EpisodicMemory()
    return _memory
