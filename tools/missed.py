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
                  r["fail"]["computed"]["scores"]["faithfulness"])
    return out

cands = [d for d in glob.glob("runs/*") if "v003_сто_пар" in d and os.path.isdir(d + "/samples")]
a = max((load(d) for d in cands), key=len)
missed = [s for s in a if a[s][0] <= a[s][1]]
caught = [s for s in a if a[s][0] > a[s][1]]
print("непойманных: %d, пойманных: %d\n" % (len(missed), len(caught)))

def norm(x):
    return x.strip().lower().replace("ё", "е")

for title, group in (("НЕ ПОЙМАНО", missed), ("ПОЙМАНО", caught)):
    c = collections.Counter()
    for s in group:
        for raw in (meta.get(s.replace("__", "/"), {}).get("error_raw") or []):
            c[norm(raw)] += 1
    print("=== %s — формулировки разметки ===" % title)
    for k, v in c.most_common(18):
        print("  %2d  %s" % (v, k[:78]))
    print()
