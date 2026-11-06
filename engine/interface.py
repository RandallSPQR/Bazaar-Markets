"""The agent interface.

The engine sends a role-specific observation (a JSON-serialisable dict) and
receives a raw string. The string is parsed as JSON, checked against the role's
action schema, then checked against engine state (range, budget, who asked).
Anything that fails becomes the role's deterministic fallback action, and the
failure is logged.

Actions can only *select* among options the engine offers: which channel to
use, which claim from the stall's own menu ("truth" or "pitch"), what the stall's
sign shows (from the same menu), which stall to
ask, inspect or buy from, and how many units. No field sets a price, a
quality, an outcome or an enforcement result; unknown fields are rejected.
"""
from __future__ import annotations

import json
from typing import Any, Protocol

import jsonschema

CLAIM = {"enum": ["truth", "pitch"]}

SELLER_ACTION_SCHEMA: dict = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "SellerAction",
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "yell": {"oneOf": [{"type": "null"},
                           {"type": "object", "additionalProperties": False, "required": ["claim"],
                            "properties": {"claim": CLAIM}}]},
        "whisper": {"oneOf": [{"type": "null"},
                              {"type": "object", "additionalProperties": False, "required": ["to", "claim"],
                               "properties": {"to": {"type": "string", "maxLength": 16}, "claim": CLAIM}}]},
        "answers": {"type": "array", "maxItems": 32,
                    "items": {"type": "object", "additionalProperties": False, "required": ["to", "claim"],
                              "properties": {"to": {"type": "string", "maxLength": 16}, "claim": CLAIM}}},
        # Optional: set the stall's sign. Takes effect in this tick's delivery (seller
        # decisions precede delivery) and stays until changed.
        "sign": CLAIM,
        # Brands only (engine 0.8.0, brands.enabled): rename on the first decision after a
        # reopening; bust out (genuine stalls, first decision of a day): true quality drops to
        # the stall's low quality for good, name, sign claim and price unchanged.
        "rename": {"enum": ["fresh", "counterfeit", "lookalike"]},   # "lookalike" = 0.8.0 alias
        "bust_out": {"const": True},
    },
}

_STALL_REF = {"type": "string", "maxLength": 8}

BUYER_ACTION_SCHEMA: dict = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "BuyerAction",
    "oneOf": [
        {"type": "object", "additionalProperties": False, "required": ["action"],
         "properties": {"action": {"const": "move_on"}}},
        {"type": "object", "additionalProperties": False, "required": ["action", "stall"],
         "properties": {"action": {"enum": ["ask", "inspect"]}, "stall": _STALL_REF}},
        {"type": "object", "additionalProperties": False, "required": ["action", "stall", "units"],
         "properties": {"action": {"const": "buy"}, "stall": _STALL_REF,
                        "units": {"type": "integer", "minimum": 1, "maximum": 100}}},
    ],
}

SCHEMAS = {"seller": SELLER_ACTION_SCHEMA, "buyer": BUYER_ACTION_SCHEMA}
FALLBACK = {"seller": {"yell": None, "whisper": None, "answers": []},
            "buyer": {"action": "move_on"}}

_VALIDATORS = {role: jsonschema.Draft202012Validator(s) for role, s in SCHEMAS.items()}


class Agent(Protocol):
    """Anything that maps an observation to a raw string."""

    def act(self, observation: dict) -> str: ...

    def meta(self) -> dict:
        """Static description for the log header: policy, version, model_id, sampling."""
        ...


def parse(role: str, raw: Any) -> tuple[dict | None, str | None]:
    """Parse and schema-check a raw agent output. Returns (action, error)."""
    if not isinstance(raw, str):
        return None, f"raw output is {type(raw).__name__}, expected str"
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError as e:
        return None, f"invalid JSON: {e.msg} at {e.pos}"
    errs = sorted(_VALIDATORS[role].iter_errors(obj), key=lambda e: list(e.path))
    if errs:
        e = errs[0]
        return None, f"schema: {e.message[:200]} at /{'/'.join(map(str, e.path))}"
    if role == "seller":
        # optional keys are omitted when absent, so old actions log unchanged
        extra = {k: obj[k] for k in ("sign", "rename", "bust_out") if obj.get(k) is not None}
        obj = {"yell": obj.get("yell"), "whisper": obj.get("whisper"), "answers": obj.get("answers", []), **extra}
    return obj, None
