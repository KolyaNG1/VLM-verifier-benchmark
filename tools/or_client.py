# -*- coding: utf-8 -*-
"""
Тонкий клиент OpenRouter для VLM-судьи.

Ключ берётся из переменной окружения OPENROUTER_API_KEY или из файла .env
рядом с этим модулем. В коде ключ не хранится и никуда не логируется.

Что умеет:
  * картинки -> base64 data URL, с даунскейлом (иначе платим за лишние токены);
  * structured outputs через JSON-схему;
  * дисковый кэш ответов -> повторный прогон не стоит ничего;
  * ретраи с backoff на 429/5xx;
  * учёт токенов и денег по каждой модели.
"""
import base64, hashlib, io, json, os, random, time
from pathlib import Path

import httpx
from PIL import Image

ROOT = Path(__file__).resolve().parent
API_URL = "https://openrouter.ai/api/v1/chat/completions"

# цены OpenRouter, $ за 1M токенов (сверено 20.08.2026)
PRICES = {
    "qwen/qwen3.5-397b-a17b":       (0.3025, 1.925),
    "qwen/qwen3.7-flash":           (0.03,   0.13),
    "qwen/qwen3.8-27b":             (0.45,   3.20),
    "qwen/qwen3.8-max":             (2.00,   6.00),
    "google/gemini-3.7-flash":      (0.375,  1.875),
    "google/gemini-3.5-flash-lite": (0.30,   2.50),
    "z-ai/glm-5.3":                 (1.40,   4.40),
    "moonshotai/kimi-k3":           (3.00,  15.00),
    "openai/gpt-5.6-sol":           (2.50,  15.00),
    "anthropic/claude-opus-5":      (5.00,  25.00),
}

JUDGE_MAIN = "qwen/qwen3.5-397b-a17b"
JUDGE_CROSS = "google/gemini-3.7-flash"
JUDGE_CHEAP = "qwen/qwen3.7-flash"


# ---------------------------------------------------------------- ключ
def _load_dotenv():
    p = ROOT / ".env"
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        # частая беда: в файл скопировали команду целиком ("echo VAR=..." / "export VAR=...")
        for junk in ("echo ", "export ", "set ", "$env:"):
            if k.lower().startswith(junk):
                k = k[len(junk):].strip()
        os.environ.setdefault(k, v.strip().strip('"').strip("'"))


def get_api_key():
    _load_dotenv()
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "Нет ключа. Создай файл %s со строкой:\n"
            "OPENROUTER_API_KEY=sk-or-v1-...\n"
            "(или задай переменную окружения OPENROUTER_API_KEY)" % (ROOT / ".env")
        )
    return key


# ---------------------------------------------------------------- картинки
def image_part(path, max_side=1024, quality=85):
    """PNG со страницы статьи -> data URL. Даунскейл режет счёт за входные токены."""
    im = Image.open(path)
    if im.mode not in ("RGB", "L"):
        im = im.convert("RGB")
    w, h = im.size
    if max(w, h) > max_side:
        s = max_side / max(w, h)
        im = im.resize((max(1, int(w * s)), max(1, int(h * s))), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=quality)
    b64 = base64.b64encode(buf.getvalue()).decode()
    return {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + b64}}


def text_part(s):
    return {"type": "text", "text": s}


# ---------------------------------------------------------------- клиент
class ORClient:
    def __init__(self, model=JUDGE_MAIN, cache_dir=None, timeout=180.0,
                 max_retries=5, referer="https://github.com/ai4s-bench",
                 title="AI4S-Bench judge"):
        self.model = model
        self.cache_dir = Path(cache_dir or (ROOT / ".cache" / model.replace("/", "__")))
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.max_retries = max_retries
        self._key = get_api_key()
        self._http = httpx.Client(timeout=timeout)
        self._headers = {
            "Authorization": "Bearer " + self._key,
            "HTTP-Referer": referer,
            "X-Title": title,
            "Content-Type": "application/json",
        }
        self.usage = {"calls": 0, "cached": 0, "prompt_tokens": 0, "completion_tokens": 0}

    # -------- деньги
    def cost_usd(self):
        pin, pout = PRICES.get(self.model, (0.0, 0.0))
        return (self.usage["prompt_tokens"] * pin + self.usage["completion_tokens"] * pout) / 1e6

    def report(self):
        u = self.usage
        return ("%s | вызовов %d (из кэша %d) | in %d tok, out %d tok | $%.4f"
                % (self.model, u["calls"], u["cached"], u["prompt_tokens"],
                   u["completion_tokens"], self.cost_usd()))

    # -------- сам вызов
    def chat(self, messages, schema=None, temperature=0.0, max_tokens=2048,
             use_cache=True, extra=None, cache_only=False):
        body = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if schema is not None:
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "verdict", "strict": True, "schema": schema},
            }
        if extra:
            body.update(extra)

        ck = hashlib.sha256(
            json.dumps(body, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()
        cpath = self.cache_dir / (ck + ".json")
        if use_cache and cpath.exists():
            self.usage["cached"] += 1
            return json.loads(cpath.read_text(encoding="utf-8"))
        if cache_only:                      # только читаем готовое, в сеть не ходим
            return None

        last = None
        for attempt in range(self.max_retries):
            try:
                r = self._http.post(API_URL, headers=self._headers, json=body)
            except httpx.HTTPError as e:
                last = e
                time.sleep(min(2 ** attempt, 30) + random.random())
                continue
            if r.status_code == 200:
                data = r.json()
                if data.get("error"):          # OpenRouter иногда кладёт ошибку внутрь 200
                    last = RuntimeError(str(data["error"]))
                    time.sleep(min(2 ** attempt, 30) + random.random())
                    continue
                out = self._pack(data)
                self._account(out)
                if use_cache:
                    cpath.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
                return out
            if r.status_code in (408, 429, 500, 502, 503, 504):
                last = RuntimeError("HTTP %d: %s" % (r.status_code, r.text[:400]))
                wait = float(r.headers.get("retry-after") or 0) or min(2 ** attempt, 30)
                time.sleep(wait + random.random())
                continue
            raise RuntimeError("HTTP %d: %s" % (r.status_code, r.text[:800]))
        raise RuntimeError("не смогли достучаться после %d попыток: %s"
                           % (self.max_retries, last))

    def _pack(self, data):
        msg = data["choices"][0]["message"]
        content = msg.get("content") or ""
        parsed = None
        try:
            parsed = json.loads(content)
        except Exception:
            pass
        return {
            "content": content,
            "parsed": parsed,
            # ризонящие модели (qwen3.5-397b, glm) кладут ход мысли отдельно от content
            "reasoning": msg.get("reasoning") or "",
            "usage": data.get("usage") or {},
            "model": data.get("model"),
            "finish_reason": data["choices"][0].get("finish_reason"),
        }

    def _account(self, out):
        u = out.get("usage") or {}
        self.usage["calls"] += 1
        self.usage["prompt_tokens"] += int(u.get("prompt_tokens") or 0)
        self.usage["completion_tokens"] += int(u.get("completion_tokens") or 0)

    # -------- удобная обёртка под сэмпл бенча
    def ask(self, system, user_text, images=(), schema=None, max_side=1024, **kw):
        parts = [text_part(user_text)] + [image_part(p, max_side=max_side) for p in images]
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": parts})
        return self.chat(messages, schema=schema, **kw)


def credits():
    """Сколько денег осталось на ключе."""
    key = get_api_key()
    r = httpx.get("https://openrouter.ai/api/v1/credits",
                  headers={"Authorization": "Bearer " + key}, timeout=30.0)
    r.raise_for_status()
    return r.json().get("data", r.json())
