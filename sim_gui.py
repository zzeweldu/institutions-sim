"""
GUI frontend for the one‑state institutional simulation ("core.py").
Adds:
  • Parameter form (state name, pop, tech, EI/PI …)
  • Editable *runtime* CFG values – click **Edit Config** to open a window where
    you can change any numeric/boolean field (including nested targets).
  • Background‑thread execution so the UI stays responsive.
  • Embedded Matplotlib plots:  
      – **left subplot:** EI, PI
      – **right subplot:** Output on a **log‑scaled** y‑axis so growth rates are visible.
  • Scrollable event log docked to the right of the controls.

Put this file next to *core.py* and run:
    python sim_gui.py
"""
from __future__ import annotations
import threading
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from typing import Dict, Any

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import random, sys

# ─── import core model ───
from core import State, CFG



# ----------------------------- GUI CLASSES --------------------------------- #

# ───────────────── Tooltip helper ──────────────────
class _Tooltip:
    """Attach to any widget ⇒ show a one-line balloon tip on hover."""
    def __init__(self, widget: tk.Widget, text: str, delay: int = 500):
        self.widget = widget
        self.text   = text
        self.delay  = delay          # ms before showing
        self._id    = None           # after() handle
        self._tip   = None           # Toplevel balloon

        widget.bind("<Enter>", self._schedule)
        widget.bind("<Leave>", self._hide)

    def _schedule(self, _e):
        self._id = self.widget.after(self.delay, self._show)

    def _show(self):
        if self._tip or not self.text:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + 20
        self._tip = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        ttk.Label(tw, text=self.text, background="#ffffe0",
                  relief="solid", borderwidth=1,
                  font=("TkDefaultFont", 9)).pack(ipadx=4, ipady=2)

    def _hide(self, _e):
        if self._id:
            self.widget.after_cancel(self._id); self._id = None
        if self._tip:
            self._tip.destroy(); self._tip = None

# Key → short description for balloon tips
CFG_DESCR = {
    "mass_growth"   : "Monthly population growth of the non-elite masses",
    "elite_growth"  : "Monthly growth rate of the elite cohort",
    "infra_decay"   : "Natural wear of infrastructure each month",
    "sec_decay"     : "Peacetime degradation of security capability",
    "tax_rate"      : "Flat share of output collected as tax revenue",
    "vote_interval" : "Time between institution change votes",

    "min_ratio"     : "Lowest allowed professionals-to-pop ratio",
    "max_ratio"     : "Ceiling on professional army size",
    "hire_limit"    : "Max change in pros per month (as % of pop)",
    "inertia_expand": "Speed of raising the target pro ratio",
    "inertia_contract":"Speed of lowering the target pro ratio",
    "soldier_cost"  : "Payroll units per professional soldier",
    "conscript_cost": "Payroll units per conscript",

    "base_draft"    : "Draft share if EI = 0 and invasion risk high",

    "base_invade"   : "Floor invasion probability per month",
    "safe_ratio"    : "Pro-troop ratio that makes invasion almost 0",
    "invade_k"      : "Steepness of risk curve below safe_ratio",
    "min_enemy_strength":"Enemy strength lower-bound (× our army)",
    "max_enemy_strength":"Enemy strength upper-bound (× our army)",

    "vote_step"     : "Max change in EI or PI after an election",

    "unrest_adjust" : "Speed at which grievance turns into unrest",
    "unrest_output_penalty":"Fractional output loss when unrest > 0.4",
    "protest_base"  : "Base chance protests ignite when unrest high",
    "civil_war_threshold":"(legacy) not used",
    "coup_probability":"Baseline chance officers plot a coup",

    "equip_weight"  : "Combat multiplier from equipment/security",

    "alloc_floor"   : "Minimum budget share any line item can get",

    "repression_effectiveness":"Unrest ↓ per $ of repression",
    "repression_cost_fraction":"Share of security budget that is repression",

    "disaster_base" : "Base probability of natural catastrophe",
    "disaster_infra_coeff":"Extra risk if infra < target",
    "disaster_unrest_coeff":"Extra risk if unrest high",

    "sleep"         : "UI delay (seconds) between months (0 = fast)",
    # nested target keys:
    "tech"          : "Long-run desired technology index",
    "infra"         : "Long-run desired infrastructure stock",
    "pc"            : "Long-run desired production capital"
}

class ConfigEditor(tk.Toplevel):
    """Modal window to edit the global *CFG* dict from *abm*."""

    def __init__(self, master: tk.Widget, cfg: Dict[str, Any]):
        super().__init__(master)
        self.title("Edit Configuration")
        self.grab_set()            # modal
        self.resizable(True, True)

        canvas = tk.Canvas(self, width=720, height=600)
        vsb    = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        frame  = ttk.Frame(canvas)
        frame.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=frame, anchor="nw")
        canvas.configure(yscrollcommand=vsb.set)
        canvas.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # --- build entry widgets in two columns --------------------------------
        self._vars: Dict[str, tk.StringVar] = {}
        self._tvars: Dict[str, tk.StringVar] = {}

        top_level = [(k, v) for k, v in sorted(cfg.items()) if not isinstance(v, dict)]
        targets   = sorted(cfg.get("targets", {}).items())

        ttk.Label(frame, text="— Top‑level —", font=("TkDefaultFont", 10, "bold")).grid(column=0, row=0, columnspan=4, pady=(4, 2))
        for idx, (k, v) in enumerate(top_level, start=1):
            col = (idx - 1) % 2 * 2
            row = (idx - 1) // 2 + 1
            ttk.Label(frame, text=k).grid(column=col, row=row, sticky="w", padx=4, pady=1)
            var = tk.StringVar(value=str(v))
            self._vars[k] = var
            entry = ttk.Entry(frame, textvariable=var, width=14)
            entry.grid(column=col + 1, row=row, padx=4, pady=1)
            _Tooltip(entry, CFG_DESCR.get(k, ""))

        start_row = (len(top_level) + 1) // 2 + 2
        ttk.Label(frame, text="— targets —", font=("TkDefaultFont", 10, "bold")).grid(column=0, row=start_row, columnspan=4, pady=(10, 2))
        for j, (k, v) in enumerate(targets):
            col = (j % 2) * 2
            row = (j // 2) + start_row + 1
            ttk.Label(frame, text=k).grid(column=col, row=row, sticky="w", padx=4, pady=1)
            var = tk.StringVar(value=str(v))
            self._tvars[k] = var
            entry = ttk.Entry(frame, textvariable=var, width=14)
            entry.grid(column=col + 1, row=row, padx=4, pady=1)
            _Tooltip(entry, CFG_DESCR.get(k, "")) 

        # buttons
        btn_fr = ttk.Frame(frame)
        btn_fr.grid(column=0, row=row + 2, columnspan=4, pady=8)
        ttk.Button(btn_fr, text="Save", command=self._save).pack(side="left", padx=4)
        ttk.Button(btn_fr, text="Cancel", command=self.destroy).pack(side="left", padx=4)

    # ------------------------------------------------------------------
    def _save(self):
        try:
            for k, var in self._vars.items():
                CFG[k] = _parse_literal(var.get(), fallback=CFG[k])
            tcfg = CFG.setdefault("targets", {})
            for k, var in self._tvars.items():
                tcfg[k] = _parse_literal(var.get(), fallback=tcfg[k])
        except ValueError as e:
            messagebox.showerror("Invalid value", str(e), parent=self)
            return
        self.destroy()


# --------------------------- MAIN APPLICATION ------------------------------ #
class SimGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("State Simulation")
        self._build()

    # ------------------------------------------------------------------
    def _build(self):
        # ---------- LEFT pane: controls --------------------------------
        left = ttk.Frame(self, padding=8)
        left.pack(side="left", fill="y")

        self.params: Dict[str, tk.StringVar] = {}
        def add_field(label: str, key: str, default: str):
            r = len(self.params)
            ttk.Label(left, text=label).grid(column=0, row=r, sticky="w", pady=2)
            var = tk.StringVar(value=default)
            self.params[key] = var
            ttk.Entry(left, textvariable=var, width=14).grid(column=1, row=r, pady=2, padx=4)
        add_field("State", "name", "Solaria")
        add_field("Population", "pop", "5000000")
        add_field("Tech index", "tech", "1.0")
        add_field("Elite share", "elite_share", "0.08")
        add_field("EI", "ei", "0.5")
        add_field("PI", "pi", "0.5")
        add_field("Months", "months", "120")
        add_field("Max step", "max_step", "0.1")
        add_field("Random Seed", "seed", "")

        # buttons
        btn_fr = ttk.Frame(left)
        btn_fr.grid(column=0, row=len(self.params), columnspan=2, pady=6)
        ttk.Button(btn_fr, text="Run", command=self._run).pack(side="left", padx=4)
        ttk.Button(btn_fr, text="Edit Config", command=lambda: ConfigEditor(self, CFG)).pack(side="left", padx=4)

        # ---------- RIGHT pane: event log --------------------------------
        right = ttk.Frame(self, padding=(4, 8))
        right.pack(side="right", fill="y")
        ttk.Label(right, text="Event log", font=("TkDefaultFont", 10, "bold")).pack(anchor="w")
        self.log_box = scrolledtext.ScrolledText(right, width=50, height=30, wrap="none", state="disabled")
        self.log_box.pack(fill="y", expand=True)

        # ---------- CENTER / bottom: plots --------------------------------
        self.fig = Figure(figsize=(10, 4))
        self.ax_left  = self.fig.add_subplot(121)   # EI/PI
        self.ax_right = self.fig.add_subplot(122)   # Output (log)
        self.ax_right.set_yscale("log")
        self.ax_right.set_ylabel("Output (log scale)")
        self.ax_left.set_ylabel("Index (0‑1 scale)")
        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas.get_tk_widget().pack(side="bottom", fill="both", expand=True)

    # ------------------------------------------------------------------
    def _run(self):
        if getattr(self, "_thread", None) and self._thread.is_alive():
            messagebox.showinfo("Busy", "Simulation already running.")
            return
        try:
            kw = {
                "name":        self.params["name"].get(),
                "pop":         float(self.params["pop"].get()),
                "tech":        float(self.params["tech"].get()),
                "elite_share": float(self.params["elite_share"].get()),
                "EI":          float(self.params["ei"].get()),
                "PI":          float(self.params["pi"].get()),
                "max_step":    float(self.params["max_step"].get()),
            }
            months = int(float(self.params["months"].get()))
            
            seed_input = self.params["seed"].get().strip()
            if seed_input:
                random.seed(int(seed_input))
        except ValueError:
            messagebox.showerror("Input error", "Please enter valid numbers.")
            return

        def worker():
            state = State(**kw)
            for _ in range(months):
                state.month_step()
            self.after(0, lambda: self._display_results(state))
        self._thread = threading.Thread(target=worker, daemon=True)
        self._thread.start()

    # ------------------------------------------------------------------
    def _display_results(self, state: State):
        # ----- plots -----
        self.ax_left.clear(); self.ax_right.clear()
        m = range(1, len(state.trend["EI"]) + 1)
        self.ax_left.plot(m, state.trend["EI"], label="EI")
        self.ax_left.plot(m, state.trend["PI"], label="PI")
        self.ax_left.set_xlabel("Month")
        self.ax_left.set_title(f"Institutions – {state.name}")
        self.ax_left.legend()

        self.ax_right.plot(m, state.trend["Y"], label="Output")
        self.ax_right.set_xlabel("Month")
        self.ax_right.set_title("Output")
        self.ax_right.grid(True, which="both", ls=":", lw=0.5)

        self.fig.tight_layout()
        self.canvas.draw_idle()

        # ----- event log -----
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.insert("end", "\n".join(state.events))
        self.log_box.configure(state="disabled")


# --------------------------- helpers --------------------------------------- #

def _parse_literal(text: str, *, fallback: Any):
    text = text.strip()
    if text.lower() in {"true", "false"}:
        return text.lower() == "true"
    try:
        return float(text) if ("." in text or "e" in text.lower()) else int(text)
    except ValueError:
        raise ValueError(f"Cannot convert '{text}' to number; leave empty for {fallback}.")


# --------------------------- run GUI --------------------------------------- #
if __name__ == "__main__":
    SimGUI().mainloop()
