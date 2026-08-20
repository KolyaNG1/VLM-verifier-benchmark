# -*- coding: utf-8 -*-
import json, os, sys, io, collections, glob
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
                  r["fail"]["computed"]["scores"]["faithfulness"],
                  r["fail"]["model_output"].get("defects"))
    return out

cands = [d for d in glob.glob("runs/*") if "сто_пар" in d and os.path.isdir(d + "/samples")]
loaded = {d: load(d) for d in cands}
# среди одноимённых прогонов берём тот, где реально досчитано больше пар
best = {}
for d, v in loaded.items():
    tag = os.path.basename(d).split("__")[1]
    if tag not in best or len(v) > len(loaded[best[tag]]):
        best[tag] = d
for tag, d in sorted(best.items()):
    print("  %-16s %-70s пар %d" % (tag, os.path.basename(d)[:70], len(loaded[d])))
a = loaded[best["v003_сто_пар"]]; b = loaded[best["v008_сто_пар"]]
common = sorted(set(a) & set(b))
print("общих пар: %d" % len(common))
for name, dd in (("v003", a), ("v008", b)):
    w = sum(1 for s in common if dd[s][0] > dd[s][1])
    inv = sum(1 for s in common if dd[s][0] < dd[s][1])
    ref5 = sum(1 for s in common if dd[s][0] == 5)
    print("%-6s ловит %2d (%.0f%%) | инверсий %d | эталонов с F=5: %d"
          % (name, w, 100 * w / len(common), inv, ref5))
print()
tp = collections.defaultdict(lambda: [0, 0, 0])
for s in common:
    t = (meta.get(s.replace("__", "/"), {}).get("error_actions") or ["?"])[0]
    tp[t][0] += 1
    tp[t][1] += a[s][0] > a[s][1]
    tp[t][2] += b[s][0] > b[s][1]
print("%-14s %-5s %-8s %-8s %s" % ("порча", "пар", "v003", "v008", "дельта"))
for t in sorted(tp, key=lambda x: tp[x][2] - tp[x][1]):
    n, x, y = tp[t]
    print("%-14s %-5d %-8d %-8d %+d" % (t, n, x, y, y - x))
print()
lost = [s for s in common if a[s][0] > a[s][1] and not (b[s][0] > b[s][1])]
gain = [s for s in common if b[s][0] > b[s][1] and not (a[s][0] > a[s][1])]
print("потеряно v008: %d | приобретено: %d" % (len(lost), len(gain)))
import json as _j
print("  приобретено:", [meta.get(s.replace("__","/"),{}).get("id") for s in gain])
print("  потеряно:   ", [meta.get(s.replace("__","/"),{}).get("id") for s in lost])
print()
nd = sum(1 for s in common if b[s][2] is None)
print("пар без поля defects в v008: %d из %d" % (nd, len(common)))
kinds = collections.Counter()
for s in common:
    for x in (b[s][2] or []):
        kinds[x.get("kind")] += 1
print("типы дефектов, названные судьёй:", dict(kinds.most_common()))
