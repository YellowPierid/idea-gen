import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class RunLogger:
    """Dual-output logger: console progress + structured JSON file log."""

    def __init__(self, run_dir: Path):
        self.run_dir = run_dir
        self.events: list[dict[str, Any]] = []
        self._console = logging.getLogger("idea_gen")
        if not self._console.handlers:
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
            self._console.addHandler(handler)
            self._console.setLevel(logging.INFO)

    def log_event(self, node: str, event_type: str, details: dict[str, Any] | None = None):
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "node": node,
            "event_type": event_type,
            "details": details or {},
        }
        self.events.append(event)

    def info(self, message: str):
        self._console.info(message)

    def warn(self, message: str):
        self._console.warning(message)

    def error(self, message: str):
        self._console.error(message)

    def node_start(self, node: str, **details):
        self.log_event(node, "node_start", details)
        self.info(f"--- {node} started ---")

    def node_end(self, node: str, **details):
        self.log_event(node, "node_end", details)
        self.info(f"--- {node} completed ---")

    def llm_call(self, node: str, model: str, prompt_len: int, response_len: int):
        self.log_event(node, "llm_call", {
            "model": model,
            "prompt_length": prompt_len,
            "response_length": response_len,
        })

    def schema_ok(self, node: str, idea_id: str):
        self.log_event(node, "schema_validation", {"idea_id": idea_id, "result": "ok"})

    def schema_fail(self, node: str, idea_id: str, error: str):
        self.log_event(node, "schema_validation", {"idea_id": idea_id, "result": "fail", "error": error})
        self.warn(f"{node}: schema validation failed for {idea_id}: {error}")

    def schema_repair(self, node: str, idea_id: str, success: bool):
        self.log_event(node, "schema_repair", {"idea_id": idea_id, "success": success})
        level = "repaired" if success else "repair failed"
        self.info(f"{node}: schema {level} for {idea_id}")

    def gate_pass(self, idea_id: str):
        self.log_event("gatekeeper", "pass", {"idea_id": idea_id})

    def gate_kill(self, idea_id: str, reason: str):
        self.log_event("gatekeeper", "kill", {"idea_id": idea_id, "reason": reason})

    def flush(self):
        """Write all accumulated events to run.log.json."""
        log_path = self.run_dir / "run.log.json"
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(self.events, f, indent=2, ensure_ascii=True)
