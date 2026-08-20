# -*- coding: utf-8 -*-
"""
Простой запрос к VLM: показать картинку и попросить описать её обычным текстом.
Без JSON-схемы — чистый ответ модели.

    python describe.py путь\к\картинке.png
    python describe.py картинка.png --model z-ai/glm-4.6v
    python describe.py --sample            # взять случайную фигуру из бенча
"""
import argparse, io, json, random, sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from or_client import ORClient

ROOT = Path(__file__).resolve().parent

PROMPT = (
    "Опиши подробно, что изображено на картинке. "
    "Перечисли все значимые элементы, надписи и связи между ними. "
    "Отвечай обычным текстом на русском языке."
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image", nargs="?", help="путь к картинке")
    ap.add_argument("--model", default="z-ai/glm-4.6v")
    ap.add_argument("--prompt", default=PROMPT)
    ap.add_argument("--max-tokens", type=int, default=4000)
    ap.add_argument("--max-side", type=int, default=1024)
    ap.add_argument("--sample", action="store_true", help="взять фигуру из bench_v0")
    ap.add_argument("--no-cache", action="store_true")
    args = ap.parse_args()

    if args.sample or not args.image:
        rows = [json.loads(l) for l in (ROOT / "bench_v0" / "samples_200.jsonl").open(encoding="utf-8")]
        s = random.Random(1).choice(rows)
        img = ROOT / s["image_reference"]
        print("сэмпл из бенча:", s["sample_id"])
    else:
        img = Path(args.image)
        if not img.is_absolute():
            img = (ROOT / img).resolve()
    if not img.exists():
        print("нет файла:", img)
        return 1

    print("картинка:", img)
    print("модель:  ", args.model)
    print("-" * 70)

    cl = ORClient(model=args.model)
    out = cl.ask(system=None, user_text=args.prompt, images=[img],
                 max_tokens=args.max_tokens, max_side=args.max_side,
                 use_cache=not args.no_cache)

    text = out["content"]
    if not text and out.get("reasoning"):
        print("[content пуст, модель отдала только reasoning]")
        text = out["reasoning"]
    print(text or "(пустой ответ)")
    print("-" * 70)
    print("finish_reason:", out.get("finish_reason"))
    u = out.get("usage") or {}
    print("токены: in %s, out %s (из них reasoning %s) | стоимость по данным OpenRouter: $%s"
          % (u.get("prompt_tokens"), u.get("completion_tokens"),
             (u.get("completion_tokens_details") or {}).get("reasoning_tokens"),
             u.get("cost")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
