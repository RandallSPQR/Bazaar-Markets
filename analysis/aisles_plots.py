"""Aisles study (plan 2026-11-27): hand-built SVG plots for the run summaries (written after the results).

    PYTHONPATH=. .venv/bin/python -m analysis.aisles_plots

Writes runs/aisles_A_cells.svg: each Run A cell's gain on the D5 primary unit (left) and in base-price units (right),
mean and 95% t interval over seeds 700-719, with the number of seeds where the primary is defined.
"""
import json
from html import escape

BG, INK, INK2, INK3, RULE, ACC = "#fffff8", "#111", "#666", "#999", "#ccc", "#e41a1c"
SERIF = "'ET Book', Palatino, 'Palatino Linotype', 'Book Antiqua', Georgia, serif"
SANS = "-apple-system, 'Helvetica Neue', Arial, sans-serif"


def _t(x, y, s, size=12, fill=INK, anchor="start", family=SERIF, style="", weight="normal"):
    st = f' font-style="{style}"' if style else ""
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-family="{family}" font-size="{size}" fill="{fill}" '
            f'text-anchor="{anchor}" font-weight="{weight}"{st}>{escape(s)}</text>')


def panel(x0, w, lo, hi, ticks, rows, title, sub, fmt):
    """rows: list of (y, stat or None, n, highlight)."""
    X = lambda v: x0 + (min(max(v, lo), hi) - lo) / (hi - lo) * w
    out = [_t(x0, 92, title, 14), _t(x0, 109, sub, 11, INK2)]
    ys = [r[0] for r in rows]
    y_top, y_bot = min(ys) - 12, max(ys) + 12
    out.append(f'<line x1="{X(0):.1f}" y1="{y_top:.1f}" x2="{X(0):.1f}" y2="{y_bot:.1f}" stroke="{RULE}" stroke-width="1"/>')
    out.append(f'<line x1="{X(ticks[0]):.1f}" y1="{y_bot + 6:.1f}" x2="{X(ticks[-1]):.1f}" y2="{y_bot + 6:.1f}" '
               f'stroke="{RULE}" stroke-width="0.6"/>')
    for t in ticks:
        out.append(f'<line x1="{X(t):.1f}" y1="{y_bot + 6:.1f}" x2="{X(t):.1f}" y2="{y_bot + 10:.1f}" stroke="{RULE}" stroke-width="0.6"/>')
        out.append(_t(X(t), y_bot + 22, fmt(t), 11, INK3, "middle", SANS))
    for y, st, n, hl in rows:
        col = ACC if hl else INK2
        if st is None or st.get("mean") is None:
            out.append(_t(X(0) + 6, y + 4, "undefined (n 0)", 11, INK3, style="italic"))
            continue
        m = st["mean"]
        if st.get("lo") is not None:
            a, b = st["lo"], st["hi"]
            out.append(f'<line x1="{X(a):.1f}" y1="{y:.1f}" x2="{X(b):.1f}" y2="{y:.1f}" stroke="{col}" stroke-width="1.4"/>')
            if b > hi:
                out.append(f'<path d="M{X(hi) - 5:.1f},{y - 3.5:.1f} L{X(hi):.1f},{y:.1f} L{X(hi) - 5:.1f},{y + 3.5:.1f}" '
                           f'fill="none" stroke="{col}" stroke-width="1.2"/>')
            if a < lo:
                out.append(f'<path d="M{X(lo) + 5:.1f},{y - 3.5:.1f} L{X(lo):.1f},{y:.1f} L{X(lo) + 5:.1f},{y + 3.5:.1f}" '
                           f'fill="none" stroke="{col}" stroke-width="1.2"/>')
            out.append(f'<circle cx="{X(m):.1f}" cy="{y:.1f}" r="3.2" fill="{col}"/>')
        else:
            out.append(f'<circle cx="{X(m):.1f}" cy="{y:.1f}" r="3.2" fill="{BG}" stroke="{col}" stroke-width="1.3"/>')
        if n < 20:
            label = f"n {n}" + (", no interval" if st.get("lo") is None else "")
            xr = X(st["hi"]) if st.get("lo") is not None else X(m)
            out.append(_t(min(xr, x0 + w) + 7, y + 4, label, 11, INK2, style="italic"))
    return out


def plot_A():
    A = json.load(open("runs/aisles_A.json", encoding="utf-8"))["cells"]
    groups = [("ds 0, t40 (PA1, PA2: confirmatory)", "ds0", "t40", True), ("ds 0, t100", "ds0", "t100", False),
              ("ds 1, t40 (PA3)", "ds1", "t40", False), ("ds 1, t100 (PA3)", "ds1", "t100", False)]
    W, H = 900, 640
    lab_x, p1, p2, pw = 24, 250, 600, 260
    y = 140
    rowsL, rowsR, labels = [], [], []
    for gt, ds, t, conf in groups:
        labels.append(_t(lab_x, y, gt, 12, INK, weight="bold" if conf else "normal"))
        y += 18
        for m in ("fat", "thin"):
            for v in ("easy", "hard"):
                c = A[f"A|{m}|{v}|{t}|{ds}"]
                rp = c["ratio"]["pooled"]
                labels.append(_t(lab_x + 12, y + 4, f"{m} margin, {v} to verify", 12, INK if conf else INK2))
                rowsL.append((y, rp if rp["n"] else None, rp["n"], conf))
                rowsR.append((y, c["base_units"]["pooled"], 20, conf))
                y += 19
        y += 14
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="100%" role="img" '
           f'aria-label="Run A: in the thin-margin ds 0 cells the D5 primary is defined in 0 to 4 of 20 seeds; in '
           f'base-price units hard verification and thin margins raise the t40 ds 0 gain; at ds 1 every cell loses.">',
           f'<rect width="{W}" height="{H}" fill="{BG}"/>',
           _t(lab_x, 36, "Thin-margin honest stalls lose money at ds 0, so the primary unit is undefined there", 19),
           _t(lab_x, 58, "Run A, bust-out gain per sampled stall (best of days 20–30 minus never), mean and 95% t "
              "interval over seeds 700–719 (n 20 unless marked)", 13, INK2)]
    svg += labels
    svg += panel(p1, pw, -5, 6, [-4, -2, 0, 2, 4, 6], rowsL, "Primary (D5): Σ gains ÷ Σ honest profits",
                 "per seed over the 3 sampled stalls; undefined if Σ ≤ 0", lambda t: f"{t:+g}" if t else "0")
    svg += panel(p2, pw, -15, 45, [-10, 0, 10, 20, 30, 40], rowsR, "Gain in base-price units (secondary)",
                 "each stall's gain ÷ its aisle's base price, mean of 3", lambda t: f"{t:+g}" if t else "0")
    svg.append(_t(lab_x, H - 30, "Engine 1.3.1; analysis/aisles_1_3.py (frozen), runs/aisles_A.json. Open circle: "
                  "defined in one seed only. Arrows: interval runs past the axis.", 10, "#aaa", family=SANS))
    svg.append(_t(lab_x, H - 16, "Honest profit = never-chain profit over the 30 days, after fixed cost and ad "
                  "spend; ds 0 thin cells average −$257 to −$421 per stall.", 10, "#aaa", family=SANS))
    svg.append("</svg>")
    with open("runs/aisles_A_cells.svg", "w", encoding="utf-8") as f:
        f.write("\n".join(svg))
    print("written runs/aisles_A_cells.svg")


def plot_C():
    """runs/aisles_C_entrance.svg: deceptive share of units at the entrance spots and elsewhere, by rent alpha, for
    t40 and t100 (small multiples on one scale), mean and 95% t interval over seeds 740-759."""
    C = json.load(open("runs/aisles_C.json", encoding="utf-8"))["cells"]
    W, H = 900, 600
    lo, hi = 0.0, 0.25
    top, bot = 150, 480
    Y = lambda v: bot - (v - lo) / (hi - lo) * (bot - top)
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="100%" role="img" '
           f'aria-label="Run C: at alpha 0 deceptive stalls sell a larger share of units at the entrance spots than '
           f'elsewhere (gap +0.10 at t40 and t100); position rent narrows the gap, to 0 at alpha 1 with tourists only.">',
           f'<rect width="{W}" height="{H}" fill="{BG}"/>',
           _t(24, 36, "Deceptive stalls sell more at the entrance; rent on the entrance spots narrows the gap", 19),
           _t(24, 58, "Run C, deceptive share of units sold, entrance spots (nearest two ranks) and the rest, never "
              "chains, mean and 95% t interval over seeds 740–759 (n 20)", 13, INK2)]
    for i, (t, title) in enumerate((("t40", "Tourists 40% (locals inspect)"), ("t100", "Tourists only"))):
        x0, w = 110 + i * 400, 300
        X = lambda a: x0 + a * w
        svg.append(_t(x0, 110, title, 14))
        if i == 0:
            for v in (0, 0.05, 0.10, 0.15, 0.20, 0.25):
                svg.append(_t(x0 - 14, Y(v) + 4, f"{v:.2f}", 11, INK3, "end", SANS))
            svg.append(f'<line x1="{x0 - 8}" y1="{Y(0):.1f}" x2="{x0 - 8}" y2="{Y(0.25):.1f}" stroke="{RULE}" stroke-width="0.6"/>')
        for a in (0, 0.5, 1):
            svg.append(_t(X(a), bot + 24, f"α {a:g}", 11, INK3, "middle", SANS))
        svg.append(f'<line x1="{X(0):.1f}" y1="{bot + 8}" x2="{X(1):.1f}" y2="{bot + 8}" stroke="{RULE}" stroke-width="0.6"/>')
        for key, col, name in (("entrance", ACC, "entrance"), ("rest", INK2, "rest")):
            pts = []
            for a, lab in ((0, "0"), (0.5, "0.5"), (1, "1")):
                st = C[f"C|a{lab}|{t}"][key]
                pts.append((X(a), Y(st["mean"])))
                svg.append(f'<line x1="{X(a):.1f}" y1="{Y(st["lo"]):.1f}" x2="{X(a):.1f}" y2="{Y(st["hi"]):.1f}" '
                           f'stroke="{col}" stroke-width="1.2" opacity="0.6"/>')
                svg.append(f'<circle cx="{X(a):.1f}" cy="{Y(st["mean"]):.1f}" r="3" fill="{col}"/>')
            svg.append(f'<polyline points="{" ".join(f"{x:.1f},{y:.1f}" for x, y in pts)}" fill="none" '
                       f'stroke="{col}" stroke-width="1.6"/>')
            svg.append(_t(pts[-1][0] + 10, pts[-1][1] + (-4 if key == "entrance" else 14) if t == "t100" else pts[-1][1] + 4,
                          name, 12, col))
        g0 = C[f"C|a0|{t}"]["gap"]
        g1 = C[f"C|a1|{t}"]["gap"]
        svg.append(_t(x0, 140, f"gap at α 0: {g0['mean']:+.3f} [{g0['lo']:+.3f}, {g0['hi']:+.3f}];  at α 1: "
                              f"{g1['mean']:+.3f} [{g1['lo']:+.3f}, {g1['hi']:+.3f}]", 11, INK2, style="italic"))
    svg.append(_t(24, H - 46, "Rent α: share of the calibrated position advantage charged as daily rent (γ tourist 1.0, "
                  "γ local 0.2). PC1 (confirmatory) is the gap at t40, α 0.", 10, "#aaa", family=SANS))
    svg.append(_t(24, H - 32, "Engine 1.3.1; realistic aisle profiles, solvency on; analysis/aisles_1_3.py (frozen), "
                  "runs/aisles_C.json.", 10, "#aaa", family=SANS))
    svg.append("</svg>")
    with open("runs/aisles_C_entrance.svg", "w", encoding="utf-8") as f:
        f.write("\n".join(svg))
    print("written runs/aisles_C_entrance.svg")


if __name__ == "__main__":
    plot_A()
    plot_C()
