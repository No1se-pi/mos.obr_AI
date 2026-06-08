from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
import re
from typing import Any


class WebTranscriptStore:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir

    def append_event(
        self,
        *,
        site_user_id: str,
        session_id: str | None,
        role: str,
        text: str,
        mode: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        self.base_dir.mkdir(parents=True, exist_ok=True)

        event = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "channel": "web",
            "site_user_id": site_user_id,
            "session_id": session_id,
            "role": role,
            "mode": mode,
            "text": text,
            "extra": extra or {},
        }

        jsonl_path = self.base_dir / f"{self._safe_name(site_user_id)}.jsonl"
        txt_path = self.base_dir / f"{self._safe_name(site_user_id)}.txt"

        with jsonl_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")

        with txt_path.open("a", encoding="utf-8") as f:
            f.write(self._format_pretty_line(event) + "\n")

    @staticmethod
    def _safe_name(value: str) -> str:
        return re.sub(r"[^a-zA-Z0-9_.-]+", "_", value)

    @staticmethod
    def _format_pretty_line(event: dict[str, Any]) -> str:
        ts = event["timestamp_utc"]
        session_id = event.get("session_id") or "-"
        mode = event.get("mode") or "-"
        role = event["role"]
        text = str(event["text"]).replace("\n", " ").strip()
        return f"[{ts}] [{session_id}] [{mode}] {role.upper()}: {text}"
