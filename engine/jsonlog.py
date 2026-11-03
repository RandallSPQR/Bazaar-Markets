"""Canonical JSONL logging.

Every event is one line of canonical JSON (sorted keys, no whitespace, numpy
scalars converted to Python types). Canonical form is what makes the
"same seed + config + agent outputs -> byte-identical log" guarantee checkable.
"""
from __future__ import annotations

import json
import math
import platform
from typing import IO, Any

import numpy as np


def _plain(x: Any) -> Any:
    if isinstance(x, dict):
        return {str(k): _plain(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_plain(v) for v in x]
    if isinstance(x, np.ndarray):
        return [_plain(v) for v in x.tolist()]
    if isinstance(x, (np.bool_,)):
        return bool(x)
    if isinstance(x, np.integer):
        return int(x)
    if isinstance(x, (float, np.floating)):
        f = float(x)
        # JSON has no NaN/Inf; encode them as null so logs stay valid JSON.
        return None if (math.isnan(f) or math.isinf(f)) else f
    return x


def dumps(obj: Any) -> str:
    return json.dumps(_plain(obj), sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def env_info() -> dict:
    """Environment facts. Logged in the header under `env`; replay reports
    differences here as warnings rather than mismatches."""
    return {"python": platform.python_version(), "numpy": np.__version__}


class JsonlLog:
    """Append-only event log. `sink` is a text file handle or None (in-memory only)."""

    def __init__(self, sink: IO[str] | None = None, keep: bool = True):
        self.sink = sink
        self.keep = keep
        self.lines: list[str] = []

    def emit(self, ev: str, **fields: Any) -> None:
        line = dumps({"ev": ev, **fields})
        if self.keep:
            self.lines.append(line)
        if self.sink is not None:
            self.sink.write(line + "\n")

    def text(self) -> str:
        return "".join(line + "\n" for line in self.lines)


def read_jsonl(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]
