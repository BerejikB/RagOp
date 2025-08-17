#!/usr/bin/env python3
import os, sys, json, shlex, subprocess, time, threading
from datetime import datetime
from typing import Optional, Dict, Any

# MCP SDK
try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
except Exception as e:
    sys.stderr.write(f"Failed to import mcp SDK: {e}\n")
    sys.exit(1)

# Env-first config with sensible defaults
RAG_ROOT = os.environ.get("RAG_ROOT", "/mnt/k/GOOSE/RAG")
RAG_CLI = os.environ.get("RAG_CLI", os.path.join(RAG_ROOT, "scripts", "goose_rag.sh"))
RAG_INDEX = os.environ.get("RAG_INDEX", os.path.join(RAG_ROOT, ".index", "rag_index.pkl"))
RAG_LOGDIR = os.environ.get("RAG_LOGDIR", os.path.join(RAG_ROOT, ".logs"))
RAG_K = int(os.environ.get("RAG_K", "1"))
RAG_SNIPPET_MAX_CHARS = int(os.environ.get("RAG_SNIPPET_MAX_CHARS", "500"))
RAG_MAX_TOTAL_CHARS = int(os.environ.get("RAG_MAX_TOTAL_CHARS", "1200"))
RAG_AUTOBUILD = os.environ.get("RAG_AUTOBUILD", "0")
TRIM_CHARS = int(os.environ.get("RAG_TRIM_CHARS", str(RAG_SNIPPET_MAX_CHARS)))
PYTHON_BIN = os.environ.get("PYTHON_BIN", os.path.join(RAG_ROOT, ".venv_rag", "bin", "python"))

os.makedirs(RAG_LOGDIR, exist_ok=True)
LOG_PATH = os.path.join(RAG_LOGDIR, "rag_mcp_server.log")
_log_lock = threading.Lock()

def _ts() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")

def _trim(s: str, n: int = TRIM_CHARS) -> str:
    if s is None:
        return ""
    if len(s) <= n:
        return s
    return s[:n]

def _jlog(event: Dict[str, Any]) -> None:
    try:
        with _log_lock:
            with open(LOG_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")
    except Exception:
        pass

# Run goose-rag via wrapper script; capture stdout/stderr fully, but return trimmed to client

def run_rag_cli(args: str, timeout: Optional[int] = 120) -> Dict[str, Any]:
    cmd = f"{shlex.quote(RAG_CLI)} {args}"
    start = time.time()
    proc = subprocess.Popen(["bash", "-lc", cmd], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        out, err = proc.communicate(timeout=timeout)
        code = proc.returncode
    except subprocess.TimeoutExpired:
        proc.kill()
        out, err, code = "", "timeout", 124
    dur = round(time.time() - start, 3)
    evt = {
        "ts": _ts(),
        "action": "rag_cli",
        "cmd": cmd,
        "code": code,
        "ms": int(dur * 1000),
        "stdout": out,
        "stderr": err,
    }
    _jlog(evt)
    return {"code": code, "stdout": _trim(out), "stderr": _trim(err)}

server = Server("rag")

@server.tool()
async def rag_build(paths: Optional[str] = None, index: Optional[str] = None) -> Dict[str, Any]:
    """Build the RAG index. Uses env defaults if not provided."""
    p = shlex.quote(paths or RAG_ROOT)
    ix = shlex.quote(index or RAG_INDEX)
    return run_rag_cli(f"build {p} --index {ix}")

@server.tool()
async def rag_query(query: str, k: Optional[int] = None, index: Optional[str] = None) -> Dict[str, Any]:
    """Query the RAG index; returns top-k tiny snippet(s)."""
    kk = int(k if k is not None else RAG_K)
    ix = shlex.quote(index or RAG_INDEX)
    q = shlex.quote(query)
    return run_rag_cli(f"query {q} --k {kk} --index {ix}")

@server.tool()
async def rag_compose(question: str, k: Optional[int] = None, snippet_max_chars: Optional[int] = None,
                      max_total_chars: Optional[int] = None, ultra_compact: bool = True,
                      index: Optional[str] = None) -> Dict[str, Any]:
    """Compose ultra-compact context for a question with citations."""
    kk = int(k if k is not None else RAG_K)
    sm = int(snippet_max_chars if snippet_max_chars is not None else RAG_SNIPPET_MAX_CHARS)
    mt = int(max_total_chars if max_total_chars is not None else RAG_MAX_TOTAL_CHARS)
    ix = shlex.quote(index or RAG_INDEX)
    q = shlex.quote(question)
    flags = "--ultra-compact" if ultra_compact else ""
    return run_rag_cli(f"compose {q} --k {kk} --snippet-max-chars {sm} --max-total-chars {mt} {flags} --index {ix}")

async def main() -> None:
    _jlog({"ts": _ts(), "event": "server_start", "rag_root": RAG_ROOT, "cli": RAG_CLI, "index": RAG_INDEX})
    await stdio_server.run(server)

if __name__ == "__main__":
    import asyncio
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        _jlog({"ts": _ts(), "event": "server_stop", "reason": "KeyboardInterrupt"})
