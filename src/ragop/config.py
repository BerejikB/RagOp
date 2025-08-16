import os
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Optional

ENV_INDEX = "RAGOP_INDEX"
ENV_K = "RAGOP_K"
ENV_SNIPPET = "RAGOP_SNIPPET_MAX_CHARS"
ENV_TOTAL = "RAGOP_MAX_TOTAL_CHARS"

DEFAULT_INDEX_FILENAME = "rag_index.jsonl"


def _repo_root_from(start: Optional[Path] = None) -> Path:
    p = Path(start or os.getcwd()).resolve()
    for _ in range(5):
        if (p / "pyproject.toml").exists() or (p / ".git").exists():
            return p
        if p.parent == p:
            break
        p = p.parent
    return Path(start or os.getcwd()).resolve()


def default_index_path(start: Optional[Path] = None) -> Path:
    root = _repo_root_from(start)
    return root / ".index" / DEFAULT_INDEX_FILENAME


@dataclass(frozen=True)
class Config:
    index_path: Path
    k: int = 1
    snippet_max_chars: int = 500
    max_total_chars: int = 1200

    @staticmethod
    def from_env(start: Optional[Path] = None) -> "Config":
        root = _repo_root_from(start)
        idx = Path(os.getenv(ENV_INDEX) or default_index_path(root))
        k = int(os.getenv(ENV_K) or 1)
        snip = int(os.getenv(ENV_SNIPPET) or 500)
        total = int(os.getenv(ENV_TOTAL) or 1200)
        return Config(index_path=idx, k=k, snippet_max_chars=snip, max_total_chars=total)

    def with_cli_overrides(
        self,
        index: Optional[str] = None,
        k: Optional[int] = None,
        snippet_max_chars: Optional[int] = None,
        max_total_chars: Optional[int] = None,
    ) -> "Config":
        cfg = self
        if index is not None:
            cfg = replace(cfg, index_path=Path(index))
        if k is not None:
            cfg = replace(cfg, k=int(k))
        if snippet_max_chars is not None:
            cfg = replace(cfg, snippet_max_chars=int(snippet_max_chars))
        if max_total_chars is not None:
            cfg = replace(cfg, max_total_chars=int(max_total_chars))
        return cfg


def load_env_defaults(start: Optional[Path] = None) -> Config:
    return Config.from_env(start)
