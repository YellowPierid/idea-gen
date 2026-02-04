import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from pydantic import BaseModel

logger = logging.getLogger("idea_gen")


class OutputStore:
    """File-based output store with JSONL/Markdown writing and checkpointing."""

    def __init__(self, output_dir: str, run_id: str | None = None):
        base = Path(output_dir) / "runs"
        if run_id:
            self.run_dir = base / run_id
            if not self.run_dir.exists():
                raise FileNotFoundError(f"Run directory not found: {self.run_dir}")
            self.run_id = run_id
        else:
            self.run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            self.run_dir = base / self.run_id
        self.run_dir.mkdir(parents=True, exist_ok=True)

    def write_jsonl(self, filename: str, items: list[BaseModel]):
        """Write a list of Pydantic models as JSONL."""
        path = self.run_dir / filename
        with open(path, "w", encoding="utf-8") as f:
            for item in items:
                f.write(item.model_dump_json() + "\n")

    def write_markdown(self, filename: str, content: str):
        """Write markdown content to file."""
        path = self.run_dir / filename
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    def save_checkpoint(self, last_node: str, state: dict[str, Any]):
        """Save pipeline state for resume capability."""
        checkpoint = {
            "last_completed_node": last_node,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "state": _serialize_state(state),
        }
        path = self.run_dir / "checkpoint.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(checkpoint, f, indent=2, ensure_ascii=True, default=str)

    def load_checkpoint(self) -> dict[str, Any] | None:
        """Load checkpoint if it exists."""
        path = self.run_dir / "checkpoint.json"
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)


def _serialize_state(state: dict[str, Any]) -> dict[str, Any]:
    """Serialize pipeline state, converting Pydantic models to dicts."""
    result = {}
    for key, value in state.items():
        if isinstance(value, list):
            result[key] = [
                item.model_dump() if isinstance(item, BaseModel) else item
                for item in value
            ]
        elif isinstance(value, BaseModel):
            result[key] = value.model_dump()
        else:
            result[key] = value
    return result


# ---------------------------------------------------------------------------
# Global history for cross-run duplicate detection
# ---------------------------------------------------------------------------

_HISTORY_JSONL = "idea_history.jsonl"
_HISTORY_VECTORS = "idea_vectors.npy"


def load_global_history(history_dir: str) -> tuple[list[dict], np.ndarray | None]:
    """Load past idea records and their embedding vectors.

    Returns (records, vectors) where records is a list of dicts with
    'name' and 'text' keys, and vectors is a numpy array or None if
    no history exists yet.
    """
    hdir = Path(history_dir)
    records_path = hdir / _HISTORY_JSONL
    vectors_path = hdir / _HISTORY_VECTORS

    records: list[dict] = []
    vectors = None

    if records_path.exists():
        with open(records_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))

    if vectors_path.exists():
        vectors = np.load(vectors_path)

    # Sanity check: records and vectors must be in sync
    if vectors is not None and len(records) != vectors.shape[0]:
        logger.warning(
            "Global history mismatch: %d records vs %d vectors. Resetting.",
            len(records), vectors.shape[0],
        )
        return [], None

    return records, vectors


def save_global_history(
    history_dir: str,
    records: list[dict],
    vectors: np.ndarray,
) -> None:
    """Persist idea records and vectors to disk.

    Overwrites the existing history files entirely (records list is
    already the full accumulated set including new entries).
    """
    hdir = Path(history_dir)
    hdir.mkdir(parents=True, exist_ok=True)

    records_path = hdir / _HISTORY_JSONL
    vectors_path = hdir / _HISTORY_VECTORS

    with open(records_path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=True) + "\n")

    np.save(vectors_path, vectors)
