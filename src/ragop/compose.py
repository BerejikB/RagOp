from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from .config import load_env_defaults
from .retrieve import retrieve, Retrieval

DEFAULT_SNIPPET_MAX_CHARS = 500
DEFAULT_MAX_TOTAL_CHARS = 1200


@dataclass
class ComposedContext:
    text: str
    citations: List[str]


def _trim(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "\u2026"


def compose_context(
    question: str,
    k: int = 1,
    snippet_max_chars: int = DEFAULT_SNIPPET_MAX_CHARS,
    max_total_chars: int = DEFAULT_MAX_TOTAL_CHARS,
    index_path: Optional[str | Path] = None,
) -> ComposedContext:
    cfg = load_env_defaults()
    k = max(1, k or cfg.k)
    snippet_max_chars = snippet_max_chars or cfg.snippet_max_chars
    max_total_chars = max_total_chars or cfg.max_total_chars
    idx_path = Path(index_path) if index_path is not None else cfg.index_path

    results = retrieve(question, k=k, index_path=idx_path, snippet_max_chars=snippet_max_chars)

    parts: List[str] = []
    cites: List[str] = []
    for r in results:
        snippet = _trim(r.text, snippet_max_chars)
        cite = f"[{r.path}:{r.start_line}-{r.end_line}]"
        parts.append(snippet)
        cites.append(cite)
        # enforce total size bound ASAP
        joined = "\n\n".join(parts)
        if len(joined) > max_total_chars:
            # drop last addition if it overflows; keep earlier ones
            parts.pop()
            cites.pop()
            break

    body = "\n\n".join(parts)
    return ComposedContext(text=body, citations=cites)


def compose_ultra_compact(
    question: str,
    k: int = 1,
    snippet_max_chars: int = DEFAULT_SNIPPET_MAX_CHARS,
    max_total_chars: int = DEFAULT_MAX_TOTAL_CHARS,
    index_path: Optional[str | Path] = None,
) -> ComposedContext:
    # Ultra-compact: return only the best single snippet, strictly bounded
    ctx = compose_context(
        question=question,
        k=max(1, k),
        snippet_max_chars=snippet_max_chars,
        max_total_chars=max_total_chars,
        index_path=index_path,
    )
    # Ensure a single snippet only
    if "\n\n" in ctx.text:
        first = ctx.text.split("\n\n", 1)[0]
        ctx = ComposedContext(text=first, citations=ctx.citations[:1])
    return ctx
