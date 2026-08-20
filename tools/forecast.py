# -*- coding: utf-8 -*-
import json, os, sys, glob, collections
sys.path.insert(0, "tools")
from ensemble import load_run, load_meta
meta = load_meta()
best = lambda pat: max((load_run(d) for d in glob.glob("runs/*" + pat + "*")), key=len)
def merged(pats):
    d = {}
    for p in pats: d.update(best(p))
    return d
v3 = merged(["v003_сто_пар", "остаток_v003_101"])
v13 = merged(["v013_сто_пар", "остаток_v013_101"])
v17 = merged(["v017_по_типу", "v017_вторая"])
hundred = set(l.strip().replace("/", "__") for l in open("bench_100.txt", encoding="utf-8") if l.strip())
def ens(ds, s):
    o = sum(d[s][0] for d in ds)/len(ds); f = sum(d[s][1] for d in ds)/len(ds)
    return o > f
allpairs = sorted(set(v3) & set(v13))
h = [s for s in allpairs if s in hundred and s in v17]
r = [s for s in allpairs if s not in hundred]
print("сотня с тремя судьями: %d пар | остаток с двумя: %d пар\n" % (len(h), len(r)))
pair_h = sum(1 for s in h if ens([v3, v13], s)); tri_h = sum(1 for s in h if ens([v3, v13, v17], s))
pair_r = sum(1 for s in r if ens([v3, v13], s))
print("на сотне : пара %d/%d = %.0f%% | тройка %d/%d = %.0f%%" % (pair_h, len(h), 100*pair_h/len(h), tri_h, len(h), 100*tri_h/len(h)))
print("на остатке: пара %d/%d = %.0f%% | тройка — неизвестна\n" % (pair_r, len(r), 100*pair_r/len(r)))
# прирост тройки над парой по типам, измеренный на сотне
gain = collections.defaultdict(lambda: [0, 0])
for s in h:
    t = (meta.get(s.replace("__","/"),{}).get("error_actions") or ["?"])[0]
    gain[t][0] += 1
    gain[t][1] += ens([v3, v13, v17], s) - ens([v3, v13], s)
comp = collections.Counter((meta.get(s.replace("__","/"),{}).get("error_actions") or ["?"])[0] for s in r)
print("%-14s %-8s %-14s %-10s %s" % ("порча", "в остатке", "прирост/пара", "ставка", "ожидаемо"))
exp = 0.0
for t in sorted(comp, key=lambda x: -comp[x]):
    n_h, g = gain.get(t, [0, 0])
    rate = g / n_h if n_h else 0.0
    add = rate * comp[t]
    exp += add
    print("%-14s %-8d %-14s %-10.2f %+.1f" % (t, comp[t], "%+d / %d" % (g, n_h), rate, add))
print("\nожидаемый прирост тройки на остатке: %+.1f пары" % exp)
tot_pair = pair_h + pair_r
tot_tri_lo = tri_h + pair_r
tot_tri_hi = tri_h + pair_r + exp
n = len(h) + len(r)
print("\nИТОГ на %d парах:" % n)
print("  пара (измерено)      : %d = %.0f%%" % (tot_pair, 100*tot_pair/n))
print("  тройка, нижняя оценка: %d = %.0f%%  (если на остатке v017 не добавит ничего)" % (tot_tri_lo, 100*tot_tri_lo/n))
print("  тройка, ожидаемая    : %.0f = %.0f%%" % (tot_tri_hi, 100*tot_tri_hi/n))
