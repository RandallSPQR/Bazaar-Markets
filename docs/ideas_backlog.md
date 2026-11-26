# Ideas backlog (parked, not preregistered)

Exploration notes from 2026-11-24, made while the 2026-11-23 plan was running. Nothing here is a prediction until it is copied into a plan file and committed before a run. Ordered roughly by dependency.

## A. Agent shoppers (from Mollick et al. 2026 and a16z/Prompting Co. 2026)

Reading the Stage 1 check-vs-read cells post hoc, the agent shopper is a local who reads ratings and does not inspect:
- Bust-out gain without inspectors: −$76 with human locals, +$165 with agent locals.
- Reputation effect at slow speed: +$1,825 with human locals, +$8,051 with agent locals.
- With inspectors, the cash-in loses in every cell.
- Ratings catch known deceivers but not a sudden switch; inspection catches the switch on the day.

Ideas:
1. **Agent-share sweep.** Vary the share of locals who read ratings and do not inspect, from 0 to 1. Find where cashing in starts to pay (an "agent threshold"). Guess: about two thirds of buyers not inspecting.
2. **Faster ratings vs inspection.** Lower the rating memory and/or add a same-day review alert. Can fast reaction replace checking? Guess: it shrinks the harvest but not the first day's take.
3. **"Too good to be true" buyer heuristic.** Avoid offers more than about 50% below the reference price (a16z pattern). Predicted to block deep fakes and stop the undercut price war above cost, which (per the price-war study) should restore verification's protection and brand value.
4. **Certifier capture with agent buyers.** Agents defer to one expert source (Wirecutter in Mollick). Run critic capture with agent-style buyers.
5. **Steering through the pitch (LLM buyer battery).** Mollick-style order, format and memory manipulations, using the seller's yell and whisper as the prior context.

Pairs that fit together: 1+3, 4+5.

## B. Category profiles (the three aisles)

Right now fish, electronics and designer are one market at three price scales: same cost formula, same buyer rules. Dollar results are designer-weighted.

0. **Analysis only, first:** split existing results by category, in dollars and in units of base price.
1. **Profiles** (draft values; refine with Randall's client data):

| Setting | Fish (experience good) | Electronics (search good) | Designer (credence good) |
|---|---|---|---|
| Price ÷ cost, genuine stall at top rating | ~1.45× gross (contribution ~10–15% after labor and spoilage) | ~1.3× on the main product; add-on at 2–3× | ~5× (sensitivity at 4× and 10×) |
| Cheap-supply cost, as a share of genuine cost | high | medium | very low |
| Fixed daily cost | high relative to sales | medium | high |
| Spoilage of unsold stock | yes | no | no |
| Inspection | cheap, accurate after purchase | cheap, accurate before purchase | expensive or noisy |
| Review accuracy | high and fast | high | low |
| Repeat purchase | daily | rare | rare |

2. **Unbundle margin from verifiability.** Cross the two as a design, as Stage 1 unbundled reading from inspecting.

Hypotheses:
- Thin-margin goods cheat on cost: quality shading, with spoilage as the motive.
- Fat-margin goods cheat on reputation: bust-out, licensing, counterfeits.
- Electronics cheats in the add-ons.

Market reference figures (orders of magnitude, sources in the 2026-11-24 chat):
- Food retail net margin 1.7% (FMI 2024); seafood department gross margin ~32% (Progressive Grocer, 2010).
- Electronics retail gross margin ~22–24%; accessories 50–70%.
- Luxury markups 4–6× cost and up; LVMH Fashion & Leather Goods operating margin 35%, Hermès 41% (2025).

## C. Rent, solvency and spot auctions

Rent is a fixed cost and cancels out of every arm-to-arm gain. It only matters through solvency, decisions that read profit, cash constraints, or who gets which spot.

1. **Solvency.** Each stall has a cash balance and a credit limit, with forced exit below the limit. Tests the **rent trap**: stalls near insolvency cash in because they will lose the spot anyway (the limited-liability logic again).
2. **Rent gradient.** Turn γ on. Rent = α × the spot's traffic advantage, with α ∈ {0, 0.5, 1} (Ricardian rent at 1). Give tourists a higher γ than locals.
   - Tests **tourist traps**: deception concentrates in prime, tourist-heavy spots.
   - Tests **rent as a bond**: a costly spot as a hostage (Klein–Leffler).
3. **Spot auction.** Periodic bidding for positions.
   - Tests sorting by margin (designer at the corners, fish at the back).
   - Tests Marti's original question in spatial form: do deceptive sellers outbid honest ones for prime placement, and does verification change the answer? This closes the loop from M0's ad auction to the bazaar.

Order: C1 → C2 (with B1) → C3.

## Measurement notes

- Report results per category and in units of base price.
- In any LLM battery, randomise option order, observation format and a memory/persona line (Mollick); report per-model stability, not only means.
- Literature to read and verify before citing: Allouah et al. 2026 (ACES, agent shopping); Cherep et al. 2026 (agents hypersensitive to nudges); Klein & Leffler 1981; Shapiro 1983; Nelson 1970; Darby & Karni 1973; Alonso 1964 (bid-rent).
