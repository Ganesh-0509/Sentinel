"""Regulation retrieval store.

Chunks the regulation corpus by heading, indexes it, and retrieves the passages
most relevant to a question -- carrying **provenance** through to every citation so
the UI can mark whether an answer rests on official text or a development summary.

Retrieval backend:
    * default  -- TF-IDF + cosine similarity (sklearn). Zero extra downloads,
      deterministic, and strong on this corpus because regulatory queries are
      keyword-dense ("hot work", "%LEL", "confined space", "oxygen").
    * optional -- Ollama embeddings, if a local embedding model is pulled.
      Set SENTINEL_EMBED=ollama to enable.

A vector database (FAISS/Chroma) is unnecessary at this corpus size; cosine over a
few hundred chunks is sub-millisecond. Swap it in when the corpus grows.
"""
from __future__ import annotations

import json
import os
import re
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
EMBED_MODEL = os.environ.get("SENTINEL_EMBED_MODEL", "nomic-embed-text")


@dataclass
class Chunk:
    text: str
    doc_title: str
    standard: str
    section: str
    provenance: str          # OFFICIAL | SUMMARY
    source_file: str
    score: float = 0.0

    def citation(self) -> str:
        mark = "" if self.provenance == "OFFICIAL" else " [development summary — not official text]"
        return f"{self.standard} — {self.section}{mark}"


def _parse_front_matter(raw: str) -> tuple[dict, str]:
    meta: dict = {}
    body = raw
    if raw.startswith("---"):
        end = raw.find("\n---", 3)
        if end != -1:
            for line in raw[3:end].strip().splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    meta[k.strip()] = v.strip()
            body = raw[end + 4:]
    return meta, body


def _split_sections(body: str) -> list[tuple[str, str]]:
    """Split markdown into (heading, text) pairs on ## headings."""
    parts = re.split(r"\n##+\s+", "\n" + body)
    out = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        lines = part.splitlines()
        heading = lines[0].strip().lstrip("# ").strip()
        text = "\n".join(lines[1:]).strip()
        if text:
            out.append((heading, text))
    return out


class RegulationStore:
    def __init__(self, corpus_dir: str | Path = "data/regulations"):
        self.corpus_dir = Path(corpus_dir)
        self.chunks: list[Chunk] = []
        self._matrix = None
        self._vectorizer: TfidfVectorizer | None = None
        self._embeddings: np.ndarray | None = None
        self.backend = "tfidf"

    # ------------------------------------------------------------------ build
    def build(self) -> "RegulationStore":
        for path in sorted(self.corpus_dir.glob("*.md")):
            if path.name.lower() == "readme.md":
                continue
            meta, body = _parse_front_matter(path.read_text(encoding="utf-8"))
            for heading, text in _split_sections(body):
                self.chunks.append(Chunk(
                    text=text,
                    doc_title=meta.get("title", path.stem),
                    standard=meta.get("standard", path.stem),
                    section=heading,
                    provenance=meta.get("provenance", "SUMMARY").upper(),
                    source_file=path.name,
                ))
        if not self.chunks:
            raise FileNotFoundError(f"no regulation documents found in {self.corpus_dir}")

        corpus = [f"{c.standard} {c.section}. {c.text}" for c in self.chunks]
        if os.environ.get("SENTINEL_EMBED") == "ollama":
            emb = self._embed_all(corpus)
            if emb is not None:
                self._embeddings, self.backend = emb, f"ollama:{EMBED_MODEL}"
                return self
        self._vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2),
                                           sublinear_tf=True)
        self._matrix = self._vectorizer.fit_transform(corpus)
        return self

    # -------------------------------------------------------------- embeddings
    def _embed_one(self, text: str) -> np.ndarray | None:
        payload = {"model": EMBED_MODEL, "prompt": text}
        req = urllib.request.Request(
            f"{OLLAMA_URL}/api/embeddings",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return np.asarray(json.loads(r.read().decode())["embedding"], dtype=float)
        except Exception:
            return None

    def _embed_all(self, texts: list[str]) -> np.ndarray | None:
        vecs = []
        for t in texts:
            v = self._embed_one(t)
            if v is None:
                return None
            vecs.append(v)
        return np.vstack(vecs)

    # --------------------------------------------------------------- retrieve
    def search(self, query: str, k: int = 4) -> list[Chunk]:
        if self._embeddings is not None:
            qv = self._embed_one(query)
            if qv is not None:
                sims = cosine_similarity(qv.reshape(1, -1), self._embeddings)[0]
            else:
                sims = np.zeros(len(self.chunks))
        else:
            qv = self._vectorizer.transform([query])
            sims = cosine_similarity(qv, self._matrix)[0]

        order = np.argsort(sims)[::-1][:k]
        out = []
        for i in order:
            if sims[i] <= 0:
                continue
            c = self.chunks[i]
            out.append(Chunk(**{**c.__dict__, "score": float(sims[i])}))
        return out
