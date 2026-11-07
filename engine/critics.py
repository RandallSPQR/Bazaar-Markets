"""Critics and capture (engine 0.11.0; all off by default).

Critics are reviewers, not buyers: they act between days, after the day's trading and before the
rating update. Each day each critic visits critics.sample stalls (without replacement, stream
[day root, 13, critic]), observes the stall's true Q and writes a review: positive when true Q
meets the stall's posted claim (sign "pitch" -> Q_pitch, "truth" -> Q_true), negative otherwise;
a stall showing no sign gets no review (decided 2026-11-07). Reviews are filed under the stall's
actual brand name and count as critics.weight rated units in that day's brand rating update.

Positive reviews are filed the day they are written. A negative review is held for
    delay = max(tie_delay if (critic, brand) is tied else 0,
                round_half_up(emb_max * p) if embarrassment else 0)
days, where p is the share of the critic's earlier reviews of that brand (written before today,
filed or not) that were positive (0 with none). A review written on day d with delay k is filed
at the end of day d + k; one due after the last day is never filed.

Ties (dependence): round_half_up(tie_share x pairs) of the (critic, genuine-origin brand) pairs,
uniformly without replacement from [seed, 14], fixed for the run. Genuine-origin brands are the
brands on genuine stalls on day 1, in stall index order.

Inspector capture: each dedicated inspector j (its order among inspectors) is tied to each
genuine-origin brand with probability inspectors.capture, from [seed, 15] (one draw per pair, in
inspector-then-brand order), fixed for the run. In engine/bazaar.py a tied inspector's catch
probability for a stall bearing that brand is multiplied by (1 - inspectors.capture_effect).
"""
from __future__ import annotations

import math

import numpy as np


def round_half_up(x: float) -> int:
    return int(math.floor(x + 0.5))


def critics_on(cfg) -> bool:
    return int(cfg.critics.count) > 0


def capture_on(cfg) -> bool:
    return float(cfg.inspectors.capture) > 0


def validate(cfg) -> None:
    c, ic = cfg.critics, cfg.inspectors
    if int(c.count) < 0 or int(c.sample) < 1 or float(c.weight) <= 0 or int(c.tie_delay) < 0 or int(c.emb_max) < 0:
        raise ValueError("critics: count >= 0, sample >= 1, weight > 0, tie_delay >= 0, emb_max >= 0 required")
    if not 0 <= float(c.tie_share) <= 1:
        raise ValueError(f"critics.tie_share must be in [0, 1], got {c.tie_share}")
    if not 0 <= float(ic.capture) <= 1 or not 0 <= float(ic.capture_effect) <= 1:
        raise ValueError("inspectors.capture and inspectors.capture_effect must be in [0, 1]")
    if (critics_on(cfg) or capture_on(cfg)) and not cfg.brands.enabled:
        raise ValueError("critics and inspector capture need brands.enabled")
    if critics_on(cfg) and cfg.ratings.mode == "off":
        raise ValueError("critics need ratings.mode != 'off'")


def init_ties(cfg, book, stalls: list) -> None:
    """Day 1: record the genuine-origin brands and draw critic ties and inspector capture."""
    book.genuine_origin = [st.brand for st in sorted(stalls, key=lambda s: s.idx) if st.stype == "genuine"]
    if critics_on(cfg) and float(cfg.critics.tie_share) > 0:
        pairs = [(c, b) for c in range(int(cfg.critics.count)) for b in book.genuine_origin]
        n = round_half_up(float(cfg.critics.tie_share) * len(pairs))
        order = np.random.default_rng([cfg.seed, 14]).permutation(len(pairs))
        book.critic_ties = {pairs[i] for i in order[:n]}
    if capture_on(cfg):
        rng = np.random.default_rng([cfg.seed, 15])
        u = rng.random((int(cfg.inspectors.count), len(book.genuine_origin)))
        book.capture_ties = {(j, b) for j in range(u.shape[0]) for k, b in enumerate(book.genuine_origin)
                             if u[j, k] < float(cfg.inspectors.capture)}


def posted_claim(st) -> float | None:
    if st.sign == "pitch":
        return st.q_pitch
    if st.sign == "truth":
        return st.q_true
    return None


def delay_for(cfg, book, critic: int, brand: str, positive: bool) -> int:
    if positive:
        return 0
    c = cfg.critics
    d = int(c.tie_delay) if (critic, brand) in book.critic_ties else 0
    if c.embarrassment:
        hist = book.critic_hist.get((critic, brand), [])
        p = (sum(hist) / len(hist)) if hist else 0.0
        d = max(d, round_half_up(int(c.emb_max) * p))
    return d


def critics_day(cfg, book, stalls: list, root: tuple, day: int) -> dict:
    """Write today's reviews, then file those due today. Returns {"written": [...], "filed": [...]}
    and leaves the rest pending in the book."""
    by_idx = sorted(stalls, key=lambda s: s.idx)
    written = []
    for c in range(int(cfg.critics.count)):
        rng = np.random.default_rng([*root, 13, c])
        k = min(int(cfg.critics.sample), len(by_idx))
        for i in rng.choice(len(by_idx), size=k, replace=False):
            st = by_idx[int(i)]
            claim = posted_claim(st)
            if claim is None:
                continue
            positive = bool(st.q_true >= claim - 1e-12)
            delay = delay_for(cfg, book, c, st.brand, positive)
            rec = {"day": day, "critic": c, "stall": st.sid, "brand": st.brand, "stype": st.stype,
                   "busted": st.busted_day is not None, "q_true": st.q_true, "claim": claim,
                   "positive": positive, "delay": delay, "file_day": day + delay,
                   "tied": (c, st.brand) in book.critic_ties}
            book.critic_hist.setdefault((c, st.brand), []).append(positive)
            written.append(rec)
            book.critic_pending.append(rec)
    filed = [r for r in book.critic_pending if r["file_day"] == day]
    book.critic_pending = [r for r in book.critic_pending if r["file_day"] > day]
    return {"written": written, "filed": filed}
