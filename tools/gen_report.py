# -*- coding: utf-8 -*-
"""
Собирает самодостаточный HTML-отчёт по каталогу запуска vlm_bench.
Картинки вшиваются в файл, интернет и локальный сервер не нужны.

    python gen_report.py                       # последний запуск
    python gen_report.py --run <путь>          # конкретный
    python gen_report.py --out report.html
"""
import argparse, base64, io, json, os, sys, html, collections
from pathlib import Path
from PIL import Image

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

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

ROOT = _repo_root()
REPO = _repo_root()
BENCH = _bench_dir()


def b64(path, max_side=760, quality=80):
    im = Image.open(path)
    if im.mode not in ("RGB", "L"):
        im = im.convert("RGB")
    im.thumbnail((max_side, max_side), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=quality)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def load_meta():
    out = {}
    if BENCH.is_dir():
        for d in sorted(BENCH.iterdir()):
            p = d / "meta.json"
            if p.is_file():
                m = json.loads(p.read_text(encoding="utf-8"))
                out[m["figure_key"]] = m
    return out


def collect(run_dir):
    meta = load_meta()
    pairs = []
    sdir = run_dir / "samples"
    for s in sorted(os.listdir(sdir)):
        key = s.replace("__", "/")
        sides = {}
        for side in ("orig", "fail"):
            f = sdir / s / side / "result.json"
            if f.is_file():
                sides[side] = json.loads(f.read_text(encoding="utf-8"))
        if len(sides) < 2:
            continue
        m = meta.get(key, {})
        pairs.append({"key": key, "meta": m, "sides": sides})
    return pairs


def verdict(p):
    a, b = p["sides"]["orig"].get("computed"), p["sides"]["fail"].get("computed")
    if a is None or b is None:
        return "error"
    fo, ff = a["scores"]["faithfulness"], b["scores"]["faithfulness"]
    return "win" if fo > ff else ("tie" if fo == ff else "lose")


CSS = """
*{box-sizing:border-box} body{margin:0;font:14px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;
background:#12141a;color:#e6e8ee}
header{padding:22px 28px;border-bottom:1px solid #262a35;background:#161923;position:sticky;top:0;z-index:5}
h1{margin:0 0 6px;font-size:19px;font-weight:650}
.sub{color:#8b93a7;font-size:13px}
.kpis{display:flex;gap:10px;flex-wrap:wrap;margin-top:14px}
.kpi{background:#1c2030;border:1px solid #2a3040;border-radius:10px;padding:9px 14px;min-width:104px}
.kpi b{display:block;font-size:21px;line-height:1.2}
.kpi span{color:#8b93a7;font-size:11px;text-transform:uppercase;letter-spacing:.5px}
.win b{color:#4ade80}.tie b{color:#fbbf24}.lose b{color:#f87171}.err b{color:#a78bfa}
main{padding:20px 28px 60px;max-width:1500px;margin:0 auto}
.filters{display:flex;gap:8px;margin:4px 0 20px;flex-wrap:wrap}
.filters button{background:#1c2030;border:1px solid #2a3040;color:#c3c9d8;border-radius:8px;
padding:7px 14px;cursor:pointer;font-size:13px}
.filters button.on{background:#2b3550;border-color:#4b5b86;color:#fff}
table.sum{border-collapse:collapse;width:100%;margin-bottom:26px;font-size:13px}
table.sum th,table.sum td{border:1px solid #262a35;padding:7px 11px;text-align:left}
table.sum th{background:#1a1e29;color:#9aa3b8;font-weight:600}
.card{border:1px solid #262a35;border-radius:12px;margin-bottom:16px;overflow:hidden;background:#161923}
.card>.head{display:flex;align-items:center;gap:12px;padding:11px 16px;background:#1a1e29;flex-wrap:wrap}
.tag{font-size:11px;padding:3px 9px;border-radius:20px;font-weight:600;letter-spacing:.3px}
.t-win{background:#14532d;color:#86efac}.t-tie{background:#78350f;color:#fcd34d}
.t-lose{background:#7f1d1d;color:#fca5a5}.t-error{background:#4c1d95;color:#ddd6fe}
.err-type{background:#232941;color:#a5b4fc;font-size:11px;padding:3px 9px;border-radius:20px}
.title{color:#8b93a7;font-size:12px;flex:1;min-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:0}
.side{padding:14px 16px}
.side+.side{border-left:1px solid #262a35}
.side h3{margin:0 0 10px;font-size:12px;text-transform:uppercase;letter-spacing:1px;color:#8b93a7}
.side img{width:100%;height:auto;border-radius:8px;background:#fff;display:block}
.scores{display:flex;gap:6px;margin:12px 0 8px;flex-wrap:wrap}
.sc{background:#1c2030;border:1px solid #2a3040;border-radius:8px;padding:6px 10px;text-align:center;min-width:62px}
.sc b{display:block;font-size:17px}.sc span{font-size:10px;color:#8b93a7;text-transform:uppercase}
.sc.f b{color:#60a5fa}
.counts{font:12px ui-monospace,Consolas,monospace;color:#9aa3b8;margin-bottom:8px}
details{margin-top:8px}summary{cursor:pointer;color:#7dd3fc;font-size:12px}
details p{color:#b6bdcd;font-size:12.5px;margin:7px 0 0}
.cap{color:#79839a;font-size:12px;padding:10px 16px;border-top:1px solid #262a35}
@media(max-width:900px){.grid{grid-template-columns:1fr}.side+.side{border-left:0;border-top:1px solid #262a35}}
"""

JS = """
document.querySelectorAll('.filters button').forEach(b=>b.onclick=()=>{
  document.querySelectorAll('.filters button').forEach(x=>x.classList.remove('on'));
  b.classList.add('on');
  const f=b.dataset.f;
  document.querySelectorAll('.card').forEach(c=>{
    c.style.display=(f==='all'||c.dataset.v===f)?'':'none';
  });
});
"""


def side_html(res, img_src, label):
    c = res.get("computed")
    mo = res.get("model_output") or {}
    audit = mo.get("audit") or {}
    parts = ['<div class="side"><h3>%s</h3><img src="%s" alt="">' % (label, img_src)]
    if c:
        s = c["scores"]
        parts.append('<div class="scores">')
        for k, lab, cls in (("faithfulness", "faith", " f"), ("clarity", "clarity", ""),
                            ("compactness", "compact", ""), ("style", "style", ""),
                            ("overall", "overall", "")):
            parts.append('<div class="sc%s"><b>%s</b><span>%s</span></div>' % (cls, s.get(k), lab))
        parts.append("</div>")
        cnt = c["counts"]
        parts.append('<div class="counts">P=%d  U=%d  M=%d  coverage=%.2f</div>'
                     % (cnt["P"], cnt["U"], cnt["M"], c["coverage"]))
    else:
        parts.append('<div class="counts">статус: %s</div>' % html.escape(str(res.get("status"))))
    if audit.get("faithfulness"):
        parts.append("<details><summary>обоснование faithfulness</summary><p>%s</p></details>"
                     % html.escape(str(audit["faithfulness"])))
    parts.append("</div>")
    return "".join(parts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", help="каталог запуска; по умолчанию последний")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    runs_root = REPO / "runs"
    if args.run:
        run_dir = Path(args.run)
    else:
        cands = sorted((d for d in runs_root.iterdir() if d.is_dir()),
                       key=lambda d: d.stat().st_mtime)
        if not cands:
            print("нет запусков в %s" % runs_root); return 1
        run_dir = cands[-1]
    print("запуск: %s" % run_dir.name)

    cfg = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    model = (cfg.get("config") or {}).get("model", "?")
    pairs = collect(run_dir)
    if not pairs:
        print("в запуске пока нет готовых пар"); return 1

    vs = collections.Counter(verdict(p) for p in pairs)
    cost = sum((p["sides"][s].get("cost_usd") or 0) for p in pairs for s in p["sides"])

    by_type = collections.defaultdict(lambda: collections.Counter())
    for p in pairs:
        for a in (p["meta"].get("error_actions") or ["?"]):
            by_type[a][verdict(p)] += 1

    body = []
    body.append("<header><h1>Отчёт VLM-судьи · %s</h1>"
                "<div class='sub'>запуск %s · промпт %s · пар готово %d</div>"
                % (html.escape(model), html.escape(run_dir.name),
                   html.escape(str((cfg.get("prompt") or {}).get("name", "?"))), len(pairs)))
    body.append("<div class='kpis'>")
    for cls, key, lab in (("win", "win", "различил"), ("tie", "tie", "не различил"),
                          ("lose", "lose", "наоборот"), ("err", "error", "сбой разбора")):
        body.append("<div class='kpi %s'><b>%d</b><span>%s</span></div>" % (cls, vs[key], lab))
    body.append("<div class='kpi'><b>$%.3f</b><span>стоимость</span></div>" % cost)
    body.append("</div></header><main>")

    body.append("<div class='filters'>"
                "<button class='on' data-f='all'>все</button>"
                "<button data-f='win'>различил</button>"
                "<button data-f='tie'>не различил</button>"
                "<button data-f='lose'>наоборот</button>"
                "<button data-f='error'>сбои</button></div>")

    body.append("<table class='sum'><tr><th>тип порчи</th><th>различил</th>"
                "<th>не различил</th><th>наоборот</th><th>сбой</th></tr>")
    for t in sorted(by_type, key=lambda x: -sum(by_type[x].values())):
        c = by_type[t]
        body.append("<tr><td>%s</td><td>%d</td><td>%d</td><td>%d</td><td>%d</td></tr>"
                    % (html.escape(t), c["win"], c["tie"], c["lose"], c["error"]))
    body.append("</table>")

    for p in pairs:
        v = verdict(p)
        m = p["meta"]
        bid = m.get("id", "?")
        d = BENCH / bid
        ref = d / "reference.png"
        bad = d / "corrupted.png"
        if not ref.exists():
            continue
        lab = {"win": "различил", "tie": "не различил", "lose": "наоборот", "error": "сбой"}[v]
        body.append("<div class='card' data-v='%s'>" % v)
        body.append("<div class='head'><span class='tag t-%s'>%s</span>"
                    "<b>bench/%s</b><span class='err-type'>%s</span>"
                    "<span class='title'>%s</span>"
                    "<span class='title' style='flex:0;color:#5c6479'>%s</span></div>"
                    % (v, lab, bid, html.escape(",".join(m.get("error_actions", []))),
                       html.escape((m.get("paper") or {}).get("title") or ""),
                       html.escape(p["key"])))
        body.append("<div class='grid'>")
        body.append(side_html(p["sides"]["orig"], b64(ref), "эталон"))
        body.append(side_html(p["sides"]["fail"], b64(bad), "испорченная"))
        body.append("</div>")
        cap = (d / "caption.txt")
        if cap.exists():
            body.append("<div class='cap'>%s</div>"
                        % html.escape(cap.read_text(encoding="utf-8").strip()[:400]))
        body.append("</div>")

    body.append("</main>")

    out = Path(args.out) if args.out else ROOT / ("report_%s.html" % model.replace("/", "_"))
    page = ("<!doctype html><html lang='ru'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>Отчёт VLM-судьи — %s</title><style>%s</style></head><body>%s"
            "<script>%s</script></body></html>" % (html.escape(model), CSS, "".join(body), JS))
    out.write_text(page, encoding="utf-8")
    print("готово: %s (%.1f MB)" % (out, out.stat().st_size / 1e6))
    print("различил %d | не различил %d | наоборот %d | сбоев %d | $%.4f"
          % (vs["win"], vs["tie"], vs["lose"], vs["error"], cost))
    return 0


if __name__ == "__main__":
    sys.exit(main())
