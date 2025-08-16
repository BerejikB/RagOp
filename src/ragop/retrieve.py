import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from .index import RAGIndex, load_index, Chunk

TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")


def _tokenize(text: str) -> List[str]:
    return [t.lower() for t in TOKEN_RE.findall(text)]


@dataclass
class Retrieval:
    path: Path
    start_line: int
    end_line: int
    text: str
    score: float


def _bm25_scores(chunks: List[Chunk], query: str) -> List[float]:
    # Simple BM25-like scoring with global IDF over chunks
    # Parameters
    k1 = 1.5
    b = 0.75

    # Precompute corpus stats
    N = len(chunks)
    avgdl = sum(len(_tokenize(ch.text)) for ch in chunks) / max(1, N)

    # Document term stats
    chunk_tokens = [
        _tokenize(ch.text) for ch in chunks
    ]
    chunk_tf = [Counter(toks) for toks in chunk_tokens]

    # IDF per term
    df = Counter()
    for toks in chunk_tokens:
        df.update(set(toks))

    def idf(term: str) -> float:
        n_qi = df.get(term, 0)
        return math.log((N - n_qi + 0.5) / (n_qi + 0.5) + 1)

    q_terms = _tokenize(query)
    scores: List[float] = []
    for i, ch in enumerate(chunks):
        dl = len(chunk_tokens[i])
        s = 0.0
        for q in q_terms:
            if q not in chunk_tf[i]:
                continue
            tf = chunk_tf[i][q]
            denom = tf + k1 * (1 - b + b * (dl / (avgdl or 1)))
            s += idf(q) * ((tf * (k1 + 1)) / (denom or 1e-9))
        scores.append(s)
    return scores


def retrieve(
    query: str,
    k: int = 1,
    index_path: Optional[str | Path] = None,
    snippet_max_chars: Optional[int] = None,
) -> List[Retrieval]:
    # Load index lazily
    idx = load_index(index_path) if index_path is not None else None
    if idx is None:
        # Try default location relative to CWD
        from .config import default_index_path

        idx = load_index(default_index_path())

    chunks = idx.chunks
    if not chunks:
        return []

    scores = _bm25_scores(chunks, query)
    ranked = sorted(zip(chunks, scores), key=lambda t: t[1], reverse=True)
    out: List[Retrieval] = []
    for ch, sc in ranked[: max(1, k)]:
        text = ch.text
        if snippet_max_chars and len(text) > snippet_max_chars:
            text = text[: snippet_max_chars - 1].rstrip() + "\u2026"
        out.append(
            Retrieval(
                path=Path(ch.path),
                start_line=ch.start_line,
                end_line=ch.end_line,
                text=text,
                score=sc,
            )
        )
    return out
