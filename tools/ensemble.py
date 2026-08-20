# -*- coding: utf-8 -*-
"""
Ансамбль судей: считает детекцию по агрегированным оценкам нескольких прогонов.

Ансамбль — не отдельный режим раннера, а арифметика поверх готовых прогонов.
Каждый судья прогоняется обычной командой `vlm_bench run`, затем оценка каждой
стороны пары усредняется по судьям, и уже усреднённые значения сравниваются.

    python tools/ensemble.py                          # найти прогоны по умолчанию
    python tools/ensemble.py --judge v003 runs/A runs/B --judge v013 runs/C runs/D
    python tools/ensemble.py --rule min

Несколько каталогов на одного судью склеиваются: так собирается полный набор из
прогона по сотне и прогона по остатку.
"""
import argparse, json, os, sys, io, glob, collections, math
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")


def repo_root():
    p = Path(__file__).resolve()
    for c in [p.parent] + list(p.parents):
        if (c / "pyproject.toml").is_file():
            return c
    return p.parent


ROOT = repo_root()
BENCH = ROOT / "bench" if (ROOT / "bench").is_dir() else Path(r"D:\llm-judge\bench")


def load_meta():
    out = {}
    if not BENCH.is_dir():
        return out
    for d in sorted(os.listdir(BENCH)):
        f = BENCH / d / "meta.json"
        if f.is_file():
            m = json.loads(f.read_text(encoding="utf-8"))
            out[m["figure_key"]] = m
    return out


def load_run(run):
    """Оценки faithfulness по парам одного прогона."""
    out = {}
    sd = Path(run) / "samples"
    if not sd.is_dir():
        return out
    for s in sorted(os.listdir(sd)):
        fs = {x: sd / s / x / "result.json" for x in ("orig", "fail")}
        if not all(f.is_file() for f in fs.values()):
            continue
        try:
            r = {x: json.loads(fs[x].read_text(encoding="utf-8")) for x in fs}
        except Exception:
            continue
        if any(r[x].get("computed") is None for x in r):
            continue
        out[s] = (r["orig"]["computed"]["scores"]["faithfulness"],
                  r["fail"]["computed"]["scores"]["faithfulness"])
    return out


def merge(runs):
    """Склейка нескольких прогонов одного судьи. При совпадении берём поздний."""
    out = {}
    for run in runs:
        out.update(load_run(run))
    return out


RULES = {"mean": lambda xs: sum(xs) / len(xs), "min": min, "max": max}


def significance(gain, lost):
    d = gain + lost
    if d == 0:
        return "расхождений нет"
    thr = math.sqrt(d) * 1.96
    return ("значимо" if abs(gain - lost) > thr else "НЕзначимо") + " (порог %.1f)" % thr


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--judge", nargs="+", action="append", metavar=("ИМЯ", "КАТАЛОГ"),
                    help="имя судьи и один или несколько каталогов прогонов")
    ap.add_argument("--rule", default="mean", choices=sorted(RULES),
                    help="как агрегировать оценки судей (по умолчанию mean)")
    ap.add_argument("--baseline", default=None, help="с кем сравнивать ансамбль")
    args = ap.parse_args()

    meta = load_meta()
    judges = {}
    if args.judge:
        for item in args.judge:
            judges[item[0]] = merge(item[1:])
    else:
        for name, tag in (("v003", "v003_"), ("v013", "v013_")):
            runs = [d for d in glob.glob(str(ROOT / "runs/*")) if tag in os.path.basename(d)]
            if runs:
                judges[name] = merge(runs)
        if not judges:
            print("прогонов не найдено, укажите --judge"); return 1

    for n, d in judges.items():
        print("судья %-6s пар с результатом: %d" % (n, len(d)))
    common = sorted(set.intersection(*(set(d) for d in judges.values())))
    print("\nпар, покрытых всеми судьями: %d\n" % len(common))
    if not common:
        return 1

    names = list(judges)
    base = args.baseline or names[0]
    rule = RULES[args.rule]

    print("=== по отдельности ===")
    single = {}
    for n in names:
        d = judges[n]
        w = sum(1 for s in common if d[s][0] > d[s][1])
        inv = sum(1 for s in common if d[s][0] < d[s][1])
        r5 = sum(1 for s in common if d[s][0] == 5)
        single[n] = {s: d[s][0] > d[s][1] for s in common}
        print("%-6s ловит %3d из %d = %2.0f%% | инверсий %d | эталонов F=5: %d (%.0f%%)"
              % (n, w, len(common), 100 * w / len(common), inv, r5, 100 * r5 / len(common)))

    print("\n=== ансамбль, правило %s ===" % args.rule)
    ens = {}
    w = inv = 0
    for s in common:
        o = rule([judges[n][s][0] for n in names])
        f = rule([judges[n][s][1] for n in names])
        ens[s] = o > f
        w += o > f
        inv += o < f
    print("%-6s ловит %3d из %d = %2.0f%% | инверсий %d"
          % ("+".join(names), w, len(common), 100 * w / len(common), inv))

    gain = sum(1 for s in common if ens[s] and not single[base][s])
    lost = sum(1 for s in common if single[base][s] and not ens[s])
    print("\nпротив одиночного %s: приобретено %d, потеряно %d -> %s"
          % (base, gain, lost, significance(gain, lost)))

    if meta:
        tp = collections.defaultdict(lambda: collections.Counter())
        for s in common:
            t = (meta.get(s.replace("__", "/"), {}).get("error_actions") or ["?"])[0]
            tp[t]["n"] += 1
            for n in names:
                tp[t][n] += single[n][s]
            tp[t]["ens"] += ens[s]
        print("\n%-14s %-5s %s %s" % ("порча", "пар",
              " ".join("%-6s" % n for n in names), "ансамбль"))
        for t in sorted(tp, key=lambda x: -tp[x]["n"]):
            c = tp[t]
            print("%-14s %-5d %s %d" % (t, c["n"],
                  " ".join("%-6d" % c[n] for n in names), c["ens"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
