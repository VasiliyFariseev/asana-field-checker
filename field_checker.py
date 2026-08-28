#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Field Checker — ищет задачи с незаполненными полями «FD: Version» и
«FD Milestone» по проектам Asana.

Задачи без этих полей теряются при сборке билда. Инструмент раскладывает
задачи проекта по трём корзинам: оба поля заполнены, заполнено только одно
(самые коварные), оба пустые.

Из терминала (окно — field_checker_ui.py):

    python3 field_checker.py                          # проект по умолчанию, проблемные
    python3 field_checker.py --projects "gid1,gid2"   # несколько проектов
    python3 field_checker.py --show all               # partial | none | both | all
    python3 field_checker.py --completed              # включая завершённые
"""
import argparse
import importlib.util
import os

ROOT = os.path.dirname(os.path.abspath(__file__))

_spec = importlib.util.spec_from_file_location("checker_config", os.path.join(ROOT, "config.py"))
config = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(config)
import requests  # noqa: E402  (config уже настроил сессию с таймаутами и ретраями)

BASE = config.ASANA_BASE
HEADERS = config.asana_headers()

TASK_FIELDS = ("name,completed,permalink_url,assignee.name,"
               "memberships.(project.gid|section.name),"
               "custom_fields.(name|display_value)")

CATEGORY_TITLES = {
    "both": "✓ оба заполнены",
    "partial": "⚠ только одно",
    "none": "✗ оба пустые",
}


def get_project(gid: str) -> dict:
    resp = requests.get(f"{BASE}/projects/{gid}",
                        headers=HEADERS, params={"opt_fields": "name"})
    if resp.status_code == 404:
        raise SystemExit(f"⛔ Проект {gid} не найден (или нет доступа).")
    resp.raise_for_status()
    return resp.json()["data"]


def project_tasks(gid: str, progress=None) -> list:
    """Все задачи проекта, с полями. progress(сколько уже) — для статуса в окне."""
    out, offset = [], None
    while True:
        params = {"opt_fields": TASK_FIELDS, "limit": 100}
        if offset:
            params["offset"] = offset
        resp = requests.get(f"{BASE}/projects/{gid}/tasks", headers=HEADERS, params=params)
        resp.raise_for_status()
        payload = resp.json()
        out.extend(payload.get("data", []))
        if progress:
            progress(len(out))
        offset = (payload.get("next_page") or {}).get("offset")
        if not offset:
            return out


def norm_name(name: str) -> str:
    """«FD: Version» → «fdversion»: сравниваем без регистра, пробелов и знаков.
    Так «FD:Version», «FD Version» и «FD: Version» — одно и то же поле."""
    return "".join(ch for ch in (name or "").lower() if ch.isalnum())


LAST_SCAN = {"field_names": set()}     # какие поля реально пришли из Asana


def field_value(task: dict, field_name: str) -> str:
    """Значение кастом-поля по имени.

    В проектах бывает несколько полей с похожими именами («FD: Version» и,
    скажем, «FD: Version (old)») — поэтому: сначала точное совпадение
    нормализованного имени, потом по вхождению; среди совпавших предпочитаем
    поле с НЕПУСТЫМ значением, а не первое попавшееся."""
    want = norm_name(field_name)
    exact, contains = [], []
    for f in task.get("custom_fields") or []:
        raw = (f.get("name") or "").strip()
        if raw:
            LAST_SCAN["field_names"].add(raw)
        name = norm_name(raw)
        if not name:
            continue
        value = (f.get("display_value") or "").strip()
        if name == want:
            exact.append(value)
        elif want in name:
            contains.append(value)
    for bucket in (exact, contains):
        for value in bucket:
            if value:
                return value
        if bucket:
            return ""                  # поле есть, но пустое во всех тёзках
    return ""


def classify(task: dict, field_a: str = None, field_b: str = None) -> dict:
    """Раскладывает задачу: значения полей и корзина both/partial/none."""
    field_a = field_a or config.FIELD_A
    field_b = field_b or config.FIELD_B
    a, b = field_value(task, field_a), field_value(task, field_b)
    if a and b:
        category = "both"
    elif a or b:
        category = "partial"
    else:
        category = "none"
    missing = []
    if not a:
        missing.append(field_a)
    if not b:
        missing.append(field_b)
    return {"a": a, "b": b, "category": category, "missing": missing}


def task_section(task: dict, project_gid: str) -> str:
    for m in task.get("memberships") or []:
        if (m.get("project") or {}).get("gid") == project_gid:
            return ((m.get("section") or {}).get("name") or "").strip()
    return ""


def scan(project_gids: list, include_completed: bool = False, progress=None) -> list:
    """[{project, project_name, section, name, assignee, a, b, category, url}]"""
    rows = []
    LAST_SCAN["field_names"] = set()
    for gid in project_gids:
        project = get_project(gid)
        if progress:
            progress(f"Проект «{project['name']}»: читаю задачи...")
        tasks = project_tasks(
            gid, progress=(lambda n, p=project: progress(
                f"Проект «{p['name']}»: прочитано {n}...")) if progress else None)
        for t in tasks:
            if t.get("completed") and not include_completed:
                continue
            info = classify(t)
            rows.append({
                "project": gid,
                "project_name": project["name"],
                "section": task_section(t, gid),
                "name": t.get("name") or "(без имени)",
                "assignee": ((t.get("assignee") or {}).get("name") or "—"),
                "a": info["a"] or "—",
                "b": info["b"] or "—",
                "category": info["category"],
                "missing": info["missing"],
                "url": t.get("permalink_url") or "",
            })
    return rows


def missing_field_warnings(rows: list) -> list:
    """Поле не нашлось ни в одной задаче → предупреждение со списком реальных имён.
    Это отличает «люди не заполнили» от «поле называется иначе»."""
    warnings = []
    for field in (config.FIELD_A, config.FIELD_B):
        want = norm_name(field)
        seen = any(want == norm_name(n) or want in norm_name(n)
                   for n in LAST_SCAN["field_names"])
        if rows and not seen:
            similar = sorted(n for n in LAST_SCAN["field_names"]
                             if "fd" in norm_name(n))[:8]
            hint = f" Похожие поля в проекте: {', '.join(similar)}" if similar else ""
            warnings.append(f"⚠ Поле «{field}» не найдено ни в одной задаче — "
                            f"проверьте имя в config.py.{hint}")
    return warnings


def counts(rows: list) -> dict:
    out = {"both": 0, "partial": 0, "none": 0}
    for r in rows:
        out[r["category"]] += 1
    return out


def report_text(rows: list, show: str) -> str:
    """Текст для чата: списком, со ссылками — чтобы призвать владельцев задач."""
    picked = [r for r in rows if show == "all" or r["category"] == show]
    title = {"partial": f"Задачи, где заполнено только одно из полей "
                        f"«{config.FIELD_A}» / «{config.FIELD_B}»",
             "none": f"Задачи без полей «{config.FIELD_A}» и «{config.FIELD_B}»",
             "both": "Задачи с заполненными полями",
             "all": "Все задачи по полям"}.get(show, "Задачи")
    lines = [f"{title} — {len(picked)} шт."]
    for r in picked:
        gaps = f" (нет: {', '.join(r['missing'])})" if r["missing"] else ""
        who = f" · {r['assignee']}" if r["assignee"] != "—" else ""
        lines.append(f"• {r['name']}{who}{gaps}\n  {r['url']}")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="Поиск задач с незаполненными FD-полями")
    ap.add_argument("--projects", default=config.DEFAULT_PROJECTS,
                    help="GID проектов через запятую")
    ap.add_argument("--show", default="partial",
                    choices=("partial", "none", "both", "all"),
                    help="какую корзину печатать (по умолчанию partial)")
    ap.add_argument("--completed", action="store_true", help="включая завершённые")
    args = ap.parse_args()

    gids = [g.strip() for g in args.projects.split(",") if g.strip()]
    rows = scan(gids, include_completed=args.completed, progress=lambda t: print(t))
    c = counts(rows)
    for warn in missing_field_warnings(rows):
        print(warn)
    print(f"\nВсего задач: {len(rows)} · оба заполнены: {c['both']} · "
          f"только одно: {c['partial']} · оба пустые: {c['none']}\n")
    print(report_text(rows, args.show))


if __name__ == "__main__":
    main()
