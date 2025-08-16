import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

from .config import load_env_defaults
from .index import build_index
from .retrieve import retrieve
from .compose import compose_context, compose_ultra_compact


def _emit(obj: Any, as_json: bool) -> None:
    print(json.dumps(obj) if as_json else json.dumps(obj, indent=2))


def _common_parser(parser: argparse.ArgumentParser):
    parser.add_argument("--index", dest="index", help="Path to index file", default=None)
    parser.add_argument("--k", dest="k", type=int, help="Number of results", default=None)
    parser.add_argument(
        "--snippet-max-chars", dest="snippet_max_chars", type=int, default=None
    )
    parser.add_argument("--max-total-chars", dest="max_total_chars", type=int, default=None)
    parser.add_argument("--json", dest="as_json", action="store_true", help="JSON output")


def cmd_build(args: argparse.Namespace) -> int:
    cfg = load_env_defaults().with_cli_overrides(
        index=args.index,
        k=args.k,
        snippet_max_chars=args.snippet_max_chars,
        max_total_chars=args.max_total_chars,
    )
    try:
        idx = build_index([str(Path(p)) for p in args.paths], cfg.index_path)
        payload: Dict[str, Any] = {
            "ok": True,
            "action": "build",
            "config": {
                "index_path": str(cfg.index_path),
                "k": cfg.k,
                "snippet_max_chars": cfg.snippet_max_chars,
                "max_total_chars": cfg.max_total_chars,
            },
            "result": {"chunks": len(idx.chunks)},
        }
        _emit(payload, args.as_json)
        return 0
    except Exception as e:
        _emit({"ok": False, "action": "build", "error": str(e)}, args.as_json)
        return 1


def cmd_query(args: argparse.Namespace) -> int:
    cfg = load_env_defaults().with_cli_overrides(
        index=args.index,
        k=args.k,
        snippet_max_chars=args.snippet_max_chars,
        max_total_chars=args.max_total_chars,
    )
    try:
        results = retrieve(
            args.query,
            k=max(1, cfg.k),
            index_path=cfg.index_path,
            snippet_max_chars=cfg.snippet_max_chars,
        )
        out: List[Dict[str, Any]] = [
            {
                "path": str(r.path),
                "start_line": r.start_line,
                "end_line": r.end_line,
                "score": r.score,
                "text": r.text,
            }
            for r in results
        ]
        _emit({"ok": True, "action": "query", "results": out}, args.as_json)
        return 0
    except Exception as e:
        _emit({"ok": False, "action": "query", "error": str(e)}, args.as_json)
        return 1


def cmd_compose(args: argparse.Namespace) -> int:
    cfg = load_env_defaults().with_cli_overrides(
        index=args.index,
        k=args.k,
        snippet_max_chars=args.snippet_max_chars,
        max_total_chars=args.max_total_chars,
    )
    try:
        if getattr(args, "ultra_compact", False):
            ctx = compose_ultra_compact(
                question=args.question,
                k=max(1, cfg.k),
                snippet_max_chars=cfg.snippet_max_chars,
                max_total_chars=cfg.max_total_chars,
                index_path=cfg.index_path,
            )
        else:
            ctx = compose_context(
                question=args.question,
                k=max(1, cfg.k),
                snippet_max_chars=cfg.snippet_max_chars,
                max_total_chars=cfg.max_total_chars,
                index_path=cfg.index_path,
            )
        _emit(
            {
                "ok": True,
                "action": "compose",
                "ultra_compact": bool(getattr(args, "ultra_compact", False)),
                "text": ctx.text,
                "citations": ctx.citations,
            },
            args.as_json,
        )
        return 0
    except Exception as e:
        _emit({"ok": False, "action": "compose", "error": str(e)}, args.as_json)
        return 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ragop", description="RagOp CLI")
    sub = p.add_subparsers(dest="cmd", required=True)

    pb = sub.add_parser("build", help="Build index from paths")
    _common_parser(pb)
    pb.add_argument("paths", nargs="+", help="Files or directories to index")
    pb.set_defaults(func=cmd_build)

    pq = sub.add_parser("query", help="Query the index")
    _common_parser(pq)
    pq.add_argument("query", help="Search text")
    pq.set_defaults(func=cmd_query)

    pc = sub.add_parser("compose", help="Compose context (ultra-compact optional)")
    _common_parser(pc)
    pc.add_argument("question", help="Question to answer")
    pc.add_argument(
        "--ultra-compact",
        dest="ultra_compact",
        action="store_true",
        help="Return only the best single snippet",
    )
    pc.set_defaults(func=cmd_compose)

    return p


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
