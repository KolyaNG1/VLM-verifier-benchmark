# -*- coding: utf-8 -*-
"""Отчёт по тем сэмплам, что уже посчитаны и лежат в кэше. В сеть не ходит."""
import json, sys, io
from pathlib import Path

from or_client import ORClient
import count_entities as ce   # он уже переназначил sys.stdout на utf-8, второй раз нельзя

ROOT = Path(__file__).resolve().parent
BENCH = ROOT / "bench"

cl = ORClient(model="z-ai/glm-4.6v")
rows = []
for d in sorted(x for x in BENCH.iterdir() if x.is_dir()):
    meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
    cap = (d / "caption.txt").read_text(encoding="utf-8").strip()
    txt = (d / "text_block.txt").read_text(encoding="utf-8").strip()
    parts = [ce.__dict__["USER"].format(caption=cap[:1200], text=txt[:4000])]
    from or_client import text_part, image_part
    messages = [
        {"role": "system", "content": ce.SYSTEM},
        {"role": "user", "content": [text_part(parts[0]),
                                     image_part(d / "reference.png", max_side=1024)]},
    ]
    out = cl.chat(messages, schema=ce.SCHEMA, max_tokens=4000, cache_only=True)
    if out is None or out.get("parsed") is None:
        continue
    p = out["parsed"]
    rows.append({
        "id": meta["id"],
        "n_visual": len(p.get("visual_entities") or []),
        "n_text": len(p.get("text_entities") or []),
        "visual": p.get("visual_entities") or [],
        "kind": p.get("figure_kind"),
        "note": p.get("note", ""),
        "err": meta["error_actions"],
        "title": (meta["paper"].get("title") or "")[:60],
    })

print("посчитано и лежит в кэше: %d из 223\n" % len(rows))
sus = sorted([r for r in rows if r["n_visual"] < 3 or r["n_text"] < 3],
             key=lambda r: (r["n_visual"], r["n_text"]))
print("ПОДОЗРИТЕЛЬНЫЕ (меньше 3 сущностей): %d\n" % len(sus))
for r in sus:
    print("bench/%s  vis=%d  text=%d  порча=%s" % (r["id"], r["n_visual"], r["n_text"],
                                                   ",".join(r["err"])))
    for v in r["visual"]:
        print("      - %s" % v[:100])
    print("      статья: %s" % r["title"])
    print()

import collections
print("распределение visual_entities по посчитанным:")
c = collections.Counter(min(r["n_visual"], 10) for r in rows)
for k in sorted(c):
    print("   %s%-3s %s" % ("10+" if k == 10 else " ", k if k < 10 else "", "#" * c[k]), c[k])

out = ROOT / "cached_report.jsonl"
out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
               encoding="utf-8", newline="\n")
print("\nсырые данные: %s" % out)
