#!/usr/bin/env python3
"""Local web server for WORKSPACE_OFERTAS."""

from __future__ import annotations

import argparse
import json
import mimetypes
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from workspace_core import WorkspaceEngine


WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
WEBAPP_DIR = WORKSPACE_ROOT / "webapp"


class WorkerLoop(threading.Thread):
    def __init__(
        self,
        engine: WorkspaceEngine,
        stop_event: threading.Event,
        poll_interval: int = 5,
    ):
        super().__init__(daemon=True)
        self.engine = engine
        self.stop_event = stop_event
        self.poll_interval = poll_interval

    def run(self) -> None:
        while not self.stop_event.is_set():
            result = self.engine.run_once()
            wait_seconds = 1 if result.get("processed") else self.poll_interval
            self.stop_event.wait(wait_seconds)


class AutoDiscoveryLoop(threading.Thread):
    """Discovers leads automatically via SerpAPI every 5 minutes."""

    INTERVAL = 300  # seconds

    def __init__(self, engine: WorkspaceEngine, stop_event: threading.Event):
        super().__init__(daemon=True)
        self.engine = engine
        self.stop_event = stop_event

    def run(self) -> None:
        try:
            from automatic_worker import AutomaticWorker
            worker = AutomaticWorker()
        except Exception as exc:
            print(f"[AutoDiscovery] Failed to init AutomaticWorker: {exc}")
            return

        print("[AutoDiscovery] Started — discovering leads every 5 minutes")
        while not self.stop_event.is_set():
            try:
                leads = worker.discover_leads()
                injected = 0
                for lead in leads:
                    existing = self.engine.state.find_prospect_by_domain(lead["domain"])
                    if not existing:
                        self.engine.create_prospect({
                            "company_name": lead["empresa"],
                            "website": f"https://{lead['domain']}",
                            "sector": lead.get("sector", "general"),
                            "recommended": False,
                            "country": "ES",
                        })
                        injected += 1
                if injected:
                    print(f"[AutoDiscovery] Injected {injected} new leads")
            except Exception as exc:
                print(f"[AutoDiscovery] Error: {exc}")
            self.stop_event.wait(self.INTERVAL)


def build_handler(engine: WorkspaceEngine):
    class Handler(BaseHTTPRequestHandler):
        server_version = "WorkspaceServer/0.1"

        def _send_json(self, payload: dict, status: int = 200) -> None:
            body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_file(self, path: Path) -> None:
            if not path.exists() or not path.is_file():
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            content = path.read_bytes()
            mime, _ = mimetypes.guess_type(str(path))
            self.send_response(200)
            self.send_header("Content-Type", mime or "application/octet-stream")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        def _read_json(self) -> dict:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0:
                return {}
            raw = self.rfile.read(length)
            return json.loads(raw.decode("utf-8"))

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path == "/api/health":
                self._send_json({"ok": True})
                return
            if parsed.path == "/api/dashboard":
                self._send_json(engine.dashboard())
                return
            if parsed.path == "/api/prospects":
                self._send_json({"prospects": engine.state.list_records("prospects")})
                return
            if parsed.path.startswith("/api/prospects/"):
                prospect_id = parsed.path.split("/")[-1]
                detail = engine.prospect_detail(prospect_id)
                if detail is None:
                    self._send_json({"error": "Prospect not found"}, status=404)
                    return
                self._send_json(detail)
                return
            if parsed.path == "/api/messages":
                self._send_json({"messages": engine.state.list_records("messages")})
                return

            target = WEBAPP_DIR / (
                "index.html" if parsed.path == "/" else parsed.path.lstrip("/")
            )
            self._send_file(target)

        def do_POST(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path == "/api/prospects":
                payload = self._read_json()
                company_name = payload.get("company_name", "").strip()
                website = payload.get("website", "").strip()
                socials = payload.get("socials", {}) or {}
                if (
                    not company_name
                    and not website
                    and not any(
                        value.strip()
                        for value in socials.values()
                        if isinstance(value, str)
                    )
                ):
                    self._send_json(
                        {
                            "error": "Provide company name, website or at least one social URL."
                        },
                        status=400,
                    )
                    return
                record = engine.create_prospect(payload)
                self._send_json({"prospect": record}, status=201)
                return

            if parsed.path == "/api/messages":
                payload = self._read_json()
                if not payload.get("content", "").strip():
                    self._send_json(
                        {"error": "Message content is required."}, status=400
                    )
                    return
                record = engine.add_message(payload)
                self._send_json({"message": record}, status=201)
                return

            if parsed.path.startswith("/api/prospects/") and parsed.path.endswith(
                "/update"
            ):
                payload = self._read_json()
                parts = [item for item in parsed.path.split("/") if item]
                if len(parts) < 4:
                    self._send_json(
                        {"error": "Invalid prospect update path"}, status=400
                    )
                    return
                prospect_id = parts[2]
                record = engine.update_prospect_controls(prospect_id, payload)
                if record is None:
                    self._send_json({"error": "Prospect not found"}, status=404)
                    return
                self._send_json({"prospect": record})
                return

            if parsed.path == "/api/worker/run-once":
                result = engine.run_once()
                self._send_json(result)
                return

            self._send_json({"error": "Unknown endpoint"}, status=404)

        def log_message(self, format: str, *args) -> None:  # noqa: A003
            return

    return Handler


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the local WORKSPACE_OFERTAS webapp and worker."
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8787, type=int)
    parser.add_argument("--poll-interval", default=5, type=int)
    parser.add_argument("--without-worker", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    engine = WorkspaceEngine(WORKSPACE_ROOT)
    handler = build_handler(engine)
    server = ThreadingHTTPServer((args.host, args.port), handler)
    stop_event = threading.Event()
    worker = None

    auto_discovery = None
    if not args.without_worker:
        worker = WorkerLoop(
            engine=engine, stop_event=stop_event, poll_interval=args.poll_interval
        )
        worker.start()
        auto_discovery = AutoDiscoveryLoop(engine=engine, stop_event=stop_event)
        auto_discovery.start()

    print(f"WORKSPACE_OFERTAS running on http://{args.host}:{args.port}")
    print(f"Auto worker enabled: {not args.without_worker}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop_event.set()
        server.server_close()
        if worker is not None:
            worker.join(timeout=1)
        if auto_discovery is not None:
            auto_discovery.join(timeout=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
