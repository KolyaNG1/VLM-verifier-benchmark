# -*- coding: utf-8 -*-
import json, os, sys, io, glob, collections
sys.path.insert(0, "tools")
from ensemble import load_run, load_meta
meta = load_meta()
def full(tag_a, tag_b):
    d = {}
    for pat in (tag_a, tag_b):
        cands = [x for x in glob.glob("runs/*") if pat in os.path.basename(x)]
        if cands:
            d.update(max((load_run(c) for c in cands), key=len))
    return d
def counts(run_glob):
    out = {}
    for R in run_glob:
        sd = os.path.join(R, "samples")
        if not os.path.isdir(sd): continue
        for s in os.listdir(sd):
            f = os.path.join(sd, s, "orig", "result.json")
            if not os.path.isfile(f): continue
            try: d = json.load(open(f, encoding="utf-8"))
            except Exception: continue
            if d.get("computed"): out[s] = d["computed"]["counts"]
    return out

for name, a, b in (("v003", "v003_сто_пар", "остаток_v003_101"),
                   ("v013", "v013_сто_пар", "остаток_v013_101")):
    d = full(a, b)
    runs = [x for x in glob.glob("runs/*") if a in os.path.basename(x) or b in os.path.basename(x)]
    c = counts(runs)
    n = len(d)
    low = [s for s in d if d[s][0] < 5]
    lost = [s for s in low if not (d[s][0] > d[s][1])]
    print("=== %s: пар %d ===" % (name, n))
    print("  эталонов с F<5: %d (%.0f%%), из них пара не поймана: %d" % (len(low), 100*len(low)/n, len(lost)))
    cu = collections.Counter(c[s]["U"] for s in low if s in c)
    cm = collections.Counter(c[s]["M"] for s in low if s in c)
    print("  причина у просевших эталонов: U =", dict(sorted(cu.items())), "| M =", dict(sorted(cm.items())))
    cu2 = collections.Counter(c[s]["U"] for s in d if s in c)
    print("  распределение U по ВСЕМ эталонам:", dict(sorted(cu2.items())))
    print("  потенциал: если бы все эталоны получили 5, добавилось бы до %d пар" % len(lost))
    print()
