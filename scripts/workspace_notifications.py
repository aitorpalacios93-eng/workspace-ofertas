#!/usr/bin/env python3
"""Telegram notifications for relevant workspace events."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request


class TelegramNotifier:
    def __init__(self) -> None:
        self.bot_token = os.getenv("WORKSPACE_TELEGRAM_BOT_TOKEN", "").strip()
        self.chat_id = os.getenv("WORKSPACE_TELEGRAM_CHAT_ID", "").strip()

    @property
    def configured(self) -> bool:
        return bool(self.bot_token and self.chat_id)

    def send(self, text: str) -> tuple[bool, str]:
        if not self.configured:
            return False, "telegram-not-configured"

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        data = urllib.parse.urlencode(
            {
                "chat_id": self.chat_id,
                "text": text[:4000],
                "disable_web_page_preview": "true",
            }
        ).encode("utf-8")

        request = urllib.request.Request(url, data=data, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                payload = json.loads(response.read().decode("utf-8", errors="replace"))
                if payload.get("ok"):
                    return True, "sent"
                return False, payload.get("description", "telegram-error")
        except urllib.error.URLError as exc:
            return False, str(exc)
