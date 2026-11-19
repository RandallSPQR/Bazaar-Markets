<!-- Exported from the project doc 'Bazaar Markets: The Agentic Ad Engine', section 'Formal model of the bazaar engine', rev 42, on 2026-11-19. Written against engine 0.15.0; later keys (licensing, counterfeit entry/price factor, white_label_tier, prior_n/scope, display stars, tie_break, profile overrides) are not in it. -->
## Formal model of the bazaar engine

This section states the engine as a model: sets, stall and buyer primitives, messages, detection, decision rules, payoffs and outcomes, with every parameter's domain and default in the table at the end. It follows the specifications given to the engine through version 0.15.0; the code (`engine/*.py`) is the source of truth, and a line-by-line cross-check against it is still to do. PLACEHOLDER marks a modelling choice not yet backed by data.

**Sets and time.** Days d = 1, …, D and ticks t = 0, …, T − 1 within a day. Categories C = {fish, electronics, designer}, one aisle each. Stalls s ∈ S, 16 per category, each with a type τ_s ∈ {G, N, F} (genuine, seconds, deceptive) apportioned 0.4 / 0.3 / 0.3 within each category. People are buyers b ∈ B (a fresh population each day) and inspectors i ∈ I. Buyer profiles are tourist, local and expert; a share of buyers are bargain hunters. Positions are cells on an integer grid; distance is Euclidean.

**Stalls.** Base price b_c by category; true quality q_s; pitched quality q̂_s; posted price p_s; unit cost k_s; fine F_c; ad costs per yell and whisper.

$$
q_s \sim \begin{cases} U[0.70,\,0.95] & \tau_s = G \\ U[0.15,\,0.45] & \tau_s \in \{N, F\} \end{cases} \qquad \hat q_s = \begin{cases} q_s & \tau_s \in \{G, N\} \\ U[0.70,\,0.95] & \tau_s = F \end{cases}
$$

$$
p_{s,d} = b_c\,\phi_{\tau_s}\,\bigl(1 + \pi\,(r_{s,d} - 0.5)\bigr), \qquad k_s = b_c\,(0.30 + 0.50\,q_s), \qquad F_c = 1.5\,b_c
$$

with φ_G = φ_F = 1 and φ_N = 0.55. The reputation premium π is 0 unless brands are on (then 0.4), and a counterfeit posts χ times the copied brand's price. Ad cost is 0.002 b_c per yell and 0.004 b_c per whisper.

**Buyers.** Each buyer gets a task (c_b, n_b, Q_b, W_b): category, units needed n_b ∈ {1, 2}, quality requirement Q_b ∼ U[0.50, 0.70] (bargain hunters U[0.15, 0.40]), and budget

$$
W_b = n_b\, b_{c_b}\, \beta_b, \qquad \beta_b \in \{1.25,\ 1.0,\ 0.8\}
$$

for budget levels above, at and below (or a fixed override). Inspecting a stall costs κ_π b_c, with κ = 0.10, 0.05, 0.02 for tourist, local, expert. In walk mode a buyer walks a seeded route through 1–3 aisles. In choice-set mode it draws a consideration set M_b of m stalls of its category, without replacement, and walks its aisle past all of them:

$$
\Pr(s \in M_b) \propto e^{-\gamma\,\rho_s}, \qquad \rho_s = \text{position rank of } s \text{ from the buyer's entrance}
$$

**Messages.** Channels h ∈ {sign, yell, whisper, answer}. A sign reaches everyone within the sight range (once per person per stall opening), a yell everyone within earshot, a whisper or an answer one addressee within the whisper range. A message from s carries claim q̃ ∈ {q_s, q̂_s}, with falsity f = max(0, q̃ − q_s). Sellers see each passer-by's profile correctly with probability 1 − η, otherwise a uniformly random one, and see a uniform on a uniformed inspector within the recognition range.

**Detection and sanctions.** When an inspector i perceives a false message from s on channel h at distance δ:

$$
\Pr(\text{catch}) = \sigma \cdot w_h \cdot g_h(\delta) \cdot \min\!\left(1,\ \frac{f}{f_0}\right), \qquad g_h(\delta) = \begin{cases} \max(0,\ 1 - \delta/\ell_h) & h \in \{\text{sign},\ \text{yell}\} \\ 1 & h \in \{\text{whisper},\ \text{answer}\} \end{cases}
$$

with σ the enforcement intensity, w_h the channel weight and ℓ_h the channel range (g = 1 for every channel when proximity is flat). A catch closes the stall for L ticks and imposes fine F_c, at once or after a lag of Λ days; a fine falling due after the stall has exited is uncollectible. A captured inspector's catch probability for a tied brand is multiplied by (1 − 0.8). Placements: fixed posts, clustered posts, patrolling, or disguised among buyers (single trip or full shift).

**Buyer rule.** The buyer's estimate of a stall's quality is its own assessment if it has one (inspector-buyers with knowledge), else its inspection result, else the latest claim heard. Tourists never inspect. Experts inspect before buying with probability θ_e, and locals inspect a stall that yelled or whispered at them with probability θ_l, if the inspection cost plus the price fits the remaining budget. A stall is a candidate if the estimate is at least Q_b and the price fits the remaining budget; the buyer buys min(units needed, units affordable). With search depth k (or consideration set m) it chooses among candidates after seeing k stalls: buyers who can see ratings (locals, experts) take the highest rating, then the lowest price, and skip stalls rated below 0.5; tourists take the lowest price.

**Seller rules.** Honest sellers always tell the truth, yell when at least 3 people are in earshot (cooldown 8 ticks), whisper to the nearest passer-by they haven't whispered to, and answer every ask. The naive deceptive seller pitches q̂_s, but tells observed experts the truth and holds its yell while one is near. The adaptive deceptive seller also makes no false claim on any channel while a uniformed inspector is within the recognition range, a catch notice from earshot is less than L ticks old, or its own stall reopened less than L ticks ago; while hiding, its sign shows the truth.

**Payoffs.**

$$
V_b(q) = \begin{cases} v\, b_c & q \ge Q_b \\ \varsigma\, v\, b_c\, q / Q_b & q ]]><**Ratings.** Ratings attach to brand names. With ȳ_{s,d} the share of day-d units where true quality met the claim the buyer acted on:

$$
r_{s,d+1} = \lambda\, r_{s,d} + (1 - \lambda)\, \bar y_{s,d}, \qquad r_{s,1} = 0.5
$$

Tourists file reviews of a counterfeit under the brand it copies. A stall can change its name only when it reopens after a closure.

**Multi-day dynamics (when on).** Each day, each genuine or deceptive stall compares itself with probability 0.2 with a random stall s' of its category and switches to s'’s type with probability max(0, Π_s' − Π_s) / max |ΔΠ|; types also flip with probability 0.02. Seconds never switch.

**Bust-out benchmark.** A genuine stall that busts out on day b keeps its name, sign and price but sells at low true quality from then on, and with exit leaves the market at the end of day b + h − 1. Holding every other genuine stall honest:

$$
G_s = \max_{\beta \in \mathcal{B}} \Pi_s^{(\beta)} - \Pi_s^{(\text{never})}
$$

where 𝓑 is the candidate set of bust-out days (or day-and-exit pairs). G_s > 0 means cashing out the brand pays.

**Outcomes.** Shortfall rate: share of purchases with q_s < Q_b. Task complete: share of buyers holding n_b units with q_s ≥ Q_b. Buyer surplus: mean U_b. Deceptive share of sales. Catches per deceptive stall-day. Inspector-active ticks. Stuck and parked buyers (must be 0).

**M0 compatibility mode.** Customers x_j ∼ U[0, 1]², a share f of them enforcers (fixed, or redrawn per impression). Advertisers hold a location, a bid in [0.001, 1], a radius in [r_min, 0.7] and a type. Each impression goes to a random customer; advertisers whose radius covers it and who are under the impression cap bid, and the highest bid wins and pays its bid. A sale happens within distance 0.1; deceptive advertisers earn m(1 + δ) per sale but pay P per enforcer impression. Each generation the lowest-fitness 20% are replaced by mutated copies of the top 20%.

| Symbol | Meaning | Domain | Default | Status |
|---|---|---|---|---|
| D, T | days per run; ticks per day | D ≥ 1; T = 240 k | 1 or 30; 240 |  |
| k | grid and time scale | positive integer | 1 |  |
| b_c | base price by category | cents > 0 | 800 / 4,000 / 12,000 |  |
| φ_N | seconds price factor | (0, 1] | 0.55 |  |
| π | reputation premium | ≥ 0 | 0 (0.4 with brands) | PLACEHOLDER |
| χ | counterfeit price factor | (0, 1] | 1.0 |  |
| β | budget factor | > 0 | 1.25 / 1.0 / 0.8 |  |
| m, γ | consideration-set size; position rent | m ≥ 1; γ ≥ 0 | 3; 0 |  |
| κ_π | inspection cost share of b_c | [0, 1] | 0.10 / 0.05 / 0.02 |  |
| θ_l, θ_e | inspection probabilities, locals and experts | [0, 1] | 1, 1 |  |
| η | profile observation noise | [0, 1] | 0.3 |  |
| ℓ_sign, ℓ_yell, ℓ_whisper | channel ranges (cells) | > 0 | 3, 4, 2 (× k) |  |
| ρ_rec | uniform recognition range | [0, ℓ_yell] | ℓ_yell |  |
| w_h | channel detection weights | [0, 1] | whisper 1, answer 1, yell 0.6, sign 0.4 | PLACEHOLDER |
| f_0 | falsity at which detection saturates | > 0 | 0.3 | PLACEHOLDER |
| σ | enforcement intensity | [0, 1] | 1 |  |
| L | closure after a catch (ticks) | ≥ 0 | 40 |  |
| F_c | fine per catch | > 0 (cents) | 1.5 b_c |  |
| Λ | fine lag (days) | ≥ 0 | 0 |  |
| v, ς | value multiple; salvage share | v > 0; [0, 1] | 1.3; 0.5 | PLACEHOLDER |
| λ | rating memory | [0, 1) | 0.7 | PLACEHOLDER |
| N_B, N_I | buyers per day; inspectors | ≥ 0 | 150; 2 |  |
| bargain share | buyers with low Q_b | [0, 1] | 0 (0.2 in choice-set runs) |  |
| tourist / local / expert | buyer profile shares | sum to 1 | 0.4 / 0.4 / 0.2 |  |
