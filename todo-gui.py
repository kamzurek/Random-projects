#!/usr/bin/env python3
import json
import os
import re
from dataclasses import dataclass, asdict
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import List, Optional, Dict, Any

import tkinter as tk
from tkinter import ttk, messagebox

# --- Storage/config ---
DB_PATH = Path(os.getenv("PYTODO_DB") or Path(__file__).with_name("tasks.json"))

# --- Date parsing helpers ---
WEEKDAYS_MAP = {
    "pn": 0, "pon": 0, "poniedzialek": 0, "poniedziałek": 0,
    "wt": 1, "wto": 1, "wtorek": 1,
    "sr": 2, "śr": 2, "sroda": 2, "środa": 2,
    "czw": 3, "czwartek": 3,
    "pt": 4, "pi": 4, "piatek": 4, "piątek": 4,
    "sb": 5, "sob": 5, "sobota": 5,
    "nd": 6, "nie": 6, "niedz": 6, "niedziela": 6,
}

def _normalize(s: str) -> str:
    return s.lower().translate(str.maketrans("ąćęłńóśźż", "acelnoszz")).strip()

def _next_weekday(target_wd: int) -> date:
    today = date.today()
    ahead = (target_wd - today.weekday()) % 7 or 7
    return today + timedelta(days=ahead)

def parse_due(text: str) -> Optional[date]:
    if not text or not text.strip():
        return None
    raw = text.strip()
    s = _normalize(raw)
    try:
        return date.fromisoformat(raw)
    except ValueError:
        pass
    if s in {"dzis", "dzisiaj", "today", "dzis'", "dzien", "dziś"}:
        return date.today()
    if s in {"jutro", "tomorrow"}:
        return date.today() + timedelta(days=1)
    m = re.fullmatch(r"\+(\d+)\s*d?", s)
    if m:
        return date.today() + timedelta(days=int(m.group(1)))
    if s in WEEKDAYS_MAP:
        return _next_weekday(WEEKDAYS_MAP[s])
    raise ValueError(f"Nieprawidłowy termin: {text!r}. Użyj YYYY-MM-DD, 'dzisiaj', 'jutro', '+3d', 'pt' itp.")

# --- Model ---
@dataclass
class Task:
    id: int
    desc: str
    priority: int = 3
    due: Optional[str] = None  # YYYY-MM-DD
    tags: List[str] = None
    done: bool = False
    created: str = None
    completed: Optional[str] = None

    def __post_init__(self):
        if self.tags is None:
            self.tags = []
        if self.created is None:
            self.created = datetime.now().isoformat(timespec="seconds")
        try:
            self.priority = max(1, min(5, int(self.priority)))
        except Exception:
            self.priority = 3
        if self.due:
            try:
                date.fromisoformat(self.due)
            except ValueError:
                self.due = None

    @property
    def is_overdue(self) -> bool:
        if self.done or not self.due:
            return False
        try:
            return date.fromisoformat(self.due) < date.today()
        except ValueError:
            return False

# --- Persistence ---
def _ensure_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not DB_PATH.exists():
        DB_PATH.write_text(json.dumps({"tasks": [], "last_id": 0}, ensure_ascii=False, indent=2), encoding="utf-8")

def _load_db() -> Dict[str, Any]:
    _ensure_db()
    try:
        data = json.loads(DB_PATH.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or "tasks" not in data:
            raise ValueError
        return {"tasks": list(data.get("tasks", [])), "last_id": int(data.get("last_id", 0))}
    except Exception:
        return {"tasks": [], "last_id": 0}

def _save_db(data: Dict[str, Any]) -> None:
    DB_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def _next_id(data: Dict[str, Any]) -> int:
    data["last_id"] = int(data.get("last_id", 0)) + 1
    return data["last_id"]

# --- GUI ---
class TodoApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("pytodo — lista zadań")
        self.geometry("1000x580")
        self.minsize(840, 500)

        self.var_desc = tk.StringVar()
        self.var_priority = tk.IntVar(value=3)
        self.var_due = tk.StringVar()
        self.var_tags = tk.StringVar()

        self.var_filter = tk.StringVar(value="open")  # open | done | all
        self.var_tag_filter = tk.StringVar()
        self.var_sort = tk.StringVar(value="id")      # id | due | priority
        self.var_stats = tk.StringVar(value="—")

        self._build_ui()
        self._build_menu()
        self.refresh()

    def _build_ui(self):
        root = ttk.Frame(self, padding=12)
        root.pack(fill="both", expand=True)

        add = ttk.LabelFrame(root, text="Dodaj zadanie", padding=8)
        add.pack(fill="x", pady=(0, 10))

        ttk.Label(add, text="Opis:").grid(row=0, column=0, sticky="w")
        ttk.Entry(add, textvariable=self.var_desc, width=40).grid(row=0, column=1, sticky="we", padx=6)

        ttk.Label(add, text="Priorytet (1–5):").grid(row=0, column=2, sticky="e")
        ttk.Spinbox(add, from_=1, to=5, textvariable=self.var_priority, width=5).grid(row=0, column=3, sticky="w", padx=6)

        ttk.Label(add, text="Termin (YYYY-MM-DD / skróty):").grid(row=0, column=4, sticky="e")
        ttk.Entry(add, textvariable=self.var_due, width=16).grid(row=0, column=5, sticky="w", padx=6)

        ttk.Button(add, text="Dziś", command=lambda: self._fill_due_days(0)).grid(row=0, column=6, padx=(4, 0))
        ttk.Button(add, text="Jutro", command=lambda: self._fill_due_days(1)).grid(row=0, column=7, padx=(4, 0))
        ttk.Button(add, text="+7 dni", command=lambda: self._fill_due_days(7)).grid(row=0, column=8, padx=(4, 0))

        ttk.Label(add, text="Tagi (,):").grid(row=0, column=9, sticky="e")
        ttk.Entry(add, textvariable=self.var_tags, width=20).grid(row=0, column=10, sticky="w", padx=6)

        ttk.Button(add, text="Dodaj", command=self.add_task).grid(row=0, column=11, sticky="e", padx=(10, 0))
        for i in range(12):
            add.grid_columnconfigure(i, weight=1 if i == 1 else 0)

        filters = ttk.LabelFrame(root, text="Widok", padding=8)
        filters.pack(fill="x", pady=(0, 8))

        for idx, (txt, val) in enumerate([("Otwarte", "open"), ("Zrobione", "done"), ("Wszystkie", "all")]):
            ttk.Radiobutton(filters, text=txt, value=val, variable=self.var_filter, command=self.refresh)\
               .grid(row=0, column=idx, padx=4)

        ttk.Label(filters, text="Tag:").grid(row=0, column=3, sticky="e")
        ttk.Entry(filters, textvariable=self.var_tag_filter, width=18).grid(row=0, column=4, padx=6)
        ttk.Button(filters, text="Filtruj", command=self.refresh).grid(row=0, column=5)

        ttk.Label(filters, text="Sortuj wg:").grid(row=0, column=6, sticky="e")
        cb_sort = ttk.Combobox(filters, textvariable=self.var_sort, width=12,
                               values=["id", "due", "priority"], state="readonly")
        cb_sort.grid(row=0, column=7, padx=6)
        cb_sort.bind("<<ComboboxSelected>>", lambda _e: self.refresh())

        ttk.Button(filters, text="Odśwież", command=self.refresh).grid(row=0, column=8, padx=(8, 0))
        for i in range(9):
            filters.grid_columnconfigure(i, weight=0)
        filters.grid_columnconfigure(4, weight=1)

        table_frame = ttk.Frame(root)
        table_frame.pack(fill="both", expand=True)

        columns = ("ID", "Status", "Priorytet", "Termin", "Opis", "Tagi")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")
        self.tree.pack(side="left", fill="both", expand=True)

        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        vsb.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=vsb.set)

        self.tree.heading("ID", text="ID")
        self.tree.heading("Status", text="Status")
        self.tree.heading("Priorytet", text="Pri")
        self.tree.heading("Termin", text="Due")
        self.tree.heading("Opis", text="Opis")
        self.tree.heading("Tagi", text="Tagi")

        self.tree.column("ID", width=60, anchor="center")
        self.tree.column("Status", width=70, anchor="center")
        self.tree.column("Priorytet", width=60, anchor="center")
        self.tree.column("Termin", width=110, anchor="center")
        self.tree.column("Opis", width=440)
        self.tree.column("Tagi", width=180)

        self.tree.tag_configure("done", foreground="#6b7280")
        self.tree.tag_configure("overdue", foreground="#b91c1c")

        self.tree.bind("<Double-1>", self._on_double_click)
        # Kontekstowe menu – różne przyciski na różnych platformach
        self.tree.bind("<Button-3>", self._on_context_menu)
        self.tree.bind("<Button-2>", self._on_context_menu)

        status = ttk.Frame(root)
        status.pack(fill="x", pady=(8, 0))
        ttk.Label(status, textvariable=self.var_stats, anchor="w").pack(side="left")

    def _build_menu(self):
        self.menu = tk.Menu(self, tearoff=0)
        self.menu.add_command(label="Przełącz wykonane", command=self.toggle_done_selected)
        self.menu.add_separator()
        self.menu.add_command(label="Usuń", command=self.delete_selected)

    # --- Helpers ---
    def _fill_due_days(self, days: int):
        self.var_due.set((date.today() + timedelta(days=days)).isoformat())

    def _get_all_tasks(self) -> List[Task]:
        data = _load_db()
        return [Task(**t) for t in data["tasks"]]

    def _selected_id(self) -> Optional[int]:
        sel = self.tree.selection()
        if not sel:
            return None
        try:
            return int(self.tree.set(sel[0], "ID"))
        except Exception:
            return None

    # --- Commands ---
    def add_task(self):
        desc = self.var_desc.get().strip()
        if not desc:
            messagebox.showwarning("Brak opisu", "Podaj opis zadania.")
            return

        due_input = self.var_due.get().strip()
        try:
            due_date = parse_due(due_input) if due_input else None
        except ValueError as e:
            messagebox.showerror("Błędny termin", str(e))
            return
        if due_date and due_date < date.today():
            messagebox.showerror("Błędny termin", "Termin nie może być w przeszłości.")
            return

        try:
            pri = int(self.var_priority.get())
        except Exception:
            pri = 3
        pri = max(1, min(5, pri))
        tags = [t.strip() for t in self.var_tags.get().split(",") if t.strip()]

        data = _load_db()
        tid = _next_id(data)
        task = Task(id=tid, desc=desc, priority=pri, due=due_date.isoformat() if due_date else None, tags=tags)
        data["tasks"].append(asdict(task))
        _save_db(data)

        self.var_desc.set("")
        self.var_priority.set(3)
        self.var_due.set("")
        self.var_tags.set("")
        self.refresh()
        self._flash_status(f"Dodano zadanie #{tid}")

    def toggle_done_selected(self):
        tid = self._selected_id()
        if tid is None:
            return
        data = _load_db()
        for t in data["tasks"]:
            if t["id"] == tid:
                t["done"] = not t.get("done", False)
                t["completed"] = datetime.now().isoformat(timespec="seconds") if t["done"] else None
                _save_db(data)
                self.refresh()
                return

    def delete_selected(self):
        tid = self._selected_id()
        if tid is None:
            return
        if not messagebox.askyesno("Usuń", f"Czy na pewno usunąć zadanie #{tid}?"):
            return
        data = _load_db()
        before = len(data["tasks"])
        data["tasks"] = [t for t in data["tasks"] if t["id"] != tid]
        if len(data["tasks"]) != before:
            _save_db(data)
            self.refresh()

    def _on_double_click(self, _event):
        self.toggle_done_selected()

    def _on_context_menu(self, event):
        try:
            row_id = self.tree.identify_row(event.y)
            if row_id:
                self.tree.selection_set(row_id)
                self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu.grab_release()

    # --- View / stats ---
    def refresh(self):
        tasks = self._get_all_tasks()

        mode = self.var_filter.get()
        if mode == "open":
            tasks = [t for t in tasks if not t.done]
        elif mode == "done":
            tasks = [t for t in tasks if t.done]

        tagf = self.var_tag_filter.get().strip()
        if tagf:
            tasks = [t for t in tasks if any(tagf.lower() in tag.lower() for tag in t.tags)]

        sort_by = self.var_sort.get()
        if sort_by == "due":
            tasks.sort(key=lambda t: (t.due is None, t.due or "9999-12-31", t.priority, t.id))
        elif sort_by == "priority":
            tasks.sort(key=lambda t: (t.priority, t.due or "9999-12-31", t.id))
        else:
            tasks.sort(key=lambda t: t.id)

        for item in self.tree.get_children():
            self.tree.delete(item)
        for t in tasks:
            status = "✓" if t.done else ("!" if t.is_overdue else "·")
            tags_str = ", ".join(t.tags)
            tags_row = []
            if t.done:
                tags_row.append("done")
            elif t.is_overdue:
                tags_row.append("overdue")
            self.tree.insert("", "end",
                             values=(t.id, status, t.priority, t.due or "-", t.desc, tags_str),
                             tags=tags_row)

        all_tasks = self._get_all_tasks()
        total = len(all_tasks)
        done = sum(1 for x in all_tasks if x.done)
        open_ = total - done
        overdue = sum(1 for x in all_tasks if x.is_overdue)
        self.var_stats.set(f"Wszystkie: {total} | Otwarte: {open_} | Zrobione: {done} | Po terminie: {overdue}")

    def _flash_status(self, text: str):
        self.var_stats.set(text)
        self.after(2000, self.refresh)

if __name__ == "__main__":
    app = TodoApp()
    app.mainloop()
