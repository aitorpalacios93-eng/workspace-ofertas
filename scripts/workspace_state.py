#!/usr/bin/env python3
"""Persistent state helpers for the workspace dashboard."""

from __future__ import annotations

import copy
import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class WorkspaceState:
    FILE_DEFAULTS = {
        "prospects": [],
        "jobs": [],
        "events": [],
        "messages": [],
        "settings": {
            "auto_worker": True,
            "poll_interval_seconds": 5,
        },
    }

    def __init__(self, workspace_root: Path):
        self.workspace_root = workspace_root
        self.state_dir = workspace_root / "state"
        self.lock = threading.RLock()
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_files()

    def _ensure_files(self) -> None:
        for name, default in self.FILE_DEFAULTS.items():
            path = self.state_dir / f"{name}.json"
            if not path.exists():
                path.write_text(json.dumps(default, indent=2), encoding="utf-8")

    def _path(self, name: str) -> Path:
        return self.state_dir / f"{name}.json"

    def _read(self, name: str) -> Any:
        path = self._path(name)
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return copy.deepcopy(self.FILE_DEFAULTS[name])

    def _write(self, name: str, payload: Any) -> None:
        path = self._path(name)
        temp_path = path.with_suffix(".json.tmp")
        temp_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8"
        )
        temp_path.replace(path)

    def _mutate_list(self, name: str, mutator):
        with self.lock:
            items = self._read(name)
            result = mutator(items)
            self._write(name, items)
            return copy.deepcopy(result)

    def list_records(self, name: str) -> list[dict[str, Any]]:
        with self.lock:
            payload = self._read(name)
            return copy.deepcopy(payload)

    def read_settings(self) -> dict[str, Any]:
        with self.lock:
            return copy.deepcopy(self._read("settings"))

    def update_settings(self, patch: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            payload = self._read("settings")
            payload.update(patch)
            self._write("settings", payload)
            return copy.deepcopy(payload)

    def create_prospect(self, payload: dict[str, Any]) -> dict[str, Any]:
        prospect = {
            "id": str(uuid.uuid4()),
            "company_name": payload.get("company_name", "").strip(),
            "website": payload.get("website", "").strip(),
            "country": payload.get("country", "").strip().upper() or "UNKNOWN",
            "sector": payload.get("sector", "").strip(),
            "notes": payload.get("notes", "").strip(),
            "socials": payload.get("socials", {}),
            "recommended": bool(payload.get("recommended")),
            "recommendation_note": payload.get("recommendation_note", "").strip(),
            "route_override": payload.get("route_override") or None,
            "status": "queued",
            "route": None,
            "fit_score": None,
            "fit_band": None,
            "fit_score_raw": None,
            "fit_band_raw": None,
            "language": None,
            "currency": None,
            "discovered_website": None,
            "decision_mode": "automatic",
            "strategic_angle": None,
            "strategic_angle_label": None,
            "proposal_ready": False,
            "reply_ready": False,
            "created_at": now_iso(),
            "updated_at": now_iso(),
            "last_processed_at": None,
            # AACORE fields
            "auditoria_score": None,
            "auditoria_resumen": None,
            "prioridad": None,
            "contacto_email": None,
            "asunto_email": None,
            "email_frio": None,
            "mensaje_linkedin": None,
            "aacore_status": "pending",
        }

        def mutator(items: list[dict[str, Any]]):
            items.insert(0, prospect)
            return prospect

        return self._mutate_list("prospects", mutator)

    def update_prospect(
        self, prospect_id: str, patch: dict[str, Any]
    ) -> dict[str, Any] | None:
        patch = copy.deepcopy(patch)
        patch["updated_at"] = now_iso()

        def mutator(items: list[dict[str, Any]]):
            for item in items:
                if item["id"] == prospect_id:
                    item.update(patch)
                    return item
            return None

        return self._mutate_list("prospects", mutator)

    def get_prospect(self, prospect_id: str) -> dict[str, Any] | None:
        for item in self.list_records("prospects"):
            if item["id"] == prospect_id:
                return item
        return None

    def find_prospect_by_domain(self, domain: str) -> dict[str, Any] | None:
        """Find a prospect by website domain (for dedup in automatic worker)."""
        domain_normalized = domain.lower().replace("https://", "").replace("http://", "").split("/")[0]
        for item in self.list_records("prospects"):
            website = item.get("website", "").lower().replace("https://", "").replace("http://", "").split("/")[0]
            if website == domain_normalized:
                return item
        return None

    def list_pending_prospects(self) -> list[dict[str, Any]]:
        prospects = self.list_records("prospects")
        return [item for item in prospects if item.get("status") in {"queued", "retry"}]

    def create_job(
        self,
        job_type: str,
        *,
        prospect_id: str | None = None,
        message_id: str | None = None,
    ) -> dict[str, Any]:
        job = {
            "id": str(uuid.uuid4()),
            "type": job_type,
            "prospect_id": prospect_id,
            "message_id": message_id,
            "status": "running",
            "summary": None,
            "error": None,
            "created_at": now_iso(),
            "updated_at": now_iso(),
            "ended_at": None,
        }

        def mutator(items: list[dict[str, Any]]):
            items.insert(0, job)
            return job

        return self._mutate_list("jobs", mutator)

    def finish_job(
        self,
        job_id: str,
        *,
        status: str,
        summary: str | None = None,
        error: str | None = None,
    ) -> dict[str, Any] | None:
        def mutator(items: list[dict[str, Any]]):
            for item in items:
                if item["id"] == job_id:
                    item.update(
                        {
                            "status": status,
                            "summary": summary,
                            "error": error,
                            "updated_at": now_iso(),
                            "ended_at": now_iso(),
                        }
                    )
                    return item
            return None

        return self._mutate_list("jobs", mutator)

    def add_event(
        self,
        *,
        event_type: str,
        message: str,
        level: str = "info",
        prospect_id: str | None = None,
        data: dict[str, Any] | None = None,
        telegram_relevant: bool = False,
    ) -> dict[str, Any]:
        event = {
            "id": str(uuid.uuid4()),
            "type": event_type,
            "message": message,
            "level": level,
            "prospect_id": prospect_id,
            "data": data or {},
            "telegram_relevant": telegram_relevant,
            "created_at": now_iso(),
        }

        def mutator(items: list[dict[str, Any]]):
            items.insert(0, event)
            return event

        return self._mutate_list("events", mutator)

    def add_message(self, payload: dict[str, Any]) -> dict[str, Any]:
        message = {
            "id": str(uuid.uuid4()),
            "prospect_id": payload.get("prospect_id"),
            "channel": payload.get("channel", "manual"),
            "direction": payload.get("direction", "inbound"),
            "content": payload.get("content", "").strip(),
            "status": "new",
            "reply_draft": None,
            "created_at": now_iso(),
            "updated_at": now_iso(),
        }

        def mutator(items: list[dict[str, Any]]):
            items.insert(0, message)
            return message

        return self._mutate_list("messages", mutator)

    def update_message(
        self, message_id: str, patch: dict[str, Any]
    ) -> dict[str, Any] | None:
        patch = copy.deepcopy(patch)
        patch["updated_at"] = now_iso()

        def mutator(items: list[dict[str, Any]]):
            for item in items:
                if item["id"] == message_id:
                    item.update(patch)
                    return item
            return None

        return self._mutate_list("messages", mutator)

    def list_pending_messages(self) -> list[dict[str, Any]]:
        messages = self.list_records("messages")
        return [
            item
            for item in messages
            if item.get("direction") == "inbound" and item.get("status") == "new"
        ]
