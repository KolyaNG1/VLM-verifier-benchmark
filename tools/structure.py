# -*- coding: utf-8 -*-
"""Проверка структуры ML-сплита: что помечено испорченным и что реально отличается."""
import json, sys, io, hashlib, collections
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path(__file__).resolve().parent
V0 = ROOT / "data" / "verifier_v0"
FIG = V0 / "figures"


def load(n):
    return [json.loads(l) for l in (V0 / n).open(encoding="utf-8") if l.strip()]


def md5(p):
    return hashlib.md5(p.read_bytes()).hexdigest()


fail = {r["sample_id"].split("/", 1)[1]: r for r in load("manifest_ml_l2_fail.jsonl")}
orig = {r["sample_id"].split("/", 1)[1]: r for r in load("manifest_ml_orig.jsonl")}
flagged = {r["sample_id"].split("/", 1)[1]
           for r in load("manifest_eval.jsonl")
           if r["split"] == "ml_l2_fail" and r["gold"]["is_corrupted"]}

print("строк в manifest_ml_l2_fail : %d" % len(fail))
print("строк в manifest_ml_orig    : %d" % len(orig))
print("помечено испорченными       : %d" % len(flagged))
print("ключей только в orig        : %d" % len(set(orig) - set(fail)))
print("ключей только в fail        : %d" % len(set(fail) - set(orig)))

st = collections.Counter()
for k in fail:
    pb, pr = FIG / "ml_l2_fail" / (k + ".png"), FIG / "ml_orig" / (k + ".png")
    if not pb.exists() or not pr.exists():
        st[("нет файла", k in flagged)] += 1
        continue
    st[("картинки РАЗНЫЕ" if md5(pb) != md5(pr) else "картинки ИДЕНТИЧНЫ", k in flagged)] += 1

print("\n%-22s %-16s %s" % ("", "помечена битой", "кол-во"))
for (what, fl), n in sorted(st.items(), key=lambda x: (-x[1])):
    print("%-22s %-16s %d" % (what, "да" if fl else "нет", n))

diff_unflagged = [k for k in fail
                  if (FIG / "ml_l2_fail" / (k + ".png")).exists()
                  and (FIG / "ml_orig" / (k + ".png")).exists()
                  and k not in flagged
                  and md5(FIG / "ml_l2_fail" / (k + ".png")) != md5(FIG / "ml_orig" / (k + ".png"))]
print("\nне помечены битыми, но картинки различаются: %d" % len(diff_unflagged))
for k in diff_unflagged[:10]:
    print("   ", k)
