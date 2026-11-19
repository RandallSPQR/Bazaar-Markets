import json, os, sys
from types import SimpleNamespace
import analysis.brand_equity_speed as S, analysis.chainrun as CR, analysis.licensing as L
def main():
    out = "runs/pilot_stars/os_check"
    jobs = S.jobs_for([330], {330: L.sample_stalls(330)}, S.LEVELS)[:16]
    want = {S.key(j) for j in jobs}; old = {}
    for line in open("runs/brand_equity_speed_cache.jsonl"):
        r = json.loads(line)
        if r["key"] in want: old[r["key"]] = r
    log = CR.file_logger(os.path.join(out, "g2_macos27_run.log"))
    runs, _ = CR.run_chains(SimpleNamespace(workers=4, min_swap_mb=0, min_free_pct=15), jobs, os.path.join(out, "g2_macos27_cache.jsonl"), log, S.job, S.key)
    same = sum(all(r.get(k) == old[r["key"]].get(k) for k in ("digest","dig_trade","all","win","totals","rating","daily")) for r in runs)
    res = {"chains": len(jobs), "found": len(old), "identical": same, "keys": sorted(want)}
    json.dump(res, open(os.path.join(out, "g2_macos27.json"), "w"), indent=1); print(res["chains"], res["found"], res["identical"])
    
if __name__ == '__main__':
    main()
