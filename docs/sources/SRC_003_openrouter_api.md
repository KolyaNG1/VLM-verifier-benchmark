---
doc_type: source
source_id: "SRC_003"
title: "Официальная документация OpenRouter API"
status: active
created: 2026-08-20
updated: 2026-08-20
summary: "Форматы мультимодальных запросов, JSON-ответов, рассуждений и учёта стоимости OpenRouter."
location: "https://openrouter.ai/docs/api_reference/overview"
related_tasks: ["TASK_004"]
---

# SRC_003 — Официальная документация OpenRouter API

[← К каталогу источников](index.md)

## Происхождение

- Владелец: OpenRouter.
- Дата доступа: 2026-08-20.
- [Справочник интерфейса](https://openrouter.ai/docs/api_reference/overview).
- [Входные изображения](https://openrouter.ai/docs/guides/overview/multimodal/image-understanding).
- [Структурированный вывод](https://openrouter.ai/docs/guides/features/structured-outputs).
- [Учёт использования](https://openrouter.ai/docs/cookbook/administration/usage-accounting).
- [Страница GLM-4.6V](https://openrouter.ai/z-ai/glm-4.6v/providers).

## Содержание

Подтверждает вызов `/api/v1/chat/completions`, передачу локального изображения
как base64-части `image_url`, формат `response_format`, наличие идентификатора
генерации, токенов, стоимости и детализации кэша/рассуждения в ответе.
Мультимодальные части относятся к пользовательскому сообщению; поддержка
строгой схемы зависит не только от модели, но и от конкретного поставщика.

## Область применимости и ограничения

- Подтверждает текущий внешний контракт, необходимый для клиента и аудита.
- Не гарантирует неизменность поддерживаемых параметров и цен; реализация должна
  сохранять фактический ответ и проверять возможности перед запуском.
- Не определяет предметную формулу оценки L2.

## Связанные задачи и знания

- [TASK_004](../tasks/TASK_004_freymvork_eksperimentov_s_vlm/004_descr.md).
- [Архитектура фреймворка](../knowledge/VLM_EXPERIMENT_FRAMEWORK.md).
