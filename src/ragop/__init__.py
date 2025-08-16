"""RagOp - machine-agnostic RAG operational scaffold.

Portable, minimal Retrieval-Augmented Generation with sensible defaults.
Environment variables and CLI flags override code defaults.
"""
from .config import Config, load_env_defaults
from .index import build_index, load_index
from .retrieve import retrieve, Retrieval
from .compose import (
    compose_context,
    compose_ultra_compact,
    DEFAULT_SNIPPET_MAX_CHARS,
    DEFAULT_MAX_TOTAL_CHARS,
)

__all__ = [
    "Config",
    "load_env_defaults",
    "build_index",
    "load_index",
    "retrieve",
    "Retrieval",
    "compose_context",
    "compose_ultra_compact",
    "DEFAULT_SNIPPET_MAX_CHARS",
    "DEFAULT_MAX_TOTAL_CHARS",
]
