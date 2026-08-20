# -*- coding: utf-8 -*-
"""
Просмотрщик бенча для ручного отсева.

    python review.py

Клавиши:
    ->      оставить, следующая
    вниз    убрать папку и перейти к следующей
    <-      вернуться к предыдущей
    вверх   переключить эталон / испорченную
    Esc     выход

Убранные папки НЕ удаляются насовсем, а переезжают в bench_trash/ — если
промахнулись, папку можно вернуть обратно. Номера убранных пишутся в
review_removed.txt. Полное удаление — только с флагом --hard.
"""
import argparse, json, shutil, sys
from pathlib import Path
import tkinter as tk
from PIL import Image, ImageTk

ROOT = Path(__file__).resolve().parent
BENCH = ROOT / "bench"
TRASH = ROOT / "bench_trash"
LOG = ROOT / "review_removed.txt"


def load_entities():
    """Числа сущностей из прошлого прогона, если есть."""
    p = ROOT / "cached_report.jsonl"
    if not p.exists():
        return {}
    out = {}
    for line in p.open(encoding="utf-8"):
        try:
            r = json.loads(line)
            out[r["id"]] = (r.get("n_visual"), r.get("n_text"))
        except Exception:
            pass
    return out


class Review:
    def __init__(self, root, dirs, hard=False):
        self.root, self.dirs, self.hard = root, dirs, hard
        self.ent = load_entities()
        self.i = 0
        self.show_corrupted = False
        self.removed = []
        self._photo = None

        root.title("Отсев бенча")
        root.geometry("1400x900")
        root.configure(bg="#1e1e1e")

        self.info = tk.Label(root, font=("Consolas", 12), bg="#1e1e1e", fg="#e0e0e0",
                             justify="left", anchor="w")
        self.info.pack(fill="x", padx=10, pady=(8, 2))

        self.cap = tk.Label(root, font=("Consolas", 10), bg="#1e1e1e", fg="#9aa0a6",
                            justify="left", anchor="w", wraplength=1360)
        self.cap.pack(fill="x", padx=10, pady=(0, 6))

        self.canvas = tk.Label(root, bg="#101010")
        self.canvas.pack(fill="both", expand=True, padx=10, pady=4)

        self.hint = tk.Label(
            root,
            text="→ оставить    ↓ убрать    ← назад    ↑ эталон/испорченная    Esc выход",
            font=("Consolas", 11), bg="#1e1e1e", fg="#7f8c8d")
        self.hint.pack(fill="x", padx=10, pady=(2, 8))

        root.bind("<Right>", self.keep)
        root.bind("<Down>", self.remove)
        root.bind("<Left>", self.back)
        root.bind("<Up>", self.toggle)
        root.bind("<Escape>", self.quit)
        root.bind("<Configure>", lambda e: self.draw_image())
        self.draw()

    # ---------- отрисовка
    def cur(self):
        return self.dirs[self.i] if 0 <= self.i < len(self.dirs) else None

    def draw(self):
        d = self.cur()
        if d is None:
            return self.finish()
        try:
            meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
        except Exception:
            meta = {}
        nv, nt = self.ent.get(d.name, (None, None))
        ent = ("сущностей: картинка %s, текст %s" % (nv, nt)) if nv is not None else "сущностей: не считалось"
        self.info.config(text="[%d / %d]  bench/%s    %s    порча: %s    %s\n%s" % (
            self.i + 1, len(self.dirs), d.name,
            meta.get("sample_id", ""),
            ",".join(meta.get("error_actions", [])) or "?",
            ent,
            (meta.get("paper", {}) or {}).get("title", "")[:110]))
        cap = (d / "caption.txt").read_text(encoding="utf-8").strip() if (d / "caption.txt").exists() else ""
        self.cap.config(text=("ЭТАЛОН" if not self.show_corrupted else "ИСПОРЧЕННАЯ") + "  |  " + cap[:400])
        self.draw_image()

    def draw_image(self):
        d = self.cur()
        if d is None:
            return
        f = d / ("corrupted.png" if self.show_corrupted else "reference.png")
        if not f.exists():
            self.canvas.config(image="", text="нет файла %s" % f.name, fg="#ff6b6b")
            return
        cw = max(self.canvas.winfo_width(), 100)
        ch = max(self.canvas.winfo_height(), 100)
        im = Image.open(f)
        im.thumbnail((cw, ch), Image.LANCZOS)
        self._photo = ImageTk.PhotoImage(im)
        self.canvas.config(image=self._photo, text="")

    # ---------- действия
    def keep(self, _=None):
        self.i += 1
        self.show_corrupted = False
        self.draw()

    def back(self, _=None):
        if self.i > 0:
            self.i -= 1
            self.show_corrupted = False
            self.draw()

    def toggle(self, _=None):
        self.show_corrupted = not self.show_corrupted
        self.draw()

    def remove(self, _=None):
        d = self.cur()
        if d is None:
            return
        name = d.name
        try:
            if self.hard:
                shutil.rmtree(d)
            else:
                TRASH.mkdir(exist_ok=True)
                dst = TRASH / name
                if dst.exists():
                    shutil.rmtree(dst)
                shutil.move(str(d), str(dst))
        except Exception as e:
            self.hint.config(text="не удалось убрать %s: %s" % (name, e), fg="#ff6b6b")
            return
        self.removed.append(name)
        with LOG.open("a", encoding="utf-8") as f:
            f.write(name + "\n")
        self.dirs.pop(self.i)
        self.show_corrupted = False
        self.draw()

    def finish(self, _=None):
        self.info.config(text="Готово. Убрано за сессию: %d" % len(self.removed))
        self.cap.config(text=", ".join(self.removed) if self.removed else "ничего не убрано")
        self.canvas.config(image="", text="")
        self._photo = None

    def quit(self, _=None):
        print("убрано за сессию: %d" % len(self.removed))
        if self.removed:
            print("номера: %s" % ", ".join(self.removed))
            print("папки лежат в %s" % (TRASH if not self.hard else "удалены насовсем"))
        self.root.destroy()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hard", action="store_true",
                    help="удалять папки насовсем, а не переносить в bench_trash")
    ap.add_argument("--start", default=None, help="начать с этого номера, например 075")
    args = ap.parse_args()

    dirs = sorted(d for d in BENCH.iterdir() if d.is_dir())
    if not dirs:
        print("в bench/ нет папок")
        return 1
    root = tk.Tk()
    app = Review(root, dirs, hard=args.hard)
    if args.start:
        names = [d.name for d in app.dirs]
        if args.start in names:
            app.i = names.index(args.start)
            app.draw()
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
