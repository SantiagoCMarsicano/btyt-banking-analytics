from __future__ import annotations

import hashlib
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from tkinter import messagebox
from typing import Any

import customtkinter as ctk

try:
    import psutil
except ImportError:
    psutil = None


APP_TITLE = "BTYT World Builder"

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = PROJECT_ROOT / "config"
WORLDS_ROOT = PROJECT_ROOT / "worlds"

ACTIVE_CONFIG_PATH = CONFIG_DIR / "world_config.json"
ACTIVE_WORLD_PATH = CONFIG_DIR / "active_world.json"
WORLD_REGISTRY_PATH = WORLDS_ROOT / "registry.json"

ORCHESTRATOR_MODULE = "scripts.generate_btyt"
MANIFEST_MODULE = "scripts.generate_manifest"

STAGES = [
    ("macro", "Macro"),
    ("banks", "Banks"),
    ("financial_institutions", "Financial Institutions"),
    ("branches", "Branches"),
    ("customers", "Customers"),
    ("accounts", "Accounts"),
    ("cards", "Cards"),
    ("loans", "Loans"),
    ("loan_snapshot", "Loan Snapshot"),
    ("external_shocks", "External Shocks"),
    ("transactions", "Transactions"),
    ("campaigns", "Campaigns"),
    ("branch_performance", "Branch Performance"),
    ("operational_exports", "Operational Exports"),
    ("cross_system_audit", "Cross-System Audit"),
]

STAGE_KEYS = [key for key, _ in STAGES]
STAGE_LABELS = {key: label for key, label in STAGES}
DISPLAY_TO_KEY = {"Beginning": None, "Final": None}
DISPLAY_TO_KEY.update({label: key for key, label in STAGES})

STAGE_PATTERN = re.compile(
    r"STAGE\s+(\d+)\s*/\s*(\d+)\s+[—-]\s+.+?\[([a-z0-9_]+)\]",
    flags=re.IGNORECASE,
)

STAGE_PASS_PATTERN = re.compile(
    r"STAGE\s+(\d+)\s*/\s*(\d+)\s+PASS\b",
    flags=re.IGNORECASE,
)

INTERNAL_PROGRESS_PATTERNS = (
    re.compile(
        r"Processed\s+([\d,]+)\s*/\s*([\d,]+)",
        flags=re.IGNORECASE,
    ),
    re.compile(
        r"([\d,]+)\s*/\s*([\d,]+)\s+(?:accounts|customers|rows|records|loans|transactions|items)\b",
        flags=re.IGNORECASE,
    ),
    re.compile(
        r"\.\.\.\s*([\d,]+)\s*/\s*([\d,]+)\s*\|\s*row group rows\s*:",
        flags=re.IGNORECASE,
    ),
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def normalize_world_name(name: str) -> str:
    return " ".join(name.strip().upper().split())


def world_slug(name: str) -> str:
    normalized = normalize_world_name(name)
    safe = "".join(ch if ch.isalnum() else "_" for ch in normalized)
    return "_".join(part for part in safe.split("_") if part) or "WORLD"


def derive_world_seed(name: str, variant: int) -> int:
    identity = f"{normalize_world_name(name)}::{variant}"
    digest = hashlib.sha256(identity.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], byteorder="big", signed=False)


def make_world_id(name: str, variant: int, seed: int) -> str:
    return f"{world_slug(name)}-{variant:02d}-{seed}"


def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default

    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def has_files(path: Path) -> bool:
    return path.exists() and any(item.is_file() for item in path.rglob("*"))


class WorldBuilder(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.title(APP_TITLE)
        self.geometry("1320x860")
        self.minsize(1120, 740)

        self.process: subprocess.Popen[str] | None = None
        self.worker_thread: threading.Thread | None = None
        self.event_queue: queue.Queue[tuple[str, Any]] = queue.Queue()

        self.generation_running = False
        self.paused = False
        self.stop_requested = False
        self.current_phase = "idle"

        self.current_world_root: Path | None = None
        self.current_definition: dict[str, Any] | None = None
        self.log_path: Path | None = None

        self.stage_rows: dict[str, ctk.CTkLabel] = {}
        self.stage_progress_bars: dict[str, ctk.CTkProgressBar] = {}
        self.stage_percent_labels: dict[str, ctk.CTkLabel] = {}
        self.stage_progress_values: dict[str, float] = {
            key: 0.0 for key in STAGE_KEYS
        }
        self.active_stage_key: str | None = None
        self.active_stage_output_ticks = 0

        self._build_variables()
        self._build_layout()
        self._load_existing_identity()
        self._update_control_states()

        self.after(100, self._poll_events)

    # ------------------------------------------------------------------
    # Variables
    # ------------------------------------------------------------------

    def _build_variables(self) -> None:
        self.world_name_var = ctk.StringVar(value="BTYT")
        self.variant_var = ctk.StringVar(value="33")
        self.canonical_var = ctk.BooleanVar(value=True)

        self.population_mode_var = ctk.StringVar(value="range")
        self.population_fixed_var = ctk.StringVar(value="60000")
        self.population_min_var = ctk.StringVar(value="50000")
        self.population_max_var = ctk.StringVar(value="70000")

        self.start_date_var = ctk.StringVar(value="2021-01-01")
        self.end_date_var = ctk.StringVar(value="2026-12-31")

        self.reliability_var = ctk.StringVar(value="realistic")

        self.pipeline_start_var = ctk.StringVar(value="Beginning")
        self.pipeline_end_var = ctk.StringVar(value="Final")

        self.create_manifest_var = ctk.BooleanVar(value=True)
        self.verify_manifest_var = ctk.BooleanVar(value=True)
        self.keep_log_var = ctk.BooleanVar(value=True)
        self.clean_outputs_var = ctk.BooleanVar(value=False)

        self.status_var = ctk.StringVar(value="READY")
        self.detail_var = ctk.StringVar(
            value="Configure the world and press GENERATE WORLD."
        )
        self.progress_var = ctk.DoubleVar(value=0.0)

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build_layout(self) -> None:
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.sidebar = ctk.CTkScrollableFrame(
            self,
            width=350,
            corner_radius=0,
            label_text="WORLD SETTINGS",
        )
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_columnconfigure(0, weight=1)

        self.main = ctk.CTkFrame(self, corner_radius=0)
        self.main.grid(row=0, column=1, sticky="nsew")
        self.main.grid_columnconfigure(0, weight=1)
        self.main.grid_rowconfigure(3, weight=1)

        self._build_sidebar()
        self._build_main_panel()

    def _build_sidebar(self) -> None:
        title = ctk.CTkLabel(
            self.sidebar,
            text="BTYT\nWORLD BUILDER",
            font=ctk.CTkFont(size=29, weight="bold"),
            justify="left",
            anchor="w",
        )
        title.grid(row=0, column=0, sticky="ew", padx=18, pady=(22, 18))

        row = 1

        row = self._section(row, "IDENTITY")
        self.world_name_entry, row = self._grid_entry(
            row, "World Name", self.world_name_var
        )
        self.variant_entry, row = self._grid_entry(
            row, "Variant", self.variant_var
        )

        self.canonical_check = ctk.CTkCheckBox(
            self.sidebar,
            text="Canonical World",
            variable=self.canonical_var,
        )
        self.canonical_check.grid(
            row=row, column=0, sticky="w", padx=18, pady=(4, 12)
        )
        row += 1

        row = self._section(row, "POPULATION")

        self.population_switch = ctk.CTkSegmentedButton(
            self.sidebar,
            values=["Fixed", "Range"],
            command=self._population_mode_changed,
        )
        self.population_switch.set("Range")
        self.population_switch.grid(
            row=row, column=0, sticky="ew", padx=18, pady=(2, 8)
        )
        row += 1

        self.fixed_population_frame = ctk.CTkFrame(
            self.sidebar,
            fg_color="transparent",
        )
        self.fixed_population_frame.grid(
            row=row, column=0, sticky="ew", padx=0, pady=0
        )
        self.fixed_population_frame.grid_columnconfigure(0, weight=1)
        fixed_label = ctk.CTkLabel(
            self.fixed_population_frame,
            text="Customers",
            anchor="w",
        )
        fixed_label.grid(row=0, column=0, sticky="ew", padx=18, pady=(2, 2))
        self.fixed_population_entry = ctk.CTkEntry(
            self.fixed_population_frame,
            textvariable=self.population_fixed_var,
        )
        self.fixed_population_entry.grid(
            row=1, column=0, sticky="ew", padx=18, pady=(0, 8)
        )

        self.range_population_frame = ctk.CTkFrame(
            self.sidebar,
            fg_color="transparent",
        )
        self.range_population_frame.grid(
            row=row, column=0, sticky="ew", padx=0, pady=0
        )
        self.range_population_frame.grid_columnconfigure(0, weight=1)

        min_label = ctk.CTkLabel(
            self.range_population_frame,
            text="Minimum",
            anchor="w",
        )
        min_label.grid(row=0, column=0, sticky="ew", padx=18, pady=(2, 2))
        self.population_min_entry = ctk.CTkEntry(
            self.range_population_frame,
            textvariable=self.population_min_var,
        )
        self.population_min_entry.grid(
            row=1, column=0, sticky="ew", padx=18, pady=(0, 8)
        )

        max_label = ctk.CTkLabel(
            self.range_population_frame,
            text="Maximum",
            anchor="w",
        )
        max_label.grid(row=2, column=0, sticky="ew", padx=18, pady=(2, 2))
        self.population_max_entry = ctk.CTkEntry(
            self.range_population_frame,
            textvariable=self.population_max_var,
        )
        self.population_max_entry.grid(
            row=3, column=0, sticky="ew", padx=18, pady=(0, 8)
        )

        self.fixed_population_frame.grid_remove()
        row += 1

        row = self._section(row, "OBSERVATION PERIOD")
        self.start_date_entry, row = self._grid_entry(
            row, "Start", self.start_date_var
        )
        self.end_date_entry, row = self._grid_entry(
            row, "End", self.end_date_var
        )

        row = self._section(row, "DATA RELIABILITY")

        self.reliability_menu = ctk.CTkOptionMenu(
            self.sidebar,
            variable=self.reliability_var,
            values=["light", "realistic", "stress"],
        )
        self.reliability_menu.grid(
            row=row, column=0, sticky="ew", padx=18, pady=(2, 6)
        )
        row += 1

        reliability_note = ctk.CTkLabel(
            self.sidebar,
            text="Stored with the world definition.",
            text_color=("gray45", "gray65"),
            font=ctk.CTkFont(size=11),
            anchor="w",
        )
        reliability_note.grid(
            row=row, column=0, sticky="ew", padx=18, pady=(0, 10)
        )
        row += 1

        row = self._section(row, "PIPELINE")

        stage_names = [label for _, label in STAGES]

        start_values = ["Beginning"] + stage_names
        self.pipeline_start_menu = ctk.CTkOptionMenu(
            self.sidebar,
            variable=self.pipeline_start_var,
            values=start_values,
        )
        pipeline_start_label = ctk.CTkLabel(
            self.sidebar,
            text="Start from",
            anchor="w",
        )
        pipeline_start_label.grid(
            row=row, column=0, sticky="ew", padx=18, pady=(2, 2)
        )
        row += 1
        self.pipeline_start_menu.grid(
            row=row, column=0, sticky="ew", padx=18, pady=(0, 8)
        )
        row += 1

        end_values = ["Final"] + stage_names
        self.pipeline_end_menu = ctk.CTkOptionMenu(
            self.sidebar,
            variable=self.pipeline_end_var,
            values=end_values,
        )
        pipeline_end_label = ctk.CTkLabel(
            self.sidebar,
            text="Run through",
            anchor="w",
        )
        pipeline_end_label.grid(
            row=row, column=0, sticky="ew", padx=18, pady=(2, 2)
        )
        row += 1
        self.pipeline_end_menu.grid(
            row=row, column=0, sticky="ew", padx=18, pady=(0, 8)
        )
        row += 1

        row = self._section(row, "FINALIZATION")

        self.manifest_check = ctk.CTkCheckBox(
            self.sidebar,
            text="Create final manifest",
            variable=self.create_manifest_var,
        )
        self.manifest_check.grid(
            row=row, column=0, sticky="w", padx=18, pady=(2, 6)
        )
        row += 1

        self.verify_manifest_check = ctk.CTkCheckBox(
            self.sidebar,
            text="Verify manifest after creation",
            variable=self.verify_manifest_var,
        )
        self.verify_manifest_check.grid(
            row=row, column=0, sticky="w", padx=18, pady=(2, 6)
        )
        row += 1

        self.keep_log_check = ctk.CTkCheckBox(
            self.sidebar,
            text="Save World Builder log",
            variable=self.keep_log_var,
        )
        self.keep_log_check.grid(
            row=row, column=0, sticky="w", padx=18, pady=(2, 6)
        )
        row += 1

        self.clean_outputs_check = ctk.CTkCheckBox(
            self.sidebar,
            text="Clean existing outputs first",
            variable=self.clean_outputs_var,
        )
        self.clean_outputs_check.grid(
            row=row, column=0, sticky="w", padx=18, pady=(2, 12)
        )
        row += 1

        row = self._section(row, "TOOLS")

        self.open_folder_button = ctk.CTkButton(
            self.sidebar,
            text="OPEN WORLD FOLDER",
            command=self.open_world_folder,
            height=36,
        )
        self.open_folder_button.grid(
            row=row, column=0, sticky="ew", padx=18, pady=(2, 6)
        )
        row += 1

        self.reset_pipeline_button = ctk.CTkButton(
            self.sidebar,
            text="FULL PIPELINE",
            command=self.reset_pipeline_selection,
            height=36,
        )
        self.reset_pipeline_button.grid(
            row=row, column=0, sticky="ew", padx=18, pady=(2, 20)
        )

    def _build_main_panel(self) -> None:
        header = ctk.CTkFrame(self.main, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=34, pady=(30, 14))
        header.grid_columnconfigure(0, weight=1)

        self.world_title = ctk.CTkLabel(
            header,
            text="BTYT",
            font=ctk.CTkFont(size=34, weight="bold"),
            anchor="w",
        )
        self.world_title.grid(row=0, column=0, sticky="w")

        self.world_subtitle = ctk.CTkLabel(
            header,
            text="Variant 33 · Ready",
            font=ctk.CTkFont(size=15),
            text_color=("gray45", "gray65"),
            anchor="w",
        )
        self.world_subtitle.grid(row=1, column=0, sticky="w", pady=(4, 0))

        status_card = ctk.CTkFrame(self.main)
        status_card.grid(row=1, column=0, sticky="ew", padx=34, pady=(0, 14))
        status_card.grid_columnconfigure(0, weight=1)

        self.status_label = ctk.CTkLabel(
            status_card,
            textvariable=self.status_var,
            font=ctk.CTkFont(size=21, weight="bold"),
            anchor="w",
        )
        self.status_label.grid(
            row=0, column=0, sticky="w", padx=20, pady=(16, 2)
        )

        self.detail_label = ctk.CTkLabel(
            status_card,
            textvariable=self.detail_var,
            anchor="w",
        )
        self.detail_label.grid(
            row=1, column=0, sticky="w", padx=20, pady=(0, 10)
        )

        overall_row = ctk.CTkFrame(
            status_card,
            fg_color="transparent",
        )
        overall_row.grid(
            row=2,
            column=0,
            sticky="ew",
            padx=20,
            pady=(0, 4),
        )
        overall_row.grid_columnconfigure(0, weight=1)

        overall_label = ctk.CTkLabel(
            overall_row,
            text="OVERALL PROGRESS",
            anchor="w",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=("gray45", "gray65"),
        )
        overall_label.grid(row=0, column=0, sticky="w")

        self.overall_percent_label = ctk.CTkLabel(
            overall_row,
            text="0%",
            anchor="e",
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        self.overall_percent_label.grid(row=0, column=1, sticky="e")

        self.progress = ctk.CTkProgressBar(
            status_card,
            variable=self.progress_var,
            height=15,
        )
        self.progress.grid(
            row=3, column=0, sticky="ew", padx=20, pady=(0, 18)
        )
        self.progress.set(0)

        self.progress_var.trace_add(
            "write",
            lambda *_: self.overall_percent_label.configure(
                text=f"{round(max(0.0, min(self.progress_var.get(), 1.0)) * 100):d}%"
            ),
        )

        controls = ctk.CTkFrame(self.main, fg_color="transparent")
        controls.grid(row=2, column=0, sticky="ew", padx=34, pady=(0, 14))
        for column in range(4):
            controls.grid_columnconfigure(column, weight=1)

        self.generate_button = ctk.CTkButton(
            controls,
            text="GENERATE WORLD",
            command=self.generate_world,
            height=46,
            font=ctk.CTkFont(size=15, weight="bold"),
        )
        self.generate_button.grid(
            row=0, column=0, sticky="ew", padx=(0, 6)
        )

        self.pause_button = ctk.CTkButton(
            controls,
            text="PAUSE",
            command=self.pause_generation,
            height=46,
        )
        self.pause_button.grid(
            row=0, column=1, sticky="ew", padx=6
        )

        self.resume_button = ctk.CTkButton(
            controls,
            text="RESUME",
            command=self.resume_generation,
            height=46,
        )
        self.resume_button.grid(
            row=0, column=2, sticky="ew", padx=6
        )

        self.stop_button = ctk.CTkButton(
            controls,
            text="STOP",
            command=self.stop_generation,
            height=46,
        )
        self.stop_button.grid(
            row=0, column=3, sticky="ew", padx=(6, 0)
        )

        content = ctk.CTkFrame(self.main, fg_color="transparent")
        content.grid(
            row=3, column=0, sticky="nsew", padx=34, pady=(0, 26)
        )
        content.grid_columnconfigure(0, weight=0)
        content.grid_columnconfigure(1, weight=1)
        content.grid_rowconfigure(0, weight=1)

        stages_card = ctk.CTkScrollableFrame(
            content,
            width=320,
            label_text="Generation Pipeline",
        )
        stages_card.grid(
            row=0, column=0, sticky="nsew", padx=(0, 8)
        )
        stages_card.grid_columnconfigure(0, weight=1)

        for index, (key, label) in enumerate(STAGES, start=1):
            stage_frame = ctk.CTkFrame(
                stages_card,
                fg_color="transparent",
            )
            stage_frame.grid(
                row=index - 1,
                column=0,
                sticky="ew",
                padx=8,
                pady=5,
            )
            stage_frame.grid_columnconfigure(0, weight=1)

            row_label = ctk.CTkLabel(
                stage_frame,
                text=f"○  {index:02d}  {label}",
                anchor="w",
                font=ctk.CTkFont(size=13),
            )
            row_label.grid(
                row=0,
                column=0,
                sticky="ew",
                padx=(2, 8),
                pady=(0, 3),
            )

            percent_label = ctk.CTkLabel(
                stage_frame,
                text="0%",
                width=44,
                anchor="e",
                font=ctk.CTkFont(size=12),
                text_color=("gray45", "gray65"),
            )
            percent_label.grid(
                row=0,
                column=1,
                sticky="e",
                padx=(4, 2),
                pady=(0, 3),
            )

            stage_bar = ctk.CTkProgressBar(
                stage_frame,
                height=8,
            )
            stage_bar.grid(
                row=1,
                column=0,
                columnspan=2,
                sticky="ew",
                padx=2,
                pady=(0, 2),
            )
            stage_bar.set(0.0)

            self.stage_rows[key] = row_label
            self.stage_percent_labels[key] = percent_label
            self.stage_progress_bars[key] = stage_bar

        log_card = ctk.CTkFrame(content)
        log_card.grid(
            row=0, column=1, sticky="nsew", padx=(8, 0)
        )
        log_card.grid_columnconfigure(0, weight=1)
        log_card.grid_rowconfigure(1, weight=1)

        log_title = ctk.CTkLabel(
            log_card,
            text="LIVE ENGINE OUTPUT",
            font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w",
        )
        log_title.grid(
            row=0, column=0, sticky="ew", padx=14, pady=(12, 6)
        )

        self.log_box = ctk.CTkTextbox(
            log_card,
            wrap="word",
            font=ctk.CTkFont(family="Consolas", size=12),
        )
        self.log_box.grid(
            row=1, column=0, sticky="nsew", padx=12, pady=(0, 12)
        )
        self.log_box.configure(state="disabled")

    def _section(self, row: int, text: str) -> int:
        label = ctk.CTkLabel(
            self.sidebar,
            text=text,
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=("gray45", "gray62"),
            anchor="w",
        )
        label.grid(
            row=row, column=0, sticky="ew", padx=18, pady=(10, 5)
        )
        return row + 1

    def _grid_entry(
        self,
        row: int,
        label_text: str,
        variable: ctk.StringVar,
    ) -> tuple[ctk.CTkEntry, int]:
        label = ctk.CTkLabel(
            self.sidebar,
            text=label_text,
            anchor="w",
        )
        label.grid(
            row=row, column=0, sticky="ew", padx=18, pady=(2, 2)
        )
        row += 1

        entry = ctk.CTkEntry(
            self.sidebar,
            textvariable=variable,
        )
        entry.grid(
            row=row, column=0, sticky="ew", padx=18, pady=(0, 8)
        )
        return entry, row + 1

    # ------------------------------------------------------------------
    # UI helpers
    # ------------------------------------------------------------------

    def _population_mode_changed(self, value: str) -> None:
        if value == "Fixed":
            self.population_mode_var.set("fixed")
            self.range_population_frame.grid_remove()
            self.fixed_population_frame.grid()
        else:
            self.population_mode_var.set("range")
            self.fixed_population_frame.grid_remove()
            self.range_population_frame.grid()

    def _refresh_identity_text(self) -> None:
        name = normalize_world_name(self.world_name_var.get()) or "WORLD"
        variant = self.variant_var.get().strip() or "?"
        self.world_title.configure(text=name)
        self.world_subtitle.configure(
            text=f"Variant {variant} · Ready"
        )

    def _append_log(self, line: str) -> None:
        self.log_box.configure(state="normal")
        self.log_box.insert("end", line + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _clear_log(self) -> None:
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")

    def _update_control_states(self) -> None:
        running = self.generation_running
        paused = self.paused

        self.generate_button.configure(
            state="disabled" if running else "normal",
            text="GENERATING..." if running else "GENERATE WORLD",
        )

        pause_available = running and not paused and psutil is not None
        resume_available = running and paused and psutil is not None

        self.pause_button.configure(
            state="normal" if pause_available else "disabled"
        )
        self.resume_button.configure(
            state="normal" if resume_available else "disabled"
        )
        self.stop_button.configure(
            state="normal" if running else "disabled"
        )

    def reset_pipeline_selection(self) -> None:
        if self.generation_running:
            return
        self.pipeline_start_var.set("Beginning")
        self.pipeline_end_var.set("Final")

    # ------------------------------------------------------------------
    # Existing world loading
    # ------------------------------------------------------------------

    def _load_existing_identity(self) -> None:
        active = load_json(ACTIVE_WORLD_PATH, default={}) or {}
        config = load_json(ACTIVE_CONFIG_PATH, default={}) or {}

        if active.get("world_name"):
            self.world_name_var.set(str(active["world_name"]))

        if active.get("variant") is not None:
            self.variant_var.set(str(active["variant"]))

        population = config.get("population", {})
        if isinstance(population, dict):
            if "customers" in population:
                self.population_fixed_var.set(
                    str(population["customers"])
                )
                self.population_switch.set("Fixed")
                self._population_mode_changed("Fixed")
            elif (
                "customers_min" in population
                and "customers_max" in population
            ):
                self.population_min_var.set(
                    str(population["customers_min"])
                )
                self.population_max_var.set(
                    str(population["customers_max"])
                )
                self.population_switch.set("Range")
                self._population_mode_changed("Range")

        observation = config.get("observation_period", {})
        if isinstance(observation, dict):
            if observation.get("start_date"):
                self.start_date_var.set(
                    str(observation["start_date"])
                )

            if observation.get("end_date"):
                self.end_date_var.set(
                    str(observation["end_date"])
                )

        reliability = config.get("data_reliability", {})
        if (
            isinstance(reliability, dict)
            and reliability.get("level") in {"light", "realistic", "stress"}
        ):
            self.reliability_var.set(str(reliability["level"]))

        self._refresh_identity_text()

    # ------------------------------------------------------------------
    # Validation and world preparation
    # ------------------------------------------------------------------

    def _validated_inputs(self) -> dict[str, Any]:
        name = normalize_world_name(self.world_name_var.get())
        if not name:
            raise ValueError("World Name cannot be empty.")

        try:
            variant = int(self.variant_var.get())
        except ValueError as exc:
            raise ValueError("Variant must be an integer.") from exc

        if variant < 1:
            raise ValueError("Variant must be >= 1.")

        population: dict[str, int]
        if self.population_mode_var.get() == "fixed":
            try:
                customers = int(self.population_fixed_var.get())
            except ValueError as exc:
                raise ValueError("Customers must be an integer.") from exc

            if customers <= 0:
                raise ValueError("Customers must be positive.")

            population = {"customers": customers}
        else:
            try:
                customers_min = int(self.population_min_var.get())
                customers_max = int(self.population_max_var.get())
            except ValueError as exc:
                raise ValueError(
                    "Population minimum and maximum must be integers."
                ) from exc

            if customers_min <= 0 or customers_max <= 0:
                raise ValueError("Population bounds must be positive.")

            if customers_min > customers_max:
                raise ValueError(
                    "Population minimum cannot exceed population maximum."
                )

            population = {
                "customers_min": customers_min,
                "customers_max": customers_max,
            }

        start_date = self.start_date_var.get().strip()
        end_date = self.end_date_var.get().strip()

        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", start_date):
            raise ValueError("Start date must use YYYY-MM-DD.")

        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", end_date):
            raise ValueError("End date must use YYYY-MM-DD.")

        start_display = self.pipeline_start_var.get()
        end_display = self.pipeline_end_var.get()

        start_key = DISPLAY_TO_KEY.get(start_display)
        end_key = DISPLAY_TO_KEY.get(end_display)

        if start_display != "Beginning" and start_key is None:
            raise ValueError("Invalid pipeline start stage.")

        if end_display != "Final" and end_key is None:
            raise ValueError("Invalid pipeline end stage.")

        start_index = 0 if start_key is None else STAGE_KEYS.index(start_key)
        end_index = len(STAGE_KEYS) - 1 if end_key is None else STAGE_KEYS.index(end_key)

        if start_index > end_index:
            raise ValueError(
                "Pipeline start stage cannot come after the end stage."
            )

        seed = derive_world_seed(name, variant)

        return {
            "world_name": name,
            "variant": variant,
            "seed": seed,
            "world_id": make_world_id(name, variant, seed),
            "population": population,
            "start_date": start_date,
            "end_date": end_date,
            "reliability": self.reliability_var.get(),
            "canonical": bool(self.canonical_var.get()),
            "start_key": start_key,
            "end_key": end_key,
            "start_index": start_index,
            "end_index": end_index,
            "create_manifest": bool(self.create_manifest_var.get()),
            "verify_manifest": bool(self.verify_manifest_var.get()),
            "keep_log": bool(self.keep_log_var.get()),
            "clean_outputs": bool(self.clean_outputs_var.get()),
        }

    def _world_root(self, definition: dict[str, Any]) -> Path:
        return (
            WORLDS_ROOT
            / world_slug(definition["world_name"])
            / f"{definition['variant']:02d}"
        )

    def _prepare_world(self, definition: dict[str, Any]) -> Path:
        world_root = self._world_root(definition)

        for path in (
            world_root,
            world_root / "audit",
            world_root / "data" / "generated",
            world_root / "data" / "interim",
            world_root / "data" / "operational",
            world_root / "database",
            world_root / "manifests",
        ):
            path.mkdir(parents=True, exist_ok=True)

        existing_config = load_json(ACTIVE_CONFIG_PATH, default={}) or {}
        existing_world = load_json(world_root / "world.json", default={}) or {}

        config_payload = dict(existing_config)

        # BTYT Core consumes a nested configuration schema. Keep that schema
        # authoritative and remove stale flat aliases that could create two
        # contradictory world identities in the same JSON file.
        world_section = dict(config_payload.get("world", {}))
        world_section.update(
            {
                "name": definition["world_name"],
                "seed": definition["seed"],
            }
        )
        config_payload["world"] = world_section

        population_section = dict(config_payload.get("population", {}))
        population_section.pop("customers", None)
        population_section.pop("customers_min", None)
        population_section.pop("customers_max", None)
        population_section.update(definition["population"])
        config_payload["population"] = population_section

        observation_section = dict(
            config_payload.get("observation_period", {})
        )
        observation_section.update(
            {
                "start_date": definition["start_date"],
                "end_date": definition["end_date"],
            }
        )
        config_payload["observation_period"] = observation_section

        reliability_section = dict(
            config_payload.get("data_reliability", {})
        )
        reliability_section["level"] = definition["reliability"]
        config_payload["data_reliability"] = reliability_section

        # Variant is Builder metadata. It is harmless at top level and useful
        # for human inspection, while world identity itself remains canonical
        # inside the nested "world" section.
        config_payload["variant"] = definition["variant"]

        # Remove obsolete flat aliases created by earlier Builder versions.
        for legacy_key in (
            "world_seed",
            "world_name",
            "name",
            "seed",
            "start_date",
            "end_date",
            "customers",
            "customers_min",
            "customers_max",
        ):
            config_payload.pop(legacy_key, None)

        world_payload = dict(existing_world)
        world_payload.update(
            {
                "world_name": definition["world_name"],
                "variant": definition["variant"],
                "world_id": definition["world_id"],
                "world_seed": definition["seed"],
                "canonical": definition["canonical"],
                "start_date": definition["start_date"],
                "end_date": definition["end_date"],
                "data_reliability_level": definition["reliability"],
                "population": definition["population"],
                "updated_at_utc": utc_now_iso(),
            }
        )
        world_payload.setdefault("created_at_utc", utc_now_iso())

        metadata = load_json(world_root / "metadata.json", default={}) or {}
        metadata.update(
            {
                "world_name": definition["world_name"],
                "variant": definition["variant"],
                "world_id": definition["world_id"],
                "seed": definition["seed"],
                "canonical": definition["canonical"],
                "status": "READY",
                "active": True,
                "updated_at_utc": utc_now_iso(),
            }
        )
        metadata.setdefault("created_at_utc", utc_now_iso())

        relative_world_path = str(world_root.relative_to(PROJECT_ROOT))

        active_pointer = {
            "world_name": definition["world_name"],
            "variant": definition["variant"],
            "path": relative_world_path,
        }

        write_json(world_root / "world.json", world_payload)
        write_json(world_root / "metadata.json", metadata)
        write_json(ACTIVE_CONFIG_PATH, config_payload)
        write_json(ACTIVE_WORLD_PATH, active_pointer)

        self._verify_active_identity(definition, world_root)

        self._update_registry(
            definition=definition,
            world_root=world_root,
            status="READY",
        )

        self.current_world_root = world_root
        self.current_definition = definition
        self.log_path = world_root / "audit" / "world_builder_generation.log"

        return world_root

    def _verify_active_identity(
        self,
        definition: dict[str, Any],
        world_root: Path,
    ) -> None:
        """Refuse generation if BTYT Core would load a stale world identity."""
        config = load_json(ACTIVE_CONFIG_PATH, default={}) or {}
        active = load_json(ACTIVE_WORLD_PATH, default={}) or {}

        expected_name = definition["world_name"]
        expected_variant = definition["variant"]
        expected_seed = definition["seed"]
        expected_path = Path(
            str(world_root.relative_to(PROJECT_ROOT))
        )

        world_section = config.get("world")
        if not isinstance(world_section, dict):
            raise RuntimeError(
                "world_config.json is missing the canonical nested 'world' section."
            )

        actual_name = world_section.get("name")
        actual_seed = world_section.get("seed")

        if actual_name != expected_name:
            raise RuntimeError(
                "BTYT Core world name is stale. "
                f"Expected {expected_name!r}, found {actual_name!r}."
            )

        try:
            actual_seed_int = int(actual_seed)
        except (TypeError, ValueError) as exc:
            raise RuntimeError(
                "BTYT Core world seed is missing or invalid."
            ) from exc

        if actual_seed_int != expected_seed:
            raise RuntimeError(
                "BTYT Core world seed is stale. "
                f"Expected {expected_seed}, found {actual_seed_int}."
            )

        population_section = config.get("population")
        if not isinstance(population_section, dict):
            raise RuntimeError(
                "world_config.json is missing the canonical nested "
                "'population' section."
            )

        expected_population = definition["population"]
        for key, expected_value in expected_population.items():
            if population_section.get(key) != expected_value:
                raise RuntimeError(
                    "BTYT Core population config is stale. "
                    f"Expected {key}={expected_value}, "
                    f"found {population_section.get(key)!r}."
                )

        observation_section = config.get("observation_period")
        if not isinstance(observation_section, dict):
            raise RuntimeError(
                "world_config.json is missing the canonical nested "
                "'observation_period' section."
            )

        if observation_section.get("start_date") != definition["start_date"]:
            raise RuntimeError(
                "BTYT Core start_date does not match the selected world."
            )

        if observation_section.get("end_date") != definition["end_date"]:
            raise RuntimeError(
                "BTYT Core end_date does not match the selected world."
            )

        if active.get("world_name") != expected_name:
            raise RuntimeError(
                "active_world.json world_name does not match the selected world."
            )

        try:
            active_variant = int(active.get("variant", -1))
        except (TypeError, ValueError):
            active_variant = -1

        if active_variant != expected_variant:
            raise RuntimeError(
                "active_world.json variant does not match the selected world."
            )

        active_path = Path(str(active.get("path", "")))
        if active_path != expected_path:
            raise RuntimeError(
                "active_world.json path does not match the selected world directory."
            )

    def _update_registry(
        self,
        definition: dict[str, Any],
        world_root: Path,
        status: str,
    ) -> None:
        registry = load_json(
            WORLD_REGISTRY_PATH,
            default={"worlds": []},
        ) or {"worlds": []}

        worlds = registry.setdefault("worlds", [])
        path_string = str(world_root.relative_to(PROJECT_ROOT))

        new_record = {
            "world_id": definition["world_id"],
            "world_name": definition["world_name"],
            "variant": definition["variant"],
            "seed": definition["seed"],
            "canonical": definition["canonical"],
            "path": path_string,
            "status": status,
        }

        replaced = False

        for index, record in enumerate(worlds):
            same_identity = (
                record.get("world_name") == definition["world_name"]
                and int(record.get("variant", -1)) == definition["variant"]
            )

            if same_identity:
                worlds[index] = new_record
                replaced = True
                break

        if not replaced:
            worlds.append(new_record)

        if definition["canonical"]:
            for record in worlds:
                same_identity = (
                    record.get("world_name") == definition["world_name"]
                    and int(record.get("variant", -1)) == definition["variant"]
                )
                if not same_identity:
                    record["canonical"] = False

        write_json(WORLD_REGISTRY_PATH, registry)

    def _set_world_status(
        self,
        definition: dict[str, Any],
        status: str,
        detail: str | None = None,
    ) -> None:
        world_root = self._world_root(definition)
        metadata_path = world_root / "metadata.json"
        metadata = load_json(metadata_path, default={}) or {}

        metadata.update(
            {
                "status": status,
                "updated_at_utc": utc_now_iso(),
            }
        )

        if status == "GENERATING":
            metadata["generation_started_at_utc"] = utc_now_iso()
            metadata.pop("generation_finished_at_utc", None)

        if status in {"COMPLETE", "FAILED", "STOPPED"}:
            metadata["generation_finished_at_utc"] = utc_now_iso()

        if detail:
            metadata["status_detail"] = detail

        write_json(metadata_path, metadata)
        self._update_registry(definition, world_root, status)

    # ------------------------------------------------------------------
    # Cleaning and tools
    # ------------------------------------------------------------------

    def _clean_existing_outputs(self, world_root: Path) -> None:
        targets = (
            world_root / "data" / "generated",
            world_root / "data" / "interim",
            world_root / "data" / "operational",
            world_root / "database",
            world_root / "manifests",
        )

        for target in targets:
            if target.exists():
                shutil.rmtree(target)
            target.mkdir(parents=True, exist_ok=True)

    def open_world_folder(self) -> None:
        try:
            definition = self._validated_inputs()
            world_root = self._world_root(definition)
        except Exception:
            world_root = self.current_world_root

        if world_root is None:
            return

        world_root.mkdir(parents=True, exist_ok=True)

        if os.name == "nt":
            os.startfile(world_root)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(world_root)])
        else:
            subprocess.Popen(["xdg-open", str(world_root)])

    # ------------------------------------------------------------------
    # Generation lifecycle
    # ------------------------------------------------------------------

    def generate_world(self) -> None:
        if self.generation_running:
            return

        try:
            definition = self._validated_inputs()
            world_root = self._world_root(definition)

            if definition["clean_outputs"] and has_files(world_root / "data"):
                confirmed = messagebox.askyesno(
                    "Clean existing outputs",
                    (
                        "This will delete existing generated, interim, operational, "
                        "database, and manifest outputs for this world before generation.\n\n"
                        "Continue?"
                    ),
                )
                if not confirmed:
                    return

            self._prepare_world(definition)

            if definition["clean_outputs"]:
                self._clean_existing_outputs(world_root)

        except Exception as exc:
            self.status_var.set("VALIDATION FAILED")
            self.detail_var.set(str(exc))
            return

        if psutil is None:
            self._append_log(
                "WARNING: psutil is not installed. PAUSE/RESUME will be unavailable."
            )
            self._append_log(
                "Install it in the project environment with: pip install psutil"
            )

        self._clear_log()
        self._refresh_identity_text()
        self._reset_stage_display(definition)

        self.generation_running = True
        self.paused = False
        self.stop_requested = False
        self.current_phase = "check"

        self.progress_var.set(0.0)
        self.status_var.set("PREPARING WORLD")
        self.detail_var.set("Validating the isolated BTYT engine.")

        self._update_control_states()

        self.worker_thread = threading.Thread(
            target=self._generation_worker,
            args=(definition,),
            daemon=True,
        )
        self.worker_thread.start()

    def _generation_worker(self, definition: dict[str, Any]) -> None:
        try:
            self._set_world_status(definition, "CHECKING")

            check_code = self._run_command(
                [
                    sys.executable,
                    "-u",
                    "-m",
                    ORCHESTRATOR_MODULE,
                    "--check-only",
                ],
                phase="check",
            )

            if self.stop_requested:
                raise InterruptedError("Generation stopped by user.")

            if check_code != 0:
                raise RuntimeError(
                    f"Engine preflight failed with exit code {check_code}."
                )

            self.event_queue.put(("check_pass", None))
            self._set_world_status(definition, "GENERATING")

            command = [
                sys.executable,
                "-u",
                "-m",
                ORCHESTRATOR_MODULE,
            ]

            if definition["start_key"] is not None:
                command.extend(
                    ["--from-stage", definition["start_key"]]
                )

            if definition["end_key"] is not None:
                command.extend(
                    ["--to-stage", definition["end_key"]]
                )

            generation_code = self._run_command(
                command,
                phase="generate",
            )

            if self.stop_requested:
                raise InterruptedError("Generation stopped by user.")

            if generation_code != 0:
                raise RuntimeError(
                    f"World generation failed with exit code {generation_code}."
                )

            self.event_queue.put(("generation_pass", None))

            reaches_final_audit = (
                definition["end_index"] == len(STAGE_KEYS) - 1
            )

            if definition["create_manifest"] and reaches_final_audit:
                manifest_code = self._run_command(
                    [
                        sys.executable,
                        "-u",
                        "-m",
                        MANIFEST_MODULE,
                    ],
                    phase="manifest",
                )

                if self.stop_requested:
                    raise InterruptedError("Generation stopped by user.")

                if manifest_code != 0:
                    raise RuntimeError(
                        f"Final manifest failed with exit code {manifest_code}."
                    )

                if definition["verify_manifest"]:
                    verify_code = self._run_command(
                        [
                            sys.executable,
                            "-u",
                            "-m",
                            MANIFEST_MODULE,
                            "--verify-only",
                        ],
                        phase="verify",
                    )

                    if self.stop_requested:
                        raise InterruptedError("Generation stopped by user.")

                    if verify_code != 0:
                        raise RuntimeError(
                            f"Manifest verification failed with exit code {verify_code}."
                        )

            elif definition["create_manifest"] and not reaches_final_audit:
                self.event_queue.put(
                    (
                        "notice",
                        (
                            "Manifest skipped because the selected pipeline "
                            "does not reach Cross-System Audit."
                        ),
                    )
                )

            final_status = (
                "COMPLETE"
                if reaches_final_audit
                else "PARTIAL_COMPLETE"
            )

            self._set_world_status(definition, final_status)
            self.event_queue.put(
                (
                    "complete",
                    {
                        **definition,
                        "final_status": final_status,
                    },
                )
            )

        except InterruptedError as exc:
            self._set_world_status(
                definition,
                "STOPPED",
                detail=str(exc),
            )
            self.event_queue.put(("stopped", str(exc)))

        except Exception as exc:
            self._set_world_status(
                definition,
                "FAILED",
                detail=str(exc),
            )
            self.event_queue.put(("failed", str(exc)))

        finally:
            self.process = None
            self.current_phase = "idle"

    def _run_command(self, command: list[str], phase: str) -> int:
        self.current_phase = phase

        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"

        self.process = subprocess.Popen(
            command,
            cwd=PROJECT_ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )

        assert self.process.stdout is not None

        for raw_line in self.process.stdout:
            line = raw_line.rstrip("\r\n")
            self.event_queue.put(
                ("log", {"phase": phase, "line": line})
            )

            if self.keep_log_var.get() and self.log_path is not None:
                self.log_path.parent.mkdir(
                    parents=True,
                    exist_ok=True,
                )
                with self.log_path.open(
                    "a",
                    encoding="utf-8",
                ) as handle:
                    handle.write(
                        f"[{utc_now_iso()}] [{phase.upper()}] {line}\n"
                    )

            if phase == "generate":
                match = STAGE_PATTERN.search(line)
                if match:
                    stage_number = int(match.group(1))
                    total = int(match.group(2))
                    key = match.group(3).lower()

                    self.event_queue.put(
                        (
                            "stage_started",
                            {
                                "number": stage_number,
                                "total": total,
                                "key": key,
                            },
                        )
                    )

                pass_match = STAGE_PASS_PATTERN.search(line)
                if pass_match:
                    self.event_queue.put(
                        (
                            "stage_passed",
                            {
                                "number": int(pass_match.group(1)),
                                "total": int(pass_match.group(2)),
                            },
                        )
                    )
                else:
                    self.event_queue.put(
                        ("stage_output", line)
                    )

        return self.process.wait()

    # ------------------------------------------------------------------
    # Pause / Resume / Stop
    # ------------------------------------------------------------------

    def _current_process_tree(self) -> list[Any]:
        if self.process is None or self.process.poll() is not None:
            return []

        if psutil is None:
            return []

        try:
            parent = psutil.Process(self.process.pid)
            children = parent.children(recursive=True)
            return children + [parent]
        except psutil.Error:
            return []

    def pause_generation(self) -> None:
        if not self.generation_running or self.paused:
            return

        if psutil is None:
            self.status_var.set("PAUSE UNAVAILABLE")
            self.detail_var.set(
                "Install psutil in the project environment: pip install psutil"
            )
            return

        processes = self._current_process_tree()
        if not processes:
            return

        suspended = 0

        for process in processes:
            try:
                process.suspend()
                suspended += 1
            except psutil.Error:
                pass

        if suspended:
            self.paused = True
            self.status_var.set("PAUSED")
            self.detail_var.set(
                f"Generation suspended during {self.current_phase}."
            )
            self._append_log("=== WORLD GENERATION PAUSED ===")
            self._update_control_states()

            if self.current_definition is not None:
                self._set_world_status(
                    self.current_definition,
                    "PAUSED",
                )

    def resume_generation(self) -> None:
        if not self.generation_running or not self.paused:
            return

        if psutil is None:
            return

        processes = self._current_process_tree()
        resumed = 0

        # Resume the parent first so it can continue managing children.
        for process in reversed(processes):
            try:
                process.resume()
                resumed += 1
            except psutil.Error:
                pass

        if resumed:
            self.paused = False
            self.status_var.set("GENERATING WORLD")
            self.detail_var.set(
                f"Generation resumed during {self.current_phase}."
            )
            self._append_log("=== WORLD GENERATION RESUMED ===")
            self._update_control_states()

            if self.current_definition is not None:
                self._set_world_status(
                    self.current_definition,
                    "GENERATING",
                )

    def stop_generation(self) -> None:
        if not self.generation_running:
            return

        confirmed = messagebox.askyesno(
            "Stop generation",
            (
                "Stop the current BTYT generation?\n\n"
                "Completed stage outputs will remain on disk. "
                "The world will be marked STOPPED and can later be "
                "resumed from a selected pipeline stage."
            ),
        )

        if not confirmed:
            return

        self.stop_requested = True
        self.status_var.set("STOPPING")
        self.detail_var.set("Terminating the current generation process tree.")
        self._append_log("=== STOP REQUESTED ===")

        self._terminate_process_tree()

    def _terminate_process_tree(self) -> None:
        if self.process is None or self.process.poll() is not None:
            return

        if psutil is not None:
            try:
                parent = psutil.Process(self.process.pid)
                processes = parent.children(recursive=True) + [parent]

                for process in processes:
                    try:
                        if process.status() == psutil.STATUS_STOPPED:
                            process.resume()
                    except psutil.Error:
                        pass

                for process in processes:
                    try:
                        process.terminate()
                    except psutil.Error:
                        pass

                _, alive = psutil.wait_procs(
                    processes,
                    timeout=3,
                )

                for process in alive:
                    try:
                        process.kill()
                    except psutil.Error:
                        pass

                return

            except psutil.Error:
                pass

        if os.name == "nt":
            subprocess.run(
                [
                    "taskkill",
                    "/PID",
                    str(self.process.pid),
                    "/T",
                    "/F",
                ],
                capture_output=True,
                text=True,
            )
        else:
            try:
                self.process.terminate()
            except OSError:
                pass

    # ------------------------------------------------------------------
    # Progress tracking
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_count(value: str) -> int:
        """Parse a human-readable integer such as '3,622,644'."""
        return int(value.replace(",", "").strip())

    def _set_stage_progress(
        self,
        key: str,
        fraction: float,
    ) -> None:
        """Update one stage and recompute overall selected-pipeline progress."""
        if key not in self.stage_progress_values:
            return

        fraction = max(0.0, min(float(fraction), 1.0))
        previous = self.stage_progress_values[key]

        # Never move a stage backwards during one run.
        fraction = max(previous, fraction)
        self.stage_progress_values[key] = fraction

        bar = self.stage_progress_bars.get(key)
        label = self.stage_percent_labels.get(key)

        if bar is not None:
            bar.set(fraction)

        if label is not None:
            label.configure(text=f"{round(fraction * 100):d}%")

        self._recompute_overall_progress()

    def _recompute_overall_progress(self) -> None:
        """Compute total progress from the selected stage interval."""
        definition = self.current_definition
        if definition is None:
            return

        selected_keys = STAGE_KEYS[
            definition["start_index"] : definition["end_index"] + 1
        ]

        if not selected_keys:
            self.progress_var.set(0.0)
            return

        total = sum(
            self.stage_progress_values.get(key, 0.0)
            for key in selected_keys
        )
        self.progress_var.set(total / len(selected_keys))

    def _extract_internal_progress(
        self,
        line: str,
    ) -> float | None:
        """Extract exact within-stage progress when a generator reports x/y."""
        for pattern in INTERNAL_PROGRESS_PATTERNS:
            match = pattern.search(line)
            if not match:
                continue

            try:
                current = self._parse_count(match.group(1))
                total = self._parse_count(match.group(2))
            except (ValueError, IndexError):
                continue

            if total <= 0:
                continue

            return max(0.0, min(current / total, 0.98))

        return None

    def _observe_stage_output(self, line: str) -> None:
        """
        Advance the active stage while output is flowing.

        Exact x/y progress wins when available. Otherwise the bar moves
        conservatively and never exceeds 90% until the orchestrator confirms PASS.
        """
        key = self.active_stage_key
        if key is None:
            return

        exact = self._extract_internal_progress(line)
        if exact is not None:
            self._set_stage_progress(key, exact)
            return

        self.active_stage_output_ticks += 1
        current = self.stage_progress_values.get(key, 0.0)

        # Conservative asymptotic activity progress:
        # starts visibly, slows down, and never claims completion.
        if current < 0.90:
            increment = max(0.003, (0.90 - current) * 0.055)
            self._set_stage_progress(
                key,
                min(current + increment, 0.90),
            )

    # ------------------------------------------------------------------
    # Event handling
    # ------------------------------------------------------------------

    def _poll_events(self) -> None:
        try:
            while True:
                event, payload = self.event_queue.get_nowait()
                self._handle_event(event, payload)
        except queue.Empty:
            pass

        self.after(100, self._poll_events)

    def _handle_event(self, event: str, payload: Any) -> None:
        if event == "log":
            phase = payload["phase"]
            line = payload["line"]

            if not line:
                return

            self._append_log(line)

            if not self.paused:
                if phase == "check":
                    self.status_var.set("ENGINE CHECK")
                    self.detail_var.set(line[-180:])
                elif phase == "generate":
                    self.detail_var.set(line[-180:])
                elif phase == "manifest":
                    self.status_var.set("FREEZING WORLD")
                    self.detail_var.set(line[-180:])
                elif phase == "verify":
                    self.status_var.set("VERIFYING WORLD")
                    self.detail_var.set(line[-180:])

        elif event == "check_pass":
            self.status_var.set("GENERATING WORLD")
            self.detail_var.set(
                "Engine preflight passed. Starting selected pipeline."
            )

        elif event == "stage_started":
            number = payload["number"]
            total = payload["total"]
            key = payload["key"]

            self.active_stage_key = key
            self.active_stage_output_ticks = 0

            if self.current_definition is not None:
                self._mark_stage_started(
                    key,
                    self.current_definition,
                )
                self._set_stage_progress(key, 0.02)

            label = STAGE_LABELS.get(
                key,
                key.replace("_", " ").title(),
            )
            self.status_var.set("GENERATING WORLD")
            self.detail_var.set(
                f"Stage {number}/{total} · {label}"
            )

        elif event == "stage_output":
            self._observe_stage_output(str(payload))

        elif event == "stage_passed":
            number = int(payload["number"])
            if 1 <= number <= len(STAGE_KEYS):
                key = STAGE_KEYS[number - 1]
                self._set_stage_progress(key, 1.0)

                label = STAGE_LABELS[key]
                self.stage_rows[key].configure(
                    text=f"✓  {number:02d}  {label}"
                )

                if self.active_stage_key == key:
                    self.active_stage_key = None
                    self.active_stage_output_ticks = 0

        elif event == "generation_pass":
            if self.current_definition is not None:
                self._mark_selected_stages_complete(
                    self.current_definition
                )
            self._recompute_overall_progress()
            self.status_var.set("FINALIZING")
            self.detail_var.set(
                "Selected generation stages completed successfully."
            )

        elif event == "notice":
            self._append_log(f"NOTICE: {payload}")

        elif event == "complete":
            if self.current_definition is not None:
                self._mark_selected_stages_complete(
                    self.current_definition
                )

            self.progress_var.set(1.0)

            if payload["final_status"] == "COMPLETE":
                self.status_var.set("WORLD COMPLETE")
                self.detail_var.set(
                    f"{payload['world_name']} · Variant {payload['variant']}"
                )
                self.world_subtitle.configure(
                    text=f"Variant {payload['variant']} · Complete"
                )
            else:
                self.status_var.set("PIPELINE COMPLETE")
                self.detail_var.set(
                    "Selected partial pipeline completed successfully."
                )
                self.world_subtitle.configure(
                    text=f"Variant {payload['variant']} · Partial"
                )

            self._finish_run_state()

        elif event == "stopped":
            self.status_var.set("WORLD STOPPED")
            self.detail_var.set(str(payload))
            self.world_subtitle.configure(
                text=f"Variant {self.variant_var.get()} · Stopped"
            )
            self._finish_run_state()

        elif event == "failed":
            self.status_var.set("WORLD FAILED")
            self.detail_var.set(str(payload))
            self.world_subtitle.configure(
                text=f"Variant {self.variant_var.get()} · Failed"
            )
            self._finish_run_state()

    def _finish_run_state(self) -> None:
        self.generation_running = False
        self.paused = False
        self.stop_requested = False
        self.process = None
        self.current_phase = "idle"
        self._update_control_states()

    # ------------------------------------------------------------------
    # Stage display
    # ------------------------------------------------------------------

    def _reset_stage_display(
        self,
        definition: dict[str, Any],
    ) -> None:
        self.active_stage_key = None
        self.active_stage_output_ticks = 0

        for index, (key, label) in enumerate(STAGES):
            selected = (
                definition["start_index"]
                <= index
                <= definition["end_index"]
            )

            prefix = "○" if selected else "·"

            self.stage_rows[key].configure(
                text=f"{prefix}  {index + 1:02d}  {label}"
            )

            self.stage_progress_values[key] = 0.0
            self.stage_progress_bars[key].set(0.0)
            self.stage_percent_labels[key].configure(
                text="0%" if selected else "—"
            )

        self.progress_var.set(0.0)

    def _mark_stage_started(
        self,
        current_key: str,
        definition: dict[str, Any],
    ) -> None:
        try:
            current_index = STAGE_KEYS.index(current_key)
        except ValueError:
            return

        for index, (key, label) in enumerate(STAGES):
            selected = (
                definition["start_index"]
                <= index
                <= definition["end_index"]
            )

            if not selected:
                prefix = "·"
            elif index < current_index:
                prefix = "✓"
            elif index == current_index:
                prefix = "▶"
            else:
                prefix = "○"

            self.stage_rows[key].configure(
                text=f"{prefix}  {index + 1:02d}  {label}"
            )

    def _mark_selected_stages_complete(
        self,
        definition: dict[str, Any],
    ) -> None:
        for index, (key, label) in enumerate(STAGES):
            selected = (
                definition["start_index"]
                <= index
                <= definition["end_index"]
            )

            prefix = "✓" if selected else "·"

            self.stage_rows[key].configure(
                text=f"{prefix}  {index + 1:02d}  {label}"
            )

            if selected:
                self.stage_progress_values[key] = 1.0
                self.stage_progress_bars[key].set(1.0)
                self.stage_percent_labels[key].configure(text="100%")

    # ------------------------------------------------------------------
    # Close behavior
    # ------------------------------------------------------------------

    def on_close(self) -> None:
        if self.generation_running:
            confirmed = messagebox.askyesno(
                "Generation active",
                (
                    "A BTYT generation is still running.\n\n"
                    "Stop it and close the World Builder?"
                ),
            )

            if not confirmed:
                return

            self.stop_requested = True
            self._terminate_process_tree()

        self.destroy()


def main() -> None:
    app = WorldBuilder()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()


if __name__ == "__main__":
    main()
