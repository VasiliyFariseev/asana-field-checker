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
    {"gid": "1", "name": "Квест 17. Craft", "completed": False,
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
    {"gid": "4", "name": "Готовая задача", "completed": True,
     "permalink_url": "https://app.asana.com/t/4",
     "assignee": {"name": "Игорь"},
     "memberships": [],
     "custom_fields": [fld("FD: Version", ""), fld("FD Milestone", "Submit")]},
]
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
# похожие, но чужие поля не подхватываются
assert core_ns["field_value"]({"custom_fields": [fld("FD QA: Weekly", "x")]},
                              "FD: Version") == ""
print("тёзки и пунктуация OK")

# диагностика: поле не нашлось нигде → предупреждение с реальными именами
core_ns["LAST_SCAN"]["field_names"] = {"FD QA: Weekly", "FD Milestone", "Prio"}
warns = core_ns["missing_field_warnings"]([{"x": 1}])
assert len(warns) == 1 and "FD: Version" in warns[0], warns
assert "FD QA: Weekly" in warns[0], warns
core_ns["LAST_SCAN"]["field_names"] = {"FD: Version", "FD Milestone"}
assert core_ns["missing_field_warnings"]([{"x": 1}]) == []
assert core_ns["missing_field_warnings"]([]) == [], "без задач не пугаем"
print("диагностика полей OK")

# скан: пагинация, пропуск завершённых, секции, счётчики
rows = core_ns["scan"](["12040152"])
assert len(rows) == 4, [r["name"] for r in rows]           # без завершённой
assert {r["category"] for r in rows} == {"both", "partial", "none"}
assert rows[0]["section"] == "Проверить в Content"
assert rows[2]["assignee"] == "—"
c = core_ns["counts"](rows)
assert c == {"both": 1, "partial": 2, "none": 1}, c
rows_all = core_ns["scan"](["12040152"], include_completed=True)
assert len(rows_all) == 5, "завершённые по флагу"
print("скан OK ->", c)

# отчёт для чата
text = core_ns["report_text"](rows, "partial")
assert "только одно" in text and "2 шт." in text, text
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

# скан из окна: по умолчанию показываются «только одно»
ns["projects_var"].set("12040152")
ns["run_scan"]()
shown = ns["view"].get_children()
assert len(shown) == 2, shown
assert "только одно: 2" in ns["status_var"].get(), ns["status_var"].get()
tags = {ns["view"].item(i, "tags")[0] for i in shown}
assert tags == {"partial"}, tags
print("окно: проблемные OK")

# переключение корзин
ns["show_var"].set("все задачи")
ns["render"]()
assert len(ns["view"].get_children()) == 4
ns["show_var"].set("✗ оба поля пустые")
ns["render"]()
rows_shown = ns["view"].get_children()
assert len(rows_shown) == 1
assert ns["view"].item(rows_shown[0], "values")[0] == "Туториал на сборщик"
print("окно: переключение корзин OK")

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

# кривый GID — статус, не падение
ns["projects_var"].set("не число")
ns["run_scan"]()
assert "GID проекта" in ns["status_var"].get()
print("кривый GID OK")

print("\nCHECKER SMOKE TESTS PASSED")
