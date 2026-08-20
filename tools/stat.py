# -*- coding: utf-8 -*-
"""Статистика детекции по faithfulness для одного или нескольких прогонов."""
import json, os, sys, io, collections
from pathlib import Path
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
REPO = _repo_root()
BENCH = _bench_dir()

meta = {}
for d in sorted(os.listdir(BENCH)):
    p = BENCH / d / "meta.json"
    if p.is_file():
        m = json.loads(p.read_text(encoding="utf-8")); meta[m["figure_key"]] = m

def stats(run_dir):
    rows, cost, err = [], 0.0, 0
    sdir = Path(run_dir) / "samples"
    for s in sorted(os.listdir(sdir)):
        fs = {x: sdir / s / x / "result.json" for x in ("orig", "fail")}
        if not all(f.is_file() for f in fs.values()):
            continue
        r = {x: json.loads(fs[x].read_text(encoding="utf-8")) for x in fs}
        cost += sum((r[x].get("cost_usd") or 0) for x in r)
        if any(r[x].get("computed") is None for x in r):
            err += 1; continue
        m = meta.get(s.replace("__", "/"), {})
        rows.append((m.get("id", "?"), (m.get("error_actions") or ["?"])[0],
                     r["orig"]["computed"]["scores"]["faithfulness"],
                     r["fail"]["computed"]["scores"]["faithfulness"]))
    return rows, cost, err

for run in sys.argv[1:]:
    rows, cost, err = stats(run)
    n = len(rows)
    w = sum(1 for r in rows if r[2] > r[3]); t = sum(1 for r in rows if r[2] == r[3])
    l = sum(1 for r in rows if r[2] < r[3])
    print("=" * 74)
    print(Path(run).name)
    print("пар %d | ЛОВИТ %d (%.0f%%) | ничья %d | инверсия %d | сбоев %d | $%.4f"
          % (n, w, 100 * w / max(n, 1), t, l, err, cost))
    print("эталоны: F=5 у %d, F=3 у %d, F=1 у %d"
          % (sum(1 for r in rows if r[2] == 5), sum(1 for r in rows if r[2] == 3),
             sum(1 for r in rows if r[2] == 1)))
    bt = collections.defaultdict(collections.Counter)
    for r in rows:
        bt[r[1]]["w" if r[2] > r[3] else ("t" if r[2] == r[3] else "l")] += 1
    print("  " + "  ".join("%s %d/%d" % (k, bt[k]["w"], sum(bt[k].values())) for k in sorted(bt)))
    print("  не поймано:", ", ".join("%s(%s)" % (r[0], r[1]) for r in rows if r[2] <= r[3]))
