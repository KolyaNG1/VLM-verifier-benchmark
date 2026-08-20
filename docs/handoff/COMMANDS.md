# Команды

Все команды из корня репозитория, в PowerShell или cmd.

## Разовая настройка

```powershell
py -3.11 -m venv .venv          # подойдёт и 3.13
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
Copy-Item src\.env.example src\.env
```

В `src/.env` вписать ключ:

```text
OPENROUTER_API_KEY=ваш_ключ
```

Ключ под `.gitignore`, в репозиторий не попадает.

### Данные

Нужен `data/data/verifier_v0/...`. Если набор лежит в другом месте, проще всего
сделать junction, а не копировать 5800 картинок:

```cmd
mklink /J data\data D:\путь\к\каталогу\data
```

Проверка: `python -m vlm_bench validate-dataset` → «Корректных пар: 243».

Для прогонов по `bench/` сам `verifier_v0` тоже нужен: раннер читает картинки из
`data/`, а `bench/` служит источником списка пар и метаданных.

### Откуда взять набор четвёрок

В репозитории его нет — 201 пара картинок весит 35 МБ, в git такое не кладём.
Два способа получить каталог `bench/`:

**1. Архив от коллеги.** Распакуйте `bench_201.zip` в корень репозитория:

```powershell
Expand-Archive -LiteralPath bench_201.zip -DestinationPath . -Force
```

**2. Собрать самому из `verifier_v0`.** Если набор данных подключён (см. ниже
про `data/`), достаточно двух команд:

```powershell
python toolsuild_folders.py
python toolserify_folders.py
```

Пересоберутся те же 223 четвёрки из манифеста. Учтите: 22 папки были убраны
вручную при отсмотре, их номера лежат в `bench/removed.txt` внутри архива. Без
архива отсев придётся повторить или работать со всеми 223.

## Проверки без сети

```powershell
python -m vlm_bench validate-dataset
python -m vlm_bench render-prompt --id document_1/figure_2
python -m vlm_bench run --dry-run --limit 1
python -m unittest discover -s tests      # 14 тестов
```

## Прогоны

Основная команда. `--pair-workers` — добавленный флаг параллельности по парам,
без него сотня считается 40 минут вместо 5.

```powershell
python tools\watch_run.py --ids-file bench_100.txt --model google/gemini-3.7-flash --prompt prompts/vlm_judge/v003_strict.md --pair-workers 6 --max-cost-usd 3 --name "v003 сотня"
```

`watch_run.py` печатает строку на каждую готовую пару: номер папки, тип порчи,
`F` эталона, `F` испорченной, вердикт, секунды от старта. Внизу — итог.

Без просмотрщика, напрямую:

```powershell
python -m vlm_bench run --ids-file bench_all.txt --model google/gemini-3.7-flash --prompt prompts/vlm_judge/v003_strict.md --pair-workers 6 --max-cost-usd 5 --name "финал 201"
```

Одна пара:

```powershell
python -m vlm_bench run --id document_1/figure_2 --model google/gemini-3.7-flash --prompt prompts/vlm_judge/v003_strict.md --max-cost-usd 1
```

Продолжить прерванный запуск:

```powershell
python -m vlm_bench resume runs\<имя_запуска>
```

### Выборки

| Файл | Пар | Для чего |
|---|---|---|
| `bench_all.txt` | 201 | финальный прогон |
| `bench_100.txt` | 100 | рабочая выборка, интервал ±10 пунктов |
| `bench_24.txt` | 24 | набор A, быстрая проба |
| `bench_24b.txt` | 24 | набор B, не пересекается с A |

Все сбалансированы по типу порчи.

## Статистика

```powershell
python tools\stat.py runs\<запуск>                  # детекция, разбивка по типам
python tools\cmp.py                                 # сравнение двух прогонов
python tools\axis_check.py                          # корреляция осей
python tools\badrefs.py                             # пары с битым эталоном
python tools\missed.py                              # формулировки разметки: что ловится, что нет
```

## HTML-отчёт

```powershell
python tools\gen_report.py --run runs\<запуск> --out report.html
```

Самодостаточный файл с вшитыми картинками: плашки со счётом, таблица по типам
порчи, карточки пар (эталон и испорченная рядом, оценки, счётчики `P/U/M`,
обоснование модели), фильтры по вердикту. Интернет и сервер не нужны.

Встроенный просмотрщик репозитория: `python -m vlm_bench viewer`, затем
<http://127.0.0.1:8080>.

## Работа с датасетом

```powershell
python tools\build_folders.py     # пересобрать bench/ из verifier_v0
python tools\verify_folders.py    # проверить целостность 201 папки
python tools\inventory.py         # что где лежит в verifier_v0
python tools\structure.py         # разметка против реальных различий картинок
python tools\diff_check.py        # насколько сильно различаются пары
python tools\review.py            # просмотрщик для ручного отсева
```

`review.py`: стрелка вправо — оставить, вниз — убрать папку (переезжает в
`bench_trash/`, не удаляется), влево — назад, вверх — переключить
эталон/испорченную, Esc — выход. Флаг `--hard` удаляет насовсем,
`--start 075` начинает с нужного номера.

## Что менялось в коде репозитория

Три файла, ветка `zhenya`:

- `config.py` — поле `pair_workers`;
- `runner.py` — пары считаются пулом потоков; общие файлы (`index.jsonl`,
  `run.json`, `pair.json`) пишутся под замком, артефакты сторон лежат в отдельных
  каталогах и в защите не нуждаются;
- `cli.py` — флаг `--pair-workers`.

Все 14 тестов проходят.
