<!-- Exported from the project doc 'Bazaar Markets: The Agentic Ad Engine', section 'Formal model of the bazaar engine', rev 42, on 2026-11-19. Written against engine 0.15.0; cross-checked line by line against the engine 0.21.0 code at the 1.0.0 cross-check (2026-11-19, see runs/formal_model_check.md): items the doc had wrong are fixed, and the later keys (licensing, counterfeit entry/price factor, white_label_tier, prior_n/scope, display stars, tie_break, profile overrides) are added in paragraphs labelled "added at the 1.0.0 cross-check". -->
## Formal model of the bazaar engine

This section states the engine as a model: sets, stall and buyer primitives, messages, detection, decision rules, payoffs and outcomes, with every parameter's domain and default in the table at the end. It follows the specifications given to the engine through version 0.15.0, extended to 0.21.0; the code (`engine/*.py`, `agents/rule_based.py`) is the source of truth. The line-by-line cross-check against it was done at 1.0.0 against the engine 0.21.0 code (see `runs/formal_model_check.md`): statements found wrong are corrected here, and rules for keys added after 0.15.0 are in paragraphs labelled *added at the 1.0.0 cross-check*. PLACEHOLDER marks a modelling choice not yet backed by data.

**Sets and time.** Days d = 1, …, D and ticks t = 0, …, T − 1 within a day. Categories C = {fish, electronics, designer}, one aisle each. Stalls s ∈ S, 16 per category, each with a type τ_s ∈ {G, N, F} (genuine, seconds, deceptive) apportioned 0.4 / 0.3 / 0.3 within each category by largest remainder (6 / 5 / 5). People are buyers b ∈ B (a fresh population each day) and inspectors i ∈ I. Buyer profiles are tourist, local and expert; a share of buyers are bargain hunters. Positions are cells on an integer grid; distance is Euclidean.

**Stalls.** Base price b_c by category; true quality q_s; pitched quality q̂_s; posted price p_s; unit cost k_s; fine F_c; ad costs per yell and whisper.

$$
q_s \sim \begin{cases} U[0.70,\,0.95] & \tau_s = G \\ U[0.15,\,0.45] & \tau_s \in \{N, F\} \end{cases} \qquad \hat q_s = \begin{cases} q_s & \tau_s \in \{G, N\} \\ U[0.70,\,0.95] & \tau_s = F \end{cases}
$$

$$
p_{s,d} = \operatorname{round}\!\Bigl(b_c\,\phi_{\tau_s}\,\bigl(1 + \pi\,(\tilde r_{s,d} - 0.5)\bigr)\Bigr), \qquad k_s = \operatorname{round}\bigl(b_c\,(0.30 + 0.50\,q_s)\bigr), \qquad F_c = \operatorname{round}(1.5\,b_c)
$$

in integer cents, with φ_G = 1, φ_N = 0.55 and φ_F = 1 (φ_F is a parameter, the deceptive price factor; below 1 models bargain fakes). r̃_{s,d} is the displayed start-of-day rating of the stall's brand, 0.5 if unrated. The reputation premium π applies only with brands on; it defaults to 0 and is set to 0.4 in every run with brands since 2026-11-06. With brands off prices stay at b_c φ_{τ_s}. A counterfeit posts round(χ p) of the stall bearing the copied name, and a licensee its owner's price (see the paragraphs on counterfeits and licensing). A rename resets the price: a fresh name posts the neutral price (r̃ = 0.5), a counterfeit name the copy price. Ad cost is round(0.002 b_c) per yell and round(0.004 b_c) per whisper; signs and answers are free.

**Buyers.** Each buyer gets a task (c_b, n_b, Q_b, W_b): category, units needed n_b ∈ {1, 2}, quality requirement Q_b ∼ U[0.50, 0.70] (bargain hunters U[0.30, 0.45] by default; every choice-set run from the verification run on sets U[0.15, 0.40]), and budget

$$
W_b = \operatorname{round}\bigl(n_b\, b_{c_b}\, \beta_b\bigr), \qquad \beta_b \in \{1.25,\ 1.0,\ 0.8\}
$$

for budget levels above, at and below ("mixed" draws one of the three per buyer), or a fixed override β. Inspecting a stall costs round(κ_{prof(b)} b_c), paid from the budget, with κ = 0.10, 0.05, 0.02 for tourist, local, expert; an inspection reveals q_s exactly. Buyers arrive spread evenly over the day. In walk mode a buyer walks a seeded route through 1–3 aisles, from a random end. In choice-set mode it draws a consideration set M_b of m stalls of its category still in the market, by successive sampling without replacement, enters its aisle at an end drawn with probability 1/2, and walks the aisle end to end past all of them; its search depth is m. At draw k = 1, …, m:

$$
\Pr\bigl(s_k = s \mid s_1, \dots, s_{k-1}\bigr) = \frac{e^{-\gamma\,\rho_s}}{\sum_{s' \notin \{s_1, \dots, s_{k-1}\}} e^{-\gamma\,\rho_{s'}}}, \qquad \rho_s = \text{position rank of } s \text{ from the buyer's entrance}
$$

with rank 0 for the nearest pair of facing stalls, which share a rank. With γ = 0 the set is uniform.

**Messages.** Channels h ∈ {sign, yell, whisper, answer}. A seller decides only on a tick when someone is within earshot or an ask is pending. A sign reaches everyone within the sight range (once per person per stall opening: a closure starts a new opening), a yell everyone within earshot, a whisper one addressee within the whisper range, and an answer one buyer or disguised inspector that asked the stall (asks are made from within the interact range). A message from s carries claim q̃ ∈ {q_s, q̂_s}, with falsity f = max(0, q̃ − q_s). Sellers see each passer-by in earshot with its observable profile with probability 1 − η, otherwise a uniformly random one (stable per seller–person pair), and see a uniform on a uniformed inspector within the recognition range.

**Detection and sanctions.** When an inspector i (a dedicated inspector, or an inspector-buyer with enforcement on) perceives a false message from s on channel h at distance δ:

$$
\Pr(\text{catch}) = \min\!\Bigl(1,\ \sigma \cdot c_{i,s} \cdot w_h \cdot g_h(\delta) \cdot \min\!\left(1,\ \frac{f}{f_0}\right)\Bigr), \qquad g_h(\delta) = \begin{cases} \max(0,\ 1 - \delta/\ell_h) & h \in \{\text{sign},\ \text{yell}\} \\ 1 & h \in \{\text{whisper},\ \text{answer}\} \end{cases}
$$

with σ ≥ 0 the enforcement intensity (detect_scale; the detection draw is consumed whenever the unscaled probability is positive, so levels of σ share draws), w_h the channel weight, ℓ_h the channel range (g = 1 for every channel when proximity is flat), and c_{i,s} = 1 − ε (ε = 0.8) if inspector i is captured by the brand s bears, else 1. A stall is caught at most once per tick. A catch closes the stall for the next L ticks and imposes fine F_c, at once or, with a lag of Λ days, at the start of day d + Λ; a fine falling due after the stall has exited is uncollectible, and one falling due after the last day at a stall still in the market is outstanding at close. Placements: fixed posts, clustered posts, patrolling, or disguised among buyers (single trip or full shift). The graded form above is the default (PLACEHOLDER); the alternatives are step, p = w_h g_h(δ) whenever f > 0, and hazard, p = 1 − exp(−k_H f w_h e^{−δ/ℓ_H}) (k_H = 6, ℓ_H = 2), with no distance decay on private channels or under flat proximity.

**Exit.** A stall may exit (seller action): it leaves the market at the end of that day, is closed on every later day, is in no consideration set and is no counterfeit target, and its fines not yet due become uncollectible. The bust-out benchmark uses exit; the rule sellers otherwise never exit.

**Buyer rule.** The buyer's estimate of a stall's quality is its own assessment if it has one (inspector-buyers with knowledge), else its inspection result, else the latest claim heard. Tourists never inspect (unless a profile override gives them an inspection probability). Experts inspect any stall before buying with probability θ_e, and locals inspect a stall that yelled or whispered at them with probability θ_l; the draw is made once per buyer and stall, and only when the probability is strictly between 0 and 1. A buyer inspects only if the inspection cost plus the price fits the remaining budget; when it does not, an expert skips the stall and a local buys on the claim. A buyer who decides not to inspect a stall trusts its latest claim. A stall is a candidate if the estimate is at least Q_b, the price fits the remaining budget and, for a buyer who sees ratings, its displayed rating is not below τ (unrated stalls are never skipped); the buyer buys min(units needed, units affordable). A buyer asks an affordable stall it has heard nothing from. At search depth 1 the buyer acts at the cheapest candidate within reach. With search depth k > 1 (or consideration set m) it may buy only once it has seen k stalls or reached the end of its route; it then chooses among candidates within reach and seen earlier: buyers who can see ratings (locals and experts by default) take the highest displayed rating (unrated = 0.5), then the lowest price; tourists take the lowest price; remaining ties go by the tie-break (below).

**Seller rules.** Honest sellers always tell the truth, yell when at least 3 people are in earshot (cooldown 8 ticks), whisper to the nearest passer-by within the whisper range they haven't whispered to (at most one whisper per tick), and answer every ask. The naive deceptive seller pitches q̂_s, but answers observed experts with the truth, does not whisper to them, and holds its yell while one is in earshot. The adaptive deceptive seller also goes quiet (no yell, no whisper, truthful answers, its sign showing the truth) while a uniformed inspector is recognised in earshot, a catch within earshot happened 1 to L ticks ago, or its own stall reopened less than L ticks ago; then it restores its sign.

**Payoffs.**

$$
V_b(q) = \begin{cases} v\, b_c & q \ge Q_b \\ \varsigma\, v\, b_c\, q / Q_b & q < Q_b \end{cases} \qquad U_b = \sum_{u \in \text{units}(b)} \bigl(V_b(q_{s(u)}) - p_{s(u)}\bigr) - n^{\text{insp}}_b\, \operatorname{round}\bigl(\kappa_{\text{prof}(b)}\, b_{c_b}\bigr)
$$

where the sum runs over the units b bought, s(u) is the stall each came from, and n^insp_b is the number of b's inspections. The step-salvage form of V is the default (PLACEHOLDER); the alternatives are linear, V = v b_c q / Q_b, and concave, V = v b_c (q / Q_b)^{1/2}. A stall's profit on day d is

$$
\Pi_{s,d} = \sum_{u \in \text{sales}(s,d)} (p_{s,d} - k_s) - A_{s,d} - \Phi_{s,d} - S_{s,d} - R^{\text{out}}_{s,d} + R^{\text{in}}_{s,d}
$$

with A ad spend, Φ fines charged that day, S the switching cost (charged on the first day in a new type), and R royalties paid and received (licensing). Over a run, Π_s = Σ_d Π_{s,d}.

**Ratings.** Ratings are computed when the ratings mode is hidden or public (off by default) and shown, in public mode, to the profiles in the visibility list (locals and experts). They attach to brand names with brands on, and to stalls otherwise. A unit is rated when its buyer had received at least one claim from the stall before buying, and is honest when q_s met the latest such claim; units bought with no claim are not rated. With ȳ_{n,d} the honest share of the day-d rated units filed under name n (critics' reviews, when on, count as rated units):

$$
r_{n,d+1} = \begin{cases} \bar y_{n,d} & n \text{ unrated} \\ \lambda\, r_{n,d} + (1 - \lambda)\, \bar y_{n,d} & \text{otherwise} \end{cases}
$$

A name starts unrated; a day with no rated units leaves its rating unchanged; every reader (prices, buyers, sellers) counts an unrated name as 0.5. Ratings persist across days and type switches.

Tourists file reviews of a counterfeit under the brand it copies; locals and experts file under the name the stall bears. With brands on, a stall can change its name only when it reopens after a closure (fresh: a new unrated name; counterfeit: see below); licensees and counterfeits entered on a fixed day never rename.

**Critics (when on; brands on).** Each day each critic visits a sample of stalls, observes true quality and writes a review, positive when q_s meets the stall's posted sign claim (no sign, no review). A review counts as a weight of rated units in that day's update of the stall's brand. Positive reviews are filed at once; a negative review is held for max(tie delay if the critic is tied to the brand, round(emb_max × the critic's earlier positive share of the brand) if embarrassment is on) days, and is never filed if due after the last day. Off by default (critics.count = 0).

**Displayed ratings (added at the 1.0.0 cross-check).** Every rating a market participant reads is the displayed rating

$$
\tilde r = \begin{cases} r & \text{display} = \text{exact} \\ \Delta \left\lfloor r / \Delta + \tfrac{1}{2} \right\rfloor & \text{display} = \text{stars} \end{cases} \qquad \Delta \in (0, 1],\ 1/\Delta \in \mathbb{N}
$$

(rounding half up; Δ = 0.02 is a tenth of a star on a five-star scale). Unrated stays unrated (read as 0.5). The readers are buyers' stall rows (ranking and the threshold τ), the posted price, the seller's view of its own brand rating, and counterfeit target choice. The stored rating r keeps updating unrounded, and the logs report it.

**Rating prior (added at the 1.0.0 cross-check).** With brands on and ratings not off, a name n that gets the prior starts with n_0 pseudo-reviews at 0.5. With H_{n,d} honest and C_{n,d} rated units on a day with rated units,

$$
\bar y_{n,d} = \frac{H_{n,d} + 0.5\, w_{n,d}}{C_{n,d} + w_{n,d}}, \qquad w_{n,d} = n_0\, \lambda^{\,d - d_n}
$$

where d_n is the day the name was created; w is multiplied by λ at every day end, rated units or not. The update above then applies (first rating = ȳ). Scope "all": every name gets the prior. Scope "new": only names created on day 2 or later (white labels, fresh or counterfeit names at reopening, counterfeit entry); names that exist on day 1, including the owners' and every original stall's name, rate as with n_0 = 0. Default n_0 = 0.

**Tie-break (added at the 1.0.0 cross-check).** Among the candidate set K_b, the searching rule buyer picks lexicographically

$$
s^* = \arg\min_{s \in K_b} \bigl(-\tilde r_s,\ p_s,\ \iota_b(s)\bigr) \ \text{(buyers who see ratings)}, \qquad s^* = \arg\min_{s \in K_b} \bigl(p_s,\ \iota_b(s)\bigr) \ \text{(others)}
$$

and at search depth 1 every buyer goes through the stalls within reach in the order (p_s, ι_b(s)). Tie-break "stall_id": ι_b(s) is the stall id. "random": ι_b(s) is the place of s in a permutation of all stalls drawn once per buyer and day from default_rng([seed, 29, d, buyer index]).

**Profile overrides (added at the 1.0.0 cross-check).** For a profile (tourist, local, expert) or for bargain hunters (whose keys win over their profile's), an optional reads-ratings flag and an optional inspection probability. A buyer b sees ratings iff the ratings mode is public and

$$
\text{reads}_b = \begin{cases} o^{\text{read}}_{g(b)} & \text{if set} \\ [\text{prof}(b) \in \text{visible\_to}] & \text{otherwise} \end{cases} \qquad \theta_b = \begin{cases} o^{\theta}_{g(b)} & \text{if set} \\ \theta_l,\ \theta_e,\ \text{none} & \text{local, expert, tourist} \end{cases}
$$

where g(b) is "bargain" for a bargain hunter whose bargain entry sets the key, else its profile. A buyer that does not read ratings ranks candidates as a tourist does (lowest price, no threshold). A tourist given θ follows the local rule (inspects a stall that yelled or whispered at it with probability θ). Budgets, Q_b, search depth, inspection cost and what sellers observe are unchanged. Default: no overrides.

**Counterfeits (added at the 1.0.0 cross-check).** A counterfeit bears a near-copy of an original name n (one edit: an accent added, two neighbouring letters swapped or a letter doubled; never a name used before) and records n as the name it copies. It enters in one of two ways. *Reopen* (default): a stall reopening after a closure may rename to a counterfeit of the highest displayed-rated name among the other stalls of its category that are not seconds, not counterfeits and still in the market (unrated = 0.5; ties uniformly at random; a fresh name if there is none); it keeps its own pitched quality q̂_s. *Day*: at the start of day d_cf (2 ≤ d_cf ≤ D) every deceptive stall still in the market that is not a licensee, in stall order, copies the top displayed-rated genuine brand of its category (rated at the end of day d_cf − 1; candidates are genuine stalls still in the market that are neither counterfeits nor licensees; ties and edits from default_rng([seed, 23])), claims that brand's true quality from then on, q̂_s := q_{s'}, and never renames. In both modes its true quality and unit cost are unchanged, and each morning

$$
p_{s,d} = \operatorname{round}(\chi\, p_{s',d})
$$

where s' is the stall bearing n that is neither a counterfeit nor a licensee (the stall's own price rule if there is none). Tourists read n on the counterfeit and file their reviews under n; locals and experts read and review the counterfeit's own name.

**Licensing (added at the 1.0.0 cross-check).** A schedule assigns a genuine owner o a licence day b_o (2 ≤ b_o ≤ D) and a count N_o ≥ 0. At the start of day b_o, before prices are set, its licensees are the first N_o stalls of a permutation of the non-genuine stalls of its category drawn from default_rng([seed, 19, o]), with one uniform u_ℓ per candidate. From day b_o to the last day a licensee ℓ claims the owner's quality and

$$
\hat q_\ell = q_o, \qquad q_\ell = \begin{cases} q_o & \text{contract} \\ 0.15 + 0.30\, u_\ell & \text{cheap} \end{cases}, \qquad k_\ell = \operatorname{round}\bigl(b_c\,(0.30 + 0.50\, q_\ell)\bigr)
$$

(cheap draws from the low-quality range). A contract licensee shows a truthful sign and runs the honest rule; a cheap licensee shows the pitch and runs the deceptive policy. Its type τ_ℓ does not change and it never renames. Under the owner's brand (default), ℓ bears o's name, posts o's price, p_ℓ = p_o, and pays o a royalty on every unit,

$$
R^{\text{out}}_{\ell,d} = n_{\ell,d}\, \operatorname{round}(\rho\, p_{\ell,d}), \qquad R^{\text{in}}_{o,d} = \sum_{\ell} R^{\text{out}}_{\ell,d}
$$

with n_{ℓ,d} units sold; reviews of its sales are filed under o's name. With owner liability on, a fine from a catch at ℓ is charged to o (ℓ is still closed). Under white labels, each licensee instead bears one fresh unrated name of its own (from default_rng([seed, 24, o])): no royalty, no owner liability, reviews filed under that name, and the price

$$
p_{\ell,d} = \operatorname{round}\Bigl(b_c\, \phi^{\text{WL}}_\ell\, \bigl(1 + \pi\, (\tilde r_{\ell,d} - 0.5)\bigr)\Bigr), \qquad \phi^{\text{WL}}_\ell = \begin{cases} \phi_{\tau_\ell} & \text{white-label tier "type"} \\ 1 & \text{white-label tier "genuine"} \end{cases}
$$

from its own name's displayed rating. Licensing needs brands on and D ≥ 2; with an empty schedule it is off.

**Multi-day dynamics (multi-day runs with brands off).** Between day d and d + 1, synchronously, each genuine or deceptive stall with probability 0.2 compares its day-d profit with a partner s' drawn uniformly from the other genuine and deceptive stalls of its category; if s' has the other type and earned more, it switches to s'’s type with probability (Π_{s'} − Π_s) / M_c, with M_c the largest difference in day-d profit among the genuine and deceptive stalls of category c. Then each genuine or deceptive stall flips type with probability 0.02. Seconds never switch and are never partners. A stall whose type changes gets new q_s, q̂_s and price by the type rules. Brands require both probabilities to be 0.

**Bust-out benchmark.** A genuine stall that busts out on day b keeps its name and price rule, while its true quality drops for good to a low quality drawn once from U[0.15, 0.45], its unit cost falls with it, and its sign shows its old quality, so its claims become false; with exit it leaves the market at the end of day b + h − 1. Holding every other genuine stall honest, with Π_s^{(β)} the stall's total profit over all days under candidate β:

$$
G_s = \max_{\beta \in \mathcal{B}} \Pi_s^{(\beta)} - \Pi_s^{(\text{never})}, \qquad G_s^{\text{floored}} = \max\bigl(G_s,\ 0\bigr)
$$

where 𝓑 is the candidate set of bust-out days (or day-and-exit pairs), {10, 20, 25, 27, 28, 29} by default (each in [2, D]). G_s > 0 means cashing out the brand pays. The unfloored G_s is the primary outcome since the 2026-11-07 capture run.

**Outcomes.** Shortfall rate: share of purchases with q_s < Q_b. Task complete: share of buyers holding n_b units with q_s ≥ Q_b. Buyer surplus: mean U_b over buyers who arrived. Deceptive share of sales (units). Catches per deceptive stall-day. Inspector-active ticks. Stuck buyers and idle choosers (must be 0).

**M0 compatibility mode.** Customers x_j ∼ U[0, 1]², a share f of them enforcers (fixed, or redrawn per impression). Advertisers hold a location, a bid (initially U[0, 0.5], kept in [0.001, 1] by mutation), a radius in [r_min, 0.7] and a type. Each impression goes to a random customer; advertisers whose radius covers it and who are under the impression cap bid, and the highest bid wins and pays its bid. A sale happens within distance 0.1; honest advertisers earn m per sale and deceptive ones m(1 + δ), but a deceptive advertiser's impression that reaches an enforcer earns nothing and costs P. Each generation the lowest-fitness 20% (idle firms ranked lowest) are replaced by mutated copies of the top 20%.

| Symbol | Meaning | Domain | Default | Status |
|---|---|---|---|---|
| D, T | days per run; ticks per day | D ≥ 1; T ≥ 1 real ticks (T k engine ticks) | 1 (30 or 60 in multi-day runs); 240 |  |
| k | grid and time scale | positive integer | 1 |  |
| b_c | base price by category | cents > 0 | 800 / 4,000 / 12,000 |  |
| type shares | genuine / seconds / deceptive per category | shares | 0.4 / 0.3 / 0.3 |  |
| q ranges | high (genuine true, deceptive pitched); low (seconds and deceptive true) | ⊂ [0, 1] | [0.70, 0.95]; [0.15, 0.45] |  |
| φ_N | seconds price factor | (0, 1] | 0.55 |  |
| φ_F | deceptive price factor | > 0 | 1.0 |  |
| c_0, c_1 | unit cost: k = b_c (c_0 + c_1 q) | ≥ 0 | 0.30, 0.50 |  |
| ad cost | per yell; per whisper, share of b_c | ≥ 0 | 0.002; 0.004 | calibration |
| π | reputation premium | ≥ 0 | 0 (0.4 in every run with brands since 2026-11-06) | PLACEHOLDER |
| χ | counterfeit price factor | (0, 10] | 1.0 |  |
| n_b, Q_b | units needed; quality requirement | integer range; ⊂ [0, 1] | {1, 2}; U[0.50, 0.70] |  |
| β | budget factor | > 0 | 1.25 / 1.0 / 0.8 (level "at" = 1.0); override none |  |
| m, γ | consideration-set size; position rent | m ≥ 1; γ ≥ 0 | 3; 0 |  |
| κ | inspection cost share of b_c | [0, 1] | 0.10 / 0.05 / 0.02 |  |
| θ_l, θ_e | inspection probabilities, locals and experts | [0, 1] | 1, 1 |  |
| τ | rating threshold | [0, 1] | 0.5 | PLACEHOLDER |
| visible_to | profiles that see ratings (public mode) | subset of profiles | local, expert |  |
| η | profile observation noise | [0, 1] | 0.3 |  |
| ℓ_sign, ℓ_yell, ℓ_whisper, ℓ_int | channel ranges; interact range (cells) | > 0 | 3, 4, 2, 1 (× k) |  |
| ρ_rec | uniform recognition range | ≥ 0 (acts as min(ρ_rec, ℓ_yell)) | ℓ_yell |  |
| w_h | channel detection weights | [0, 1] | whisper 1, answer 1, yell 0.6, sign 0.4 | PLACEHOLDER |
| f_0 | falsity at which detection saturates | > 0 | 0.3 | PLACEHOLDER |
| σ | enforcement intensity | finite ≥ 0 | 1 |  |
| capture, ε | tie probability per (inspector, genuine-origin brand); capture effect | [0, 1]; [0, 1] | 0; 0.8 | ε PLACEHOLDER |
| L | closure after a catch (ticks); catch-notice window | ≥ 0 | 40 |  |
| F_c | fine per catch | > 0 (cents) | 1.5 b_c |  |
| Λ | fine lag (days) | integer ≥ 0 | 0 |  |
| v, ς | value multiple; salvage share | v > 0; [0, 1] | 1.3; 0.5 | PLACEHOLDER |
| λ | rating memory | [0, 1) | 0.7 | PLACEHOLDER |
| n_0, prior scope | rating prior pseudo-reviews; which names get them | ≥ 0; {all, new} | 0; all |  |
| display, Δ | rating display; display step | {exact, stars}; (0, 1] with 1/Δ an integer | exact; 0.02 |  |
| tie-break | ι_b(s) | {stall_id, random} | stall_id |  |
| profile overrides | per profile or bargain: reads ratings, θ | mapping | none |  |
| counterfeit entry, d_cf | entry mode; entry day | {reopen, day}; [2, D] | reopen; 2 |  |
| licence schedule, quality | {owner: (b, N)}; licence quality | 2 ≤ b ≤ D, N ≥ 0; {cheap, contract} | none (off); cheap |  |
| ρ | royalty share of price | [0, 1] | 0.15 | PLACEHOLDER |
| owner liable | fines at licensees charged to the owner | true / false | false |  |
| licence brand, white-label tier | owner's name or white labels; white-label price tier | {owner, white_label}; {type, genuine} | owner; type |  |
| revise, mutate | imitation and mutation probabilities (multi-day, brands off) | [0, 1] | 0.2; 0.02 |  |
| 𝓑 | bust-out candidate days | integers in [2, D] | {10, 20, 25, 27, 28, 29} |  |
| critics | count; sample; weight; tie share; tie delay; emb_max | ≥ 0; ≥ 1; > 0; [0, 1]; ≥ 0; ≥ 0 | 0 (off); 6; 5; 0; 10; 10 | PLACEHOLDER |
| N_B, N_I | buyers per day; inspectors | ≥ 0 | 150; 2 |  |
| bargain share | buyers with low Q_b | [0, 1] | 0 in walk mode, 0.2 in choice-set mode |  |
| bargain Q_b | bargain hunters' Q_b range | ⊂ [0, 1] | U[0.30, 0.45] (U[0.15, 0.40] in runs from verification on) |  |
| tourist / local / expert | buyer profile shares | sum to 1 | 0.4 / 0.4 / 0.2 |  |
