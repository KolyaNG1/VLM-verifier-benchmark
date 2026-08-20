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
R = [d for d in glob.glob("runs/*") if "v003" in d and os.path.isdir(d + "/samples")
     and len(os.listdir(d + "/samples")) > 50][0]
print("прогон:", os.path.basename(R))
BENCH = str(_bench_dir())
meta = {}
for d in sorted(os.listdir(BENCH)):
    p = os.path.join(BENCH, d, "meta.json")
    if os.path.isfile(p):
        m = json.load(open(p, encoding="utf-8")); meta[m["figure_key"]] = m
rows = []
for s in sorted(os.listdir(R + "/samples")):
    fs = {x: os.path.join(R, "samples", s, x, "result.json") for x in ("orig", "fail")}
    if not all(os.path.isfile(f) for f in fs.values()):
        continue
    r = {x: json.load(open(fs[x], encoding="utf-8")) for x in fs}
    if any(r[x].get("computed") is None for x in r):
        continue
    m = meta.get(s.replace("__", "/"), {})
    rows.append(((m.get("error_actions") or ["?"])[0],
                 {x: r[x]["computed"]["scores"] for x in r}))
ax = ["faithfulness", "clarity", "style"]
by = collections.defaultdict(lambda: collections.defaultdict(int))
tot = collections.Counter()
for t, sc in rows:
    tot[t] += 1
    for a in ax:
        if sc["orig"][a] > sc["fail"][a]:
            by[t][a] += 1
print()
print("%-14s %-5s %-14s %-13s %-13s" % ("порча", "пар", "faithfulness", "clarity", "style"))
for t in sorted(tot, key=lambda x: -tot[x]):
    f = lambda a: "%d (%.0f%%)" % (by[t][a], 100 * by[t][a] / tot[t])
    print("%-14s %-5d %-14s %-13s %-13s" % (t, tot[t], f("faithfulness"), f("clarity"), f("style")))
n = len(rows)
w = sum(by[t]["faithfulness"] for t in by)
print()
print("ВСЕ типы:%s %d/%d = %.0f%%" % (" " * 22, w, n, 100 * w / n))
for excl in (["restyle"], ["restyle", "geom"], ["restyle", "geom", "edit_value"]):
    sub = [(t, sc) for t, sc in rows if t not in excl]
    k = sum(1 for t, sc in sub if sc["orig"]["faithfulness"] > sc["fail"]["faithfulness"])
    print("без %-27s %d/%d = %.0f%%" % (",".join(excl), k, len(sub), 100 * k / len(sub)))
