# -*- coding: utf-8 -*-
import json, os, sys, io, glob
sys.path.insert(0, "tools")
from ensemble import load_meta

def load_counts(pats):
    out = {}
    for pat in pats:
        cands = [x for x in glob.glob("runs/*") if pat in os.path.basename(x)]
        best, bn = {}, -1
        for R in cands:
            sd = os.path.join(R, "samples"); cur = {}
            if not os.path.isdir(sd): continue
            for s in os.listdir(sd):
                fs = {x: os.path.join(sd, s, x, "result.json") for x in ("orig", "fail")}
                if not all(os.path.isfile(f) for f in fs.values()): continue
                try: r = {x: json.load(open(fs[x], encoding="utf-8")) for x in fs}
                except Exception: continue
                if any(r[x].get("computed") is None for x in r): continue
                cur[s] = {x: r[x]["computed"]["counts"] for x in fs}
            if len(cur) > bn: best, bn = cur, len(cur)
        out.update(best)
    return out

def F(c, u_hard, u_soft, mid, mx):
    P, U, M = c["P"], c["U"], c["M"]
    if P + M < 1: return None
    cov = P / (P + M)
    if U >= u_hard: return 1
    if U >= u_soft: return 1 if M >= 1 else 3
    if cov >= mx: return 5
    if cov >= mid: return 3
    return 1

rules = [
    ("текущее: U>=2 ->1, U==1 ->1/3",      2, 1),
    ("мягче: U>=3 ->1, U==2 ->1/3",        3, 2),
    ("ещё мягче: U>=4 ->1, U==3 ->1/3",    4, 3),
    ("терпим одно: U>=2 ->1, U==1 не штрафуется", 2, 99),
    ("без штрафа за U вовсе",              99, 99),
]
for name, pats in (("v003", ["v003_сто_пар", "остаток_v003_101"]),
                   ("v013", ["v013_сто_пар", "остаток_v013_101"])):
    d = load_counts(pats)
    print("=== %s, пар %d ===" % (name, len(d)))
    for rn, uh, us in rules:
        w = i = r5 = 0; n = 0
        for s, c in d.items():
            fo = F(c["orig"], uh, us, 0.60, 0.80); ff = F(c["fail"], uh, us, 0.60, 0.80)
            if fo is None or ff is None: continue
            n += 1; w += fo > ff; i += fo < ff; r5 += fo == 5
        print("  %-46s ловит %3d/%d = %2.0f%% | инверсий %2d | эталонов F=5: %3d (%.0f%%)"
              % (rn, w, n, 100*w/n, i, r5, 100*r5/n))
    print()
