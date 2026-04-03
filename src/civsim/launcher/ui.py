from __future__ import annotations

from dataclasses import dataclass, replace
import random
import tkinter as tk
from tkinter import messagebox


@dataclass(slots=True)
class LaunchSettings:
    days: int | None
    total_agents: int
    children: int
    start_paused: bool = False
    open_report: bool = False
    random_seed_each_run: bool = True
    fixed_seed: int | None = None


@dataclass(slots=True, frozen=True)
class LauncherOutcome:
    action: str
    settings: LaunchSettings | None = None


def normalize_launch_settings(settings: LaunchSettings, config) -> LaunchSettings:
    default_total = max(1, config.agents.initial_population + config.agents.initial_children)
    total_agents = max(2, int(settings.total_agents if settings.total_agents > 0 else default_total))
    children = max(0, int(settings.children))
    children = min(children, total_agents - 1)
    days = None if settings.days is None else int(settings.days)
    if days is not None and days <= 0:
        days = None
    fixed_seed = None if settings.random_seed_each_run else (0 if settings.fixed_seed is None else max(0, int(settings.fixed_seed)))
    return replace(
        settings,
        days=days,
        total_agents=total_agents,
        children=children,
        fixed_seed=fixed_seed,
    )


def choose_launch_seed(settings: LaunchSettings) -> int:
    if settings.random_seed_each_run or settings.fixed_seed is None:
        return random.SystemRandom().randint(1, 2_147_483_647)
    return max(0, int(settings.fixed_seed))


def _center_window(window: tk.Tk | tk.Toplevel, width: int, height: int) -> None:
    window.update_idletasks()
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()
    x = max(40, (screen_width - width) // 2)
    y = max(40, (screen_height - height) // 2)
    window.geometry(f"{width}x{height}+{x}+{y}")


def show_launcher_menu(
    *,
    config,
    initial_settings: LaunchSettings,
    last_seed: int | None = None,
    last_summary: str | None = None,
) -> LauncherOutcome:
    settings = normalize_launch_settings(initial_settings, config)
    root = tk.Tk()
    root.title("CivSim Launcher")
    root.configure(bg="#141821")
    root.resizable(False, False)
    _center_window(root, 540, 420)

    result: LauncherOutcome = LauncherOutcome("quit")

    title = tk.Label(
        root,
        text="CivSim Launcher",
        fg="#F2F5F8",
        bg="#141821",
        font=("Segoe UI", 18, "bold"),
    )
    title.pack(anchor="w", padx=20, pady=(18, 4))

    subtitle = tk.Label(
        root,
        text="Set the starting conditions, then launch a fresh live simulation run.",
        fg="#AAB3C2",
        bg="#141821",
        font=("Segoe UI", 10),
    )
    subtitle.pack(anchor="w", padx=20, pady=(0, 14))

    if last_summary:
        summary_box = tk.Label(
            root,
            text=last_summary,
            justify="left",
            anchor="w",
            fg="#D8DEE8",
            bg="#1B2130",
            bd=1,
            relief="solid",
            padx=12,
            pady=10,
            font=("Consolas", 9),
        )
        summary_box.pack(fill="x", padx=20, pady=(0, 14))

    form = tk.Frame(root, bg="#141821")
    form.pack(fill="both", expand=True, padx=20)

    days_var = tk.IntVar(value=0 if settings.days is None else settings.days)
    agents_var = tk.IntVar(value=settings.total_agents)
    children_var = tk.IntVar(value=settings.children)
    paused_var = tk.BooleanVar(value=settings.start_paused)
    open_report_var = tk.BooleanVar(value=settings.open_report)
    random_seed_var = tk.BooleanVar(value=settings.random_seed_each_run)
    fixed_seed_var = tk.StringVar(value="" if settings.fixed_seed is None else str(settings.fixed_seed))

    next_seed_preview = tk.StringVar(value="A fresh random seed will be used." if settings.random_seed_each_run else f"Fixed seed: {settings.fixed_seed or 0}")
    if last_seed is not None:
        next_seed_preview.set(f"Last seed: {last_seed}  |  Next launch: {'random' if settings.random_seed_each_run else f'fixed {settings.fixed_seed or 0}'}")

    def add_row(label_text: str, widget: tk.Widget, row: int) -> None:
        label = tk.Label(form, text=label_text, fg="#E7ECF2", bg="#141821", anchor="w", font=("Segoe UI", 10, "bold"))
        label.grid(row=row, column=0, sticky="w", pady=6)
        widget.grid(row=row, column=1, sticky="ew", pady=6)

    spin_style = {"from_": 0, "to": 5000, "width": 12}
    days_spin = tk.Spinbox(form, textvariable=days_var, **spin_style)
    agents_spin = tk.Spinbox(form, textvariable=agents_var, **spin_style)
    children_spin = tk.Spinbox(form, textvariable=children_var, from_=0, to=5000, width=12)
    seed_entry = tk.Entry(form, textvariable=fixed_seed_var, width=14)

    add_row("Max days (0 = extinction)", days_spin, 0)
    add_row("Total starting agents", agents_spin, 1)
    add_row("Starting children", children_spin, 2)

    seed_frame = tk.Frame(form, bg="#141821")
    random_check = tk.Checkbutton(
        seed_frame,
        text="Randomize seed every new run",
        variable=random_seed_var,
        onvalue=True,
        offvalue=False,
        fg="#DCE4EE",
        bg="#141821",
        activebackground="#141821",
        activeforeground="#FFFFFF",
        selectcolor="#1F2635",
        highlightthickness=0,
    )
    random_check.pack(anchor="w")
    fixed_seed_row = tk.Frame(seed_frame, bg="#141821")
    fixed_seed_row.pack(anchor="w", pady=(6, 0))
    tk.Label(fixed_seed_row, text="Fixed seed", fg="#AAB3C2", bg="#141821", font=("Segoe UI", 9)).pack(side="left", padx=(0, 8))
    seed_entry.pack(in_=fixed_seed_row, side="left")
    add_row("Seed behavior", seed_frame, 3)

    options_frame = tk.Frame(form, bg="#141821")
    tk.Checkbutton(
        options_frame,
        text="Start paused",
        variable=paused_var,
        fg="#DCE4EE",
        bg="#141821",
        activebackground="#141821",
        activeforeground="#FFFFFF",
        selectcolor="#1F2635",
        highlightthickness=0,
    ).pack(anchor="w")
    tk.Checkbutton(
        options_frame,
        text="Open report after run",
        variable=open_report_var,
        fg="#DCE4EE",
        bg="#141821",
        activebackground="#141821",
        activeforeground="#FFFFFF",
        selectcolor="#1F2635",
        highlightthickness=0,
    ).pack(anchor="w", pady=(6, 0))
    add_row("Run options", options_frame, 4)

    preview_label = tk.Label(form, textvariable=next_seed_preview, fg="#9FB0C6", bg="#141821", anchor="w", font=("Consolas", 9))
    preview_label.grid(row=5, column=0, columnspan=2, sticky="w", pady=(12, 0))

    form.columnconfigure(1, weight=1)

    def refresh_seed_state(*_args) -> None:
        enabled = not random_seed_var.get()
        seed_entry.configure(state=("normal" if enabled else "disabled"))
        if random_seed_var.get():
            next_seed_preview.set(
                f"Last seed: {last_seed}  |  Next launch: random"
                if last_seed is not None
                else "A fresh random seed will be used."
            )
        else:
            shown = fixed_seed_var.get().strip() or "0"
            next_seed_preview.set(
                f"Last seed: {last_seed}  |  Next launch: fixed {shown}"
                if last_seed is not None
                else f"Fixed seed: {shown}"
            )

    random_seed_var.trace_add("write", refresh_seed_state)
    fixed_seed_var.trace_add("write", refresh_seed_state)
    refresh_seed_state()

    def launch() -> None:
        nonlocal result
        try:
            fixed_seed = None if random_seed_var.get() else int(fixed_seed_var.get().strip() or "0")
        except ValueError:
            messagebox.showerror("Invalid seed", "The fixed seed must be a whole number.", parent=root)
            return
        candidate = LaunchSettings(
            days=days_var.get(),
            total_agents=agents_var.get(),
            children=children_var.get(),
            start_paused=paused_var.get(),
            open_report=open_report_var.get(),
            random_seed_each_run=random_seed_var.get(),
            fixed_seed=fixed_seed,
        )
        normalized = normalize_launch_settings(candidate, config)
        if normalized.children >= normalized.total_agents:
            messagebox.showerror("Invalid counts", "Starting children must be fewer than total starting agents.", parent=root)
            return
        result = LauncherOutcome("launch", normalized)
        root.destroy()

    def quit_launcher() -> None:
        nonlocal result
        result = LauncherOutcome("quit", settings)
        root.destroy()

    button_bar = tk.Frame(root, bg="#141821")
    button_bar.pack(fill="x", padx=20, pady=(10, 18))
    tk.Button(button_bar, text="Quit", width=10, command=quit_launcher).pack(side="right")
    tk.Button(button_bar, text="Launch Simulation", width=18, command=launch).pack(side="right", padx=(0, 10))

    root.protocol("WM_DELETE_WINDOW", quit_launcher)
    root.mainloop()
    return result


def show_finish_popup(*, summary_text: str) -> str:
    root = tk.Tk()
    root.title("Simulation Ended")
    root.configure(bg="#151922")
    root.resizable(False, False)
    _center_window(root, 440, 240)

    result = {"action": "quit"}

    tk.Label(
        root,
        text="Simulation Ended",
        fg="#F2F5F8",
        bg="#151922",
        font=("Segoe UI", 17, "bold"),
    ).pack(anchor="w", padx=20, pady=(18, 8))

    tk.Label(
        root,
        text=summary_text,
        justify="left",
        anchor="w",
        fg="#D8DEE8",
        bg="#1B2130",
        bd=1,
        relief="solid",
        padx=12,
        pady=10,
        font=("Consolas", 9),
    ).pack(fill="x", padx=20)

    tk.Label(
        root,
        text="Run again starts a fresh new simulation. Wait returns to the launcher menu so you can adjust the settings first.",
        justify="left",
        anchor="w",
        fg="#AAB3C2",
        bg="#151922",
        wraplength=390,
        font=("Segoe UI", 9),
    ).pack(fill="x", padx=20, pady=(12, 0))

    button_bar = tk.Frame(root, bg="#151922")
    button_bar.pack(fill="x", padx=20, pady=18)

    def choose(action: str) -> None:
        result["action"] = action
        root.destroy()

    tk.Button(button_bar, text="Quit", width=10, command=lambda: choose("quit")).pack(side="right")
    tk.Button(button_bar, text="Wait", width=10, command=lambda: choose("menu")).pack(side="right", padx=(0, 10))
    tk.Button(button_bar, text="Run Again", width=12, command=lambda: choose("run_again")).pack(side="right", padx=(0, 10))

    root.protocol("WM_DELETE_WINDOW", lambda: choose("quit"))
    root.mainloop()
    return result["action"]
