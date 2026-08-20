# -*- coding: utf-8 -*-
"""
Раскладывает 223 четвёрки по пронумерованным папкам в bench/.

Каждая папка bench/NNN/ содержит:
    reference.png   — эталон из figures/ml_orig
    corrupted.png   — испорченная из figures/ml_l2_fail
    caption.txt     — caption из manifest_ml_l2_fail.jsonl
    text_block.txt  — блок текста оттуда же
    meta.json       — sample_id, статья, тип порчи, проверочные md5

Источник caption и текста — manifest_ml_l2_fail.jsonl.
"""
import json, os, shutil, sys, io, hashlib, collections, re
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path(__file__).resolve().parent
V0 = ROOT / "data" / "verifier_v0"
FIG = V0 / "figures"
ORIG_DIR = FIG / "ml_orig"
FAIL_DIR = FIG / "ml_l2_fail"
OUT = ROOT / "bench"

MIN_TEXT_WORDS = 40
MIN_CAPTION_WORDS = 5


def md5(p):
    return hashlib.md5(Path(p).read_bytes()).hexdigest()


def load(name):
    return [json.loads(l) for l in (V0 / name).open(encoding="utf-8") if l.strip()]


# нормализация меток порчи (та же, что в build_bench.py)
ACTIONS = [
    ("delete",    r"удал|убран|убрал|уберн"),
    ("add",       r"добавл|дублир|продублир|дубликат"),
    ("permute",   r"перемеш|пермеш|переш|мест[ao]ми|помен[яе]ны мест|помещены мест|поряд[оa]к|положжени|перемещ|переставл"),
    ("rewire",    r"(стрел|связ).*(измен|направл|инвертир|новы)|(измен|инвертир|добавл).*(стрел|связ)"),
    ("geom",      r"отзеркал|отзерка|зеркал|перевернут|поверн|инвертир"),
    ("restyle",   r"цвет|палитр|стилистик|качеств"),
    ("replace",   r"полност|заменен|заменены|подменен|искаж|идентичны|изменен рисунок|изменен график|график изменен|изменен вид график|изменено изображени|изменены изображени|изменен правый рисунок"),
    ("edit_value", r"числен|числов|значени|диапазон|единиц|нумерац|формул|индекс"),
    ("edit_text", r"подпис|полпис|надпис|текст|назван|обознач|легенд|содерж|метрик|описан"),
    ("edit_value2", r"вспомогательная шкала"),
    ("edit_generic", r"измен|исправл|загружен пуст"),
]
TARGETS = [
    ("block", r"блок|схем|диаграмм"),
    ("arrow", r"стрел|связ"),
    ("axis",  r"шкал|ось |оси |осям|абсцисс|ординат|нумерац"),
    ("plot",  r"график|гистограмм|столб|кривая|s-cruve|маркер|точк|метрик"),
    ("image", r"изображени|рисун|картинк|фото"),
    ("label", r"подпис|полпис|надпис|легенд|обознач|назван"),
]


def norm(lies):
    acts, tgts = set(), set()
    for raw in lies:
        s = raw.strip().lower().replace("ё", "е")
        a = [n for n, p in ACTIONS if re.search(p, s)]
        a = ["edit_value" if x == "edit_value2" else x for x in a]
        if len(a) > 1:
            strong = [x for x in a if x != "edit_generic"] or a
            a = [x for x in strong if x not in ("edit_text", "edit_value")] or strong
        acts.update(a)
        tgts.update(n for n, p in TARGETS if re.search(p, s))
    return sorted(acts), sorted(tgts)


def main():
    rows = load("manifest_ml_l2_fail.jsonl")
    print("прочитано строк из manifest_ml_l2_fail.jsonl: %d" % len(rows))

    picked, drops = [], collections.Counter()
    for r in rows:
        g = r.get("gold") or {}
        if not g.get("is_corrupted"):
            drops["не помечена испорченной"] += 1; continue
        key = r["sample_id"].split("/", 1)[1]
        ref, bad = ORIG_DIR / (key + ".png"), FAIL_DIR / (key + ".png")
        if not ref.exists() or not bad.exists():
            drops["нет файла картинки"] += 1; continue
        if md5(ref) == md5(bad):
            drops["картинки идентичны"] += 1; continue
        cap = (r.get("caption") or "").strip()
        txt = (r.get("text_block") or "").strip()
        if len(txt.split()) < MIN_TEXT_WORDS:
            drops["текст короче %d слов" % MIN_TEXT_WORDS] += 1; continue
        if len(cap.split()) < MIN_CAPTION_WORDS:
            drops["caption короче %d слов" % MIN_CAPTION_WORDS] += 1; continue
        if not g.get("lies"):
            drops["нет метки порчи"] += 1; continue
        picked.append((key, r, cap, txt))

    print("\nотсев:")
    for k, v in drops.most_common():
        print("   %-30s %d" % (k, v))
    print("\nотобрано четвёрок: %d" % len(picked))

    picked.sort(key=lambda x: (int(x[0].split("/")[0].split("_")[1]),
                               int(x[0].split("/")[1].split("_")[1])))

    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    index = []
    for i, (key, r, cap, txt) in enumerate(picked, 1):
        d = OUT / ("%03d" % i)
        d.mkdir()
        ref, bad = ORIG_DIR / (key + ".png"), FAIL_DIR / (key + ".png")
        shutil.copy2(ref, d / "reference.png")
        shutil.copy2(bad, d / "corrupted.png")
        (d / "caption.txt").write_text(cap, encoding="utf-8", newline="\n")
        (d / "text_block.txt").write_text(txt, encoding="utf-8", newline="\n")
        acts, tgts = norm(r["gold"]["lies"])
        meta = {
            "id": "%03d" % i,
            "sample_id": r["sample_id"],
            "figure_key": key,
            "paper": {"pdf_id": r["pdf_id"], "arxiv_id": r.get("arxiv_id"),
                      "title": r.get("title"), "page": r.get("page"),
                      "figure_id": r.get("figure_id")},
            "text_block_source": r.get("text_block_source"),
            "text_block_words": len(txt.split()),
            "caption_words": len(cap.split()),
            "error_actions": acts,
            "error_targets": tgts,
            "error_raw": r["gold"]["lies"],
            "source_reference": str(ref.relative_to(ROOT)).replace("\\", "/"),
            "source_corrupted": str(bad.relative_to(ROOT)).replace("\\", "/"),
            "md5_reference": md5(ref),
            "md5_corrupted": md5(bad),
        }
        (d / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2),
                                     encoding="utf-8", newline="\n")
        index.append(meta)

    (OUT / "index.jsonl").write_text(
        "".join(json.dumps(m, ensure_ascii=False) + "\n" for m in index),
        encoding="utf-8", newline="\n")

    print("создано папок: %d -> %s" % (len(index), OUT))
    print("\nраспределение действий:",
          dict(collections.Counter(a for m in index for a in m["error_actions"]).most_common()))
    print("распределение объектов:",
          dict(collections.Counter(t for m in index for t in m["error_targets"]).most_common()))
    return index


if __name__ == "__main__":
    main()
