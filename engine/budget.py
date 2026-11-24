"""Run-level spend ceiling for LLM agents (engine 1.2.0; open point 2 of docs/agent_interface.md).

One SpendTracker per run (bazaar.run installs it; cli.run passes --allow-spend and --dry-run-cost through it).
Every LLMAgent call goes through SpendTracker.call(), which:

  1. answers from the response cache if the request is there (free; counts against no limit);
  2. refuses the call unless the run was started with allow_spend, the model has a price, and the call's worst case
     fits inside every limit: calls + 1 <= max_calls_run; tokens + in_est + max_out <= max_tokens_run; usd +
     cost(in_est, max_out) <= max_usd_run; today's ledger usd + this run's usd + that cost <= max_usd_day.
     in_est = ceil(characters of the system prompt and messages / 3), a deliberately high estimate; max_out is the
     call's max_tokens. Every limit defaults to 0, so by default no call fits;
  3. makes the call, records the provider's reported usage (actual tokens, actual cost), appends one line to the
     ledger and stores the reply in the response cache.

A refused call raises BudgetExceeded and marks the tracker stopped. The agent's decision is then invalid (the engine
counts it as a fallback), and the engine stops the run at the next decision point (BudgetStop) and returns a partial
outcome marked INVALID: budget. A run never continues past a refused call, so no agent falls back silently to the
rule fallback for the rest of a run.

Dry run (dry_run=True): no call is made. Each would-be call is counted with its estimated input tokens and max_out
output tokens at the model's price (0 if it has none), and the agent gets the role's fallback as a valid reply so the
run goes on. The estimate assumes one attempt per decision (retries would add up to max_retries more each) and that
the market follows the fallback actions, so it is an estimate, not a bound.
"""
from __future__ import annotations

import contextvars
import datetime as _dt
import hashlib
import json
import math
import os
from contextlib import contextmanager

INVALID = "INVALID: budget"
CHARS_PER_TOKEN_EST = 3

_CURRENT: contextvars.ContextVar = contextvars.ContextVar("bazaar_spend_tracker", default=None)


class BudgetExceeded(RuntimeError):
    """A call was refused: no allow_spend, no price for the model, or a limit would be passed."""


class BudgetStop(RuntimeError):
    """Raised by the engine at the first decision after a refused call; bazaar.run turns it into a partial
    outcome marked INVALID: budget."""

    def __init__(self, reason: str, where: dict):
        super().__init__(reason)
        self.reason, self.where = reason, where


def est_tokens(system: str, messages: list[dict]) -> int:
    n = len(system or "") + sum(len(m.get("content", "")) for m in messages)
    return int(math.ceil(n / CHARS_PER_TOKEN_EST))


def request_key(provider: str, model_id: str, sampling: dict, system: str, messages: list[dict]) -> str:
    blob = json.dumps({"provider": provider, "model_id": model_id, "sampling": sampling, "system": system,
                       "messages": messages}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _today() -> str:
    return _dt.date.today().isoformat()


class SpendTracker:
    def __init__(self, budget, allow_spend: bool = False, dry_run: bool = False, run_id: str | None = None,
                 today=None):
        self.b = budget
        self.allow_spend, self.dry_run = bool(allow_spend), bool(dry_run)
        self.run_id = run_id or _dt.datetime.now().strftime("%Y%m%dT%H%M%S.%f")
        self._today = today or _today
        self.calls = self.input_tokens = self.output_tokens = 0
        self.usd = 0.0
        self.cache_hits = self.refused = 0
        self.est = {"calls": 0, "input_tokens": 0, "output_tokens": 0, "usd": 0.0, "unpriced_models": []}
        self.stopped: str | None = None
        self._cache: dict | None = None

    # ---------------------------------------------------------------- prices, ledger, cache

    def price(self, model_id: str) -> dict | None:
        p = (self.b.prices or {}).get(model_id)
        if not isinstance(p, dict) or not {"in", "out"} <= set(p):
            return None
        return {"in": float(p["in"]), "out": float(p["out"])}

    def cost(self, model_id: str, tin: int, tout: int) -> float:
        p = self.price(model_id)
        return 0.0 if p is None else (tin * p["in"] + tout * p["out"]) / 1e6

    def day_usd(self) -> float:
        path, day, tot = self.b.ledger, self._today(), 0.0
        if path and os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        r = json.loads(line)
                        if r.get("date") == day:
                            tot += float(r.get("usd", 0.0))
        return tot

    def _ledger(self, rec: dict) -> None:
        if not self.b.ledger:
            raise BudgetExceeded("agents.budget.ledger is empty: a paid call needs a ledger")
        d = os.path.dirname(os.path.abspath(self.b.ledger))
        os.makedirs(d, exist_ok=True)
        with open(self.b.ledger, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, sort_keys=True) + "\n")

    def _load_cache(self) -> dict:
        if self._cache is None:
            self._cache = {}
            path = self.b.response_cache
            if path and os.path.exists(path):
                with open(path, encoding="utf-8") as f:
                    for line in f:
                        if line.strip():
                            r = json.loads(line)
                            self._cache.setdefault(r["key"], r["raw"])     # the first reply wins
        return self._cache

    def _cache_put(self, key: str, raw: str) -> None:
        path = self.b.response_cache
        if not path:
            return
        self._load_cache()[key] = raw
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps({"key": key, "raw": raw}, sort_keys=True) + "\n")

    # ---------------------------------------------------------------- the gate

    def _refuse(self, why: str):
        self.refused += 1
        if self.stopped is None:
            self.stopped = why
        raise BudgetExceeded(why)

    def check(self, model_id: str, tin: int, tout: int) -> None:
        """Raise BudgetExceeded (and stop the run) unless a call of this worst case fits."""
        if self.stopped is not None:
            self._refuse(f"run already stopped: {self.stopped}")
        if not self.allow_spend:
            self._refuse("spend not allowed (start the run with --allow-spend)")
        if self.price(model_id) is None:
            self._refuse(f"no price for model {model_id!r} in agents.budget.prices")
        c = self.cost(model_id, tin, tout)
        b = self.b
        if self.calls + 1 > b.max_calls_run:
            self._refuse(f"max_calls_run {b.max_calls_run} reached")
        if self.input_tokens + self.output_tokens + tin + tout > b.max_tokens_run:
            self._refuse(f"max_tokens_run {b.max_tokens_run} would be passed")
        if self.usd + c > b.max_usd_run + 1e-12:
            self._refuse(f"max_usd_run {b.max_usd_run} would be passed")
        if self.day_usd() + c > b.max_usd_day + 1e-12:
            self._refuse(f"max_usd_day {b.max_usd_day} would be passed (ledger {b.ledger})")

    def call(self, agent, system: str, messages: list[dict], fallback_raw: str) -> str:
        """One LLM request for `agent` (an LLMAgent): cache, gate, call, record. Returns the reply text."""
        sampling = agent.sampling_dict()
        key = request_key(agent.provider, agent.model_id, sampling, system, messages)
        cache = self._load_cache() if self.b.response_cache else {}
        if key in cache:
            self.cache_hits += 1
            return cache[key]
        tin, tout = est_tokens(system, messages), int(sampling["max_tokens"])
        if self.dry_run:
            self.est["calls"] += 1
            self.est["input_tokens"] += tin
            self.est["output_tokens"] += tout
            if self.price(agent.model_id) is None and agent.model_id not in self.est["unpriced_models"]:
                self.est["unpriced_models"].append(agent.model_id)
            self.est["usd"] += self.cost(agent.model_id, tin, tout)
            return fallback_raw
        self.check(agent.model_id, tin, tout)
        raw, usage = agent._call(system, messages)
        ui, uo = int(usage.get("input_tokens", tin)), int(usage.get("output_tokens", tout))
        c = self.cost(agent.model_id, ui, uo)
        self.calls += 1
        self.input_tokens += ui
        self.output_tokens += uo
        self.usd += c
        self._ledger({"ts": _dt.datetime.now().isoformat(timespec="seconds"), "date": self._today(),
                      "run_id": self.run_id, "provider": agent.provider, "model_id": agent.model_id,
                      "input_tokens": ui, "output_tokens": uo, "usd": round(c, 10)})
        self._cache_put(key, raw)
        return raw

    def summary(self) -> dict:
        out = {"allow_spend": self.allow_spend, "calls": self.calls, "input_tokens": self.input_tokens,
               "output_tokens": self.output_tokens, "usd": round(self.usd, 10), "cache_hits": self.cache_hits,
               "refused": self.refused, "stopped": self.stopped}
        if self.dry_run:
            out["dry_run"] = {**self.est, "usd": round(self.est["usd"], 10)}
        return out


def current() -> SpendTracker | None:
    return _CURRENT.get()


@contextmanager
def session(cfg, allow_spend: bool = False, dry_run: bool = False, run_id: str | None = None, today=None):
    """Install a SpendTracker for one run (or reuse the one already installed)."""
    t = _CURRENT.get()
    if t is not None:
        yield t
        return
    t = SpendTracker(cfg.agents.budget, allow_spend=allow_spend, dry_run=dry_run, run_id=run_id, today=today)
    tok = _CURRENT.set(t)
    try:
        yield t
    finally:
        _CURRENT.reset(tok)
