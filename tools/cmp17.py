# -*- coding: utf-8 -*-
import json, os, sys, glob, collections
sys.path.insert(0, "tools")
from ensemble import load_run, load_meta
meta = load_meta()
best = lambda pat: max((load_run(d) for d in glob.glob("runs/*" + pat + "*")), key=len)
v3, v13, v16, v17 = best("v003_сто_пар"), best("v013_сто_пар"), best("v016_проверка"), best("v017_по_типу")
common = sorted(set(v3) & set(v13) & set(v17))
print("общих пар: %d\n" % len(common))
def ens(ds, s):
    o = sum(d[s][0] for d in ds)/len(ds); f = sum(d[s][1] for d in ds)/len(ds)
    return o > f, o < f
for name, ds in (("v003", [v3]), ("v013", [v13]), ("v017", [v17]),
                 ("v003+v013", [v3, v13]), ("v003+v017", [v3, v17]), ("v013+v017", [v13, v17]),
                 ("v003+v013+v017", [v3, v13, v17])):
    w = i = 0
    for s in common:
        a, b = ens(ds, s); w += a; i += b
    print("%-16s ловит %2d из %d = %2.0f%% | инверсий %d" % (name, w, len(common), 100*w/len(common), i))
# насколько ошибки v017 отличаются от ошибок остальных
print()
c = {n: {s: d[s][0] > d[s][1] for s in common} for n, d in (("v003", v3), ("v013", v13), ("v017", v17))}
for a, b in (("v003", "v013"), ("v003", "v017"), ("v013", "v017")):
    only_a = sum(1 for s in common if c[a][s] and not c[b][s])
    only_b = sum(1 for s in common if c[b][s] and not c[a][s])
    both = sum(1 for s in common if c[a][s] and c[b][s])
    un = both + only_a + only_b
    print("%-5s vs %-5s: оба %2d | только %s %2d | только %s %2d | пересечение %.0f%% от объединения"
          % (a, b, both, a, only_a, b, only_b, 100*both/un if un else 0))
# распределение типов фигур
tf = collections.Counter()
R = max(glob.glob("runs/*v017_по_типу*"))
sd = os.path.join(R, "samples")
for s in os.listdir(sd):
    f = os.path.join(sd, s, "orig", "result.json")
    if os.path.isfile(f):
        try: tf[(json.load(open(f, encoding="utf-8")).get("model_output") or {}).get("figure_type")] += 1
        except Exception: pass
print("\nтипы фигур по мнению судьи:", dict(tf.most_common()))
