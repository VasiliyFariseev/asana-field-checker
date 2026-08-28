#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Field Checker — окно.

Проверяет задачи проектов Asana на заполненность полей «FD: Version» и
«FD Milestone»: оба заполнены / только одно / оба пустые. Кнопка «Скопировать
список» кладёт выбранную корзину в буфер со ссылками — готовый пост в чат.

Логика — в field_checker.py (работает и из терминала), токен — в config.py.
"""
import importlib.util
import os
import sys
import threading
import tkinter as tk
import webbrowser
from tkinter import ttk, messagebox

APP_DIR = os.path.dirname(os.path.abspath(__file__))
TOOL_VERSION = "1.5"


def _die(text: str):
    try:
        err_root = tk.Tk()
        err_root.withdraw()
        messagebox.showerror("Field Checker", text)
    except Exception:  # noqa: BLE001
        print(text, file=sys.stderr)
    raise SystemExit(text)


core_path = os.path.join(APP_DIR, "field_checker.py")
if not os.path.exists(core_path):
    _die("Рядом нет field_checker.py — он должен лежать в одной папке с окном.")
_spec = importlib.util.spec_from_file_location("checker_core", core_path)
CORE = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(CORE)

# ── тёмная тема, как в остальных инструментах ──
UI_BG, UI_PANEL, UI_FIELD = "#1D1F24", "#262930", "#2B2E36"
UI_FG, UI_MUTED, UI_BORDER = "#E8E9ED", "#9BA3AF", "#3C404A"
UI_SELECT, UI_GOOD, UI_BAD, UI_WARN = "#3B5C8F", "#5BD08C", "#FF7A6E", "#FFC069"

root = tk.Tk()
root.title(f"Field Checker · {TOOL_VERSION}")
root.geometry("1150x680")
style = ttk.Style(root)
try:
    style.theme_use("clam")
    root.configure(bg=UI_BG)
    style.configure(".", background=UI_BG, foreground=UI_FG, font=("", 12),
                    fieldbackground=UI_FIELD, bordercolor=UI_BORDER,
                    troughcolor=UI_PANEL, selectbackground=UI_SELECT,
                    selectforeground=UI_FG, insertcolor=UI_FG, arrowcolor=UI_MUTED)
    style.configure("TButton", padding=(10, 5), background=UI_PANEL, foreground=UI_FG)
    style.map("TButton", background=[("active", "#333743")])
    for kind in ("TEntry", "TCombobox"):
        style.configure(kind, fieldbackground=UI_FIELD, foreground=UI_FG)
        style.map(kind, fieldbackground=[("readonly", UI_FIELD)],
                  foreground=[("readonly", UI_FG)])
    style.configure("Treeview", rowheight=26, fieldbackground=UI_FIELD,
                    background=UI_FIELD, foreground=UI_FG)
    style.map("Treeview", background=[("selected", UI_SELECT)])
    style.configure("Treeview.Heading", font=("", 11, "bold"), padding=(4, 5),
                    background=UI_PANEL, foreground=UI_FG)
    root.option_add("*TCombobox*Listbox.background", UI_FIELD)
    root.option_add("*TCombobox*Listbox.foreground", UI_FG)
    root.option_add("*TCombobox*Listbox.selectBackground", UI_SELECT)
except Exception:  # noqa: BLE001
    pass

# ── буфер обмена: правый клик и русская раскладка ──
CLIP_KEYS = {"м": "<<Paste>>", "с": "<<Copy>>", "ч": "<<Cut>>", "ф": "<<SelectAll>>"}


def clip_hotkey(event):
    """Cmd/Ctrl+V в русской раскладке шлёт «м», и Tk сам такое не понимает."""
    virt = CLIP_KEYS.get((event.char or "").lower())
    if virt and isinstance(event.widget, (tk.Entry, ttk.Entry, tk.Text)):
        event.widget.event_generate(virt)
        return "break"
    return None


def entry_menu(event):
    """Правый клик по полю ввода — меню Вставить/Копировать/Очистить."""
    w = event.widget
    menu = tk.Menu(root, tearoff=0, bg=UI_PANEL, fg=UI_FG,
                   activebackground=UI_SELECT, activeforeground=UI_FG)
    for label, virt in (("Вставить", "<<Paste>>"), ("Копировать", "<<Copy>>"),
                        ("Вырезать", "<<Cut>>"), ("Выделить всё", "<<SelectAll>>")):
        menu.add_command(label=label, command=lambda v=virt: w.event_generate(v))
    menu.add_separator()
    menu.add_command(label="Очистить поле",
                     command=lambda: w.delete(0, "end") if hasattr(w, "delete") else None)
    try:
        w.focus_set()
        menu.tk_popup(event.x_root, event.y_root)
    finally:
        menu.grab_release()
    return "break"


for _seq in ("<Command-KeyPress>", "<Control-KeyPress>"):
    try:
        root.bind_all(_seq, clip_hotkey)
    except tk.TclError:
        pass
for _seq in ("<Button-3>", "<Button-2>", "<Control-Button-1>"):
    for _cls in ("TEntry", "Entry"):
        try:
            root.bind_class(_cls, _seq, entry_menu)
        except tk.TclError:
            pass

frame = ttk.Frame(root, padding=12)
frame.pack(fill="both", expand=True)

row1 = ttk.Frame(frame)
row1.pack(fill="x")
ttk.Label(row1, text="Проекты Asana (GID через запятую):").pack(side="left")
projects_var = tk.StringVar(value=CORE.config.DEFAULT_PROJECTS)
projects_entry = ttk.Entry(row1, textvariable=projects_var, width=40)
projects_entry.pack(side="left", padx=6)
scan_btn = ttk.Button(row1, text="🔎 Проверить")
scan_btn.pack(side="left")
completed_var = tk.BooleanVar(value=False)
ttk.Checkbutton(row1, text="включая завершённые",
                variable=completed_var).pack(side="left", padx=10)
subtasks_var = tk.BooleanVar(value=True)
ttk.Checkbutton(row1, text="с сабтасками",
                variable=subtasks_var).pack(side="left")

row2 = ttk.Frame(frame)
row2.pack(fill="x", pady=(8, 0))
ttk.Label(row2, text="Показать:").pack(side="left")
SHOW_CHOICES = [
    ("⚠ заполнено только одно", "partial"),
    ("✗ оба поля пустые", "none"),
    ("✓ оба заполнены", "both"),
    ("все задачи", "all"),
]
show_var = tk.StringVar(value=SHOW_CHOICES[0][0])
show_box = ttk.Combobox(row2, textvariable=show_var, state="readonly", width=28,
                        values=[title for title, _ in SHOW_CHOICES])
show_box.pack(side="left", padx=6)
copy_btn = ttk.Button(row2, text="📋 Скопировать список", state="disabled")
copy_btn.pack(side="left", padx=6)
ttk.Label(row2, text=f"Поля: «{CORE.config.FIELD_A}» и «{CORE.config.FIELD_B}»",
          foreground=UI_MUTED).pack(side="left", padx=10)

cols = ("name", "section", "assignee", "a", "b")
view = ttk.Treeview(frame, columns=cols, show="headings")
for key, title, width, anchor in (
    ("name", "Задача", 470, "w"),
    ("section", "Секция", 170, "w"),
    ("assignee", "Исполнитель", 150, "w"),
    ("a", CORE.config.FIELD_A, 110, "center"),
    ("b", CORE.config.FIELD_B, 110, "center"),
):
    view.heading(key, text=title)
    view.column(key, width=width, anchor=anchor)
view.tag_configure("both", foreground=UI_GOOD)
view.tag_configure("partial", foreground=UI_WARN)
view.tag_configure("none", foreground=UI_BAD)
scroll = ttk.Scrollbar(frame, orient="vertical", command=view.yview)
view.configure(yscrollcommand=scroll.set)
scroll.pack(side="right", fill="y")
view.pack(fill="both", expand=True, pady=(10, 0))

status_var = tk.StringVar(value="Нажмите «Проверить» — задачи прочитаются из Asana.")
ttk.Label(frame, textvariable=status_var, foreground=UI_MUTED,
          wraplength=1100, justify="left").pack(anchor="w", pady=(8, 0))
ttk.Label(frame, text="Двойной клик — открыть задачу в Asana · правый клик — "
                      "все поля задачи, как их отдаёт API (для отладки)",
          foreground=UI_MUTED).pack(anchor="w")

ROWS: list = []                       # результат последнего скана
ROW_URLS: dict = {}                   # iid → ссылка


def show_key() -> str:
    for title, key in SHOW_CHOICES:
        if title == show_var.get():
            return key
    return "partial"


def render():
    view.delete(*view.get_children())
    ROW_URLS.clear()
    key = show_key()
    shown = 0
    for i, r in enumerate(ROWS):
        if key != "all" and r["category"] != key:
            continue
        iid = f"r{i}"
        view.insert("", "end", iid=iid, tags=(r["category"],),
                    values=(r["name"], r["section"] or "—", r["assignee"],
                            r["a"], r["b"]))
        ROW_URLS[iid] = r["url"]
        shown += 1
    c = CORE.counts(ROWS)
    text = (f"Всего задач: {len(ROWS)} · ✓ оба: {c['both']} · "
            f"⚠ только одно: {c['partial']} · ✗ пустые: {c['none']} · "
            f"показано: {shown}")
    warnings = CORE.missing_field_warnings(ROWS)
    if warnings:
        text += "\n" + "\n".join(warnings)
    status_var.set(text)
    copy_btn.configure(state="normal" if ROWS else "disabled")


def run_scan():
    gids = [g.strip() for g in projects_var.get().split(",") if g.strip()]
    if not gids or not all(g.isdigit() for g in gids):
        status_var.set("GID проекта — число из ссылки .../project/<число>/... "
                       "Несколько — через запятую.")
        return
    scan_btn.configure(state="disabled")
    status_var.set("Читаю задачи...")

    def progress(text):
        root.after(0, lambda: status_var.set(text))

    def job():
        try:
            rows, err = CORE.scan(gids, include_completed=completed_var.get(),
                                  include_subtasks=subtasks_var.get(),
                                  progress=progress), ""
        except SystemExit as exc:
            rows, err = [], str(exc)
        except Exception as exc:  # noqa: BLE001
            rows, err = [], str(exc)

        def apply():
            scan_btn.configure(state="normal")
            if err:
                status_var.set(err[:200])
                return
            ROWS[:] = rows
            render()
        root.after(0, apply)

    threading.Thread(target=job, daemon=True).start()


def copy_report():
    text = CORE.report_text(ROWS, show_key())
    root.clipboard_clear()
    root.clipboard_append(text)
    status_var.set("Список скопирован — можно вставить в чат")


def show_row_fields(event=None):
    """Правый клик по строке: все кастом-поля задачи из API + сразу в буфер."""
    iid = view.identify_row(event.y) if event is not None else ""
    if iid:
        view.selection_set(iid)
    sel = view.selection()
    if not sel:
        return
    row = ROWS[int(sel[0][1:])]
    text = CORE.task_fields_text(row)
    root.clipboard_clear()
    root.clipboard_append(text)
    win = tk.Toplevel(root)
    win.title("Поля задачи (API)")
    win.configure(bg=UI_BG)
    win.geometry("760x420")
    box = tk.Text(win, bg=UI_FIELD, fg=UI_FG, insertbackground=UI_FG,
                  wrap="word", padx=10, pady=10, borderwidth=0)
    box.insert("1.0", text + "\n\n(уже скопировано в буфер — можно вставить в чат)")
    box.configure(state="disabled")
    box.pack(fill="both", expand=True, padx=8, pady=8)
    ttk.Button(win, text="Закрыть", command=win.destroy).pack(pady=(0, 8))
    return win


def open_task(_event=None):
    for iid in view.selection():
        url = ROW_URLS.get(iid)
        if url:
            webbrowser.open(url)


scan_btn.configure(command=run_scan)
copy_btn.configure(command=copy_report)
show_box.bind("<<ComboboxSelected>>", lambda _e: render())
view.bind("<Double-1>", open_task)
for _seq in ("<Button-3>", "<Button-2>", "<Control-Button-1>"):
    try:
        view.bind(_seq, show_row_fields)
    except tk.TclError:
        pass

if __name__ == "__main__":
    root.mainloop()
