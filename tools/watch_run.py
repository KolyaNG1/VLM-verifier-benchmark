# -*- coding: utf-8 -*-
"""Запускает vlm_bench run и печатает строку на каждую готовую пару."""
import json, os, subprocess, sys, time, io
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)

def _repo_root():
    """Корень репозитория: поднимаемся, пока не увидим pyproject.toml."""
    p = Path(__file__).resolve()
    for cand in [p.parent] + list(p.parents):
        if (cand / "pyproject.toml").is_file():
            return cand
    return p.parent


def _bench_dir():
    """bench/ рядом с репозиторием; запасной путь — старое расположение."""
    here = _repo_root() / "bench"
    if here.is_dir():
        return here
    alt = Path(r"D:\llm-judgeench")
    return alt if alt.is_dir() else here
REPO = _repo_root()
BENCH = _bench_dir()

meta = {}
for d in sorted(os.listdir(BENCH)):
    p = BENCH / d / "meta.json"
    if p.is_file():
        m = json.loads(p.read_text(encoding="utf-8"))
        meta[m["figure_key"]] = m

args = [str(REPO / ".venv/Scripts/python.exe"), "-m", "vlm_bench", "run"] + sys.argv[1:]
before = {d.name for d in (REPO / "runs").iterdir() if d.is_dir()}
proc = subprocess.Popen(args, cwd=REPO, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)

run_dir = None
t0 = time.time()
while run_dir is None and proc.poll() is None:
    new = {d.name for d in (REPO / "runs").iterdir() if d.is_dir()} - before
    if new:
        run_dir = REPO / "runs" / sorted(new)[-1]
    time.sleep(0.5)
if run_dir is None:
    print("не удалось определить каталог запуска"); sys.exit(1)
print("запуск: %s\n" % run_dir.name)
print("%-4s %-5s %-14s %-9s %-9s %-6s %s" % ("#", "папка", "порча", "F эталон", "F испорч", "вердикт", "сек"))

seen, cost = set(), 0.0
w = t = l = e = 0
while True:
    sdir = run_dir / "samples"
    if sdir.is_dir():
        for s in sorted(os.listdir(sdir)):
            if s in seen:
                continue
            fs = {x: (sdir / s / x / "result.json") for x in ("orig", "fail")}
            if not all(f.is_file() for f in fs.values()):
                continue
            seen.add(s)
            key = s.replace("__", "/")
            m = meta.get(key, {})
            r = {}
            broken = False
            for x in fs:
                # Файл пишется атомарно через os.replace: в момент подмены Windows
                # не даёт его открыть, а дочитать можно пустой хвост. Просто ждём.
                for _ in range(10):
                    try:
                        r[x] = json.loads(fs[x].read_text(encoding="utf-8"))
                        break
                    except (PermissionError, OSError, json.JSONDecodeError):
                        time.sleep(0.2)
                else:
                    broken = True
            if broken:
                seen.discard(s)          # вернём пару в очередь, покажем на следующем круге
                continue
            cost += sum((r[x].get("cost_usd") or 0) for x in r)
            if any(r[x].get("computed") is None for x in r):
                e += 1
                print("%-4d %-5s %-14s %-9s %-9s %-6s %.0f" % (
                    len(seen), m.get("id", "?"), ",".join(m.get("error_actions", []))[:14],
                    "-", "-", "СБОЙ", time.time() - t0))
                continue
            fo = r["orig"]["computed"]["scores"]["faithfulness"]
            ff = r["fail"]["computed"]["scores"]["faithfulness"]
            v = "ЛОВИТ" if fo > ff else ("=" if fo == ff else "ИНВЕРС")
            w += fo > ff; t += fo == ff; l += fo < ff
            print("%-4d %-5s %-14s %-9d %-9d %-6s %.0f" % (
                len(seen), m.get("id", "?"), ",".join(m.get("error_actions", []))[:14],
                fo, ff, v, time.time() - t0))
    if proc.poll() is not None and not (sdir.is_dir() and
            any(s not in seen and all((sdir / s / x / "result.json").is_file()
                for x in ("orig", "fail")) for s in os.listdir(sdir))):
        break
    time.sleep(1.0)

print("\nготово за %.1f мин | ловит %d | не ловит %d | инверсия %d | сбоев %d | $%.4f"
      % ((time.time() - t0) / 60, w, t, l, e, cost))
print("каталог: %s" % run_dir)
