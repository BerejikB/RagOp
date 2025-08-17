# ragop/incremental.py
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Set, Tuple

DEFAULT_INCLUDE_EXTS = {
    ".py", ".md", ".txt", ".json", ".toml", ".yaml", ".yml",
    ".sh", ".ps1", ".psm1", ".cmd", ".bat",
}
DEFAULT_IGNORE_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache"}

def _norm_rel(path: Path, roots: List[Path]) -> str:
    # Store relative, forward-slash paths for stability across OS/WT
    p = path.resolve()
    for root in roots:
        root = root.resolve()
        try:
            rel = p.relative_to(root)
            return str(rel.as_posix())
        except ValueError:
            continue
    return str(p.as_posix())

def _should_skip_dir(dir_name: str, ignore_dirs: Set[str]) -> bool:
    return dir_name in ignore_dirs

def _iter_files(roots: Iterable[Path],
                include_exts: Optional[Set[str]],
                ignore_dirs: Set[str]) -> Iterable[Path]:
    inc = set(e.lower() for e in (include_exts or DEFAULT_INCLUDE_EXTS))
    ign = set(ignore_dirs or DEFAULT_IGNORE_DIRS)
    for root in roots:
        root = Path(root)
        if not root.exists():
            continue
        for dpath, dnames, fnames in os.walk(root):
            # prune ignored directories in-place (os.walk optimization)
            dnames[:] = [d for d in dnames if not _should_skip_dir(d, ign)]
            for fn in fnames:
                p = Path(dpath) / fn
                if p.suffix.lower() in inc:
                    yield p

def _sha1(path: Path, chunk_size: int = 1 << 20) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk_size)
            if not b:
                break
            h.update(b)
    return h.hexdigest()

def _file_info(path: Path, mode: str = "mtime") -> Dict:
    st = path.stat()
    info = {
        "size": st.st_size,
        "mtime_ns": st.st_mtime_ns,
    }
    if mode == "hash":
        info["sha1"] = _sha1(path)
    return info

def _load_manifest(manifest_path: Path) -> Dict[str, Dict]:
    if manifest_path.exists():
        try:
            return json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}

def _save_manifest(manifest_path: Path, data: Dict[str, Dict]) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")

def diff_tree(roots: List[Path],
              include_exts: Optional[Set[str]] = None,
              ignore_dirs: Optional[Set[str]] = None,
              mode: str = "mtime",
              prev: Optional[Dict[str, Dict]] = None) -> Tuple[Dict[str, Dict], Set[str], Set[str], Set[str]]:
    """
    Returns (current_manifest, added, modified, removed) where keys are normalized relative paths.
    mode: "mtime" (fast) or "hash" (slower but robust).
    """
    prev = prev or {}
    cur: Dict[str, Dict] = {}

    roots_resolved = [Path(r).resolve() for r in roots]
    for f in _iter_files(roots_resolved, include_exts, set(ignore_dirs or DEFAULT_IGNORE_DIRS)):
        key = _norm_rel(f, roots_resolved)
        cur[key] = _file_info(f, mode=mode)

    prev_keys = set(prev.keys())
    cur_keys = set(cur.keys())

    added = cur_keys - prev_keys
    removed = prev_keys - cur_keys

    modified: Set[str] = set()
    intersect = cur_keys & prev_keys
    for k in intersect:
        a = prev[k]
        b = cur[k]
        # Compare by fields present (mtime/size or SHA)
        if a.get("mtime_ns") != b.get("mtime_ns") or a.get("size") != b.get("size") or a.get("sha1") != b.get("sha1"):
            modified.add(k)

    return cur, added, modified, removed

def incremental_build(
    roots: List[str],
    index_path: str,
    perform_full_build: Callable[[List[str], str], None],
    manifest_path: Optional[str] = None,
    include_exts: Optional[Iterable[str]] = None,
    ignore_dirs: Optional[Iterable[str]] = None,
    mode: str = "mtime",
    quiet: bool = False,
) -> Dict[str, object]:
    """
    Skips a rebuild when nothing changed. Otherwise, invokes perform_full_build(roots, index_path)
    and updates a manifest next to the index for future fast no-op runs.

    - roots: list of project roots to scan
    - index_path: path to your RAG index file
    - perform_full_build: callback that runs your existing full build
    - manifest_path: overrides default (index_path + '.manifest.json')
    - mode: 'mtime' (fast; default) or 'hash' (slower; robust)
    """
    ipath = Path(index_path)
    mpath = Path(manifest_path) if manifest_path else ipath.with_suffix(ipath.suffix + ".manifest.json")
    include = set(include_exts) if include_exts else DEFAULT_INCLUDE_EXTS
    ignore = set(ignore_dirs) if ignore_dirs else DEFAULT_IGNORE_DIRS

    prev = _load_manifest(mpath)
    cur, added, modified, removed = diff_tree(
        [Path(r) for r in roots],
        include_exts=include,
        ignore_dirs=ignore,
        mode=mode,
        prev=prev,
    )

    if not quiet:
        print(f"[incremental] files: prev={len(prev)}, cur={len(cur)}, added={len(added)}, modified={len(modified)}, removed={len(removed)}")

    if len(added) == 0 and len(modified) == 0 and len(removed) == 0 and ipath.exists():
        if not quiet:
            print("[incremental] No changes detected. Index is up-to-date. Skipping rebuild.")
        return {
            "skipped": True,
            "added": 0,
            "modified": 0,
            "removed": 0,
            "total": len(cur),
            "index_path": str(ipath),
            "manifest_path": str(mpath),
        }

    # Changes detected → run your existing full build.
    perform_full_build([str(Path(r)) for r in roots], str(ipath))

    # Only on successful build, persist manifest
    _save_manifest(mpath, cur)

    return {
        "skipped": False,
        "added": len(added),
        "modified": len(modified),
        "removed": len(removed),
        "total": len(cur),
        "index_path": str(ipath),
        "manifest_path": str(mpath),
    }