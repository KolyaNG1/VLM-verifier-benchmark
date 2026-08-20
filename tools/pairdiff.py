# -*- coding: utf-8 -*-
import json, os, sys, io, glob, hashlib
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
S = None
for R in sorted(glob.glob("runs/*"), reverse=True):
    sd = os.path.join(R, "samples")
    if not os.path.isdir(sd):
        continue
    for name in sorted(os.listdir(sd)):
        if all(os.path.isfile(os.path.join(sd, name, x, "request.json")) for x in ("orig", "fail")):
            S = os.path.join(sd, name); break
    if S: break
print("прогон:", os.path.basename(R))
print("пара:", os.path.basename(S))
req = {}
for side in ("orig", "fail"):
    req[side] = json.load(open(os.path.join(S, side, "request.json"), encoding="utf-8"))
for side in ("orig", "fail"):
    print("\n=== %s ===" % side)
    print("  модель:", req[side]["model"])
    for m in req[side]["messages"]:
        c = m["content"]
        if isinstance(c, str):
            print("  %-6s текст %d симв | md5 %s" % (m["role"], len(c), hashlib.md5(c.encode()).hexdigest()[:8]))
        else:
            for p in c:
                if p.get("type") == "text":
                    t = p["text"]
                    print("  %-6s текст %-5d симв | md5 %s | %s" % (
                        m["role"], len(t), hashlib.md5(t.encode()).hexdigest()[:8],
                        t.strip()[:46].replace("\n", " ")))
                else:
                    u = p.get("image_url", {}).get("url", "")
                    print("  %-6s КАРТИНКА %-6d симв base64 | md5 %s" % (
                        m["role"], len(u), hashlib.md5(u.encode()).hexdigest()[:8]))
def parts(side):
    out = []
    for m in req[side]["messages"]:
        c = m["content"]
        if isinstance(c, str): out.append(("text", hashlib.md5(c.encode()).hexdigest()))
        else:
            for p in c:
                if p.get("type") == "text": out.append(("text", hashlib.md5(p["text"].encode()).hexdigest()))
                else: out.append(("image", hashlib.md5(p["image_url"]["url"].encode()).hexdigest()))
    return out
a, b = parts("orig"), parts("fail")
print("\n=== сравнение ===")
print("частей одинаково:", len(a) == len(b))
for i, (x, y) in enumerate(zip(a, b)):
    same = "СОВПАДАЕТ" if x[1] == y[1] else "РАЗЛИЧАЕТСЯ"
    print("  часть %d (%s): %s" % (i + 1, x[0], same))
