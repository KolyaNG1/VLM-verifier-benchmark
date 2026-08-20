# -*- coding: utf-8 -*-
"""Перебор порогов faithfulness по уже сохранённым счётчикам. Запросов не делает."""
import json, os, sys, io, glob
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

def F(P, U, M, mid, mx):
    tot = P + M
    if tot < 1:
        return None
    cov = P / tot
    if U >= 2: return 1
    if U == 1: return 1 if M >= 1 else 3
    if cov >= mx: return 5
    if cov >= mid: return 3
    return 1

def load(run):
    out = []
    for s in sorted(os.listdir(run + "/samples")):
        fs = {x: os.path.join(run, "samples", s, x, "result.json") for x in ("orig", "fail")}
        if not all(os.path.isfile(f) for f in fs.values()):
            continue
        r = {x: json.load(open(fs[x], encoding="utf-8")) for x in fs}
        if any(r[x].get("computed") is None for x in r):
            continue
        out.append({x: r[x]["computed"]["counts"] for x in r})
    return out

runs = {}
for d in glob.glob("runs/*"):
    if "сто_пар" not in d or not os.path.isdir(d + "/samples"):
        continue
    tag = os.path.basename(d).split("__")[1]
    v = load(d)
    if tag not in runs or len(v) > len(runs[tag]):
        runs[tag] = v

for tag in sorted(runs):
    rows = runs[tag]
    print("=" * 66)
    print("%s — пар %d" % (tag, len(rows)))
    print("%-8s %-8s %-14s %-14s %s" % ("mid", "max", "ловит", "инверсия", "эталонов F=5"))
    best = None
    for mid in (0.50, 0.60, 0.70, 0.80, 0.90):
        for mx in (0.80, 0.90, 0.95, 0.99, 1.00):
            if mx < mid:
                continue
            w = inv = ref5 = 0
            for c in rows:
                fo = F(c["orig"]["P"], c["orig"]["U"], c["orig"]["M"], mid, mx)
                ff = F(c["fail"]["P"], c["fail"]["U"], c["fail"]["M"], mid, mx)
                if fo is None or ff is None:
                    continue
                w += fo > ff; inv += fo < ff; ref5 += fo == 5
            score = (w, -inv)
            if best is None or score > best[0]:
                best = (score, mid, mx, w, inv, ref5)
            star = ""
            print("%-8.2f %-8.2f %-14s %-14d %d%s"
                  % (mid, mx, "%d (%.0f%%)" % (w, 100 * w / len(rows)), inv, ref5, star))
    print("ЛУЧШЕЕ: mid=%.2f max=%.2f -> ловит %d (%.0f%%), инверсий %d, эталонов F=5: %d"
          % (best[1], best[2], best[3], 100 * best[3] / len(rows), best[4], best[5]))
