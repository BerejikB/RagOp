import argparse, json, sys, os, time, tempfile, shutil
from pathlib import Path
from typing import Any, Dict, List, Iterable, Tuple, Set

from .config import load_env_defaults
from .index import build_index
from .retrieve import retrieve
from .compose import compose_context, compose_ultra_compact

def _emit(obj: Any, as_json: bool) -> None:
    print(json.dumps(obj) if as_json else json.dumps(obj, indent=2))

def _common_parser(p: argparse.ArgumentParser):
    p.add_argument("--index", dest="index", help="Path to index file", default=None)
    p.add_argument("--k", dest="k", type=int, help="Number of results", default=None)
    p.add_argument("--snippet-max-chars", dest="snippet_max_chars", type=int, default=None)
    p.add_argument("--max-total-chars", dest="max_total_chars", type=int, default=None)
    p.add_argument("--json", dest="as_json", action="store_true", help="JSON output")

def _is_jsonl(path: Path) -> bool:
    return str(path).lower().endswith(".jsonl")

def _manifest_path(index_path: Path) -> Path:
    return index_path.with_suffix(index_path.suffix + ".manifest.json")

def _iter_files(paths: List[str]) -> Iterable[Path]:
    for p in map(Path, paths):
        if p.is_file():
            yield p
        elif p.is_dir():
            for r, _, files in os.walk(p):
                for f in files:
                    yield Path(r) / f

def _snapshot(paths: List[str]) -> Dict[str, Tuple[float, int]]:
    snap: Dict[str, Tuple[float, int]] = {}
    for f in _iter_files(paths):
        try:
            st = f.stat()
            snap[str(f)] = (st.st_mtime, st.st_size)
        except FileNotFoundError:
            pass
    return snap

def _load_manifest(path: Path) -> Dict[str, Tuple[float, int]]:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        return {k: tuple(v) for k, v in data.items()}
    except Exception:
        return {}

def _save_manifest(path: Path, snap: Dict[str, Tuple[float, int]]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(snap, fh, separators=(",", ":"))
    tmp.replace(path)

def _merge_jsonl(old_index: Path, new_parts: Path, out_path: Path, changed: Set[str], deleted: Set[str]) -> int:
    count = 0
    tmp = out_path.with_suffix(out_path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as out:
        # keep old lines not in changed/deleted
        if old_index.exists():
            with old_index.open("r", encoding="utf-8") as fh:
                for line in fh:
                    try:
                        obj = json.loads(line)
                        p = str(obj.get("path",""))
                        if p and p not in changed and p not in deleted:
                            out.write(json.dumps(obj, separators=(",", ":")) + "\n")
                            count += 1
                    except Exception:
                        pass
        # append new parts
        if new_parts.exists():
            with new_parts.open("r", encoding="utf-8") as fh2:
                for line in fh2:
                    try:
                        obj = json.loads(line)
                        out.write(json.dumps(obj, separators=(",", ":")) + "\n")
                        count += 1
                    except Exception:
                        pass
    tmp.replace(out_path)
    return count

def cmd_build(args: argparse.Namespace) -> int:
    cfg = load_env_defaults().with_cli_overrides(
        index=args.index, k=args.k,
        snippet_max_chars=args.snippet_max_chars,
        max_total_chars=args.max_total_chars,
    )
    idx_path = Path(cfg.index_path)
    incr = bool(getattr(args, "incremental", False))
    no_delete = bool(getattr(args, "no_delete", False))
    manifest = Path(getattr(args, "manifest", _manifest_path(idx_path)))
    try:
        if incr and _is_jsonl(idx_path):
            prev = _load_manifest(manifest)
            curr = _snapshot(args.paths)
            prev_keys = set(prev.keys()); curr_keys = set(curr.keys())
            changed: Set[str] = {p for p in curr_keys if (p not in prev) or (prev[p] != curr[p])}
            deleted: Set[str] = set() if no_delete else (prev_keys - curr_keys)
            if not changed and not deleted and idx_path.exists():
                _emit({"ok": True, "action": "build", "incremental": True, "changed_files": 0, "deleted_files": 0, "result": {"chunks": sum(1 for _ in idx_path.open('r',encoding='utf-8'))}}, args.as_json)
                return 0
            # build temp index for changed only
            tmpdir = Path(tempfile.mkdtemp(prefix="ragop_incr_"))
            try:
                tmp_index = tmpdir / "parts.jsonl"
                if changed:
                    build_index(sorted(list(changed)), tmp_index)
                merged_count = _merge_jsonl(idx_path, tmp_index, idx_path, changed, deleted)
            finally:
                shutil.rmtree(tmpdir, ignore_errors=True)
            _save_manifest(manifest, curr)
            _emit({"ok": True, "action": "build", "incremental": True, "changed_files": len(changed), "deleted_files": len(deleted), "result": {"chunks": merged_count}, "config": {"index_path": str(idx_path)}}, args.as_json)
            return 0
        # fallback: full build
        idx = build_index([str(Path(p)) for p in args.paths], idx_path)
        # refresh manifest if jsonl
        if _is_jsonl(idx_path):
            _save_manifest(manifest, _snapshot(args.paths))
        payload: Dict[str, Any] = {
            "ok": True, "action": "build", "incremental": False,
            "config": {"index_path": str(idx_path), "k": cfg.k,
                       "snippet_max_chars": cfg.snippet_max_chars,
                       "max_total_chars": cfg.max_total_chars},
            "result": {"chunks": len(idx.chunks)},
        }
        _emit(payload, args.as_json); return 0
    except Exception as e:
        _emit({"ok": False, "action": "build", "error": str(e)}, args.as_json); return 1

def cmd_query(args: argparse.Namespace) -> int:
    cfg = load_env_defaults().with_cli_overrides(index=args.index, k=args.k,
        snippet_max_chars=args.snippet_max_chars, max_total_chars=args.max_total_chars)
    try:
        results = retrieve(args.query, k=max(1, cfg.k), index_path=cfg.index_path, snippet_max_chars=cfg.snippet_max_chars)
        out: List[Dict[str, Any]] = [{"path": str(r.path), "start_line": r.start_line, "end_line": r.end_line, "score": r.score, "text": r.text} for r in results]
        _emit({"ok": True, "action": "query", "results": out}, args.as_json); return 0
    except Exception as e:
        _emit({"ok": False, "action": "query", "error": str(e)}, args.as_json); return 1

def cmd_compose(args: argparse.Namespace) -> int:
    cfg = load_env_defaults().with_cli_overrides(index=args.index, k=args.k,
        snippet_max_chars=args.snippet_max_chars, max_total_chars=args.max_total_chars)
    try:
        if getattr(args, "ultra_compact", False):
            ctx = compose_ultra_compact(question=args.question, k=max(1, cfg.k),
                snippet_max_chars=cfg.snippet_max_chars, max_total_chars=cfg.max_total_chars, index_path=cfg.index_path)
        else:
            ctx = compose_context(question=args.question, k=max(1, cfg.k),
                snippet_max_chars=cfg.snippet_max_chars, max_total_chars=cfg.max_total_chars, index_path=cfg.index_path)
        _emit({"ok": True, "action": "compose", "ultra_compact": bool(getattr(args, "ultra_compact", False)), "text": ctx.text, "citations": ctx.citations}, args.as_json); return 0
    except Exception as e:
        _emit({"ok": False, "action": "compose", "error": str(e)}, args.as_json); return 1

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ragop", description="RagOp CLI")
    sub = p.add_subparsers(dest="cmd", required=True)
    pb = sub.add_parser("build", help="Build index from paths")
    _common_parser(pb)
    pb.add_argument("paths", nargs="+", help="Files or directories to index")
    pb.add_argument("--incremental", action="store_true", help="Update JSONL index by changed files only")
    pb.add_argument("--manifest", help="Override manifest path (defaults to index.jsonl.manifest.json)")
    pb.add_argument("--no-delete", action="store_true", help="Do not purge entries for deleted files")
    pb.set_defaults(func=cmd_build)
    pq = sub.add_parser("query", help="Query the index"); _common_parser(pq)
    pq.add_argument("query", help="Search text"); pq.set_defaults(func=cmd_query)
    pc = sub.add_parser("compose", help="Compose context (ultra-compact optional)"); _common_parser(pc)
    pc.add_argument("question", help="Question to answer")
    pc.add_argument("--ultra-compact", dest="ultra_compact", action="store_true", help="Return only the best single snippet")
    pc.set_defaults(func=cmd_compose); return p

def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    parser = build_parser(); args = parser.parse_args(argv); return args.func(args)

if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())