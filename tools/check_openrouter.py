# -*- coding: utf-8 -*-
"""
Проверка связки с OpenRouter: ключ, баланс, текстовый вызов, картиночный вызов,
structured output. Гоняет на самой дешёвой модели, стоит доли цента.

    python check_openrouter.py
    python check_openrouter.py --model qwen/qwen3.5-397b-a17b
"""
import argparse, json, sys, io, random
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from or_client import ORClient, credits, get_api_key, JUDGE_CHEAP, PRICES

ROOT = Path(__file__).resolve().parent

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["figure_kind", "visible_elements", "score"],
    "properties": {
        "figure_kind": {"type": "string", "enum": ["flowchart", "plot", "image_grid", "other"]},
        "visible_elements": {"type": "array", "items": {"type": "string"}},
        "score": {"type": "integer", "enum": [1, 3, 5]},
    },
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=JUDGE_CHEAP)
    args = ap.parse_args()

    print("=" * 70)
    key = get_api_key()
    print("1) ключ найден: %s...%s (длина %d)" % (key[:8], key[-4:], len(key)))

    try:
        c = credits()
        print("2) баланс:", json.dumps(c, ensure_ascii=False))
    except Exception as e:
        print("2) баланс не прочитался:", e)

    cl = ORClient(model=args.model)
    print("3) модель:", cl.model, "| цена $%.4f/$%.4f за 1M" % PRICES.get(cl.model, (0, 0)))

    r = cl.chat([{"role": "user", "content": "Ответь одним словом: работает?"}],
                max_tokens=16, use_cache=False)
    print("   текстовый вызов ->", repr(r["content"][:80]))

    # берём реальную пару из бенча
    pool = ROOT / "bench_v0" / "samples_200.jsonl"
    if not pool.exists():
        print("!! нет %s — сначала запусти build_bench.py" % pool)
        return 1
    rows = [json.loads(l) for l in pool.open(encoding="utf-8")]
    s = random.Random(0).choice(rows)
    ref = ROOT / s["image_reference"]
    bad = ROOT / s["image_corrupted"]
    print("4) сэмпл:", s["sample_id"], "| порча:", s["error_actions"], s["error_targets"])

    out = cl.ask(
        system="Ты аккуратный аналитик научных иллюстраций. Отвечай строго по JSON-схеме.",
        user_text=(
            "Ниже две версии одной иллюстрации из статьи: сначала эталон, затем вторая версия.\n"
            "Caption: %s\n\n"
            "Определи тип рисунка, перечисли до 8 видимых элементов эталона и поставь score: "
            "5 — вторая версия совпадает с эталоном, 3 — есть заметное расхождение, "
            "1 — расхождение грубое." % s["caption"][:400]
        ),
        images=[ref, bad],
        schema=SCHEMA,
        max_tokens=800,
        use_cache=False,
    )
    print("   картинки + JSON-схема ->")
    print("   raw:", out["content"][:300])
    if out["parsed"] is None:
        print("   !! JSON не распарсился — модель не держит strict schema, нужен фолбэк")
    else:
        print("   parsed:", json.dumps(out["parsed"], ensure_ascii=False)[:400])

    print("5)", cl.report())
    print("=" * 70)
    print("готово")
    return 0


if __name__ == "__main__":
    sys.exit(main())
