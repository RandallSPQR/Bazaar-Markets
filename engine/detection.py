"""Detection: probability that an inspector who perceives a claim catches the stall.

Inputs are the claim's falsity (claimed Q minus true Q, floored at 0), the
channel it travelled on, and the inspector's distance from the stall. A true
claim is never caught under any form.

PLACEHOLDER default ("graded", chosen 2026-11-03):
    p = w_channel * proximity(d) * min(1, falsity / f_scale)
with proximity(d) = max(0, 1 - d / channel_range) for broadcast channels
(sign, yell) and 1 for private ones (whisper, answer), which reach an
inspector only when the inspector is the recipient.

Defaults make private channels easier to detect than broadcast ones, conditional on
an inspector perceiving the message (weight 1.0 vs 0.6 / 0.4, and no distance decay).
That is a modelling choice: channel outcomes then mix exposure differences with
detection differences. proximity="flat" plus equal channel weights
(configs/detection_equal.json) removes the detection difference, so channels differ
only in exposure.

Alternatives:
    "step":   p = w_channel * proximity(d) whenever falsity > 0
    "hazard": p = 1 - exp(-k * falsity * w_channel * exp(-d / lam))
"""
from __future__ import annotations

import math

from .config import DetectionCfg

PRIVATE = ("whisper", "answer")


def proximity(channel: str, d: float, rng_for_channel: float) -> float:
    if channel in PRIVATE:
        return 1.0
    return max(0.0, 1.0 - d / rng_for_channel)


def catch_prob(cfg: DetectionCfg, falsity: float, channel: str, d: float, channel_range: float) -> float:
    if falsity <= 0:
        return 0.0
    w = cfg.channel_weight[channel]
    if cfg.proximity not in ("linear", "flat"):
        raise ValueError(f"unknown detection proximity {cfg.proximity!r}")
    flat = cfg.proximity == "flat"
    prox = 1.0 if flat else proximity(channel, d, channel_range)
    if cfg.form == "graded":
        return w * prox * min(1.0, falsity / cfg.f_scale)
    if cfg.form == "step":
        return w * prox
    if cfg.form == "hazard":
        reach = 1.0 if (channel in PRIVATE or flat) else math.exp(-d / cfg.hazard_lam)
        return 1.0 - math.exp(-cfg.hazard_k * falsity * w * reach)
    raise ValueError(f"unknown detection form {cfg.form!r}")
