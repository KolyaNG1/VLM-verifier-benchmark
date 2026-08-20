# -*- coding: utf-8 -*-
import json, os, sys, glob, collections, math
sys.path.insert(0, "tools")
from ensemble import load_run, load_meta
meta = load_meta()
best = lambda pat: max((load_run(d) for d in glob.glob("runs/*" + pat + "*")), key=len)
v3, v13 = best("v003_сто_пар"), best("v013_сто_пар")
v17 = {}
for pat in ("v017_по_типу", "v017_вторая"):
    v17.update(best(pat))
common = sorted(set(v3) & set(v13) & set(v17))
print("v017 покрывает пар: %d | общих со всеми: %d\n" % (len(v17), len(common)))
def ens(ds, s):
    o = sum(d[s][0] for d in ds)/len(ds); f = sum(d[s][1] for d in ds)/len(ds)
    return o > f, o < f
res = {}
for name, ds in (("v003", [v3]), ("v013", [v13]), ("v017", [v17]),
                 ("v003+v013", [v3, v13]), ("v003+v017", [v3, v17]), ("v013+v017", [v13, v17]),
                 ("тройка", [v3, v13, v17])):
    w = i = 0
    for s in common:
        a, b = ens(ds, s); w += a; i += b
    res[name] = {s: ens(ds, s)[0] for s in common}
    print("%-14s ловит %2d из %d = %2.0f%% | инверсий %d" % (name, w, len(common), 100*w/len(common), i))
g = [s for s in common if res["тройка"][s] and not res["v003+v013"][s]]
l = [s for s in common if res["v003+v013"][s] and not res["тройка"][s]]
d = len(g) + len(l)
print("\nтройка против пары: приобретено %d, потеряно %d, расхождений %d" % (len(g), len(l), d))
if d: print("%s (порог %.1f)" % ("значимо" if abs(len(g)-len(l)) > math.sqrt(d)*1.96 else "НЕзначимо", math.sqrt(d)*1.96))
nm = lambda s: "%s(%s)" % (meta.get(s.replace("__","/"),{}).get("id","?"),
                           ",".join(meta.get(s.replace("__","/"),{}).get("error_actions",[]))[:10])
if g: print("  + " + ", ".join(nm(s) for s in g))
if l: print("  - " + ", ".join(nm(s) for s in l))
tp = collections.defaultdict(lambda: [0,0,0,0,0])
for s in common:
    t = (meta.get(s.replace("__","/"),{}).get("error_actions") or ["?"])[0]
    tp[t][0]+=1; tp[t][1]+=res["v003"][s]; tp[t][2]+=res["v013"][s]
    tp[t][3]+=res["v017"][s]; tp[t][4]+=res["тройка"][s]
print("\n%-14s %-5s %-6s %-6s %-6s %s" % ("порча","пар","v003","v013","v017","тройка"))
for t in sorted(tp, key=lambda x: -tp[x][0]):
    n,a,b,c,e = tp[t]; print("%-14s %-5d %-6d %-6d %-6d %d" % (t,n,a,b,c,e))
tf = collections.Counter()
for R in glob.glob("runs/*v017*"):
    sd = os.path.join(R, "samples")
    if not os.path.isdir(sd): continue
    for s in os.listdir(sd):
        f = os.path.join(sd, s, "orig", "result.json")
        if os.path.isfile(f):
            try: tf[(json.load(open(f, encoding="utf-8")).get("model_output") or {}).get("figure_type")] += 1
            except Exception: pass
print("\nтипы фигур:", dict(tf.most_common()))
