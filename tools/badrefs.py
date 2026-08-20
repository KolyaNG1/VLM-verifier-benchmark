# -*- coding: utf-8 -*-
import json, os, sys, io, glob, collections
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

def _repo_root():
    """Корень репозитория: поднимаемся, пока не увидим pyproject.toml."""
    p = Path(__file__).resolve()
    for cand in [p.parent] + list(p.parents):
        if (cand / "pyproject.toml").is_file():
            return cand
    return p.parent


def _bench_dir():
    """bench/ рядом с репозиторием; запасной путь — старое расположение."""
    here = _repo_root() / "bench"
    if here.is_dir():
        return here
    alt = Path(r"D:\llm-judgeench")
    return alt if alt.is_dir() else here
BENCH = str(_bench_dir())
meta = {}
for d in sorted(os.listdir(BENCH)):
    p = os.path.join(BENCH, d, "meta.json")
    if os.path.isfile(p):
        m = json.load(open(p, encoding="utf-8")); meta[m["figure_key"]] = m
ent = {}
cr = str(_repo_root() / "cached_report.jsonl")
if os.path.isfile(cr):
    for line in open(cr, encoding="utf-8"):
        r = json.loads(line); ent[r["id"]] = (r["n_visual"], r["n_text"])

def load(run):
    out = {}
    for s in sorted(os.listdir(run + "/samples")):
        fs = {x: os.path.join(run, "samples", s, x, "result.json") for x in ("orig", "fail")}
        if not all(os.path.isfile(f) for f in fs.values()):
            continue
        r = {x: json.load(open(fs[x], encoding="utf-8")) for x in fs}
        if any(r[x].get("computed") is None for x in r):
            continue
        out[s] = (r["orig"]["computed"]["scores"]["faithfulness"],
                  r["fail"]["computed"]["scores"]["faithfulness"],
                  r["orig"]["computed"]["counts"], r["orig"]["computed"]["coverage"])
    return out

cands = [d for d in glob.glob("runs/*") if "сто_пар" in d and os.path.isdir(d + "/samples")]
loaded = {d: load(d) for d in cands}
best = {}
for d, v in loaded.items():
    tag = os.path.basename(d).split("__")[1]
    if tag not in best or len(v) > len(loaded[best[tag]]):
        best[tag] = d
a = loaded[best["v003_сто_пар"]]; b = loaded[best["v007_сто_пар"]]
common = sorted(set(a) & set(b))

bad = [s for s in common if a[s][0] < 5 and b[s][0] < 5]
print("пар, где эталон просел в ОБОИХ прогонах: %d из %d" % (len(bad), len(common)))
print()
print("%-5s %-14s %-9s %-9s %-16s %s" % ("папка", "порча", "v003 э/и", "v007 э/и", "счётчики эталона", "сущн. карт/текст"))
for s in bad:
    m = meta.get(s.replace("__", "/"), {})
    i = m.get("id", "?")
    c = a[s][2]
    e = ent.get(i, ("?", "?"))
    print("%-5s %-14s %-9s %-9s P%s/U%s/M%s cov%.2f  %s/%s"
          % (i, ",".join(m.get("error_actions", []))[:14],
             "%d/%d" % (a[s][0], a[s][1]), "%d/%d" % (b[s][0], b[s][1]),
             c["P"], c["U"], c["M"], a[s][3], e[0], e[1]))
w3 = sum(1 for s in common if a[s][0] > a[s][1])
w7 = sum(1 for s in common if b[s][0] > b[s][1])
rest = [s for s in common if s not in bad]
w3r = sum(1 for s in rest if a[s][0] > a[s][1])
w7r = sum(1 for s in rest if b[s][0] > b[s][1])
print()
print("со всеми парами:      v003 %d/%d = %.0f%% | v007 %d/%d = %.0f%%"
      % (w3, len(common), 100 * w3 / len(common), w7, len(common), 100 * w7 / len(common)))
print("без битых эталонов:   v003 %d/%d = %.0f%% | v007 %d/%d = %.0f%%"
      % (w3r, len(rest), 100 * w3r / len(rest), w7r, len(rest), 100 * w7r / len(rest)))
