"""Plot for runs/state_bank_summary.md (written after the bank results; descriptive only, no new simulation).

Reads runs/state_bank/states.jsonl.gz and writes runs/state_bank/paying_minus_honest.svg: per state, the best paying
option's mean remaining profit minus keep_supply's (dollars), with its paired 95% t interval over K = 20 continuations,
one row per market. Hand-built SVG (matplotlib is not installed), Tufte style.
"""
import gzip
import json
import random

SRC = "runs/state_bank/states.jsonl.gz"
OUT = "runs/state_bank/paying_minus_honest.svg"
ORDER = ["t40|ds0|pn0", "t40|ds0|pn10new", "t40|ds1|pn0", "t40|ds1|pn10new",
         "t100|ds0|pn0", "t100|ds0|pn10new", "t100|ds1|pn0", "t100|ds1|pn10new"]
LABEL = {"t40": "locals inspect", "t100": "tourists only", "ds0": "no enforcement", "ds1": "enforcement",
         "pn0": "", "pn10new": ", slow new brands"}
SERIF = '"ET Book","Palatino Linotype",Palatino,"Book Antiqua",Georgia,serif'
SANS = "-apple-system,Helvetica,Arial,sans-serif"


def main():
    rows = [json.loads(x) for x in gzip.open(SRC, "rt", encoding="utf-8")]
    W, H, L, R, T, B = 900, 600, 250, 30, 80, 70
    lo, hi = -4000, 10000
    x = lambda v: L + (v - lo) / (hi - lo) * (W - L - R)
    band = (H - T - B) / len(ORDER)
    rng = random.Random(0)
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" role="img" '
         f'aria-label="Deception pays in every tourists-only state and in 4 of 114 states where locals inspect, '
         f'each within noise.">',
         f'<rect width="{W}" height="{H}" fill="#fffff8"/>',
         f'<text x="20" y="32" font-family=\'{SERIF}\' font-size="20" fill="#111">Deception pays where no buyer '
         f'inspects, and almost never where locals do</text>',
         f'<text x="20" y="56" font-family=\'{SERIF}\' font-size="14" fill="#666">Best paying option (a supply switch '
         f'or the cheap licence) minus staying honest, remaining profit to day 30, per state; 200 states</text>']
    zx = x(0)
    s.append(f'<line x1="{zx:.1f}" y1="{T - 6}" x2="{zx:.1f}" y2="{H - B + 4}" stroke="#ccc" stroke-width="1"/>')
    for i, m in enumerate(ORDER):
        v, ds, pn = m.split("|")
        y0 = T + i * band
        cy = y0 + band / 2
        pts = [r for r in rows if r["hidden"]["market"] == m]
        npay = sum(r["labels"]["pays"] for r in pts)
        name = f"{LABEL[v]}, {LABEL[ds]}"
        sub = f"{'slow new brands; ' if pn == 'pn10new' else ''}pays in {npay} of {len(pts)}"
        s.append(f'<text x="{L - 12}" y="{cy - 3:.1f}" text-anchor="end" font-family=\'{SERIF}\' font-size="13" '
                 f'fill="#333">{name}</text>')
        s.append(f'<text x="{L - 12}" y="{cy + 13:.1f}" text-anchor="end" font-family=\'{SERIF}\' font-size="12" '
                 f'fill="#666">{sub}</text>')
        for r in pts:
            d = r["labels"]["paying_minus_honest"] / 100
            a, b = (c / 100 for c in r["labels"]["paying_minus_honest_ci95"])
            yy = cy + rng.uniform(-band * 0.32, band * 0.32)
            col = "#e41a1c" if r["labels"]["pays"] and v == "t40" else ("#666" if d > 0 else "#999")
            s.append(f'<line x1="{x(max(a, lo)):.1f}" y1="{yy:.1f}" x2="{x(min(b, hi)):.1f}" y2="{yy:.1f}" '
                     f'stroke="{col}" stroke-opacity="0.35" stroke-width="1"/>')
            s.append(f'<circle cx="{x(d):.1f}" cy="{yy:.1f}" r="2.4" fill="{col}"/>')
    ax = H - B + 10
    s.append(f'<line x1="{x(lo):.1f}" y1="{ax}" x2="{x(hi):.1f}" y2="{ax}" stroke="#ccc" stroke-width="0.5"/>')
    for t in range(lo, hi + 1, 2000):
        lab = f"{'−' if t < 0 else ('+' if t > 0 else '')}${abs(t):,}"
        s.append(f'<line x1="{x(t):.1f}" y1="{ax}" x2="{x(t):.1f}" y2="{ax + 4}" stroke="#ccc" stroke-width="0.5"/>')
        s.append(f'<text x="{x(t):.1f}" y="{ax + 18}" text-anchor="middle" font-family="{SANS}" font-size="11" '
                 f'fill="#999">{lab}</text>')
    s.append(f'<text x="{zx + 6:.1f}" y="{T - 10}" font-family=\'{SERIF}\' font-size="12" font-style="italic" '
             f'fill="#333">honest = 0</text>')
    s.append(f'<text x="20" y="{H - 15}" font-family="{SANS}" font-size="10" fill="#aaa">Bazaar Markets engine 1.1.0, '
             f'state bank (runs/state_bank/states.jsonl.gz): 8 markets, seeds 400–499, snapshot days 5–20. Dots: mean '
             f'over K = 20</text>')
    s.append(f'<text x="20" y="{H - 1}" font-family="{SANS}" font-size="10" fill="#aaa">paired continuations; lines: '
             f'95% t intervals, unadjusted. Red: the 4 paying states where locals inspect; every one\'s interval '
             f'includes 0.</text>')
    s.append("</svg>")
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(s) + "\n")
    print(OUT)


if __name__ == "__main__":
    main()
