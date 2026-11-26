"""Plot for runs/state_bank_v2_summary.md (written after the bank results; descriptive only, no new simulation).

Reads runs/state_bank_v2/states.jsonl.gz and writes runs/state_bank_v2/cheating_minus_honest.svg: per state, the best
cheating option's mean remaining profit minus keep_supply's, as a share of keep_supply's mean, with its paired 95% t
interval over K = 20 continuations; one row per tourist share x detect_scale. Close calls in red. Values beyond the
axis are drawn at the edge as open circles. Hand-built SVG (matplotlib is not installed), Tufte style.
"""
import gzip
import json
import random

SRC = "runs/state_bank_v2/states.jsonl.gz"
OUT = "runs/state_bank_v2/cheating_minus_honest.svg"
SERIF = '"ET Book","Palatino Linotype",Palatino,"Book Antiqua",Georgia,serif'
SANS = "-apple-system,Helvetica,Arial,sans-serif"
TS = {0.4: "40% tourists", 0.7: "70% tourists", 1.0: "tourists only"}
DS = {0.0: "no enforcement", 0.1: "light enforcement", 1.0: "full enforcement"}


def main():
    rows = [json.loads(x) for x in gzip.open(SRC, "rt", encoding="utf-8")]
    groups = [(t, d) for t in (0.4, 0.7, 1.0) for d in (0.0, 0.1, 1.0)]
    W, H, L, R, T, B = 900, 640, 250, 40, 84, 74
    lo, hi = -1.5, 3.0
    x = lambda v: L + (min(max(v, lo), hi) - lo) / (hi - lo) * (W - L - R)
    band = (H - T - B) / len(groups)
    rng = random.Random(0)
    npay = sum(r["labels"]["pays"] for r in rows)
    ncc = sum(r["labels"]["close_call"] for r in rows)
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" role="img" '
         f'aria-label="Cheating pays in {npay} of 300 states; whether it pays depends on tourist share, enforcement '
         f'and liability together; {ncc} close calls.">',
         f'<rect width="{W}" height="{H}" fill="#fffff8"/>',
         f'<text x="20" y="32" font-family=\'{SERIF}\' font-size="20" fill="#111">Whether cheating pays now turns on '
         f'more than who checks</text>',
         f'<text x="20" y="56" font-family=\'{SERIF}\' font-size="14" fill="#666">Best cheating option minus staying '
         f'honest, remaining profit as a share of honest\'s, per state; 300 states, {npay} pay, '
         f'{ncc} close calls (red)</text>']
    zx = x(0)
    s.append(f'<line x1="{zx:.1f}" y1="{T - 6}" x2="{zx:.1f}" y2="{H - B + 4}" stroke="#ccc" stroke-width="1"/>')
    for i, (t, d) in enumerate(groups):
        cy = T + i * band + band / 2
        pts = [r for r in rows if r["hidden"]["tourist_share"] == t and r["hidden"]["detect_scale"] == d]
        np_ = sum(r["labels"]["pays"] for r in pts)
        s.append(f'<text x="{L - 12}" y="{cy - 3:.1f}" text-anchor="end" font-family=\'{SERIF}\' font-size="13" '
                 f'fill="#333">{TS[t]}, {DS[d]}</text>')
        s.append(f'<text x="{L - 12}" y="{cy + 13:.1f}" text-anchor="end" font-family=\'{SERIF}\' font-size="12" '
                 f'fill="#666">pays in {np_} of {len(pts)}</text>')
        if i:
            s.append(f'<line x1="{L}" y1="{T + i * band:.1f}" x2="{W - R}" y2="{T + i * band:.1f}" stroke="#eee" '
                     f'stroke-width="0.5"/>')
        for r in pts:
            h = abs(r["labels"]["means"]["keep_supply"]) or 1.0
            v = r["labels"]["cheating_minus_honest"] / h
            a, b = (c / h for c in r["labels"]["cheating_minus_honest_ci95"])
            yy = cy + rng.uniform(-band * 0.33, band * 0.33)
            col = "#e41a1c" if r["labels"]["close_call"] else ("#555" if v > 0 else "#999")
            s.append(f'<line x1="{x(a):.1f}" y1="{yy:.1f}" x2="{x(b):.1f}" y2="{yy:.1f}" stroke="{col}" '
                     f'stroke-opacity="0.3" stroke-width="1"/>')
            if lo <= v <= hi:
                s.append(f'<circle cx="{x(v):.1f}" cy="{yy:.1f}" r="2.3" fill="{col}"/>')
            else:
                s.append(f'<circle cx="{x(v):.1f}" cy="{yy:.1f}" r="2.3" fill="none" stroke="{col}" '
                         f'stroke-width="1"/>')
    ax = H - B + 10
    s.append(f'<line x1="{x(lo):.1f}" y1="{ax}" x2="{x(hi):.1f}" y2="{ax}" stroke="#ccc" stroke-width="0.5"/>')
    for k in range(-3, 7):
        tv = k * 0.5
        lab = f"{'−' if tv < 0 else ('+' if tv > 0 else '')}{abs(tv) * 100:.0f}%"
        s.append(f'<line x1="{x(tv):.1f}" y1="{ax}" x2="{x(tv):.1f}" y2="{ax + 4}" stroke="#ccc" stroke-width="0.5"/>')
        s.append(f'<text x="{x(tv):.1f}" y="{ax + 18}" text-anchor="middle" font-family="{SANS}" font-size="11" '
                 f'fill="#999">{lab}</text>')
    s.append(f'<text x="{zx + 6:.1f}" y="{T - 10}" font-family=\'{SERIF}\' font-size="12" font-style="italic" '
             f'fill="#333">honest = 0</text>')
    s.append(f'<text x="20" y="{H - 16}" font-family="{SANS}" font-size="10" fill="#aaa">Bazaar Markets engine 1.2.0, '
             f'state bank v2 (runs/state_bank_v2/states.jsonl.gz): 24 markets, seeds 600–699, days 5–20. Dots: mean '
             f'over K = 20 paired continuations;</text>')
    s.append(f'<text x="20" y="{H - 2}" font-family="{SANS}" font-size="10" fill="#aaa">lines: 95% t intervals, '
             f'unadjusted; open circles: beyond the axis. Unweighted; 176 states come from one stratum '
             f'(40% tourists, full enforcement).</text>')
    s.append("</svg>")
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(s) + "\n")
    print(OUT)


if __name__ == "__main__":
    main()
