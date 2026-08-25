# Утилита разметки изображений

Это самостоятельная программа для создания и ручной проверки английских
описаний PNG из соседней папки `nikolay_ai_360_student`.

## Быстрый старт

1. Положите папку `nikolay_ai_360_annotation` рядом с
   `nikolay_ai_360_student`.
2. Откройте `nikolay_ai_360_annotation/.env` и добавьте ключ OpenRouter после
   `OPENROUTER_API_KEY=`. Если `.env` отсутствует, скопируйте `.env.example` в
   `.env`.
3. Из родительской папки запустите проверку:

   ```powershell
   python nikolay_ai_360_annotation/run.py validate
   ```

4. Запустите первые пять изображений:

   ```powershell
   python nikolay_ai_360_annotation/run.py run --limit 5 --workers 2 --max-pending-review 4
   ```

Браузер откроется сам. Ответ модели сохраняется около картинки, а окончательное
описание появляется там же только после одобрения.

Подробная инструкция: [docs/USER_GUIDE.md](docs/USER_GUIDE.md). Устройство и
перенос на другой компьютер: [docs/STORAGE_AND_PORTABILITY.md](docs/STORAGE_AND_PORTABILITY.md).
