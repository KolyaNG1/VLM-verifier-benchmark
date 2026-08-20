# -*- coding: utf-8 -*-
"""Насколько сильно различаются непомеченные пары: шум пережатия или настоящая порча."""
import json, sys, io, hashlib, collections
from pathlib import Path
from PIL import Image, ImageChops
import numpy as np

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path(__file__).resolve().parent
V0 = ROOT / "data" / "verifier_v0"
FIG = V0 / "figures"


def load(n):
    return [json.loads(l) for l in (V0 / n).open(encoding="utf-8") if l.strip()]


def md5(p):
    return hashlib.md5(p.read_bytes()).hexdigest()


fail_keys = [r["sample_id"].split("/", 1)[1] for r in load("manifest_ml_l2_fail.jsonl")]
flagged = {r["sample_id"].split("/", 1)[1]
           for r in load("manifest_eval.jsonl")
           if r["split"] == "ml_l2_fail" and r["gold"]["is_corrupted"]}


def compare(k):
    pb, pr = FIG / "ml_l2_fail" / (k + ".png"), FIG / "ml_orig" / (k + ".png")
    a, b = Image.open(pr).convert("RGB"), Image.open(pb).convert("RGB")
    if a.size != b.size:
        return "разный размер", a.size, b.size, None
    d = np.asarray(ImageChops.difference(a, b), dtype=np.float32)
    frac = float((d.max(axis=2) > 12).mean())      # доля заметно изменённых пикселей
    return "тот же размер", a.size, b.size, frac


for group, keys in (("НЕ помечены битыми, но различаются",
                     [k for k in fail_keys if k not in flagged]),
                    ("помечены битыми и различаются",
                     [k for k in fail_keys if k in flagged])):
    rows = []
    for k in keys:
        pb, pr = FIG / "ml_l2_fail" / (k + ".png"), FIG / "ml_orig" / (k + ".png")
        if not pb.exists() or not pr.exists() or md5(pb) == md5(pr):
            continue
        rows.append((k,) + compare(k))
    print("\n=== %s : %d пар ===" % (group, len(rows)))
    print("  разный размер холста:", sum(1 for r in rows if r[1] == "разный размер"))
    fr = sorted(r[4] for r in rows if r[4] is not None)
    if fr:
        q = lambda p: fr[min(len(fr) - 1, int(len(fr) * p))]
        print("  доля изменённых пикселей: p10=%.4f  медиана=%.4f  p90=%.4f  max=%.4f"
              % (q(.1), q(.5), q(.9), fr[-1]))
        print("  почти неотличимы (<0.1%% пикселей): %d из %d" % (sum(1 for x in fr if x < 0.001), len(fr)))
    print("  примеры сильных различий:")
    for k, kind, sa, sb, f in sorted([r for r in rows if r[4] is not None],
                                     key=lambda r: -r[4])[:5]:
        print("     %-28s изменено %.1f%% пикселей" % (k, f * 100))
