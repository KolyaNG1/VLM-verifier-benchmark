# -*- coding: utf-8 -*-
"""Полная инвентаризация: что где лежит и сколько четвёрок реально собирается."""
import json, os, sys, io, hashlib, collections
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path(__file__).resolve().parent
V0 = ROOT / "data" / "verifier_v0"
FIG = V0 / "figures"


def load(name):
    return [json.loads(l) for l in (V0 / name).open(encoding="utf-8") if l.strip()]


def md5(p):
    return hashlib.md5(p.read_bytes()).hexdigest()


print("=" * 78)
print("МАНИФЕСТЫ (JSONL, поля: caption, text_block, image_path, gold)")
for f in sorted(V0.glob("manifest*.jsonl")):
    n = sum(1 for _ in f.open(encoding="utf-8"))
    print("  %-32s %5d строк  %8.1f KB" % (f.name, n, f.stat().st_size / 1024))

print("\nФИГУРЫ (PNG, путь = figures/<split>/<document_N>/<figure_M>.png)")
for d in sorted(p for p in FIG.iterdir() if p.is_dir()):
    docs = [p for p in d.iterdir() if p.is_dir()]
    pngs = sum(len(list(p.glob("*.png"))) for p in docs)
    print("  %-16s %3d документов, %5d png" % (d.name, len(docs), pngs))

ev = load("manifest_eval.jsonl")
print("\nmanifest_eval.jsonl — только испорченные фигуры и их оригиналы:")
for k, v in sorted(collections.Counter(
        (r["split"], r["gold"]["is_corrupted"]) for r in ev).items()):
    print("  %-16s is_corrupted=%-5s %4d" % (k[0], k[1], v))

print("\n" + "=" * 78)
print("СКОЛЬКО ЧЕТВЁРОК РЕАЛЬНО СОБИРАЕТСЯ")
PAIRS = {"ml_l2_fail": "ml_orig", "juri_l2_fail": "juri_orig"}
orig_ids = {}
for sp in set(PAIRS.values()):
    orig_ids[sp] = {r["sample_id"].split("/", 1)[1] for r in load("manifest_%s.jsonl" % sp)}

for fail, orig in PAIRS.items():
    rows = [r for r in ev if r["split"] == fail and r["gold"]["is_corrupted"]]
    st = collections.Counter()
    for r in rows:
        key = r["sample_id"].split("/", 1)[1]
        pb, pr = FIG / fail / (key + ".png"), FIG / orig / (key + ".png")
        if key not in orig_ids[orig] or not pr.exists() or not pb.exists():
            st["нет пары"] += 1
        elif md5(pb) == md5(pr):
            st["картинки идентичны (порча не применилась)"] += 1
        elif len((r.get("text_block") or "").split()) < 40:
            st["текст короче 40 слов"] += 1
        elif len((r.get("caption") or "").split()) < 5:
            st["caption короче 5 слов"] += 1
        elif not r["gold"]["lies"]:
            st["нет метки порчи"] += 1
        else:
            st["ГОДНЫХ ЧЕТВЁРОК"] += 1
    print("\n  %s -> %s : помечено испорченными %d" % (fail, orig, len(rows)))
    for k, v in sorted(st.items(), key=lambda x: -x[1]):
        print("     %-46s %4d" % (k, v))

print("\n  bt_l2_fail : оригиналов нет вообще, четвёрку собрать нельзя")

print("\n" + "=" * 78)
print("ПРОЧЕЕ")
for name, path in [("hints_ml_l2_fail.json", ROOT / "hints_ml_l2_fail.json"),
                   ("data.zip", ROOT / "data.zip"),
                   ("main_2.pdf (черновик статьи)", ROOT / "main_2.pdf"),
                   ("bench_v0/pool.jsonl", ROOT / "bench_v0" / "pool.jsonl"),
                   ("bench_v0/samples_200.jsonl", ROOT / "bench_v0" / "samples_200.jsonl")]:
    print("  %-32s %s" % (name, "%.1f KB" % (path.stat().st_size / 1024) if path.exists() else "НЕТ"))
