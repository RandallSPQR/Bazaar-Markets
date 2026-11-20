# Formal-model cross-check (Stage 2, step 1)

- **Compared:** `docs/formal_model.md` (export rev 42, written against engine 0.15.0) against the engine code, equation by equation and rule by rule: `engine/*.py` (world, bazaar, brands, days, licensing, critics, detection, valuation, benchmark, m0, scaling), `agents/rule_based.py`, `agents/registry.py`, and the defaults in `engine/config.py`. Intent was checked against `docs/config_reference.md`, the version history in `engine/__init__.py`, and code comments.
- **Engine version:** 0.21.0 (`engine/__init__.py:88`).
- **Commit:** written against `7bc8142` plus the 0.21.0 working tree, which was committed unchanged as `4a83784` (engine 0.21.0); code line numbers below refer to 4a83784.
- **Date:** 2026-11-19.
- **Method:** read-only. No test or simulation was run; defaults were confirmed by reading `engine/config.py`, plus one import (`_apportion([0.3, 0.4, 0.3], 16)` = [5, 6, 5]; `BazaarConfig()` defaults for tau, bargain_q_req, premium and recognition_range).
- **Doc line numbers:** "old" is the line in the rev 42 export; "new" is the line in the edited `docs/formal_model.md`.
- **Result codes:** *matches*; *doc wrong (fixed)*: the doc differed from code that agrees with its own documented spec, and the doc was corrected (this includes omissions and keys added after 0.15.0, written in paragraphs labelled "added at the 1.0.0 cross-check"); *code wrong?*: the code contradicts a deliberate, documented specification elsewhere in the repo.

| # | Item | Doc (line) | Code (file:line) | Result | Note |
|---|---|---|---|---|---|
| 1 | Categories, 16 stalls per category, type shares | old 6 / new 6 | world.py:146-151, 185-210; config.py:73-74, 100 | matches | Largest-remainder apportionment gives 6 genuine / 5 seconds / 5 deceptive per category; count added to the doc. |
| 2 | Euclidean distance; fresh buyers each day | old 6 / new 6 | bazaar.py:62-63; days.py:3-10 | matches | `math.hypot`. |
| 3 | True quality q_s and pitched quality q̂_s draws | old 11 / new 11 | world.py:214-220; config.py:101-102 | matches | Both draws are made for every stall; genuine uses the high draw, seconds and deceptive the low; deceptive pitch = high draw. |
| 4 | Posted price formula (premium, start-of-day rating) | old 15 / new 15 | brands.py:193-208; world.py:221-227; bazaar.py:187-197 | doc wrong (fixed) | `int(round(base * tier * (1 + premium * (r - 0.5))))` with r = `shown(cfg, st.rating)` (displayed start-of-day rating of the brand, 0.5 unrated); applied only when brands are on (`morning_prices` is called only in the brands branch). Doc lacked the rounding, the displayed rating and the brands-only condition. |
| 5 | Seconds price factor φ_N | old 18, 76 / new 18, 157 | config.py:110; world.py:222-223; brands.py:185 | matches | 0.55. |
| 6 | Deceptive price factor φ_F | old 18 / new 18, 158 | config.py:111; world.py:224-225; brands.py:185; days.py:87 | doc wrong (fixed) | Doc fixed φ_F = 1; code has `pricing.deceptive_price_factor` (default 1.0; 0.8 used in the choice-set counterfeit pilot). Added as a parameter and a table row. |
| 7 | Reputation premium π default | old 18, 77 / new 18, 161 | config.py:312-314 | doc wrong (fixed) | Doc: "0 unless brands are on (then 0.4)". Code default is 0.0 even with brands on; 0.4 is the value set in the runs (comment config.py:312). |
| 8 | Counterfeit price factor χ | old 18, 78 / new 108-114, 162 | brands.py:217-229, 205-208; config.py:323-325 | doc wrong (fixed) | Domain is (0, 10] (validated brands.py:228-229), not (0, 1]. Price = round(χ × the price of the stall bearing the original name that is neither a counterfeit nor a licensee), own rule if none. See also candidate C1. |
| 9 | Unit cost k_s | old 15 / new 15 | world.py:233; brands.py:335-338; days.py:91 | matches | Rounded to cents; doc now shows the rounding. |
| 10 | Fine F_c | old 15 / new 15 | world.py:236; bazaar.py:546-552 | matches | `round(base * penalty_mult)`, 1.5. |
| 11 | Ad costs per yell / whisper | old 18 / new 18 | world.py:234-235; bazaar.py:414-419 | matches | Rounded; signs and answers are free (stated in the doc now). |
| 12 | Units needed n_b | old 20 / new 20 | config.py:132; world.py:364 | matches | Uniform integer on [1, 2]. |
| 13 | Quality requirement Q_b | old 20 / new 20 | config.py:133; world.py:365 | matches | U[0.50, 0.70], rounded to 4 dp. |
| 14 | Bargain hunters' Q_b | old 20, 95 / new 20, 195-196 | config.py:162-167; world.py:343-370 | doc wrong (fixed) | Doc: U[0.15, 0.40]. Code default `bargain_q_req = [0.30, 0.45]` (since 0.11.0; config_reference.md:263); [0.15, 0.40] is an override set in every choice-set run from verification on (analysis/verification.py:62, liability.py, licensing.py). Doc now gives both. Bargain share default (0 walk, 0.2 choice set) matches (world.py:260-264). |
| 15 | Budget W_b and levels | old 22-26 / new 22-26 | world.py:373-380; config.py:134-135 | matches | Rounded to cents; "mixed" draws a level per buyer (stated now). |
| 16 | budget_factor_override | old 26 / new 26 | config.py:136-138; world.py:379 | matches | |
| 17 | Inspection cost | old 26 / new 26, 166 | world.py:395; config.py:181; bazaar.py:697-701, 728-732 | doc wrong (fixed) | Notation κ_π clashed with the premium π; now κ_{prof(b)}. Rounded to cents, paid from the budget; inspection reveals q_s exactly (bazaar.py:732). |
| 18 | Walk-mode route | old 26 / new 26 | world.py:336-340, 382; config.py:182 | matches | 1–3 aisles (capped at the number of aisles), random entrance end; arrivals spread evenly (added). |
| 19 | Choice-set consideration-set weights | old 26-30 / new 26-32 | world.py:280-308, 358; bazaar.py:113 | doc wrong (fixed) | Doc wrote Pr(s ∈ M_b) ∝ e^{−γρ_s}, an inclusion probability. Code is successive sampling without replacement: per-draw probability ∝ e^{−γρ_s} among the stalls not yet drawn (world.py:302-306). Also: entrance end drawn with probability 1/2 (296), exited stalls excluded (358), search depth = m (bazaar.py:113). |
| 20 | Signs and yells: reach | old 32 / new 34 | bazaar.py:373-374, 416, 425-430, 446 | matches | Sign once per person per stall epoch; yell to everyone in earshot. Added: a seller decides only when someone is in earshot or an ask is pending (bazaar.py:376). |
| 21 | Whisper and answer reach | old 32 / new 34 | bazaar.py:379, 392-399, 419-421, 726-727, 513-519 | doc wrong (fixed) | Whisper: one target within whisper range (matches). Answer: doc said "within the whisper range"; code sends an answer to a buyer or disguised inspector that asked, and asks are made from within the interact range (1 cell). No whisper-range test applies to answers. |
| 22 | Falsity f | old 32 / new 34 | bazaar.py:434, 450; detection.py:40-41 | matches | f = q̃ − q_s when positive; true claims never caught. |
| 23 | Profile noise η | old 32 / new 34 | bazaar.py:257-265; config.py:183 | matches | Random profile with probability η (may coincide with the true one), stable per seller–person pair. |
| 24 | Uniform recognition range | old 32, 85 / new 34, 172 | bazaar.py:154-155, 807-808 | matches | Only passers-by in earshot are listed, so a range above ℓ_yell acts as ℓ_yell; code does not validate an upper bound. Table domain reworded. |
| 25 | Detection probability | old 36-38 / new 38-40 | detection.py:39-48; bazaar.py:448-453 | doc wrong (fixed) | Code: catch iff `u < pr * capture_factor * detect_scale`, draw consumed only when pr > 0; at most one catch per stall per tick (`caught_now`); perceivers are dedicated inspectors and enforcing inspector-buyers (bazaar.py:267-272). Doc now has min(1, ·) (σ may exceed 1), the capture factor c_{i,s} inside the formula, the one-catch rule and the perceivers. |
| 26 | σ = detect_scale | old 40, 88 / new 42, 175 | config.py:223-226; bazaar.py:202-207 | doc wrong (fixed) | σ is `inspectors.detect_scale`. Domain: code accepts any finite value ≥ 0, doc said [0, 1]. |
| 27 | w_h, g_h, ℓ_h, f_0, flat proximity | old 37, 40, 84, 86-87 / new 39, 42, 171, 173-174 | detection.py:33-48; config.py:78-80, 238-240; bazaar.py:281-283 | matches | Defaults 1 / 1 / 0.6 / 0.4 and 0.3. Alternatives step and hazard added to the doc. |
| 28 | Closure for L ticks | old 40 / new 42 | bazaar.py:554-555, 240-241 | matches | `closed_until = t + 1 + L`, so closed on the L ticks after the catch tick; the epoch increments (signs re-perceived). |
| 29 | Fine timing and lag Λ | old 40 / new 42 | bazaar.py:546-552, 209-215; days.py:160 | matches | Lagged fine charged at the start of day d + Λ if the stall has not exited. |
| 30 | Uncollectible after exit; outstanding at close | old 40 / new 42 | bazaar.py:1001-1008; days.py:252-261 | matches | "Outstanding at close" was missing from the doc's sentence and is added. |
| 31 | Inspector capture factor | old 40 / new 40-42, 176 | bazaar.py:228-232; critics.py:67-71; config.py:217-222 | matches | (1 − ε), ε = capture_effect 0.8; ties drawn per (inspector, genuine-origin brand) with probability `capture` (default 0). Named as parameters now. |
| 32 | Inspector placements | old 40 / new 42 | world.py:398-420 | matches | |
| 33 | Exit (seller action) | none (old 59 mentions it) / new 44 | bazaar.py:410-411, 1001-1008; days.py:161-162; world.py:358; brands.py:249-252, 283-284 | doc wrong (fixed) | 0.15.0 feature the doc left out: leaves at the end of the day, closed every later day, in no consideration set, no counterfeit target, pending fines uncollectible. Paragraph added. |
| 34 | Buyer's quality estimate | old 42 / new 46 | rule_based.py:362-371, 400-405 | matches | Own assessment, else inspection, else latest claim. |
| 35 | Who inspects: θ_l, θ_e, affordability | old 42 / new 46, 167 | rule_based.py:311-317, 332-344, 374-382, 407-413; config_reference.md:449-457 | doc wrong (fixed) | Draw made once per (buyer, stall), only when θ is strictly inside (0, 1). When inspection cost + price exceeds the budget left, an expert skips the stall and a local buys on the claim (377-382); the doc only gave the affordability condition. |
| 36 | Tourists never inspect | old 42 / new 46 | rule_based.py:323-330 | doc wrong (fixed) | True by default; since 0.21.0 a tourist given an inspect_prob override follows the local rule. |
| 37 | Candidate rule; units bought | old 42 / new 46 | rule_based.py:358-367, 395-405, 462 | matches | min(need, ⌊left / price⌋). Asking a silent affordable stall (383-387) added. |
| 38 | Rating threshold τ | old 42 / new 46, 168 | rule_based.py:311-313, 357, 392-393; registry.py:47-48; config.py:284 | doc wrong (fixed) | Doc hard-coded 0.5. Threshold is `ratings.tau` (default 0.5, PLACEHOLDER), passed to rule_buyer as `rating_tau`, applied to the displayed rating; unrated stalls are never skipped. Row added to the table. |
| 39 | Choice at search depth 1 | old 42 / new 46 | rule_based.py:356-382 | doc wrong (fixed) | Doc was silent. At depth 1 the buyer goes through stalls within reach by (price, tie-break) and acts at the first candidate; ratings enter only through τ. |
| 40 | When a searching buyer may buy | old 42 / new 46 | bazaar.py:652-657 | doc wrong (fixed) | Doc: "after seeing k stalls". Code: after seeing k stalls or at the end of its route; once in "choose" it stays there (0.14.0). |
| 41 | Lexicographic choice: highest displayed rating, then lowest price | old 42 / new 46, 92-98 | rule_based.py:448-464 | matches | Key (−rating, price, tie), unrated = 0.5 (456). |
| 42 | Tourists rank by lowest price | old 42 / new 46 | rule_based.py:455-457; bazaar.py:883-889 | matches | Rows carry `rating` only for buyers who see ratings; others rank by (price, tie). |
| 43 | Rating visibility | old 42 / new 64, 169 | config.py:280-285; bazaar.py:883-889 | matches | Public mode, profiles in `visible_to` (local, expert). Table row added. |
| 44 | Tie-break (0.20.0) | none / new 92-98, 184 | rule_based.py:356, 456-457, 467-470; bazaar.py:219-226, 851-852, 909-910; config.py:148-151 | doc wrong (fixed) | Added at the 1.0.0 cross-check. Code note: the searching buyer's learn-first loop (rule_based.py:429) orders stalls to inspect or ask by (price, stall id), not by tie_rank. That ordering decides what it inspects first, not what it buys, so it agrees with the spec ("ranks stalls to buy from", config_reference.md:260). |
| 45 | profile_overrides (0.21.0) | none / new 100-106, 185 | bazaar.py:37-54, 172, 863-889; rule_based.py:323-344, 377, 407-411, 440; config.py:152-161 | doc wrong (fixed) | Added at the 1.0.0 cross-check: reads_ratings replaces `visible_to`, inspect_prob replaces θ; bargain keys win; a tourist with θ follows the local rule. |
| 46 | Honest seller rule | old 44 / new 48 | rule_based.py:24-58 | matches | Yell at ≥ 3 in earshot, cooldown 8; one whisper per tick to the nearest in whisper range not yet whispered to; answers every ask. |
| 47 | Naive deceptive seller | old 44 / new 48 | rule_based.py:101-108 | doc wrong (fixed) | Also does not whisper to observed experts (`wants_whisper`), which the doc left out. |
| 48 | Adaptive deceptive seller | old 44 / new 48 | rule_based.py:134-156; bazaar.py:775-785, 802 | doc wrong (fixed) | (a) While hiding it goes quiet entirely (no yell, no whisper, even truthful), not only "no false claim". (b) The catch-notice condition is a catch 1 to L ticks ago (`1 <= ago <= L`), not "less than L ticks old". Reopen condition `0 <= tick − reopened < L` matches. |
| 49 | Buyer value V_b(q) (line-49 export glitch) | old 48-49 / new 50-54 | valuation.py:17-25; config.py:246-251 | doc wrong (fixed) | Equation was cut off after "q / Q_b & q" and ran into the Ratings paragraph. Restored: V = v b_c if q ≥ Q_b, else ς v b_c q / Q_b (default); linear and concave alternatives listed. |
| 50 | Buyer surplus U_b (lost in the glitch) | old 49 / new 52-54 | bazaar.py:754-756, 929-930 | doc wrong (fixed) | U_b = Σ units (V − price) − inspection spend, rebuilt from `value - paid_cents - inspect_spent_cents`. |
| 51 | Stall profit Π_s (lost in the glitch) | old 49 / new 56-60 | days.py:55-57; bazaar.py:948-951, 1077-1078 | doc wrong (fixed) | Revenue − unit costs − ad spend − fines charged − switching cost − royalties paid + royalties received; run total = sum over days. |
| 52 | What ratings attach to; when computed | old 49 / new 64 | days.py:192, 209-216; config.py:278-282 | doc wrong (fixed) | Doc: "Ratings attach to brand names". Only with brands on; per stall otherwise (`update_ratings`). Computed only for mode hidden or public (off by default). |
| 53 | Rated-unit share ȳ | old 49 / new 64 | brands.py:310-316; days.py:67-73 | doc wrong (fixed) | Doc: "claim the buyer acted on". Code: the latest claim the buyer had received from the stall before buying (`known_claims[-1]`), even if it then inspected; units bought with no claim are not rated. Critics' reviews count as `weight` rated units (brands.py:306-309). |
| 54 | Rating update and starting value | old 52 / new 66-70 | brands.py:317-321; days.py:74-77; brands.py:195 | doc wrong (fixed) | Doc: r_{s,1} = 0.5. Code: a name starts unrated (None); its first rating is that day's share, with no blend; a day with no rated units leaves it unchanged; readers count unrated as 0.5. Matches config_reference.md:177-181. |
| 55 | Rating memory λ | old 52, 93 / new 68, 181 | config.py:283 | matches | 0.7 PLACEHOLDER. Code does not validate the [0, 1) domain. |
| 56 | Tourists' reviews of a counterfeit | old 55 / new 72, 114 | bazaar.py:250-255, 767; brands.py:313 | matches | Filed under `perceived_brand`: the original's name for tourists. |
| 57 | Renaming only at reopening | old 55 / new 72 | bazaar.py:382-383, 564-565, 568-592 | doc wrong (fixed) | Brands only; licensees (0.16.0) and day-entry counterfeits (0.17.0) never get a rename. |
| 58 | Displayed ratings: stars, display_step (0.20.0) | none / new 76-82, 183 | brands.py:109-128, 204, 256, 287-288; bazaar.py:818, 850, 908; config.py:295-302 | doc wrong (fixed) | Added at the 1.0.0 cross-check: Δ⌊r/Δ + 1/2⌋ (+1e-9 guard), readers listed; stored rating and logs unrounded. |
| 59 | Rating prior prior_n, prior_scope (0.18.0, 0.19.0) | none / new 84-90, 182 | brands.py:135-166, 317-323; bazaar.py:93-94, 161-167; config.py:287-294 | doc wrong (fixed) | Added at the 1.0.0 cross-check: share = (H + 0.5w)/(C + w), w = n_0 λ^{d − d_n}, fades every day end; scope "new" = names created on day ≥ 2. |
| 60 | Critics (0.11.0) | none / new 74, 193 | critics.py:74-118; days.py:208-212; config.py:328-348 | doc wrong (fixed) | Pre-0.15.0 feature the doc never mentioned; short paragraph and table row added (off by default). |
| 61 | Counterfeit at reopening: target and claim | old 55 (implicit) / new 108 | brands.py:279-291; bazaar.py:568-592 | doc wrong (fixed) | Target: highest displayed-rated name among other stalls of the category that are not seconds, not counterfeits, still in the market; ties at random; a fresh name if none. A reopening counterfeit keeps its own q̂_s (`rename` does not touch `q_pitch`). See note N1. |
| 62 | Counterfeit entry "day" (0.17.0) | none / new 108-114, 186 | brands.py:241-269; bazaar.py:192-195; config.py:315-322 | doc wrong (fixed) | Added at the 1.0.0 cross-check: on day d_cf, every deceptive non-licensee stall still in the market copies the top displayed-rated genuine brand (non-counterfeit, non-licensee, still in the market), claims its q, never renames; stream [seed, 23]. |
| 63 | Licensing: owner brand, cheap / contract, royalty (0.16.0) | none / new 116-128, 187-189 | licensing.py:44-144; bazaar.py:95-97, 127, 196-197, 543-545, 750-753 | doc wrong (fixed) | Added at the 1.0.0 cross-check: licensee selection [seed, 19, o]; q̂ = q_o; q = q_o (contract) or low draw (cheap); price = owner's; royalty units × round(ρp); owner_liable moves the fine (closure stays). |
| 64 | White labels and white_label_tier (0.17.0, 0.18.0) | none / new 128-134, 190 | licensing.py:109-122, 135-140; brands.py:181-185; bazaar.py:544, 750 | doc wrong (fixed) | Added at the 1.0.0 cross-check: fresh name [seed, 24, o], no royalty, no owner liability, own-rating price with tier φ_τ ("type") or 1 ("genuine"). |
| 65 | Counterfeit price when the original name is borne by a white-label licensee | none / new 112-114 | brands.py:205-208 | code wrong? | See candidate C1. Not reached in any published run. |
| 66 | Multi-day type revision | old 57 / new 136 | days.py:94-140, 181-182; config.py:264-267 | doc wrong (fixed) | Doc: partner "a random stall s' of its category". Code: the partner is drawn from the other genuine and deceptive stalls (seconds are never partners); the update is synchronous; a switched stall redraws q, q̂ and price; brands require imitation and mutation off. Normaliser max − min matches "max abs ΔΠ"; mutation 0.02 matches. |
| 67 | Bust-out mechanics | old 59 / new 138 | bazaar.py:594-606; brands.py:327-338; days.py:154-155 | doc wrong (fixed) | Doc: "keeps its name, sign and price". Code: the sign switches to "pitch" (showing the old quality, since q̂ = old q); the price rule, not the price, is unchanged (morning prices still follow the rating); unit cost falls to the cost at the low quality, drawn from [seed, 12, stall]. |
| 68 | Bust-out with exit timing | old 59 / new 138 | benchmark.py:36-40; rule_based.py:274-280 | matches | Exit at the end of day b + h − 1. |
| 69 | Bust-out gain: floored and unfloored | old 61-65 / new 140-144, 192 | benchmark.py:7-10, 21, 55-67, 70-76 | doc wrong (fixed) | Doc gave one G_s with 𝓑 "candidate days", unclear whether "never" is in it. Code has gain_unfloored = max over bust-out days − never (primary since 2026-11-07) and gain_floored = max over all candidates including never − never = max(G, 0). Default candidates {never, 10, 20, 25, 27, 28, 29}; validated days in [2, D]. |
| 70 | Outcomes | old 67 / new 146 | bazaar.py:928-999, 1010-1056; days.py:247-262 | doc wrong (fixed) | Guard outcomes are `stuck_buyers` and `idle_choosers`; "parked" names the 0.14.0 bug, not an outcome. Surplus is the mean over buyers who arrived. Others match. |
| 71 | M0 compatibility mode | old 69 / new 148 | m0.py:78-81, 106-110, 130-140 | doc wrong (fixed) | A deceptive impression that reaches an enforcer earns nothing and costs P (m0.py:108-110); initial bids U[0, 0.5), clipped to [0.001, 1] after mutation; idle firms rank lowest. Rest matches. |
| 72 | Table: D, T | old 73 / new 152 | config.py:77, 89; scaling.py:41 | matches | Domain reworded: T real ticks, T k engine ticks; D 30 or 60 in multi-day runs. |
| 73 | Table: k | old 74 / new 153 | config.py:86 | matches | |
| 74 | Table: b_c | old 75 / new 154 | config.py:109 | matches | |
| 75 | Table: β | old 79 / new 164 | config.py:134-138 | matches | |
| 76 | Table: m, γ | old 80 / new 165 | config.py:178-180; world.py:267-277 | matches | |
| 77 | Table: θ_l, θ_e | old 82 / new 167 | rule_based.py:311-317 | matches | rule_buyer params, default 1.0. |
| 78 | Table: η | old 83 / new 170 | config.py:183 | matches | |
| 79 | Table: channel ranges | old 84 / new 171 | config.py:78-81; scaling.py:42-45 | matches | Interact range 1 added. |
| 80 | Table: L | old 89 / new 177 | config.py:116 | matches | |
| 81 | Table: F_c | old 90 / new 178 | config.py:115 | matches | |
| 82 | Table: Λ | old 91 / new 179 | config.py:121; bazaar.py:205-206 | matches | Domain integer ≥ 0. |
| 83 | Table: v, ς | old 92 / new 180 | config.py:250-251 | matches | |
| 84 | Table: N_B, N_I | old 94 / new 194 | config.py:130, 198 | matches | |
| 85 | Table: bargain share | old 95 / new 195 | world.py:260-264 | matches | |
| 86 | Table: profile shares | old 96 / new 197 | config.py:131 | matches | |
| 87 | Table: rows for keys or parameters missing from the table | none / new 155-160, 163, 176, 182-193, 196 | config.py (sections as cited in rows 6, 14, 31, 38, 58-64, 66, 69) | doc wrong (fixed) | Added rows: type shares, q ranges, φ_F, c_0 and c_1, ad cost, n_b and Q_b, τ, visible_to, capture and ε, n_0 and scope, display and Δ, tie-break, profile overrides, counterfeit entry and d_cf, licence schedule and quality, ρ, owner liable, licence brand and white-label tier, revise and mutate, 𝓑, critics, bargain Q_b. |

### Candidates for "code wrong?"

**C1. A counterfeit of a white-label brand does not follow the white label's price** (`engine/brands.py:205-208`).

```python
holder = {st.brand: st for st in stalls if st.counterfeit_of is None and st.licensed_from is None}
for st in stalls:
    if st.counterfeit_of is not None and st.counterfeit_of in holder:
        st.price_cents = counterfeit_price(cfg, holder[st.counterfeit_of].price_cents)
```

- **Spec it contradicts.** `docs/config_reference.md:207-211` says a counterfeit "then takes the current price of the stall bearing the original's name". The `engine/brands.py` docstring (lines 19-20) says "A counterfeit posts the current price of the stall bearing the original's name (its own rule if none does)". `engine/config.py:323-324` says "A counterfeit posts round(counterfeit_price_factor x the original's posted price) each day (both entry modes)".
- **What the code does.** The `licensed_from is None` filter was added at 0.16.0 (commit 6e0b3b2), when every licensee bore its owner's name; there it keeps the owner, not a licensee, as the holder. At 0.17.0 white labels arrived. A white-label licensee is the only stall bearing its fresh name, but it also has `licensed_from` set, so it is excluded. A counterfeit of a white-label name therefore posts its own rule's price on every later morning. On the rename day it does post the right price, because `rename` sets `counterfeit_price(cfg, target.price_cents)` at bazaar.py:585.
- **When it can happen.** Only with `licensing.brand` "white_label", a deceptive-type white-label licensee as the highest-rated non-seconds name in its category, and a deceptive seller that renames to "counterfeit" at reopening. Counterfeit entry "day" cannot target licensees (brands.py:251-252).
- **Reachability.** Every published white-label run (`analysis/brand_equity*.py`, `check_vs_read.py`) uses naive deceptive sellers with fresh reopening, so no saved run reaches this case and no reference cell would change. Not fixed (read-only audit). The doc states the specified rule.
- **Decision (2026-11-19 13:00).** Reported as a STOP (`runs/STATUS.md`, 12:55). Randall chose to fix it in 1.0.0: owner-branded licensees stay out of the name→stall map and a white label's own stall goes in, as its own Stage 2 commit, with a test that every reference cell still reproduces. Deferred until the Stage 1 main run (engine 0.21.0) finishes, so that run imports unchanged code. **Fixed at engine 1.0.0 (2026-11-20, the commit that bumps the engine to 1.0.0):** `engine/brands.py` `morning_prices` keeps a white-label licensee in the name→stall map and an owner-branded licensee out. `tests/test_v100.py` checks both cases and the no-holder case; the white-label test fails on the 0.21.0 code. All 174 0.20.0 reference cells and the licensing, counterfeit, 0.17.0 and 0.18.0 tests reproduce at 1.0.0 (660 passed, `runs/tests_100_c1.log`).

### Notes (ambiguities, not counted as code wrong)

**N1. "It still claims the original's quality"** (`engine/config.py:324`, `docs/config_reference.md:190`) is written for both entry modes. In code, only day-entry counterfeits set q̂ to the original's true quality (brands.py:266). A counterfeit made by renaming at reopening keeps its own pitched quality: bazaar.py:568-592 never changes `q_pitch`, which has been the behaviour since 0.8.0, and the reopening spec (config_reference.md:196-203, brands.py:11-13) says nothing about claims. This reads as loose wording in the 0.17.0 comment rather than a deliberate rule for reopening counterfeits. The doc states what the code does. To do at 1.0.0 (with the C1 fix, after the Stage 1 run): reword config.py:324 and config_reference.md:190.

**N2. Searching buyer's learn-first order** (rule_based.py:429) sorts by (price, stall id) even under tie_break "random". This agrees with the tie-break spec, which governs only the ranking for purchase (row 44).

### Count by result

| Result | Rows |
|---|---|
| matches | 46 |
| doc wrong (fixed) | 40 |
| code wrong? | 1 |
| **Total** | **87** |
