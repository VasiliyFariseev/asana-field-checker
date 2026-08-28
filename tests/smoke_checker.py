"""Смоук Field Checker на заглушках: классификация, скан, окно, отчёт."""
import os
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Resp:
    def __init__(self, payload=None, code=200):
        self._p, self.status_code, self.text = payload, code, ""
        self.ok = 200 <= code < 300

    def json(self):
        return self._p

    def raise_for_status(self):
        if not self.ok:
            raise RuntimeError(self.status_code)


def fld(name, value):
    return {"name": name, "display_value": value}


TASKS_PAGE1 = [
    {"gid": "1", "name": "Квест 17. Craft", "completed": False, "num_subtasks": 2,
     "permalink_url": "https://app.asana.com/t/1",
     "assignee": {"name": "Юлия Титова"},
     "memberships": [{"project": {"gid": "12040152"}, "section": {"name": "Проверить в Content"}}],
     "custom_fields": [fld("FD: Version", "1005"), fld("FD Milestone", "Submit")]},
    {"gid": "2", "name": "Квест 13. Craft", "completed": False,
     "permalink_url": "https://app.asana.com/t/2",
     "assignee": {"name": "Юлия Титова"},
     "memberships": [{"project": {"gid": "12040152"}, "section": {"name": "Проверить в Content"}}],
     "custom_fields": [fld("FD: Version", "1005"), fld("FD Milestone", "")]},
    {"gid": "3", "name": "Туториал на сборщик", "completed": False,
     "permalink_url": "https://app.asana.com/t/3",
     "assignee": None,
     "memberships": [{"project": {"gid": "12040152"}, "section": {"name": "Бэклог"}}],
     "custom_fields": [fld("FD:Version", None), fld("fd milestone", "")]},
    {"gid": "4", "name": "Готовая задача", "completed": True, "num_subtasks": 1,
     "permalink_url": "https://app.asana.com/t/4",
     "assignee": {"name": "Игорь"},
     "memberships": [],
     "custom_fields": [fld("FD: Version", ""), fld("FD Milestone", "Submit")]},
]
SUBTASKS = {
    "1": [
        {"gid": "1a", "name": "Сабтаск А", "completed": False, "num_subtasks": 1,
         "permalink_url": "https://app.asana.com/t/1a",
         "assignee": {"name": "Пётр"}, "memberships": [],
         "custom_fields": [fld("FD: Version", "1005")]},
        {"gid": "1c", "name": "Закрытый сабтаск", "completed": True, "num_subtasks": 0,
         "permalink_url": "https://app.asana.com/t/1c",
         "assignee": None, "memberships": [],
         "custom_fields": [fld("FD: Version", "1005"), fld("FD Milestone", "Submit")]},
    ],
    "1a": [
        {"gid": "1b", "name": "Вложенный сабтаск", "completed": False, "num_subtasks": 0,
         "permalink_url": "https://app.asana.com/t/1b",
         "assignee": None, "memberships": [], "custom_fields": []},
    ],
    "4": [
        {"gid": "4a", "name": "Хвост под закрытой", "completed": False, "num_subtasks": 0,
         "permalink_url": "https://app.asana.com/t/4a",
         "assignee": None, "memberships": [], "custom_fields": []},
    ],
}
TASKS_PAGE2 = [
    {"gid": "5", "name": "Квест 55. Плитки", "completed": False,
     "permalink_url": "https://app.asana.com/t/5",
     "assignee": {"name": "Александр"},
     "memberships": [{"project": {"gid": "12040152"}, "section": {"name": "Проверить в Content"}}],
     "custom_fields": [fld("FD: Version", ""), fld("FD Milestone", "Submit")]},
]


def fake_get(url, headers=None, params=None, **kw):
    if url.endswith("/projects/12040152"):
        return Resp({"data": {"name": "Expedition Team QA"}})
    if url.endswith("/projects/MISSING"):
        return Resp({}, 404)
    if "/projects/12040152/tasks" in url:
        if params and params.get("offset"):
            return Resp({"data": TASKS_PAGE2, "next_page": None})
        return Resp({"data": TASKS_PAGE1, "next_page": {"offset": "abc"}})
    if "/subtasks" in url:
        gid = url.split("/tasks/")[1].split("/")[0]
        return Resp({"data": SUBTASKS.get(gid, []), "next_page": None})
    return Resp({}, 404)


# ── ядро ──
core_src = open(os.path.join(ROOT, "field_checker.py"), encoding="utf-8").read()
core_src = core_src.replace('if __name__ == "__main__":', 'if False:')
core_ns = {"__name__": "core_test", "__file__": os.path.join(ROOT, "field_checker.py")}
exec(compile(core_src, "field_checker.py", "exec"), core_ns)
core_ns["requests"] = types.SimpleNamespace(get=fake_get)
print("CORE IMPORT OK")

# классификация: регистр, вхождение имени, None-значения
assert core_ns["classify"](TASKS_PAGE1[0])["category"] == "both"
info = core_ns["classify"](TASKS_PAGE1[1])
assert info["category"] == "partial" and info["missing"] == ["FD Milestone"], info
assert core_ns["classify"](TASKS_PAGE1[2])["category"] == "none"
info4 = core_ns["classify"](TASKS_PAGE1[3])
assert info4["category"] == "partial" and info4["missing"] == ["FD: Version"], info4
print("классификация OK")

# тёзки полей: пустой дубль не должен затирать заполненное поле
twin_task = {"custom_fields": [
    fld("FD: Version", ""),            # пустой тёзка идёт ПЕРВЫМ
    fld("FD:Version", "1010"),         # настоящее значение, имя без пробела
    fld("FD Milestone", "Submit"),
]}
info_twin = core_ns["classify"](twin_task)
assert info_twin["a"] == "1010", info_twin
assert info_twin["category"] == "both", info_twin
# вариации пунктуации в config-имени тоже находятся
assert core_ns["field_value"]({"custom_fields": [fld("FD Version", "1005")]},
                              "FD: Version") == "1005"
# кириллические двойники: «FD: Versiоn» с русской «о» (реальный случай EXP51)
cyr_task = {"custom_fields": [
    fld("FD: Reported Version", "999"),
    fld("FD: Versiоn", "1010"),   # о — кириллическая «о»
    fld("FD Milestone", "Submit"),
]}
info_cyr = core_ns["classify"](cyr_task)
assert info_cyr["a"] == "1010", info_cyr   # именно Versiоn, не Reported Version
assert info_cyr["category"] == "both", info_cyr
assert core_ns["norm_name"]("FD: Versiоn") == "fdversion"
# похожие, но чужие поля не подхватываются
assert core_ns["field_value"]({"custom_fields": [fld("FD QA: Weekly", "x")]},
                              "FD: Version") == ""
print("тёзки и пунктуация OK")

# display_value пуст, но поле заполнено сырыми значениями
fd = core_ns["field_display"]
assert fd({"display_value": "", "number_value": 1011.0}) == "1011"
assert fd({"display_value": None, "number_value": 10.5}) == "10.5"
assert fd({"display_value": "", "enum_value": {"name": "Code Freeze"}}) == "Code Freeze"
assert fd({"display_value": "", "multi_enum_values": [{"name": "A"}, {"name": "B"}]}) == "A, B"
assert fd({"display_value": "", "text_value": " 1011 "}) == "1011"
assert fd({"display_value": "", "date_value": {"date": "2026-09-01"}}) == "2026-09-01"
assert fd({"display_value": "1012", "number_value": 9}) == "1012", "display_value главнее"
assert fd({"name": "x"}) == ""
num_task = {"custom_fields": [
    {"name": "FD: Version", "display_value": "", "number_value": 1011.0},
    fld("FD Milestone", "Submit")]}
assert core_ns["classify"](num_task)["a"] == "1011"
print("сырые значения OK")

# диагностика: поле не нашлось нигде → предупреждение с реальными именами
core_ns["LAST_SCAN"]["field_names"] = {"FD QA: Weekly", "FD Milestone", "Prio"}
warns = core_ns["missing_field_warnings"]([{"x": 1}])
assert len(warns) == 1 and "FD: Version" in warns[0], warns
assert "FD QA: Weekly" in warns[0], warns
core_ns["LAST_SCAN"]["field_names"] = {"FD: Version", "FD Milestone"}
assert core_ns["missing_field_warnings"]([{"x": 1}]) == []
assert core_ns["missing_field_warnings"]([]) == [], "без задач не пугаем"
print("диагностика полей OK")

# скан: пагинация, пропуск завершённых, секции, счётчики, сабтаски
rows = core_ns["scan"](["12040152"])
names = [r["name"] for r in rows]
assert len(rows) == 7, names                               # 4 задачи + 3 сабтаска
assert "↳ Сабтаск А" in names and "↳ ↳ Вложенный сабтаск" in names, names
assert "↳ Хвост под закрытой" in names, "сабтаски закрытой задачи проверяются"
assert "Закрытый сабтаск" not in " ".join(names), "закрытый сабтаск пропущен"
sub_a = next(r for r in rows if r["name"] == "↳ Сабтаск А")
assert sub_a["section"] == "Проверить в Content", "секция наследуется"
assert sub_a["category"] == "partial"
assert rows[0]["section"] == "Проверить в Content"
c = core_ns["counts"](rows)
assert c == {"both": 1, "partial": 3, "none": 3}, c
rows_all = core_ns["scan"](["12040152"], include_completed=True)
assert len(rows_all) == 9, "завершённые по флагу (и их сабтаски)"
rows_flat = core_ns["scan"](["12040152"], include_subtasks=False)
assert len(rows_flat) == 4, [r["name"] for r in rows_flat]
assert core_ns["counts"](rows_flat) == {"both": 1, "partial": 2, "none": 1}
print("скан OK ->", c)

# рентген полей строки
assert rows[0]["fields_raw"], rows[0]
dump = core_ns["task_fields_text"](rows[0])
assert "FD: Version" in dump and "FD Milestone" in dump, dump
dump_empty = core_ns["task_fields_text"]({"name": "x", "fields_raw": []})
assert "ни одного кастом-поля" in dump_empty
print("рентген полей OK")

# отчёт для чата
text = core_ns["report_text"](rows, "partial")
assert "только одно" in text and "3 шт." in text, text
assert "Квест 13" in text and "нет: FD Milestone" in text, text
assert "https://app.asana.com/t/2" in text
assert "Квест 17" not in text, "оба заполнены — не в этом списке"
print("отчёт OK")

# несуществующий проект — понятная ошибка
try:
    core_ns["scan"](["MISSING"])
    raise AssertionError("должен быть SystemExit")
except SystemExit as exc:
    assert "не найден" in str(exc)
print("404 OK")

# ── окно ──
ui_src = open(os.path.join(ROOT, "field_checker_ui.py"), encoding="utf-8").read()
ui_src = ui_src.replace('if __name__ == "__main__":', 'if False:')
os.chdir(ROOT)
ns = {"__name__": "uitest", "__file__": os.path.join(ROOT, "field_checker_ui.py")}
exec(compile(ui_src, "field_checker_ui.py", "exec"), ns)
root = ns["root"]
ns["CORE"].requests = types.SimpleNamespace(get=fake_get)


class Sync:
    def __init__(self, target=None, args=(), daemon=None):
        self._t = target

    def start(self):
        self._t()


ns["threading"] = types.SimpleNamespace(Thread=Sync)
root.after = lambda ms, fn=None, *a: (fn() if fn else None)
print("UI IMPORT OK")

# тёмная тема
import tkinter.ttk as ttk_mod
assert ttk_mod.Style(root).lookup("Treeview", "background") == ns["UI_FIELD"]

# скан из окна: по умолчанию показываются «только одно» (с сабтасками)
ns["projects_var"].set("12040152")
ns["run_scan"]()
shown = ns["view"].get_children()
assert len(shown) == 3, shown
assert "только одно: 3" in ns["status_var"].get(), ns["status_var"].get()
tags = {ns["view"].item(i, "tags")[0] for i in shown}
assert tags == {"partial"}, tags
print("окно: проблемные OK")

# переключение корзин
ns["show_var"].set("все задачи")
ns["render"]()
assert len(ns["view"].get_children()) == 7
ns["show_var"].set("✗ оба поля пустые")
ns["render"]()
rows_shown = ns["view"].get_children()
shown_names = {ns["view"].item(i, "values")[0] for i in rows_shown}
assert len(rows_shown) == 3, shown_names
assert "Туториал на сборщик" in shown_names, shown_names
assert "↳ ↳ Вложенный сабтаск" in shown_names, shown_names
print("окно: переключение корзин OK")

# галочка «с сабтасками» выключена — только задачи проекта
ns["subtasks_var"].set(False)
ns["show_var"].set("все задачи")
ns["run_scan"]()
assert len(ns["view"].get_children()) == 4, ns["view"].get_children()
ns["subtasks_var"].set(True)
ns["run_scan"]()
print("окно: галочка сабтасков OK")

# копирование отчёта и открытие задачи
opened = []
ns["webbrowser"] = types.SimpleNamespace(open=lambda url: opened.append(url))
ns["show_var"].set("⚠ заполнено только одно")
ns["render"]()
ns["copy_report"]()
clip = root.clipboard_get()
assert "Квест 13" in clip and "только одно" in clip
first = ns["view"].get_children()[0]
ns["view"].selection_set(first)
ns["open_task"]()
assert opened and opened[0].startswith("https://app.asana.com/t/"), opened
print("копирование и открытие OK")

# правый клик по строке — окно со всеми полями + буфер
ns["show_var"].set("все задачи")
ns["render"]()
first = ns["view"].get_children()[0]
ns["view"].selection_set(first)
win = ns["show_row_fields"]()
assert win is not None
clip = root.clipboard_get()
assert "по данным API Asana" in clip and "FD" in clip, clip
win.destroy()
print("рентген из окна OK")

# вставка из буфера в русской раскладке: Cmd+V шлёт «м»
root.clipboard_clear()
root.clipboard_append("1215934810295116")
ns["projects_var"].set("")
ns["projects_entry"].focus_set()
fake_ev = types.SimpleNamespace(char="м", widget=ns["projects_entry"])
assert ns["clip_hotkey"](fake_ev) == "break"
root.update()
assert ns["projects_var"].get() == "1215934810295116", ns["projects_var"].get()
assert ns["clip_hotkey"](types.SimpleNamespace(char="q", widget=ns["projects_entry"])) is None
assert callable(ns["entry_menu"])
print("вставка в русской раскладке OK")

# кривый GID — статус, не падение
ns["projects_var"].set("не число")
ns["run_scan"]()
assert "GID проекта" in ns["status_var"].get()
print("кривый GID OK")

print("\nCHECKER SMOKE TESTS PASSED")
