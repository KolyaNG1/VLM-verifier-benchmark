# -*- coding: utf-8 -*-
"""Независимая проверка bench/: картинки из нужных каталогов, тексты на месте."""
import json, sys, io, hashlib
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path(__file__).resolve().parent
OUT = ROOT / "bench"
ORIG_DIR = ROOT / "data/verifier_v0/figures/ml_orig"
FAIL_DIR = ROOT / "data/verifier_v0/figures/ml_l2_fail"


def md5(p):
    return hashlib.md5(Path(p).read_bytes()).hexdigest()


dirs = sorted(d for d in OUT.iterdir() if d.is_dir())
print("папок в bench/: %d" % len(dirs))

errors = []
for d in dirs:
    try:
        m = json.loads((d / "meta.json").read_text(encoding="utf-8"))
    except Exception as e:
        errors.append("%s: meta.json не читается (%s)" % (d.name, e)); continue

    key = m["figure_key"]
    src_ref, src_bad = ORIG_DIR / (key + ".png"), FAIL_DIR / (key + ".png")
    f_ref, f_bad = d / "reference.png", d / "corrupted.png"

    for f in (f_ref, f_bad, d / "caption.txt", d / "text_block.txt"):
        if not f.exists():
            errors.append("%s: нет файла %s" % (d.name, f.name))
    if not (f_ref.exists() and f_bad.exists()):
        continue

    h_ref, h_bad = md5(f_ref), md5(f_bad)
    if h_ref != md5(src_ref):
        errors.append("%s: reference.png НЕ совпадает с ml_orig/%s" % (d.name, key))
    if h_bad != md5(src_bad):
        errors.append("%s: corrupted.png НЕ совпадает с ml_l2_fail/%s" % (d.name, key))
    if h_ref == h_bad:
        errors.append("%s: две картинки идентичны" % d.name)
    if h_ref != m["md5_reference"] or h_bad != m["md5_corrupted"]:
        errors.append("%s: md5 в meta.json не сходится" % d.name)

    cap = (d / "caption.txt").read_text(encoding="utf-8").strip()
    txt = (d / "text_block.txt").read_text(encoding="utf-8").strip()
    if len(cap.split()) < 5:
        errors.append("%s: caption слишком короткий" % d.name)
    if len(txt.split()) < 40:
        errors.append("%s: text_block слишком короткий" % d.name)
    if not m["error_actions"]:
        errors.append("%s: пустой error_actions" % d.name)

names = [d.name for d in dirs]
expected = ["%03d" % i for i in range(1, len(dirs) + 1)]
if names != expected:
    errors.append("нумерация папок не сплошная 001..%03d" % len(dirs))

idx = [json.loads(l) for l in (OUT / "index.jsonl").open(encoding="utf-8") if l.strip()]
if len(idx) != len(dirs):
    errors.append("index.jsonl: %d строк против %d папок" % (len(idx), len(dirs)))
if len({m["sample_id"] for m in idx}) != len(idx):
    errors.append("index.jsonl: есть дубликаты sample_id")

print("проверено пар: %d" % len(dirs))
if errors:
    print("\nОШИБКИ (%d):" % len(errors))
    for e in errors[:40]:
        print("   " + e)
else:
    print("\nОШИБОК НЕТ: все картинки взяты из нужных каталогов, различаются,")
    print("тексты и метки на месте, нумерация сплошная 001..%03d" % len(dirs))
