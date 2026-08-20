# -*- coding: utf-8 -*-
"""
Считает визуальные сущности на эталонных картинках бенча и сущности,
выписываемые из блока текста. Нужно, чтобы найти сэмплы с менее чем 3 сущностями.

    python count_entities.py --limit 3          # проба
    python count_entities.py                    # все 223
"""
import argparse, json, sys, io, threading, traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
from or_client import ORClient

ROOT = Path(__file__).resolve().parent
BENCH = ROOT / "bench"

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["figure_kind", "visual_entities", "text_entities", "note"],
    "properties": {
        "figure_kind": {
            "type": "string",
            "enum": ["flowchart", "plot", "image_grid", "single_photo",
                     "table", "equation", "mixed", "other"],
        },
        "visual_entities": {
            "type": "array",
            "description": "Самостоятельные смысловые элементы картинки",
            "items": {"type": "string"},
        },
        "text_entities": {
            "type": "array",
            "description": "Сущности из блока текста, которые обязаны быть на картинке",
            "items": {"type": "string"},
        },
        "note": {"type": "string"},
    },
}

SYSTEM = (
    "Ты аккуратный аналитик научных иллюстраций. "
    "Отвечай строго по JSON-схеме, без пояснений вне JSON."
)

USER = """Перед тобой эталонная иллюстрация из научной статьи.

Caption:
{caption}

Блок текста, к которому привязана иллюстрация:
{text}

Сделай два независимых списка.

1. visual_entities — самостоятельные смысловые элементы, которые видно на картинке:
   блоки схемы, стрелки и связи, отдельные панели, кривые на графике, оси с подписями,
   легенда, модули, подписанные объекты. НЕ считай сущностями декоративные детали,
   рамки, фон и отдельные буквы. Если картинка — одна фотография без внутренней
   структуры, список должен быть коротким, не выдумывай элементы.

2. text_entities — то, что упомянуто в блоке текста и обязано быть изображено.
   Выписывай только то, что действительно следует из текста.

В note одним предложением скажи, выглядит ли картинка содержательной или она слишком
простая для оценки достоверности."""

lock = threading.Lock()


def run_one(cl, d):
    meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
    cap = (d / "caption.txt").read_text(encoding="utf-8").strip()
    txt = (d / "text_block.txt").read_text(encoding="utf-8").strip()
    out = cl.ask(
        system=SYSTEM,
        user_text=USER.format(caption=cap[:1200], text=txt[:4000]),
        images=[d / "reference.png"],
        schema=SCHEMA,
        max_tokens=4000,
    )
    p = out["parsed"]
    rec = {
        "id": meta["id"],
        "sample_id": meta["sample_id"],
        "error_actions": meta["error_actions"],
        "text_block_source": meta["text_block_source"],
        "ok": p is not None,
        "finish_reason": out.get("finish_reason"),
    }
    if p:
        rec.update({
            "figure_kind": p.get("figure_kind"),
            "n_visual": len(p.get("visual_entities") or []),
            "n_text": len(p.get("text_entities") or []),
            "visual_entities": p.get("visual_entities") or [],
            "text_entities": p.get("text_entities") or [],
            "note": p.get("note", ""),
        })
    else:
        rec["raw"] = (out.get("content") or "")[:300]
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="z-ai/glm-4.6v")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--out", default="bench_entities.jsonl")
    args = ap.parse_args()

    dirs = sorted(d for d in BENCH.iterdir() if d.is_dir())
    if args.limit:
        dirs = dirs[: args.limit]
    print("картинок к разбору: %d, модель %s" % (len(dirs), args.model))

    cl = ORClient(model=args.model)
    results, fails = [], []

    def task(d):
        try:
            return run_one(cl, d)
        except Exception as e:
            return {"id": d.name, "ok": False, "error": "%s: %s" % (type(e).__name__, e)}

    done = 0
    if args.workers <= 1:
        for d in dirs:                      # строго по одному запросу за раз
            rec = task(d)
            done += 1
            (fails if not rec.get("ok") else results).append(rec)
            if rec.get("ok"):
                print("  %s/%d  %-4s vis=%-3d text=%-3d %-12s %s"
                      % (str(done).rjust(3), len(dirs), rec["id"], rec["n_visual"],
                         rec["n_text"], rec["figure_kind"], rec["note"][:70]))
            else:
                print("  %s/%d  %-4s СБОЙ: %s"
                      % (str(done).rjust(3), len(dirs), rec.get("id"),
                         str(rec.get("error") or rec.get("raw", ""))[:90]))
    else:
        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            for rec in ex.map(task, dirs):
                done += 1
                with lock:
                    (fails if not rec.get("ok") else results).append(rec)
                    if done % 25 == 0:
                        print("   ...%d/%d" % (done, len(dirs)))

    results.sort(key=lambda r: r["id"])
    outp = ROOT / args.out
    with outp.open("w", encoding="utf-8", newline="\n") as f:
        for r in results + fails:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print("\nразобрано: %d, сбоев: %d -> %s" % (len(results), len(fails), outp))
    if fails:
        for r in fails[:10]:
            print("   сбой %s: %s" % (r.get("id"), r.get("error") or r.get("raw", ""))[:160])
    print(cl.report())

    low_v = [r for r in results if r["n_visual"] < 3]
    low_t = [r for r in results if r["n_text"] < 3]
    print("\nменее 3 визуальных сущностей: %d" % len(low_v))
    print("менее 3 текстовых сущностей:  %d" % len(low_t))


if __name__ == "__main__":
    main()
