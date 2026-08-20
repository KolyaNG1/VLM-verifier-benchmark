# -*- coding: utf-8 -*-
import json, os, sys, glob, collections
sys.path.insert(0, "tools")
from ensemble import load_run, load_meta
meta = load_meta()
def best(pat):
    return max((load_run(d) for d in glob.glob("runs/*" + pat + "*")), key=len)
v3, v13, v16 = best("v003_сто_пар"), best("v013_сто_пар"), best("v016_проверка")
common = sorted(set(v3) & set(v13) & set(v16))
print("общих пар: %d\n" % len(common))
def ens(ds, s):
    o = sum(d[s][0] for d in ds)/len(ds); f = sum(d[s][1] for d in ds)/len(ds)
    return o > f, o < f
for name, ds in (("v003", [v3]), ("v013", [v13]), ("v016", [v16]),
                 ("v003+v013", [v3, v13]), ("v003+v016", [v3, v16]),
                 ("v013+v016", [v13, v16]), ("все трое", [v3, v13, v16])):
    w = i = 0
    for s in common:
        a, b = ens(ds, s); w += a; i += b
    r5 = sum(1 for s in common if len(ds) == 1 and ds[0][s][0] == 5)
    extra = " | эталонов F=5: %d" % r5 if len(ds) == 1 else ""
    print("%-12s ловит %2d из %d = %2.0f%% | инверсий %d%s" % (name, w, len(common), 100*w/len(common), i, extra))
b13 = {s: ens([v13], s)[0] for s in common}
b16 = {s: ens([v16], s)[0] for s in common}
g = [s for s in common if b16[s] and not b13[s]]; l = [s for s in common if b13[s] and not b16[s]]
nm = lambda s: "%s(%s)" % (meta.get(s.replace("__","/"),{}).get("id","?"),
                           ",".join(meta.get(s.replace("__","/"),{}).get("error_actions",[]))[:10])
print("\nv016 против v013: приобретено %d, потеряно %d" % (len(g), len(l)))
if g: print("  + " + ", ".join(nm(s) for s in g))
if l: print("  - " + ", ".join(nm(s) for s in l))
e2 = {s: ens([v3, v13], s)[0] for s in common}
e3 = {s: ens([v3, v16], s)[0] for s in common}
g2 = [s for s in common if e3[s] and not e2[s]]; l2 = [s for s in common if e2[s] and not e3[s]]
print("\nансамбль v003+v016 против v003+v013: приобретено %d, потеряно %d" % (len(g2), len(l2)))
tp = collections.defaultdict(lambda: [0,0,0])
for s in common:
    t = (meta.get(s.replace("__","/"),{}).get("error_actions") or ["?"])[0]
    tp[t][0]+=1; tp[t][1]+=b13[s]; tp[t][2]+=b16[s]
print("\n%-14s %-5s %-7s %s" % ("порча","пар","v013","v016"))
for t in sorted(tp, key=lambda x: tp[x][2]-tp[x][1]):
    n,x,y = tp[t]; print("%-14s %-5d %-7d %d" % (t,n,x,y))
