# -*- coding: utf-8 -*-
"""Агрегация на уровне счётчиков, а не оценок: согласие судей по U и M."""
import json, os, sys, io, glob
sys.path.insert(0, "tools")
import ensemble  # ставит utf-8 на stdout

def load(pats):
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

def F(P, U, M, mid=0.60, mx=0.80):
    if P + M < 1: return None
    cov = P / (P + M)
    if U >= 2: return 1
    if U == 1: return 1 if M >= 1 else 3
    if cov >= mx: return 5
    if cov >= mid: return 3
    return 1

a = load(["v003_сто_пар", "остаток_v003_101"])
b = load(["v013_сто_пар", "остаток_v013_101"])
common = sorted(set(a) & set(b))
print("пар: %d\n" % len(common))

def score(name, fn):
    w = i = r5 = n = 0
    for s in common:
        vals = {}
        for side in ("orig", "fail"):
            ca, cb = a[s][side], b[s][side]
            vals[side] = fn(ca, cb)
        if vals["orig"] is None or vals["fail"] is None: continue
        n += 1
        w += vals["orig"] > vals["fail"]; i += vals["orig"] < vals["fail"]
        r5 += vals["orig"] == 5
    print("%-52s ловит %3d/%d = %2.0f%% | инверсий %2d | эталонов F=5: %3d (%.0f%%)"
          % (name, w, n, 100*w/n, i, r5, 100*r5/n))

score("одиночный v003", lambda ca, cb: F(ca["P"], ca["U"], ca["M"]))
score("одиночный v013", lambda ca, cb: F(cb["P"], cb["U"], cb["M"]))
score("среднее оценок (нынешний ансамбль)",
      lambda ca, cb: (F(ca["P"], ca["U"], ca["M"]) + F(cb["P"], cb["U"], cb["M"])) / 2)
print()
score("согласие по U: U=min, P и M усреднены",
      lambda ca, cb: F((ca["P"]+cb["P"])/2, min(ca["U"], cb["U"]), (ca["M"]+cb["M"])/2))
score("согласие по U и M: оба min",
      lambda ca, cb: F((ca["P"]+cb["P"])/2, min(ca["U"], cb["U"]), min(ca["M"], cb["M"])))
score("U=min, остальное от того, у кого U меньше",
      lambda ca, cb: F(*( (ca["P"], ca["U"], ca["M"]) if ca["U"] <= cb["U"] else (cb["P"], cb["U"], cb["M"]) )))
score("все счётчики усреднены",
      lambda ca, cb: F((ca["P"]+cb["P"])/2, (ca["U"]+cb["U"])/2, (ca["M"]+cb["M"])/2))
score("U=max (наоборот, для контроля)",
      lambda ca, cb: F((ca["P"]+cb["P"])/2, max(ca["U"], cb["U"]), (ca["M"]+cb["M"])/2))
