import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, List, Sequence


INCLUDE_EXTS = {".py", ".md", ".txt", ".toml", ".json", ".sh", ".ps1"}
IGNORE_DIRS = {".git", ".venv", ".index", "__pycache__", "node_modules"}
MAX_FILE_BYTES = 5_000_000  # 5MB safety
CHUNK_LINES = 200
CHUNK_OVERLAP = 40


@dataclass
class Chunk:
    path: str
    start_line: int
    end_line: int
    text: str


@dataclass
class RAGIndex:
    chunks: List[Chunk]


def _iter_files(paths: Sequence[str | Path]) -> Iterator[Path]:
    for p in [Path(p) for p in paths]:
        if p.is_file():
            if p.suffix.lower() in INCLUDE_EXTS:
                yield p
            continue
        if p.is_dir():
            for root, dirs, files in os.walk(p):
                # prune ignored dirs in-place
                dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
                for f in files:
                    fp = Path(root) / f
                    if fp.suffix.lower() in INCLUDE_EXTS:
                        yield fp


def _chunk_file(path: Path, lines_per_chunk: int = CHUNK_LINES, overlap: int = CHUNK_OVERLAP) -> Iterator[Chunk]:
    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            return
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return
    lines = text.splitlines()
    n = len(lines)
    if n == 0:
        return
    i = 0
    while i < n:
        j = min(n, i + lines_per_chunk)
        chunk_text = "\n".join(lines[i:j])
        yield Chunk(path=str(path), start_line=i + 1, end_line=j, text=chunk_text)
        if j >= n:
            break
        i = max(i + lines_per_chunk - overlap, j)


def build_index(paths: Iterable[str | Path], index_path: str | Path) -> RAGIndex:
    ipath = Path(index_path)
    ipath.parent.mkdir(parents=True, exist_ok=True)

    chunks: List[Chunk] = []
    with ipath.open("w", encoding="utf-8") as f:
        for file_path in _iter_files(list(paths)):
            for ch in _chunk_file(file_path):
                chunks.append(ch)
                f.write(json.dumps(ch.__dict__, ensure_ascii=False) + "\n")

    return RAGIndex(chunks=chunks)


def load_index(index_path: str | Path) -> RAGIndex:
    ipath = Path(index_path)
    if not ipath.exists():
        raise FileNotFoundError(f"Index not found: {ipath}")
    chunks: List[Chunk] = []
    with ipath.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
                chunks.append(Chunk(**d))
            except Exception:
                continue
    return RAGIndex(chunks=chunks)
