# -*- coding: utf-8 -*-
import json, os, sys, io, glob, collections
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
from pathlib import Path
def root():
    p = Path(__file__).resolve()
    for c in [p.parent] + list(p.parents):
        if (c / "pyproject.toml").is_file(): return c
    return p.parent
R = root()
meta = {}
bd = R / "bench"
for d in sorted(os.listdir(bd)):
    f = bd / d / "meta.json"
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
v3 = pick("v003_сто_пар"); v12 = pick("v012"); v11 = pick("v011")
common = sorted(set(v3) & set(v12))
print("общих пар с прогоном v003: %d\n" % len(common))
print("%-5s %-15s %-10s %-10s %s" % ("папка", "порча", "v003", "v012", ""))
w3 = w12 = 0
for s in common:
    m = meta.get(s.replace("__", "/"), {})
    a, b = v3[s], v12[s]
    c3, c12 = a[0] > a[1], b[0] > b[1]
    w3 += c3; w12 += c12
    mark = "" if c3 == c12 else ("<- ПРИОБРЕЛИ" if c12 else "<- ПОТЕРЯЛИ")
    print("%-5s %-15s %-10s %-10s %s" % (m.get("id", "?"), ",".join(m.get("error_actions", []))[:15],
          "%d/%d %s" % (a[0], a[1], "лов" if c3 else "="),
          "%d/%d %s" % (b[0], b[1], "лов" if c12 else "="), mark))
print("\nна %d общих парах: v003 ловит %d (%.0f%%), v012 ловит %d (%.0f%%)"
      % (len(common), w3, 100*w3/len(common), w12, 100*w12/len(common)))
for tag, dd in (("v011", v11), ("v012", v12)):
    n = len(dd); w = sum(1 for s in dd if dd[s][0] > dd[s][1])
    r5 = sum(1 for s in dd if dd[s][0] == 5)
    print("%s на всех 35: ловит %d (%.0f%%), эталонов F=5: %d" % (tag, w, 100*w/n, r5))
