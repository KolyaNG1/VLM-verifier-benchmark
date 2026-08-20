# -*- coding: utf-8 -*-
import json, os, sys, io, glob
from pathlib import Path
sys.path.insert(0, "tools")
from ensemble import load_run, load_meta  # он сам ставит utf-8 на stdout
meta = load_meta()
def best(pat):
    """из одноимённых прогонов берём тот, где реально досчитано больше пар"""
    return max((load_run(d) for d in glob.glob("runs/*" + pat + "*")), key=len)
v3, v13, v14 = best("v003_сто_пар"), best("v013_сто_пар"), best("v014_инвент")
common = sorted(set(v3) & set(v13) & set(v14))
print("общих пар: %d\n" % len(common))
def ens(ds, s):
    o = sum(d[s][0] for d in ds) / len(ds); f = sum(d[s][1] for d in ds) / len(ds)
    return o > f, o < f
rows = [("v003 один", [v3]), ("v013 один", [v13]), ("v014 один", [v14]),
        ("v003+v013", [v3, v13]), ("v003+v014", [v3, v14]), ("v013+v014", [v13, v14]),
        ("все трое", [v3, v13, v14])]
for name, ds in rows:
    w = i = 0
    for s in common:
        a, b = ens(ds, s); w += a; i += b
    print("%-12s ловит %2d из %d = %2.0f%% | инверсий %d" % (name, w, len(common), 100*w/len(common), i))
base = {s: ens([v3, v13], s)[0] for s in common}
tri = {s: ens([v3, v13, v14], s)[0] for s in common}
gain = [s for s in common if tri[s] and not base[s]]
lost = [s for s in common if base[s] and not tri[s]]
print("\nтройка против двойки: приобретено %d, потеряно %d" % (len(gain), len(lost)))
nm = lambda s: "%s(%s)" % (meta.get(s.replace("__","/"),{}).get("id","?"),
                           ",".join(meta.get(s.replace("__","/"),{}).get("error_actions",[]))[:10])
if gain: print("  + " + ", ".join(nm(s) for s in gain))
if lost: print("  - " + ", ".join(nm(s) for s in lost))
