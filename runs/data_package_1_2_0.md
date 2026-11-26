# Bazaar Markets v1.2.0: data package

Dataset for Zenodo, licence CC BY 4.0 ([creativecommons.org/licenses/by/4.0](https://creativecommons.org/licenses/by/4.0/)). Built 2026-11-26; engine 1.2.0. Every file that is also in git matches commit 54c57c4; the caches are not in git. Prepared by Claude for Randall; not uploaded.

## Archive

`bazaar-markets-v1.2.0-data.tar.gz`: 17,082,463 bytes, sha256 `8ceaf5c1665dd4889be739c767e47878c9ce3f4f5e6c0eee90ec550997d393a7`. It unpacks to the repository paths below (`tar xzf … ` in a checkout's root). `SHA256SUMS_files.txt` has the checksum of every file inside; checked by extracting and verifying all 25 (2026-11-26).

## Contents

| File | Bytes | What it is |
|---|---|---|
| `runs/state_bank_v2/README.md` | 4,480 | Bank v2 README: fields, options, suggested use |
| `runs/state_bank_v2/states.jsonl.gz` | 240,831 | Bank v2: 300 seller states (observations, hidden variables, lotteries, labels, weights) |
| `runs/state_bank_v2/summary.json` | 3,893 | Bank v2 counts, guards, final leakage check, run record |
| `runs/state_bank_v2/leak_final.json` | 5,186 | Leakage classifiers on the final bank |
| `runs/state_bank_v2/describe.json` | 7,441 | Descriptive tables (written after the results) |
| `runs/state_bank_v2/design.json` | 12,736 | The 24 markets |
| `runs/state_bank_v2/pilot_gates.json` | 51,411 | Pilot gates, stratum rates, allocation |
| `runs/state_bank_v2/state_bank_v2_run.log` | 20,303 | Run records of every bank phase |
| `runs/state_bank_v2/cheating_minus_honest.svg` | 55,704 | Summary plot |
| `runs/state_bank_v2/enumerate_cache.jsonl` | 386,434,767 | Cache: 2,400 base chains with every eligible state (172,800) and both observations |
| `runs/state_bank_v2/lottery_cache.jsonl` | 1,160,596 | Cache: 1,112 continuation chains (pilot and bank) |
| `runs/state_bank_v2_summary.md` | 10,906 | Bank v2 summary and reading |
| `runs/pilot_state_bank_v2.md` | 2,800 | Bank v2 pilot record (gates, allocation, D5) |
| `runs/state_bank_v2_bank_stdout.log` | 9,721 | Bank phase stdout, all five launches |
| `runs/state_bank_v2_stdout.log` | 11,721 | Design, enumerate and pilot stdout |
| `runs/price_war_cache.jsonl` | 5,571,636 | Cache: price-war main run, 3,440 chains, seeds 500–519 |
| `runs/price_war.json.gz` | 8,307 | Price-war results (tables regenerated after D4) |
| `runs/price_war.svg` | 6,593 | Price-war plot |
| `runs/price_war_summary.md` | 8,917 | Price-war summary, predictions and reading |
| `runs/price_war_run.log` | 11,705 | Price-war run records |
| `runs/pilot_price_war.md` | 1,019 | Price-war pilot record |
| `runs/pilot_price_war/price_war_cache.jsonl` | 834,516 | Cache: price-war pilot chains, seeds 900–902 |
| `runs/pilot_price_war/price_war_pilot_gates.json` | 28,393 | Price-war pilot gates |
| `runs/pilot_price_war/price_war_repro.json` | 1,054 | G2: m = 0 against the 1.1.0 undercut chains |
| `runs/pilot_price_war/price_war_run.log` | 5,534 | Price-war pilot run records |

## How to use the caches

- The caches are JSON lines, one finished chain per line. The scripts that wrote them (`analysis/state_bank_v2.py`, `analysis/price_war.py`) read them back: put the files at their paths in a v1.2.0 checkout and rerun a phase. Cached chains are skipped, so `--phase build` (bank) or the summary step (price war) rebuilds every table without simulating.
- Every chain can also be resimulated from its seed with engine 1.2.0; the run records give commit, script sha256, numpy and platform.

## Not included

Earlier caches are in the v1.0.0 run-cache dataset (10.5281/zenodo.24406657). The engine 1.1.0 runs (state bank v1, robustness sweep) are not in this package; their results files are in git.
