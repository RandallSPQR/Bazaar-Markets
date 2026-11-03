# Reference prototype v1 (corrected idle-exit rule: idle firms rank below every active firm).
# Every result in the research doc used this version. Copied verbatim; do not edit.
import numpy as np

def run(n_cust=1000, n_adv=100, f_enf=0.05, r_min=0.02, r_max=0.7, d_sale=0.1,
        m=1.0, delta=0.2, P=5.0, gens=250, T=None, seed=0, keep=0.2, flip=0.02, return_state=False, cap_mult=3.0, auction='first', exit_rule='idle_lowest', bid_cap=1.0, enf_mode='spatial', op_cost=0.5, wealth_decay=0.5):
    rng = np.random.default_rng(seed)
    T = T or 20*n_adv
    cust = rng.random((n_cust,2)); enf = rng.random(n_cust) < f_enf
    loc = rng.random((n_adv,2)); bid = rng.random(n_adv)*0.5
    rad = np.exp(rng.uniform(np.log(r_min), np.log(r_max), n_adv))
    dec = rng.random(n_adv) < 0.5
    hist = []; wealth = np.zeros(n_adv)
    for g in range(gens):
        idx = rng.integers(0, n_cust, T)
        c = cust[idx]; e = enf[idx] if enf_mode=='spatial' else (rng.random(T) < f_enf)
        cap = int(cap_mult*T/n_adv); used = np.zeros(n_adv, int)
        W=[]; D=[]; E=[]; OK=[]; PR=[]
        for ch in np.array_split(np.arange(T), 40):
            cc = c[ch]; ee = e[ch]
            d = np.sqrt(((cc[:,None,:]-loc[None,:,:])**2).sum(-1))
            elig = (d <= rad[None,:]) & (used < cap)[None,:]
            b = np.where(elig, bid[None,:], -1.0)
            w = b.argmax(1); ok = b.max(1) > 0
            if auction == 'second':
                sb = np.sort(b, 1)[:, -2] if b.shape[1] > 1 else np.zeros(len(b))
                pr = np.clip(sb, 0, None)
            else:
                pr = b.max(1)
            used += np.bincount(w[ok], minlength=n_adv)
            W.append(w[ok]); D.append(d[ok, w[ok]]); E.append(ee[ok]); OK.append(ok); PR.append(pr[ok])
        w=np.concatenate(W); d_w=np.concatenate(D); e_w=np.concatenate(E); ok=np.concatenate(OK); price=np.concatenate(PR)
        sale = d_w < d_sale
        dw = dec[w]
        gain = np.where(dw, np.where(e_w, -P, sale*m*(1+delta)), sale*m) - price
        profit = np.bincount(w, weights=gain, minlength=n_adv)
        wins = np.bincount(w, minlength=n_adv)
        hist.append(dict(dec_share_imp = dw.mean() if len(dw) else np.nan,
                         dec_pop = dec.mean(),
                         fill = ok.mean()))
        # selection
        if exit_rule=='idle_lowest': fit = np.where(wins>0, profit, profit.min()-1.0)
        elif exit_rule=='idle_zero': fit = profit
        elif exit_rule=='op_cost': fit = profit - op_cost
        elif exit_rule=='wealth':
            wealth = wealth_decay*wealth + profit; fit = wealth
        order = np.argsort(fit); k = int(keep*n_adv)
        lose, win = order[:k], order[-k:]
        loc[lose] = np.clip(loc[win] + rng.normal(0,0.03,(k,2)),0,1)
        bid[lose] = np.clip(bid[win] + rng.normal(0,0.05,k),0.001,bid_cap)
        rad[lose] = np.clip(rad[win]*np.exp(rng.normal(0,0.15,k)), r_min, r_max)
        dec[lose] = dec[win] ^ (rng.random(k) < flip)
        wealth[lose] = 0.0
    if return_state:
        # local enforcer fraction within each advertiser's radius
        dc = np.sqrt(((cust[:,None,:]-loc[None,:,:])**2).sum(-1))
        inr = dc <= rad[None,:]
        loc_e = np.array([enf[inr[:,j]].mean() if inr[:,j].any() else np.nan for j in range(n_adv)])
        return hist, dict(loc=loc, bid=bid, rad=rad, dec=dec, loc_e=loc_e, wins=wins, profit=profit, cust=cust, enf=enf)
    return hist

def summary(h, last=30):
    x = np.array([r['dec_share_imp'] for r in h[-last:]]); return np.nanmean(x)
