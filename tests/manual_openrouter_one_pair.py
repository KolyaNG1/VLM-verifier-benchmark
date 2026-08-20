"""Ручной реальный тест одной пары VLM.

Этот файл намеренно не запускается unit-тестами. Запрос отправляется только при
явном флаге --live и требует OPENROUTER_API_KEY в src/.env.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vlm_bench.cli import main  # noqa: E402


if __name__ == "__main__":
    if "--live" not in sys.argv:
        raise SystemExit("Это реальный запрос. Для запуска явно добавьте флаг --live.")
    raise SystemExit(
        main(
            [
                "run",
                "--id",
                "document_1/figure_2",
                "--max-cost-usd",
                "1.0",
            ]
        )
    )
