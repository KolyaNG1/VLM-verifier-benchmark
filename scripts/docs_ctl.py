#!/usr/bin/env python3
"""Создание задач, сборка сводок и проверка документации без внешних библиотек."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import unicodedata
from datetime import date, datetime
from pathlib import Path
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
TASKS = DOCS / "tasks"
TEMPLATES = DOCS / "templates"
LOCK = DOCS / ".docs_ctl.lock"
TASK_RE = re.compile(r"^TASK_(\d{3})_(.+)$")
LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
TASK_STATUSES = {"planned", "active", "waiting", "blocked", "done", "cancelled", "superseded"}
ACTIVE_STATUSES = {"planned", "active", "waiting", "blocked"}
REQUIRED_GLOBAL = [
    "index.md", "MAIN_DESCRIPTION.md", "CURRENT_STATE.md", "TASKS_DASHBOARD.md",
    "DOCUMENTATION_SYSTEM.md", "GLOSSARY.md", "knowledge/index.md",
    "decisions/index.md", "sources/index.md", "templates/index.md",
]


class DocsLock:
    """Межпроцессная блокировка через атомарное создание файла."""

    def __init__(self, timeout: float = 20.0) -> None:
        self.timeout = timeout
        self.fd: int | None = None

    def __enter__(self) -> "DocsLock":
        deadline = time.monotonic() + self.timeout
        LOCK.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({
            "pid": os.getpid(),
            "created": datetime.now().isoformat(timespec="seconds"),
        }, ensure_ascii=False).encode("utf-8")
        while True:
            try:
                self.fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(self.fd, payload)
                os.fsync(self.fd)
                return self
            except FileExistsError:
                if time.monotonic() >= deadline:
                    raise RuntimeError(f"Документация занята или осталась блокировка: {LOCK}")
                time.sleep(0.1)

    def __exit__(self, *_: object) -> None:
        if self.fd is not None:
            os.close(self.fd)
        try:
            LOCK.unlink()
        except FileNotFoundError:
            pass


def scalar(value: str) -> object:
    value = value.strip()
    if value in {"null", "~"}:
        return None
    if value in {"true", "false"}:
        return value == "true"
    if value.startswith(("[", '"')):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value.strip('"')
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    return value


def metadata(path: Path) -> dict[str, object]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    result: dict[str, object] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            return result
        if line.strip() and not line.lstrip().startswith("#") and ":" in line:
            key, value = line.split(":", 1)
            result[key.strip()] = scalar(value)
    return {}


def atomic_write(path: Path, text: str) -> bool:
    text = text.rstrip() + "\n"
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temp.write_text(text, encoding="utf-8", newline="\n")
    os.replace(temp, path)
    return True


def replace_block(path: Path, name: str, body: str) -> bool:
    text = path.read_text(encoding="utf-8")
    start, end = f"<!-- AUTO:{name}:START -->", f"<!-- AUTO:{name}:END -->"
    pattern = re.compile(re.escape(start) + r".*?" + re.escape(end), re.S)
    if not pattern.search(text):
        raise RuntimeError(f"Нет служебных меток {name} в {path}")
    text = pattern.sub(f"{start}\n{body.rstrip()}\n{end}", text, count=1)
    text = re.sub(r"(?m)^(updated:\s*).+$", rf"\g<1>{date.today().isoformat()}", text, count=1)
    return atomic_write(path, text)


def task_id(value: object) -> str | None:
    if value is None or value == "":
        return None
    if isinstance(value, int):
        return f"TASK_{value:03d}"
    text = str(value).strip().upper()
    match = re.fullmatch(r"(?:TASK_)?(\d{1,3})", text)
    return f"TASK_{int(match.group(1)):03d}" if match else text


def task_ids(value: object) -> list[str]:
    values = value if isinstance(value, list) else ([] if value in {None, ""} else [value])
    return [normalized for item in values if (normalized := task_id(item))]


def task_pages() -> list[tuple[Path, dict[str, object]]]:
    pages: list[tuple[Path, dict[str, object]]] = []
    if not TASKS.exists():
        return pages
    for folder in TASKS.iterdir():
        match = TASK_RE.match(folder.name) if folder.is_dir() else None
        if match and (path := folder / f"{match.group(1)}_descr.md").exists():
            pages.append((path, metadata(path)))
    return sorted(pages, key=lambda item: int(item[1].get("task_num", 999999)))


def typed_pages(folder: str, page_type: str) -> list[tuple[Path, dict[str, object]]]:
    result: list[tuple[Path, dict[str, object]]] = []
    base = DOCS / folder
    if not base.exists():
        return result
    for path in sorted(base.rglob("*.md")):
        if path.name.lower() == "index.md":
            continue
        meta = metadata(path)
        if meta.get("doc_type") == page_type:
            result.append((path, meta))
    return result


def rel(from_path: Path, to_path: Path) -> str:
    return Path(os.path.relpath(to_path, from_path.parent)).as_posix()


def cell(value: object) -> str:
    return str(value if value is not None else "—").replace("|", "\\|").replace("\n", " ")


def table(pages: list[tuple[Path, dict[str, object]]], from_path: Path, id_key: str | None = None) -> str:
    if not pages:
        return "Страницы ещё не созданы."
    lines = ["| Страница | Кратко | Статус | Обновлена |", "|---|---|---|---|"]
    for path, meta in pages:
        title = cell(meta.get("title", path.stem))
        if id_key and meta.get(id_key):
            title = f"{cell(meta[id_key])} — {title}"
        lines.append(
            f"| [{title}]({rel(from_path, path)}) | {cell(meta.get('summary'))} | "
            f"`{cell(meta.get('status', 'unknown'))}` | {cell(meta.get('updated'))} |"
        )
    return "\n".join(lines)


def dashboard(tasks: list[tuple[Path, dict[str, object]]]) -> str:
    if not tasks:
        return "Задачи ещё не созданы."
    dashboard_path = DOCS / "TASKS_DASHBOARD.md"
    by_id = {task_id(meta.get("task_id")): path for path, meta in tasks}
    lines = ["## Все задачи", "", "| Задача | Кратко | Статус | Обновлена |", "|---|---|---|---|"]
    for path, meta in tasks:
        ident = task_id(meta.get("task_id")) or "UNKNOWN"
        lines.append(
            f"| [{ident}]({rel(dashboard_path, path)}) — {cell(meta.get('title'))} | "
            f"{cell(meta.get('summary'))} | `{cell(meta.get('status'))}` | {cell(meta.get('updated'))} |"
        )
    relations: list[tuple[str, str, str]] = []
    for _, meta in tasks:
        source = task_id(meta.get("task_id")) or "UNKNOWN"
        if parent := task_id(meta.get("parent_task")):
            relations.append((source, "дочерняя для", parent))
        for field, label in (("depends_on", "зависит от"), ("related_tasks", "связана с"), ("supersedes", "заменяет")):
            relations.extend((source, label, target) for target in task_ids(meta.get(field)))
    lines.extend(["", "## Связи задач", ""])
    if not relations:
        lines.append("Явные связи пока не заданы.")
    else:
        lines.extend(["| Задача | Связь | Другая задача |", "|---|---|---|"])
        for source, label, target in sorted(set(relations)):
            left = f"[{source}]({rel(dashboard_path, by_id[source])})" if source in by_id else f"`{source}`"
            right = f"[{target}]({rel(dashboard_path, by_id[target])})" if target in by_id else f"`{target}`"
            lines.append(f"| {left} | {label} | {right} |")
    return "\n".join(lines)


def current_state(
    tasks: list[tuple[Path, dict[str, object]]],
    knowledge: list[tuple[Path, dict[str, object]]],
    decisions: list[tuple[Path, dict[str, object]]],
) -> str:
    active = [page for page in tasks if page[1].get("status") in ACTIVE_STATUSES]
    done = sorted(
        [page for page in tasks if page[1].get("status") == "done"],
        key=lambda page: str(page[1].get("updated", "")), reverse=True,
    )[:10]
    state_path = DOCS / "CURRENT_STATE.md"
    return "\n".join([
        "## Глобальные знания", "", table(knowledge, state_path), "",
        "## Текущие задачи", "", table(active, state_path) if active else "Активных и запланированных задач нет.", "",
        "## Последние завершённые задачи", "", table(done, state_path) if done else "Завершённых задач пока нет.", "",
        "## Решения", "", table(decisions, state_path, "decision_id") if decisions else "Решения пока не зафиксированы.",
    ])


def sync_unlocked() -> list[Path]:
    tasks = task_pages()
    knowledge = typed_pages("knowledge", "knowledge")
    decisions = typed_pages("decisions", "decision")
    sources = typed_pages("sources", "source")
    operations = [
        (DOCS / "TASKS_DASHBOARD.md", "TASK_DASHBOARD", dashboard(tasks)),
        (DOCS / "knowledge/index.md", "KNOWLEDGE_INDEX", table(knowledge, DOCS / "knowledge/index.md")),
        (DOCS / "decisions/index.md", "DECISION_INDEX", table(decisions, DOCS / "decisions/index.md", "decision_id")),
        (DOCS / "sources/index.md", "SOURCE_INDEX", table(sources, DOCS / "sources/index.md", "source_id")),
        (DOCS / "CURRENT_STATE.md", "CURRENT_STATE", current_state(tasks, knowledge, decisions)),
    ]
    changed: list[Path] = []
    for path, marker, body in operations:
        if replace_block(path, marker, body):
            changed.append(path)
    return changed


CYRILLIC = str.maketrans({
    "а":"a","б":"b","в":"v","г":"g","д":"d","е":"e","ё":"e","ж":"zh","з":"z","и":"i","й":"y",
    "к":"k","л":"l","м":"m","н":"n","о":"o","п":"p","р":"r","с":"s","т":"t","у":"u","ф":"f",
    "х":"h","ц":"ts","ч":"ch","ш":"sh","щ":"sch","ъ":"","ы":"y","ь":"","э":"e","ю":"yu","я":"ya",
})


def slugify(value: str) -> str:
    value = value.strip().lower().translate(CYRILLIC)
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "_", value).strip("_")[:60] or "task"


def render(name: str, values: dict[str, str]) -> str:
    text = (TEMPLATES / name).read_text(encoding="utf-8")
    for key, value in values.items():
        text = text.replace("{{" + key + "}}", value)
    unresolved = sorted(set(re.findall(r"{{([A-Z0-9_]+)}}", text)))
    if unresolved:
        raise RuntimeError(f"Не заполнены поля шаблона {name}: {unresolved}")
    return text


def create_task(title: str, slug: str | None, status: str) -> Path:
    TASKS.mkdir(parents=True, exist_ok=True)
    numbers = [int(match.group(1)) for path in TASKS.iterdir() if path.is_dir() and (match := TASK_RE.match(path.name))]
    number = max(numbers, default=0) + 1
    if number > 999:
        raise RuntimeError("Исчерпан диапазон номеров TASK_001…TASK_999")
    num = f"{number:03d}"
    folder = TASKS / f"TASK_{num}_{slugify(slug or title)}"
    folder.mkdir(exist_ok=False)
    today = date.today().isoformat()
    values = {
        "TASK_ID": str(number), "TASK_NUM": num, "TASK_TITLE": title,
        "TASK_TITLE_JSON": json.dumps(title, ensure_ascii=False),
        "TASK_SLUG": slugify(slug or title), "TASK_STATUS": status,
        "TASK_DOCS_PREFIX": "../../",
        "DATE": today, "DATE_COMPACT": today.replace("-", ""),
    }
    names = {"task_descr.md": f"{num}_descr.md", "task_logs.md": f"{num}_logs.md", "task_concl.md": f"{num}_concl.md"}
    try:
        for template, output in names.items():
            atomic_write(folder / output, render(template, values))
    except Exception:
        for path in folder.iterdir():
            path.unlink()
        folder.rmdir()
        raise
    return folder


def links(path: Path) -> list[str]:
    return [match.group(1).strip().strip("<>") for match in LINK_RE.finditer(path.read_text(encoding="utf-8"))]


def local_target(source: Path, raw: str) -> Path | None:
    if not raw or raw.startswith(("#", "http://", "https://", "mailto:", "data:")) or "{{" in raw or "YYYY" in raw:
        return None
    clean = unquote(raw.split("#", 1)[0].split("?", 1)[0]).split(" ", 1)[0]
    if not clean:
        return None
    if re.match(r"^[A-Za-z]:[\\/]", clean) or clean.startswith(("/", "\\")):
        return Path(clean)
    return (source.parent / clean).resolve()


def lint() -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    for relative in REQUIRED_GLOBAL:
        if not (DOCS / relative).is_file():
            errors.append(f"Нет обязательного файла: docs/{relative}")

    tasks = task_pages()
    by_id: dict[str, Path] = {}
    by_num: dict[int, Path] = {}
    for path, meta in tasks:
        match = TASK_RE.match(path.parent.name)
        if not match:
            continue
        num_text, num = match.group(1), int(match.group(1))
        ident = task_id(meta.get("task_id"))
        if num in by_num:
            errors.append(f"Повторяется номер TASK_{num_text}")
        by_num[num] = path
        if ident:
            if ident in by_id:
                errors.append(f"Повторяется идентификатор {ident}")
            by_id[ident] = path
        for suffix in ("descr", "logs", "concl"):
            required = path.parent / f"{num_text}_{suffix}.md"
            if not required.is_file():
                errors.append(f"Нет файла задачи: {required.relative_to(ROOT)}")
        for field in ("task_id", "task_num", "title", "status", "created", "updated", "summary"):
            if field not in meta:
                errors.append(f"{path.relative_to(ROOT)}: нет поля {field}")
        if meta.get("status") not in TASK_STATUSES:
            errors.append(f"{path.relative_to(ROOT)}: недопустимый статус {meta.get('status')!r}")

    for path, meta in tasks:
        source = task_id(meta.get("task_id")) or str(path)
        related = task_ids(meta.get("depends_on")) + task_ids(meta.get("related_tasks")) + task_ids(meta.get("supersedes"))
        if parent := task_id(meta.get("parent_task")):
            related.append(parent)
        for target in related:
            if target not in by_id:
                errors.append(f"{source}: неизвестная связанная задача {target}")

    for folder, expected in (("knowledge", "knowledge"), ("decisions", "decision"), ("sources", "source")):
        for path in (DOCS / folder).rglob("*.md"):
            if path.name.lower() == "index.md":
                continue
            meta = metadata(path)
            if meta.get("doc_type") != expected:
                errors.append(f"{path.relative_to(ROOT)}: ожидается doc_type: {expected}")
            for field in ("title", "status", "updated", "summary"):
                if field not in meta:
                    errors.append(f"{path.relative_to(ROOT)}: нет поля {field}")

    markdown = sorted(DOCS.rglob("*.md"))
    graph = {path.resolve(): set() for path in markdown}
    for path in markdown:
        for raw in links(path):
            target = local_target(path, raw)
            if target is None:
                continue
            if not str(target).lower().startswith(str(ROOT).lower()):
                errors.append(f"{path.relative_to(ROOT)}: ссылка вне проекта: {raw}")
            elif not target.exists():
                errors.append(f"{path.relative_to(ROOT)}: битая ссылка: {raw}")
            elif target.is_file() and target.suffix.lower() == ".md" and target in graph:
                graph[path.resolve()].add(target)
    entry = (DOCS / "index.md").resolve()
    if entry in graph:
        visited: set[Path] = set()
        stack = [entry]
        while stack:
            current = stack.pop()
            if current not in visited:
                visited.add(current)
                stack.extend(graph.get(current, set()) - visited)
        for path in graph:
            if path not in visited:
                errors.append(f"Недостижима из docs/index.md: {path.relative_to(ROOT)}")
    if LOCK.exists():
        warnings.append(f"Остался файл блокировки: {LOCK.relative_to(ROOT)}")
    return errors, warnings


def report_changes(changed: list[Path]) -> None:
    if not changed:
        print("Общие страницы уже актуальны.")
    else:
        print("Обновлены общие страницы:")
        for path in changed:
            print(f"- {path.relative_to(ROOT)}")


def do_create(args: argparse.Namespace) -> int:
    with DocsLock():
        folder = create_task(args.title, args.slug, args.status)
        changed = sync_unlocked()
    print(f"Создана задача: {folder.relative_to(ROOT)}")
    report_changes(changed)
    return 0


def do_sync(_: argparse.Namespace) -> int:
    with DocsLock():
        changed = sync_unlocked()
    report_changes(changed)
    return 0


def do_lint(_: argparse.Namespace) -> int:
    errors, warnings = lint()
    for warning in warnings:
        print(f"ПРЕДУПРЕЖДЕНИЕ: {warning}")
    for error in errors:
        print(f"ОШИБКА: {error}")
    if errors:
        print(f"Проверка не пройдена: ошибок — {len(errors)}, предупреждений — {len(warnings)}.")
        return 1
    print(f"Проверка пройдена: ошибок нет, предупреждений — {len(warnings)}.")
    return 0


def do_check(args: argparse.Namespace) -> int:
    return do_sync(args) or do_lint(args)


def do_export(args: argparse.Namespace) -> int:
    destination = Path(args.destination).resolve()
    if destination.exists():
        raise ValueError(f"Путь экспорта уже существует: {destination}")
    destination.mkdir(parents=True)
    (destination / "docs/knowledge").mkdir(parents=True)
    (destination / "docs/decisions").mkdir(parents=True)
    (destination / "docs/sources").mkdir(parents=True)
    (destination / "docs/tasks").mkdir(parents=True)
    (destination / "scripts").mkdir(parents=True)

    root_files = ["AGENTS.md", ".gitignore"]
    doc_files = [
        "index.md", "MAIN_DESCRIPTION.md", "CURRENT_STATE.md",
        "TASKS_DASHBOARD.md", "DOCUMENTATION_SYSTEM.md", "GLOSSARY.md",
        "knowledge/index.md", "decisions/index.md", "sources/index.md",
    ]
    for relative in root_files:
        shutil.copy2(ROOT / relative, destination / relative)
    for relative in doc_files:
        target = destination / "docs" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(DOCS / relative, target)
    shutil.copytree(TEMPLATES, destination / "docs/templates")
    (destination / "docs/tasks/.gitkeep").touch()
    shutil.copy2(Path(__file__).resolve(), destination / "scripts/docs_ctl.py")

    subprocess.run(
        [sys.executable, str(destination / "scripts/docs_ctl.py"), "check"],
        cwd=destination,
        check=True,
    )
    print(f"Переносимая основа экспортирована без задач и проектных знаний: {destination}")
    return 0


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Управление документацией проекта")
    commands = result.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create", help="Создать задачу")
    create.add_argument("title")
    create.add_argument("--slug")
    create.add_argument("--status", choices=sorted(TASK_STATUSES), default="active")
    create.set_defaults(handler=do_create)
    sync = commands.add_parser("sync", help="Пересобрать общие страницы")
    sync.set_defaults(handler=do_sync)
    lint_cmd = commands.add_parser("lint", help="Проверить без сборки")
    lint_cmd.set_defaults(handler=do_lint)
    check = commands.add_parser("check", help="Пересобрать и проверить")
    check.set_defaults(handler=do_check)
    export = commands.add_parser("export-template", help="Экспортировать чистую переносимую основу")
    export.add_argument("destination", help="Новый, ещё не существующий каталог")
    export.set_defaults(handler=do_export)
    return result


def main() -> int:
    args = parser().parse_args()
    try:
        return int(args.handler(args))
    except (OSError, RuntimeError, ValueError) as error:
        print(f"ОШИБКА: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
