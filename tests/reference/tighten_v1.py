import json, numpy as np
from multiprocessing import Pool
from sim_prototype_v1 import run  # was: from sim import run
def stats(h, a=-30, b=None):
    seg=h[a:b]
    return dict(imp=float(np.nanmean([r['dec_share_imp'] for r in seg])), pop=float(np.mean([r['dec_pop'] for r in seg])), fill=float(np.mean([r['fill'] for r in seg])))
def job(cfg):
    kw=dict(cfg['kw']); h=run(seed=cfg['s'], **kw)
    out=dict(cfg); out.update(stats(h))
    if kw.get('gens',250)==500:
        out['early']=stats(h,220,250); out['traj']=[float(r['dec_share_imp']) for r in h]
    return out
F=[0,0.01,0.02,0.03,0.05,0.08,0.12,0.2]
cfgs=[]
for mode in ['spatial','redraw']:
    for f in F:
        for s in range(6): cfgs.append(dict(exp='mech',mode=mode,f=f,s=s,kw=dict(f_enf=f,r_min=0.02,enf_mode=mode)))
sens={'baseline':{}, 'exit=idle_zero':{'exit_rule':'idle_zero'}, 'exit=wealth':{'exit_rule':'wealth'},
      'bid_cap=1.5':{'bid_cap':1.5}, 'bid_cap=2.0':{'bid_cap':2.0},
      'budget=2x':{'cap_mult':2.0}, 'budget=5x':{'cap_mult':5.0}, 'budget=none':{'cap_mult':1e6}}
for name,kw in sens.items():
    for (r,f) in [(0.02,0.05),(0.02,0.08),(0.7,0.01)]:
        for s in range(6):
            k=dict(f_enf=f,r_min=r); k.update(kw); cfgs.append(dict(exp='sens',name=name,r=r,f=f,s=s,kw=k))
for s in range(6): cfgs.append(dict(exp='stab',s=s,kw=dict(f_enf=0.05,r_min=0.02,gens=500)))
if __name__=='__main__':
    with Pool(2) as p: res=p.map(job,cfgs,chunksize=4)
    json.dump(res,open('tighten.json','w'))
