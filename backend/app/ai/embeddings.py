"""Text embeddings used for theme discovery, duplicate detection and Ask-your-feedback retrieval.

We always embed the *working-language* text (the translation when one exists), so
once an LLM has translated feedback, a German and a Spanish complaint about the
same bug land in the same theme even with the purely local embedder.
"""

from __future__ import annotations

import os
import zlib
from abc import ABC, abstractmethod
from typing import Any

import httpx
import numpy as np
from scipy import sparse
from sklearn.feature_extraction.text import TfidfTransformer
from sklearn.preprocessing import normalize as l2_normalize

from ..config import get_settings
from .ollama_provider import model_present, ollama_models
from .concepts import concepts_in
from .textutil import content_tokens, stem


class Embedder(ABC):
    name = "base"
    model = ""
    # Average-linkage cosine distance under which items form one theme
    cluster_distance = 0.5
    # Cosine similarity above which two items count as duplicates
    dup_threshold = 0.95
    # Minimum cosine similarity for Ask-your-feedback retrieval
    retrieval_min = 0.2

    @property
    def label(self) -> str:
        return f"{self.name}:{self.model}"

    @abstractmethod
    def available(self) -> tuple[bool, str]: ...

    @abstractmethod
    def embed(self, texts: list[str]) -> list[Any]:
        """Return one JSON-serializable vector per text (stored on the feedback row)."""

    def matrix(self, stored: list[Any]) -> np.ndarray | sparse.csr_matrix:
        """Stack stored vectors into an L2-normalized matrix so ``A @ B.T`` is cosine similarity."""
        arr = np.asarray(stored, dtype=np.float32)
        return l2_normalize(arr)


def cosine(a: Any, b: Any) -> np.ndarray:
    sim = a @ b.T
    return sim.toarray() if sparse.issparse(sim) else np.asarray(sim)


class LocalEmbedder(Embedder):
    """Stateless hashed bag-of-words (stemmed unigrams + bigrams), TF-IDF weighted at query time."""

    name = "local"
    model = "hashed-tfidf-concepts-v1"
    dims = 4096
    cluster_distance = 0.88  # tuned: ARI 1.00 on the sample set, 0.74 on held-out phrasings
    dup_threshold = 0.9
    retrieval_min = 0.05

    def available(self) -> tuple[bool, str]:
        return True, "Built-in hashed TF-IDF vectors (no model needed)"

    concept_weight = 3

    def _features(self, text: str) -> dict[str, int]:
        toks = [stem(t) for t in content_tokens(text)]
        feats = toks + [f"{a}_{b}" for a, b in zip(toks, toks[1:])]
        # cross-lingual concepts let offline mode group "langsam", "lento" and "slow"
        feats += [f"concept:{c}" for c in concepts_in(text) for _ in range(self.concept_weight)]
        counts: dict[str, int] = {}
        for f in feats:
            idx = str(zlib.crc32(f.encode()) % self.dims)
            counts[idx] = counts.get(idx, 0) + 1
        return counts

    def embed(self, texts: list[str]) -> list[Any]:
        return [self._features(t) for t in texts]

    def matrix(self, stored: list[Any]) -> sparse.csr_matrix:
        rows, cols, vals = [], [], []
        for i, vec in enumerate(stored):
            for k, v in (vec or {}).items():
                rows.append(i)
                cols.append(int(k))
                vals.append(float(v))
        counts = sparse.csr_matrix((vals, (rows, cols)), shape=(len(stored), self.dims), dtype=np.float32)
        if counts.shape[0] == 0:
            return counts
        tfidf = TfidfTransformer(sublinear_tf=True, smooth_idf=True).fit_transform(counts)
        return l2_normalize(tfidf)


class OpenAIEmbedder(Embedder):
    name = "openai"
    cluster_distance = 0.55
    dup_threshold = 0.95
    retrieval_min = 0.25

    def __init__(self, client: Any = None):
        settings = get_settings()
        self.model = settings.openai_embedding_model
        self._api_key = settings.openai_api_key
        self._client = client

    def available(self) -> tuple[bool, str]:
        if self._client is not None or self._api_key or os.environ.get("OPENAI_API_KEY"):
            return True, f"OpenAI {self.model}"
        return False, "Set OPENAI_API_KEY to use OpenAI embeddings"

    @property
    def client(self) -> Any:
        if self._client is None:
            import openai

            self._client = openai.OpenAI(api_key=self._api_key) if self._api_key else openai.OpenAI()
        return self._client

    def embed(self, texts: list[str]) -> list[Any]:
        out: list[Any] = []
        for i in range(0, len(texts), 100):
            resp = self.client.embeddings.create(model=self.model, input=[t[:8000] for t in texts[i:i + 100]])
            out.extend([round(x, 5) for x in d.embedding] for d in resp.data)
        return out


class OllamaEmbedder(Embedder):
    name = "ollama"
    cluster_distance = 0.42
    dup_threshold = 0.97
    retrieval_min = 0.35

    def __init__(self, client: httpx.Client | None = None):
        settings = get_settings()
        self.model = settings.ollama_embed_model
        self.base_url = settings.ollama_base_url.rstrip("/")
        self._client = client

    def available(self) -> tuple[bool, str]:
        installed = ollama_models(self.base_url, self._client)
        if installed is None:
            return False, "Ollama not reachable"
        if not model_present(self.model, installed):
            return False, f"Run `ollama pull {self.model}` to enable local semantic embeddings"
        return True, f"Ollama {self.model}"

    def embed(self, texts: list[str]) -> list[Any]:
        client = self._client or httpx.Client(timeout=120)
        r = client.post(f"{self.base_url}/api/embed", json={"model": self.model, "input": texts})
        r.raise_for_status()
        return [[round(x, 5) for x in v] for v in r.json()["embeddings"]]


_EMBEDDERS: dict[str, Embedder] = {}


def get_embedder(name: str | None = None) -> Embedder:
    choice = name or get_settings().embeddings_provider
    if choice in _EMBEDDERS:
        return _EMBEDDERS[choice]
    candidates: list[Embedder]
    if choice == "auto":
        candidates = [OpenAIEmbedder(), OllamaEmbedder(), LocalEmbedder()]
    else:
        candidates = [{"openai": OpenAIEmbedder, "ollama": OllamaEmbedder}.get(choice, LocalEmbedder)(), LocalEmbedder()]
    for emb in candidates:
        if emb.available()[0]:
            _EMBEDDERS[choice] = emb
            return emb
    return LocalEmbedder()  # pragma: no cover


def set_embedder(embedder: Embedder | None) -> None:
    """Override (tests) or reset the cached embedder choice."""
    _EMBEDDERS.clear()
    if embedder is not None:
        _EMBEDDERS[get_settings().embeddings_provider] = embedder
