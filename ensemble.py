# -*- coding: utf-8 -*-
import json, os, sys, io, glob, collections
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
def root():
    p = Path(__file__).resolve()
    for c in [p.parent] + list(p.parents):
        if (c / "pyproject.toml").is_file(): return c
    return p.parent
R = root()
meta = {}
for d in sorted(os.listdir(R / "bench")):
    f = R / "bench" / d / "meta.json"
    if f.is_file():
        m = json.loads(f.read_text(encoding="utf-8")); meta[m["figure_key"]] = m
def load(run):
    out = {}
    sd = os.path.join(run, "samples")
    for s in sorted(os.listdir(sd)):
        fs = {x: os.path.join(sd, s, x, "result.json") for x in ("orig", "fail")}
        if not all(os.path.isfile(f) for f in fs.values()): continue
        r = {x: json.load(open(fs[x], encoding="utf-8")) for x in fs}
        if any(r[x].get("computed") is None for x in r): continue
        out[s] = (r["orig"]["computed"]["scores"]["faithfulness"],
                  r["fail"]["computed"]["scores"]["faithfulness"])
    return out
pick = lambda tag: max((load(d) for d in glob.glob(str(R / "runs/*")) if tag in d), key=len)
v3, v12, v13 = pick("v003_сто_пар"), pick("v012_сто_пар"), pick("v013_полсотни")
common = sorted(set(v3) & set(v12) & set(v13))
print("пар, где есть все три прогона: %d\n" % len(common))
catch = lambda d, s: d[s][0] > d[s][1]
inv = lambda d, s: d[s][0] < d[s][1]
def agg(fn, s, *ds):
    """Симметричная агрегация: оценка каждой стороны считается по всем судьям."""
    o = fn(d[s][0] for d in ds); f = fn(d[s][1] for d in ds)
    return o, f
print("=== честная агрегация: обе стороны считаются одним правилом ===")
for name, fn, ds in (("min(v003,v013)", min, (v3, v13)),
                     ("min(v003,v012,v013)", min, (v3, v12, v13)),
                     ("среднее(v003,v013)", lambda xs: sum(xs)/2, (v3, v13)),
                     ("max(v003,v013)", max, (v3, v13))):
    w = i = 0
    for s in common:
        o, f = agg(fn, s, *ds)
        w += o > f; i += o < f
    print("%-22s ловит %2d из %d = %.0f%% | инверсий %d" % (name, w, len(common), 100*w/len(common), i))
# значимость: сравниваем среднее(v003,v013) против одиночного v003
g = l = 0
for s in common:
    o1, f1 = v3[s]; o2, f2 = ((v3[s][0]+v13[s][0])/2, (v3[s][1]+v13[s][1])/2)
    c1, c2 = o1 > f1, o2 > f2
    g += (c2 and not c1); l += (c1 and not c2)
d = g + l
print("среднее против одиночного v003: приобретено %d, потеряно %d, расхождений %d" % (g, l, d))
print("значимо" if abs(g - l) > (d ** 0.5) * 1.96 else "НЕзначимо", "(порог %.1f)" % ((d ** 0.5) * 1.96))
print()
combos = {
    "v003 один":            lambda s: catch(v3, s),
    "v012 один":            lambda s: catch(v12, s),
    "v013 один":            lambda s: catch(v13, s),
    "v003 ИЛИ v013":        lambda s: catch(v3, s) or catch(v13, s),
    "v012 ИЛИ v013":        lambda s: catch(v12, s) or catch(v13, s),
    "v003 ИЛИ v012":        lambda s: catch(v3, s) or catch(v12, s),
    "любой из трёх":        lambda s: catch(v3, s) or catch(v12, s) or catch(v13, s),
    "хотя бы двое из трёх": lambda s: sum((catch(v3,s), catch(v12,s), catch(v13,s))) >= 2,
    "все трое":             lambda s: catch(v3, s) and catch(v12, s) and catch(v13, s),
}
for name, f in combos.items():
    w = sum(1 for s in common if f(s))
    fp = sum(1 for s in common if (inv(v3,s) or inv(v12,s) or inv(v13,s)) and f(s))
    print("%-22s ловит %2d из %d = %.0f%%" % (name, w, len(common), 100*w/len(common)))
print()
tp = collections.defaultdict(lambda: [0,0,0,0,0])
for s in common:
    t = (meta.get(s.replace("__","/"),{}).get("error_actions") or ["?"])[0]
    tp[t][0]+=1; tp[t][1]+=catch(v3,s); tp[t][2]+=catch(v12,s); tp[t][3]+=catch(v13,s)
    tp[t][4]+= (catch(v3,s) or catch(v13,s))
print("%-14s %-5s %-6s %-6s %-6s %s" % ("порча","пар","v003","v012","v013","v003 ИЛИ v013"))
for t in sorted(tp, key=lambda x: -tp[x][0]):
    n,a,b,c,u = tp[t]
    print("%-14s %-5d %-6d %-6d %-6d %d" % (t,n,a,b,c,u))
