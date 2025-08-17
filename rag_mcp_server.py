#!/usr/bin/env python3
"""
RAG MCP Server
- TCP JSON line protocol on 127.0.0.1:8765
- Commands:
  • ping -> {ok:true}
  • stop -> shutdown server
  • build {paths:[...], index:str}
  • query {query:str, k:int=5, index:str}
  • compose {question:str, k:int=1, snippet_max_chars:int=500, max_total_chars:int=1200, index:str}

Implementation notes:
- Invokes goose-rag CLI in the RAG venv for stability.
- Defaults:
  host=127.0.0.1, port=8765
  CLI=/mnt/k/GOOSE/RAG/.venv_rag/bin/goose-rag
  INDEX=/mnt/k/GOOSE/RAG/.index/rag_index.pkl
"""
from __future__ import annotations
import json
import os
import socket
import socketserver
import subprocess
import sys
import threading
from typing import Any, Dict, List

HOST = os.environ.get("RAG_MCP_HOST", "127.0.0.1")
PORT = int(os.environ.get("RAG_MCP_PORT", "8765"))
GOOSE_RAG = os.environ.get("GOOSE_RAG_CLI", "/mnt/k/GOOSE/RAG/.venv_rag/bin/goose-rag")
DEFAULT_INDEX = os.environ.get("RAG_INDEX", "/mnt/k/GOOSE/RAG/.index/rag_index.pkl")

TRIM_STDIO_AT = int(os.environ.get("RAG_MCP_STDIO_TRIM", "200000"))  # avoid unbounded payloads
CMD_TIMEOUT = int(os.environ.get("RAG_MCP_CMD_TIMEOUT", "180"))      # seconds per command

_shutdown_event = threading.Event()


def _which_cli() -> str:
    if os.path.exists(GOOSE_RAG) and os.access(GOOSE_RAG, os.X_OK):
        return GOOSE_RAG
    # Fallback: rely on PATH
    return "goose-rag"


def _run_cli(args: List[str]) -> Dict[str, Any]:
    cmd = [_which_cli()] + args
    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=CMD_TIMEOUT,
            check=False,
        )
        out = (proc.stdout or "")
        err = (proc.stderr or "")
        if len(out) > TRIM_STDIO_AT:
            out = out[:TRIM_STDIO_AT] + "\n... [trimmed]"
        if len(err) > TRIM_STDIO_AT:
            err = err[:TRIM_STDIO_AT] + "\n... [trimmed]"
        return {"ok": proc.returncode == 0, "code": proc.returncode, "stdout": out, "stderr": err, "cmd": cmd}
    except subprocess.TimeoutExpired as te:
        return {"ok": False, "code": -1, "stdout": te.stdout or "", "stderr": f"timeout: {te}", "cmd": cmd}
    except Exception as e:
        return {"ok": False, "code": -2, "stdout": "", "stderr": f"exception: {e}", "cmd": cmd}


def handle_ping(_: Dict[str, Any]) -> Dict[str, Any]:
    return {"ok": True, "pong": True}


def handle_stop(_: Dict[str, Any]) -> Dict[str, Any]:
    # Trigger graceful shutdown
    _shutdown_event.set()
    # Shutdown must be invoked from outside the handler thread; the server loop watches the event.
    return {"ok": True, "stopping": True}


def handle_build(payload: Dict[str, Any]) -> Dict[str, Any]:
    paths = payload.get("paths") or ["/mnt/k/GOOSE"]
    if not isinstance(paths, list) or not paths:
        return {"ok": False, "error": "paths must be a non-empty list"}
    index = payload.get("index") or DEFAULT_INDEX
    args = ["build", *paths, "--index", index]
    res = _run_cli(args)
    return res


def handle_query(payload: Dict[str, Any]) -> Dict[str, Any]:
    query = payload.get("query")
    if not query:
        return {"ok": False, "error": "query is required"}
    k = int(payload.get("k", 5))
    index = payload.get("index") or DEFAULT_INDEX
    args = ["query", query, "--k", str(k), "--index", index, "--jsonl"]
    res = _run_cli(args)
    if not res.get("ok"):
        return res
    # Parse JSONL
    items: List[Dict[str, Any]] = []
    for line in res.get("stdout", "").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            items.append(json.loads(line))
        except Exception:
            # include raw line if parsing fails
            items.append({"raw": line})
    return {"ok": True, "results": items, "k": k, "index": index}


def handle_compose(payload: Dict[str, Any]) -> Dict[str, Any]:
    question = payload.get("question") or payload.get("query")
    if not question:
        return {"ok": False, "error": "question (or query) is required"}
    k = int(payload.get("k", 1))
    snippet_max = int(payload.get("snippet_max_chars", 500))
    total_max = int(payload.get("max_total_chars", 1200))
    index = payload.get("index") or DEFAULT_INDEX
    args = [
        "compose",
        question,
        "--ultra-compact",
        "--k", str(k),
        "--snippet-max-chars", str(snippet_max),
        "--max-total-chars", str(total_max),
        "--index", index,
        "--json",
    ]
    res = _run_cli(args)
    if not res.get("ok"):
        return res
    try:
        data = json.loads(res.get("stdout", "") or "{}")
    except Exception as e:
        return {"ok": False, "error": f"failed to parse compose JSON: {e}", "stdout": res.get("stdout", ""), "stderr": res.get("stderr", "")}
    return {"ok": True, "data": data}


HANDLERS = {
    "ping": handle_ping,
    "stop": handle_stop,
    "build": handle_build,
    "query": handle_query,
    "compose": handle_compose,
}


class JSONLineHandler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        peer = f"{self.client_address[0]}:{self.client_address[1]}"
        while True:
            line = self.rfile.readline()
            if not line:
                break
            try:
                text = line.decode("utf-8", errors="replace").strip()
            except Exception:
                text = line.decode(errors="replace").strip()
            if not text:
                continue
            try:
                payload = json.loads(text)
            except Exception as e:
                self._send_json({"ok": False, "error": f"invalid JSON: {e}"})
                continue
            cmd = (payload.get("cmd") or payload.get("command") or payload.get("action") or "").lower()
            handler = HANDLERS.get(cmd)
            if not handler:
                self._send_json({"ok": False, "error": f"unknown cmd: {cmd}"})
                continue
            try:
                resp = handler(payload)
            except Exception as e:  # noqa: BLE001
                resp = {"ok": False, "error": f"handler exception: {e}"}
            self._send_json(resp)
            if cmd == "stop":
                break

    def _send_json(self, obj: Dict[str, Any]) -> None:
        data = (json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8", errors="replace")
        try:
            self.wfile.write(data)
            self.wfile.flush()
        except BrokenPipeError:
            pass


class ThreadingTCPServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True



def serve_stdio() -> None:
    """Serve simple JSON line protocol over stdio.
    Accepts one JSON object per line with keys: cmd|command|action and optional payload.
    Replies with one JSON object per line.
    """
    sys.stdout.write("[rag_mcp_server] stdio mode\n")
    sys.stdout.flush()
    while not _shutdown_event.is_set():
        line = sys.stdin.readline()
        if not line:
            break
        text = line.strip()
        if not text:
            continue
        try:
            payload = json.loads(text)
        except Exception as e:
            sys.stdout.write(json.dumps({"ok": False, "error": f"invalid JSON: {e}"}) + "\n")
            sys.stdout.flush()
            continue

        cmd = (payload.get("cmd") or payload.get("command") or payload.get("action") or "").lower()
        handler = HANDLERS.get(cmd)
        if not handler:
            # Unknown command – keep the original behaviour but without stray argv logic
            sys.stdout.write(json.dumps({"ok": False, "error": f"unknown cmd: {cmd}"}) + "\n")
            sys.stdout.flush()
            continue

        try:
            resp = handler(payload)
        except Exception as e:  # noqa: BLE001
            resp = {"ok": False, "error": f"handler exception: {e}"}
        sys.stdout.write(json.dumps(resp) + "\n")
        sys.stdout.flush()
        if cmd == "stop":
            break
def serve(host: str = HOST, port: int = PORT) -> None:
    with ThreadingTCPServer((host, port), JSONLineHandler) as server:
        sys.stdout.write(f"[rag_mcp_server] listening on {host}:{port}\n")
        sys.stdout.flush()

        # Main loop with shutdown watch
        t = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.5}, daemon=True)
        t.start()
        try:
            while not _shutdown_event.is_set():
                _shutdown_event.wait(timeout=1.0)
        except KeyboardInterrupt:
            sys.stdout.write("[rag_mcp_server] KeyboardInterrupt -> shutdown\n")
            sys.stdout.flush()
        finally:
            server.shutdown()
            server.server_close()
            sys.stdout.write("[rag_mcp_server] stopped\n")
            sys.stdout.flush()


if __name__ == "__main__":
    # Optional CLI args: [--stdio] [host] [port]
    h = HOST
    p = PORT
    argv = sys.argv[1:]

    if "--help" in argv or "-h" in argv:
        sys.stdout.write(
            "Usage: rag_mcp_server.py [--stdio] [host] [port]\n"
            "  --stdio        Serve JSON line protocol on stdio (no TCP bind)\n"
            "  host port      TCP bind address (defaults 127.0.0.1 8765)\n"
        )
        sys.stdout.flush()
        sys.exit(0)

    if "--stdio" in argv:
        serve_stdio()
        sys.exit(0)

    # Remove flags and parse host/port
    args = [a for a in argv if not a.startswith("-")]
    if len(args) >= 1:
        h = args[0]
    if len(args) >= 2:
        try:
            p = int(args[1])
        except ValueError:
            sys.stderr.write("invalid port; using default 8765\n")
            p = PORT
    serve(h, p)
