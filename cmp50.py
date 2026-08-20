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
a0 = pick("v003_сто_пар"); b0 = pick("v012_сто_пар"); c = pick("v013_полсотни")
keys = set(c)
a = {k: v for k, v in a0.items() if k in keys}
b0 = {k: v for k, v in b0.items() if k in keys}
for tag, dd in (("v003", a), ("v012", b0), ("v013", c)):
    n = len(dd); w = sum(1 for s in dd if dd[s][0] > dd[s][1])
    inv = sum(1 for s in dd if dd[s][0] < dd[s][1])
    r5 = sum(1 for s in dd if dd[s][0] == 5)
    print("%-5s пар %3d | ловит %2d (%.0f%%) | инверсий %d | эталонов F=5: %d (%.0f%%)"
          % (tag, n, w, 100*w/n, inv, r5, 100*r5/n))
b = c
common = sorted(set(a) & set(c))
gain = [s for s in common if b[s][0] > b[s][1] and not (a[s][0] > a[s][1])]
lost = [s for s in common if a[s][0] > a[s][1] and not (b[s][0] > b[s][1])]
w3 = sum(1 for s in common if a[s][0] > a[s][1]); w12 = sum(1 for s in common if b[s][0] > b[s][1])
print("\nна %d общих парах: v003 %d, v012 %d" % (len(common), w3, w12))
print("приобретено %d, потеряно %d" % (len(gain), len(lost)))
nm = lambda s: "%s(%s)" % (meta.get(s.replace("__","/"),{}).get("id","?"),
                           ",".join(meta.get(s.replace("__","/"),{}).get("error_actions",[]))[:12])
print("  + " + ", ".join(nm(s) for s in gain))
print("  - " + ", ".join(nm(s) for s in lost))
# знак различия: McNemar по расхождениям
d = len(gain) + len(lost)
print("\nрасхождений всего %d (приобретено %d, потеряно %d)" % (d, len(gain), len(lost)))
print("при таком числе расхождений разница статистически незначима" if abs(len(gain)-len(lost)) <= (d**0.5)*1.96 else "разница значима")
tp = collections.defaultdict(lambda: [0,0,0])
for s in common:
    t = (meta.get(s.replace("__","/"),{}).get("error_actions") or ["?"])[0]
    tp[t][0]+=1; tp[t][1]+= a[s][0]>a[s][1]; tp[t][2]+= b[s][0]>b[s][1]
print("\n%-14s %-5s %-7s %-7s %s" % ("порча","пар","v003","v012","дельта"))
tp2 = collections.defaultdict(int)
for s in common:
    tt = (meta.get(s.replace("__","/"),{}).get("error_actions") or ["?"])[0]
    tp2[tt] += b0[s][0] > b0[s][1]
for t in sorted(tp, key=lambda x: tp[x][2]-tp[x][1]):
    n,x,y = tp[t]; print("%-14s %-5d %-7d %-7d %-7d" % (t,n,x,tp2[t],y))
