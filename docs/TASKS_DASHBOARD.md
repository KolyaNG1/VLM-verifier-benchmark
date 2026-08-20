---
doc_type: task_dashboard
title: "Дашборд задач"
status: active
updated: 2026-08-20
---

# Дашборд задач

[← К оглавлению](index.md)

Дашборд автоматически собирается из служебных шапок файлов `*_descr.md`.
Не редактируйте блок между служебными метками вручную.

<!-- AUTO:TASK_DASHBOARD:START -->
## Все задачи

| Задача | Кратко | Статус | Обновлена |
|---|---|---|---|
| [TASK_000](tasks/TASK_000_documentation_system/000_descr.md) — Создание универсальной системы документации | Создать переносимую связанную документацию, общую память задач и автоматические проверки. | `done` | 2026-08-20 |
| [TASK_001](tasks/TASK_001_frontier_vlm_evaluation/001_descr.md) — Роль фронтирных моделей в оценке VLM | Роль фронтирных моделей в оценке VLM | `done` | 2026-08-20 |
| [TASK_002](tasks/TASK_002_project_start_scaffold/002_descr.md) — Создание чистого каркаса project_start | Создать готовый к копированию каркас нового проекта без истории и предметных знаний текущего проекта. | `done` | 2026-08-20 |
| [TASK_003](tasks/TASK_003_issledovanie_struktury_nabora_verifier_v0/003_descr.md) — Исследование структуры набора verifier_v0 | Проверить и задокументировать структуру ML-поднабора verifier_v0 как основу будущего фреймворка данных. | `done` | 2026-08-20 |
| [TASK_004](tasks/TASK_004_freymvork_eksperimentov_s_vlm/004_descr.md) — Фреймворк экспериментов с VLM | Создать фреймворк парных запусков VLM и утилиту набора для сравнения системных промптов. | `done` | 2026-08-20 |
| [TASK_005](tasks/TASK_005_publikatsiya_proekta_v_github/005_descr.md) — Публикация проекта в GitHub | Публикация проекта в GitHub | `active` | 2026-08-20 |

## Связи задач

| Задача | Связь | Другая задача |
|---|---|---|
| [TASK_002](tasks/TASK_002_project_start_scaffold/002_descr.md) | связана с | [TASK_000](tasks/TASK_000_documentation_system/000_descr.md) |
| [TASK_004](tasks/TASK_004_freymvork_eksperimentov_s_vlm/004_descr.md) | зависит от | [TASK_003](tasks/TASK_003_issledovanie_struktury_nabora_verifier_v0/003_descr.md) |
| [TASK_004](tasks/TASK_004_freymvork_eksperimentov_s_vlm/004_descr.md) | связана с | [TASK_001](tasks/TASK_001_frontier_vlm_evaluation/001_descr.md) |
<!-- AUTO:TASK_DASHBOARD:END -->

## Правила

- Новая глобальная цель или самостоятельное исследование получает отдельную
  задачу.
- Небольшие шаги внутри одной цели остаются в существующей задаче.
- Источником истины являются файлы внутри папки задачи, а не эта таблица.
- Связи задач задаются полями `parent_task`, `depends_on`, `related_tasks` и
  `supersedes` в `*_descr.md`.
