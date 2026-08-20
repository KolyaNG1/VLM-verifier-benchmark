# -*- coding: utf-8 -*-
import json, os, sys, io, glob
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
def root():
    from pathlib import Path
    p = Path(__file__).resolve()
    for c in [p.parent] + list(p.parents):
        if (c / "pyproject.toml").is_file(): return c
    return p.parent
R = root()
meta = {}
for d in sorted(os.listdir(R / "bench")):
    p = R / "bench" / d / "meta.json"
    if p.is_file():
        m = json.loads(p.read_text(encoding="utf-8")); meta[m["figure_key"]] = m
def load(run):
    out = {}
    sd = os.path.join(run, "samples")
    for s in sorted(os.listdir(sd)):
        fs = {x: os.path.join(sd, s, x, "result.json") for x in ("orig", "fail")}
        if not all(os.path.isfile(f) for f in fs.values()): continue
        r = {x: json.load(open(fs[x], encoding="utf-8")) for x in fs}
        if any(r[x].get("computed") is None for x in r):
            out[s] = None; continue
        out[s] = (r["orig"]["computed"]["scores"]["faithfulness"],
                  r["fail"]["computed"]["scores"]["faithfulness"])
    return out
new = [d for d in glob.glob(str(R / "runs/*")) if "v010" in d]
old = [d for d in glob.glob(str(R / "runs/*")) if "v003_сто_пар" in d]
b = load(sorted(new)[-1]); a = max((load(d) for d in old), key=len)
done = [s for s in b if b[s] is not None and s in a and a[s] is not None]
print("готово в v010: %d пар, из них есть в v003: %d\n" % (len([x for x in b.values() if x is not None]), len(done)))
print("%-5s %-14s %-10s %-10s %s" % ("папка", "порча", "v003", "v010", "изменение"))
w3 = w10 = 0
for s in done:
    m = meta.get(s.replace("__", "/"), {})
    fo3, ff3 = a[s]; fo, ff = b[s]
    c3 = fo3 > ff3; c10 = fo > ff
    w3 += c3; w10 += c10
    mark = "" if c3 == c10 else ("<- ПРИОБРЕЛИ" if c10 else "<- ПОТЕРЯЛИ")
    print("%-5s %-14s %-10s %-10s %s" % (m.get("id", "?"),
          ",".join(m.get("error_actions", []))[:14],
          "%d/%d %s" % (fo3, ff3, "лов" if c3 else "="),
          "%d/%d %s" % (fo, ff, "лов" if c10 else "="), mark))
print("\nна этих %d парах: v003 ловит %d, v010 ловит %d" % (len(done), w3, w10))
