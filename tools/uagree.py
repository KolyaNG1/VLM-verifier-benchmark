# -*- coding: utf-8 -*-
"""Согласны ли два независимых судьи в том, ГДЕ они находят галлюцинации?"""
import json, os, sys, io, glob, collections
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
                cur[s] = {x: r[x]["computed"]["counts"]["U"] for x in fs}
            if len(cur) > bn: best, bn = cur, len(cur)
        out.update(best)
    return out

a = load_counts(["v003_сто_пар", "остаток_v003_101"])
b = load_counts(["v013_сто_пар", "остаток_v013_101"])
common = sorted(set(a) & set(b))
print("пар с обоими прогонами: %d\n" % len(common))
for side, label in (("orig", "ЭТАЛОНЫ (здесь любое U — ошибка судьи)"),
                    ("fail", "ИСПОРЧЕННЫЕ (здесь U — настоящий сигнал)")):
    both = sum(1 for s in common if a[s][side] > 0 and b[s][side] > 0)
    only_a = sum(1 for s in common if a[s][side] > 0 and b[s][side] == 0)
    only_b = sum(1 for s in common if a[s][side] == 0 and b[s][side] > 0)
    none = sum(1 for s in common if a[s][side] == 0 and b[s][side] == 0)
    flagged = both + only_a + only_b
    print("%s" % label)
    print("  оба нашли U>0      : %3d" % both)
    print("  только v003        : %3d" % only_a)
    print("  только v013        : %3d" % only_b)
    print("  никто              : %3d" % none)
    if flagged:
        print("  --> согласие среди «хоть кто-то нашёл»: %.0f%%" % (100 * both / flagged))
    print()
