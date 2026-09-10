from __future__ import annotations

import json
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path
from tkinter import messagebox
from typing import Any

import customtkinter as ctk

try:
    import psutil
except ImportError:
    psutil = None

from .state import (
    ACTIVE_CONFIG_PATH,
    ACTIVE_WORLD_PATH,
    GENERATION_SHARE,
    PROJECT_ROOT,
    STAGES,
    STAGE_KEYS,
    STAGE_LABELS,
    WORLD_REGISTRY_PATH,
    WORLDS_ROOT,
    ReconstructedWorldState,
    derive_world_seed,
    has_files,
    load_json,
    make_world_id,
    materialize_reference_assets,
    normalize_world_name,
    persist_builder_state,
    reconstruct_world_state,
    utc_now_iso,
    world_progress,
    world_root_for,
    write_json,
)

APP_TITLE = "BTYT World Builder"
ORCHESTRATOR_MODULE = "scripts.generate_btyt"
MANIFEST_MODULE = "scripts.generate_manifest"

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
GENERIC_PROGRESS_PATTERNS = (
    re.compile(r"Processed\s+([\d,]+)\s*/\s*([\d,]+)", re.IGNORECASE),
    re.compile(
        r"([\d,]+)\s*/\s*([\d,]+)\s+(?:accounts|customers|rows|records|loans|transactions|items)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\.\.\.\s*([\d,]+)\s*/\s*([\d,]+)\s*\|\s*row group rows\s*:", re.IGNORECASE),
)
TX_CHUNK_PATTERN = re.compile(r"chunk\s+([\d,]+)\s*/\s*([\d,]+)", re.IGNORECASE)
TX_MONTH_PATTERN = re.compile(r"\b(20\d{2}-\d{2})\b")
AUDIT_STREAM_PATTERN = re.compile(
    r"operational transaction audit:\s*([\d,]+)\s+rows checked",
    re.IGNORECASE,
)


def parse_count(value: str) -> int:
    return int(value.replace(",", "").strip())


class WorldBuilder(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.title(APP_TITLE)
        self.geometry("1440x900")
        self.minsize(1180, 760)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.process: subprocess.Popen[str] | None = None
        self.worker_thread: threading.Thread | None = None
        self.event_queue: queue.Queue[tuple[str, Any]] = queue.Queue()

        self.generation_running = False
        self.stop_requested = False
        self.current_phase = "idle"
        self.current_world_root: Path | None = None
        self.current_definition: dict[str, Any] | None = None
        self.log_path: Path | None = None
        self.active_stage_key: str | None = None

        self.stage_progress_values = {key: 0.0 for key in STAGE_KEYS}
        self.stage_rows: dict[str, ctk.CTkLabel] = {}
        self.stage_progress_bars: dict[str, ctk.CTkProgressBar] = {}
        self.stage_percent_labels: dict[str, ctk.CTkLabel] = {}

        self.world_state = ReconstructedWorldState()
        self.selected_keys_for_run: list[str] = STAGE_KEYS.copy()

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
        self.variant_var = ctk.StringVar(value="1")
        self.canonical_var = ctk.BooleanVar(value=False)

        self.execution_mode_var = ctk.StringVar(value="Full")
        self.smoke_customers_var = ctk.StringVar(value="1000")

        self.population_mode_var = ctk.StringVar(value="range")
        self.population_fixed_var = ctk.StringVar(value="100000")
        self.population_min_var = ctk.StringVar(value="85000")
        self.population_max_var = ctk.StringVar(value="123500")

        self.start_date_var = ctk.StringVar(value="2021-01-01")
        self.end_date_var = ctk.StringVar(value="2026-12-31")
        self.reliability_var = ctk.StringVar(value="realistic")

        self.pipeline_start_var = ctk.StringVar(value="Beginning")
        self.pipeline_end_var = ctk.StringVar(value="Final")
        self.auto_finalize_var = ctk.BooleanVar(value=True)
        self.keep_log_var = ctk.BooleanVar(value=True)
        self.clean_outputs_var = ctk.BooleanVar(value=False)

        self.status_var = ctk.StringVar(value="READY")
        self.detail_var = ctk.StringVar(value="Configure a world or resume an existing one.")
        self.world_progress_var = ctk.DoubleVar(value=0.0)
        self.pipeline_progress_var = ctk.DoubleVar(value=0.0)
        self.world_percent_var = ctk.StringVar(value="0%")
        self.pipeline_percent_var = ctk.StringVar(value="0%")
        self.registry_choice_var = ctk.StringVar(value="")

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build_layout(self) -> None:
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.sidebar = ctk.CTkScrollableFrame(
            self,
            width=365,
            corner_radius=0,
            label_text="WORLD DEFINITION",
        )
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_columnconfigure(0, weight=1)

        self.main = ctk.CTkFrame(self, corner_radius=0)
        self.main.grid(row=0, column=1, sticky="nsew")
        self.main.grid_columnconfigure(0, weight=1)
        self.main.grid_rowconfigure(4, weight=1)

        self._build_sidebar()
        self._build_main_panel()

    def _section(self, row: int, text: str) -> int:
        label = ctk.CTkLabel(
            self.sidebar,
            text=text,
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=("gray45", "gray62"),
            anchor="w",
        )
        label.grid(row=row, column=0, sticky="ew", padx=18, pady=(12, 5))
        return row + 1

    def _grid_entry(
        self,
        row: int,
        label_text: str,
        variable: ctk.StringVar,
    ) -> tuple[ctk.CTkEntry, int]:
        ctk.CTkLabel(self.sidebar, text=label_text, anchor="w").grid(
            row=row, column=0, sticky="ew", padx=18, pady=(2, 2)
        )
        row += 1
        entry = ctk.CTkEntry(self.sidebar, textvariable=variable)
        entry.grid(row=row, column=0, sticky="ew", padx=18, pady=(0, 8))
        return entry, row + 1

    def _build_sidebar(self) -> None:
        ctk.CTkLabel(
            self.sidebar,
            text="BTYT\nWORLD BUILDER",
            font=ctk.CTkFont(size=29, weight="bold"),
            justify="left",
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=18, pady=(22, 18))

        row = 1
        row = self._section(row, "REGISTERED WORLDS")
        self.registry_menu = ctk.CTkOptionMenu(
            self.sidebar,
            variable=self.registry_choice_var,
            values=["No registered worlds"],
        )
        self.registry_menu.grid(row=row, column=0, sticky="ew", padx=18, pady=(2, 6))
        row += 1
        self.load_world_button = ctk.CTkButton(
            self.sidebar,
            text="LOAD SELECTED WORLD",
            command=self.load_selected_world,
            height=34,
        )
        self.load_world_button.grid(row=row, column=0, sticky="ew", padx=18, pady=(0, 10))
        row += 1

        row = self._section(row, "IDENTITY")
        self.world_name_entry, row = self._grid_entry(row, "World Name", self.world_name_var)
        self.variant_entry, row = self._grid_entry(row, "Variant", self.variant_var)
        self.canonical_check = ctk.CTkCheckBox(
            self.sidebar,
            text="Canonical World",
            variable=self.canonical_var,
        )
        self.canonical_check.grid(row=row, column=0, sticky="w", padx=18, pady=(4, 10))
        row += 1

        row = self._section(row, "EXECUTION PROFILE")
        self.execution_mode = ctk.CTkSegmentedButton(
            self.sidebar,
            values=["Full", "Smoke"],
            variable=self.execution_mode_var,
            command=self._execution_mode_changed,
        )
        self.execution_mode.grid(row=row, column=0, sticky="ew", padx=18, pady=(2, 8))
        row += 1
        self.smoke_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.smoke_frame.grid(row=row, column=0, sticky="ew")
        self.smoke_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self.smoke_frame, text="Smoke customers", anchor="w").grid(
            row=0, column=0, sticky="ew", padx=18, pady=(2, 2)
        )
        self.smoke_entry = ctk.CTkEntry(self.smoke_frame, textvariable=self.smoke_customers_var)
        self.smoke_entry.grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 8))
        self.smoke_frame.grid_remove()
        row += 1

        row = self._section(row, "POPULATION")
        self.population_switch = ctk.CTkSegmentedButton(
            self.sidebar,
            values=["Fixed", "Range"],
            command=self._population_mode_changed,
        )
        self.population_switch.set("Range")
        self.population_switch.grid(row=row, column=0, sticky="ew", padx=18, pady=(2, 8))
        row += 1

        self.fixed_population_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.fixed_population_frame.grid(row=row, column=0, sticky="ew")
        self.fixed_population_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self.fixed_population_frame, text="Customers", anchor="w").grid(
            row=0, column=0, sticky="ew", padx=18, pady=(2, 2)
        )
        self.fixed_population_entry = ctk.CTkEntry(
            self.fixed_population_frame,
            textvariable=self.population_fixed_var,
        )
        self.fixed_population_entry.grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 8))

        self.range_population_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.range_population_frame.grid(row=row, column=0, sticky="ew")
        self.range_population_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self.range_population_frame, text="Minimum", anchor="w").grid(
            row=0, column=0, sticky="ew", padx=18, pady=(2, 2)
        )
        self.population_min_entry = ctk.CTkEntry(
            self.range_population_frame,
            textvariable=self.population_min_var,
        )
        self.population_min_entry.grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 8))
        ctk.CTkLabel(self.range_population_frame, text="Maximum", anchor="w").grid(
            row=2, column=0, sticky="ew", padx=18, pady=(2, 2)
        )
        self.population_max_entry = ctk.CTkEntry(
            self.range_population_frame,
            textvariable=self.population_max_var,
        )
        self.population_max_entry.grid(row=3, column=0, sticky="ew", padx=18, pady=(0, 8))
        self.fixed_population_frame.grid_remove()
        row += 1

        row = self._section(row, "OBSERVATION PERIOD")
        self.start_date_entry, row = self._grid_entry(row, "Start", self.start_date_var)
        self.end_date_entry, row = self._grid_entry(row, "End", self.end_date_var)

        row = self._section(row, "DATA RELIABILITY")
        self.reliability_menu = ctk.CTkOptionMenu(
            self.sidebar,
            variable=self.reliability_var,
            values=["light", "realistic", "stress"],
        )
        self.reliability_menu.grid(row=row, column=0, sticky="ew", padx=18, pady=(2, 10))
        row += 1

        row = self._section(row, "PIPELINE")
        stage_names = [label for _, label in STAGES]
        ctk.CTkLabel(self.sidebar, text="Start from", anchor="w").grid(
            row=row, column=0, sticky="ew", padx=18, pady=(2, 2)
        )
        row += 1
        self.pipeline_start_menu = ctk.CTkOptionMenu(
            self.sidebar,
            variable=self.pipeline_start_var,
            values=["Beginning"] + stage_names,
        )
        self.pipeline_start_menu.grid(row=row, column=0, sticky="ew", padx=18, pady=(0, 8))
        row += 1
        ctk.CTkLabel(self.sidebar, text="Run through", anchor="w").grid(
            row=row, column=0, sticky="ew", padx=18, pady=(2, 2)
        )
        row += 1
        self.pipeline_end_menu = ctk.CTkOptionMenu(
            self.sidebar,
            variable=self.pipeline_end_var,
            values=["Final"] + stage_names,
        )
        self.pipeline_end_menu.grid(row=row, column=0, sticky="ew", padx=18, pady=(0, 8))
        row += 1

        self.auto_finalize_check = ctk.CTkCheckBox(
            self.sidebar,
            text="Auto-finalize after full pipeline",
            variable=self.auto_finalize_var,
        )
        self.auto_finalize_check.grid(row=row, column=0, sticky="w", padx=18, pady=(4, 6))
        row += 1
        self.keep_log_check = ctk.CTkCheckBox(
            self.sidebar,
            text="Save World Builder log",
            variable=self.keep_log_var,
        )
        self.keep_log_check.grid(row=row, column=0, sticky="w", padx=18, pady=(2, 6))
        row += 1
        self.clean_outputs_check = ctk.CTkCheckBox(
            self.sidebar,
            text="Clean existing outputs first",
            variable=self.clean_outputs_var,
        )
        self.clean_outputs_check.grid(row=row, column=0, sticky="w", padx=18, pady=(2, 10))
        row += 1

        row = self._section(row, "TOOLS")
        self.open_folder_button = ctk.CTkButton(
            self.sidebar,
            text="OPEN WORLD FOLDER",
            command=self.open_world_folder,
            height=34,
        )
        self.open_folder_button.grid(row=row, column=0, sticky="ew", padx=18, pady=(2, 6))
        row += 1
        self.reload_state_button = ctk.CTkButton(
            self.sidebar,
            text="RELOAD WORLD STATE",
            command=self.reload_world_state,
            height=34,
        )
        self.reload_state_button.grid(row=row, column=0, sticky="ew", padx=18, pady=(0, 18))

        self._refresh_registry_menu()

    def _build_main_panel(self) -> None:
        header = ctk.CTkFrame(self.main, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=34, pady=(28, 12))
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
            text="Variant 1 · Ready",
            font=ctk.CTkFont(size=15),
            text_color=("gray45", "gray65"),
            anchor="w",
        )
        self.world_subtitle.grid(row=1, column=0, sticky="w", pady=(4, 0))

        status_card = ctk.CTkFrame(self.main)
        status_card.grid(row=1, column=0, sticky="ew", padx=34, pady=(0, 12))
        status_card.grid_columnconfigure(0, weight=1)
        self.status_label = ctk.CTkLabel(
            status_card,
            textvariable=self.status_var,
            font=ctk.CTkFont(size=21, weight="bold"),
            anchor="w",
        )
        self.status_label.grid(row=0, column=0, sticky="w", padx=20, pady=(14, 2))
        self.detail_label = ctk.CTkLabel(status_card, textvariable=self.detail_var, anchor="w")
        self.detail_label.grid(row=1, column=0, sticky="w", padx=20, pady=(0, 10))

        world_row = ctk.CTkFrame(status_card, fg_color="transparent")
        world_row.grid(row=2, column=0, sticky="ew", padx=20)
        world_row.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            world_row,
            text="WORLD PROGRESS",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=("gray45", "gray65"),
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            world_row,
            textvariable=self.world_percent_var,
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=0, column=1, sticky="e")
        self.world_progress_bar = ctk.CTkProgressBar(
            status_card,
            variable=self.world_progress_var,
            height=15,
        )
        self.world_progress_bar.grid(row=3, column=0, sticky="ew", padx=20, pady=(2, 8))
        self.world_progress_bar.set(0.0)

        pipeline_row = ctk.CTkFrame(status_card, fg_color="transparent")
        pipeline_row.grid(row=4, column=0, sticky="ew", padx=20)
        pipeline_row.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            pipeline_row,
            text="CURRENT PIPELINE",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=("gray45", "gray65"),
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            pipeline_row,
            textvariable=self.pipeline_percent_var,
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=0, column=1, sticky="e")
        self.pipeline_progress_bar = ctk.CTkProgressBar(
            status_card,
            variable=self.pipeline_progress_var,
            height=9,
        )
        self.pipeline_progress_bar.grid(row=5, column=0, sticky="ew", padx=20, pady=(2, 16))
        self.pipeline_progress_bar.set(0.0)

        controls = ctk.CTkFrame(self.main, fg_color="transparent")
        controls.grid(row=2, column=0, sticky="ew", padx=34, pady=(0, 10))
        for column in range(4):
            controls.grid_columnconfigure(column, weight=1)

        self.generate_button = ctk.CTkButton(
            controls,
            text="GENERATE WORLD",
            command=self.generate_world,
            height=46,
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        self.generate_button.grid(row=0, column=0, sticky="ew", padx=(0, 5))

        self.resume_button = ctk.CTkButton(
            controls,
            text="RESUME WORLD",
            command=self.resume_world,
            height=46,
        )
        self.resume_button.grid(row=0, column=1, sticky="ew", padx=5)

        self.finalize_button = ctk.CTkButton(
            controls,
            text="FINALIZE WORLD",
            command=self.finalize_world,
            height=46,
        )
        self.finalize_button.grid(row=0, column=2, sticky="ew", padx=5)

        self.stop_button = ctk.CTkButton(
            controls,
            text="STOP RUN",
            command=self.stop_generation,
            height=46,
        )
        self.stop_button.grid(row=0, column=3, sticky="ew", padx=(5, 0))

        lifecycle = ctk.CTkLabel(
            self.main,
            text="READY → GENERATING → GENERATED → AUDITED → MANIFESTED → VERIFIED → FROZEN",
            font=ctk.CTkFont(size=11),
            text_color=("gray45", "gray65"),
            anchor="w",
        )
        lifecycle.grid(row=3, column=0, sticky="ew", padx=36, pady=(0, 8))

        content = ctk.CTkFrame(self.main, fg_color="transparent")
        content.grid(row=4, column=0, sticky="nsew", padx=34, pady=(0, 24))
        content.grid_columnconfigure(0, weight=0)
        content.grid_columnconfigure(1, weight=1)
        content.grid_rowconfigure(0, weight=1)

        stages_card = ctk.CTkScrollableFrame(
            content,
            width=355,
            label_text="WORLD PIPELINE",
        )
        stages_card.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        stages_card.grid_columnconfigure(0, weight=1)

        for index, (key, label) in enumerate(STAGES, start=1):
            frame = ctk.CTkFrame(stages_card, fg_color="transparent")
            frame.grid(row=index - 1, column=0, sticky="ew", padx=8, pady=4)
            frame.grid_columnconfigure(0, weight=1)

            row_label = ctk.CTkLabel(
                frame,
                text=f"○  {index:02d}  {label}",
                anchor="w",
                font=ctk.CTkFont(size=13),
            )
            row_label.grid(row=0, column=0, sticky="ew", padx=(2, 8), pady=(0, 3))
            percent_label = ctk.CTkLabel(
                frame,
                text="0%",
                width=46,
                anchor="e",
                font=ctk.CTkFont(size=12),
                text_color=("gray45", "gray65"),
            )
            percent_label.grid(row=0, column=1, sticky="e", padx=(4, 2), pady=(0, 3))
            stage_bar = ctk.CTkProgressBar(frame, height=8)
            stage_bar.grid(row=1, column=0, columnspan=2, sticky="ew", padx=2, pady=(0, 2))
            stage_bar.set(0.0)

            self.stage_rows[key] = row_label
            self.stage_percent_labels[key] = percent_label
            self.stage_progress_bars[key] = stage_bar

        log_card = ctk.CTkFrame(content)
        log_card.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        log_card.grid_columnconfigure(0, weight=1)
        log_card.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(
            log_card,
            text="LIVE ENGINE OUTPUT",
            font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 6))
        self.log_box = ctk.CTkTextbox(
            log_card,
            wrap="word",
            font=ctk.CTkFont(family="Consolas", size=12),
        )
        self.log_box.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        self.log_box.configure(state="disabled")

    # ------------------------------------------------------------------
    # UI state
    # ------------------------------------------------------------------

    def _execution_mode_changed(self, value: str) -> None:
        if value == "Smoke":
            self.smoke_frame.grid()
            self.canonical_var.set(False)
        else:
            self.smoke_frame.grid_remove()

    def _population_mode_changed(self, value: str) -> None:
        if value == "Fixed":
            self.population_mode_var.set("fixed")
            self.range_population_frame.grid_remove()
            self.fixed_population_frame.grid()
        else:
            self.population_mode_var.set("range")
            self.fixed_population_frame.grid_remove()
            self.range_population_frame.grid()

    def _append_log(self, text: str) -> None:
        self.log_box.configure(state="normal")
        self.log_box.insert("end", text + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _clear_log(self) -> None:
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")

    def _refresh_identity_text(self) -> None:
        name = normalize_world_name(self.world_name_var.get()) or "WORLD"
        variant = self.variant_var.get().strip() or "?"
        self.world_title.configure(text=name)
        self.world_subtitle.configure(text=f"Variant {variant} · {self.status_var.get().title()}")

    def _refresh_registry_menu(self) -> None:
        registry = load_json(WORLD_REGISTRY_PATH, {"worlds": []}) or {"worlds": []}
        values = []
        for record in registry.get("worlds", []) or []:
            if not isinstance(record, dict):
                continue
            world_id = record.get("world_id")
            if world_id:
                values.append(str(world_id))
        if not values:
            values = ["No registered worlds"]
        self.registry_menu.configure(values=values)
        if self.registry_choice_var.get() not in values:
            self.registry_choice_var.set(values[0])

    def load_selected_world(self) -> None:
        if self.generation_running:
            return
        choice = self.registry_choice_var.get()
        registry = load_json(WORLD_REGISTRY_PATH, {"worlds": []}) or {"worlds": []}
        record = next(
            (
                item for item in registry.get("worlds", []) or []
                if isinstance(item, dict) and str(item.get("world_id")) == choice
            ),
            None,
        )
        if record is None:
            return
        self.world_name_var.set(str(record.get("world_name", "BTYT")))
        self.variant_var.set(str(record.get("variant", 1)))
        self._load_world_definition_from_disk()

    def _load_world_definition_from_disk(self) -> None:
        try:
            name = normalize_world_name(self.world_name_var.get())
            variant = int(self.variant_var.get())
        except Exception:
            return
        world_root = world_root_for(name, variant)
        world = load_json(world_root / "world.json", {}) or {}

        self.current_world_root = world_root
        if world.get("canonical") is not None:
            self.canonical_var.set(bool(world.get("canonical")))
        if world.get("start_date"):
            self.start_date_var.set(str(world["start_date"]))
        if world.get("end_date"):
            self.end_date_var.set(str(world["end_date"]))
        if world.get("data_reliability_level"):
            self.reliability_var.set(str(world["data_reliability_level"]))

        population = world.get("population", {})
        if isinstance(population, dict):
            if "customers" in population:
                self.population_fixed_var.set(str(population["customers"]))
                self.population_switch.set("Fixed")
                self._population_mode_changed("Fixed")
            elif "customers_min" in population and "customers_max" in population:
                self.population_min_var.set(str(population["customers_min"]))
                self.population_max_var.set(str(population["customers_max"]))
                self.population_switch.set("Range")
                self._population_mode_changed("Range")

        self.reload_world_state()

    def _load_existing_identity(self) -> None:
        active = load_json(ACTIVE_WORLD_PATH, {}) or {}
        config = load_json(ACTIVE_CONFIG_PATH, {}) or {}

        if active.get("world_name"):
            self.world_name_var.set(str(active["world_name"]))
        if active.get("variant") is not None:
            self.variant_var.set(str(active["variant"]))

        population = config.get("population", {})
        if isinstance(population, dict):
            if "customers" in population:
                self.population_fixed_var.set(str(population["customers"]))
                self.population_switch.set("Fixed")
                self._population_mode_changed("Fixed")
            elif "customers_min" in population and "customers_max" in population:
                self.population_min_var.set(str(population["customers_min"]))
                self.population_max_var.set(str(population["customers_max"]))
                self.population_switch.set("Range")
                self._population_mode_changed("Range")

        observation = config.get("observation_period", {})
        if isinstance(observation, dict):
            if observation.get("start_date"):
                self.start_date_var.set(str(observation["start_date"]))
            if observation.get("end_date"):
                self.end_date_var.set(str(observation["end_date"]))

        reliability = config.get("data_reliability", {})
        if isinstance(reliability, dict) and reliability.get("level"):
            self.reliability_var.set(str(reliability["level"]))

        self._load_world_definition_from_disk()

    def reload_world_state(self) -> None:
        try:
            definition = self._validated_inputs()
        except Exception:
            return
        world_root = world_root_for(definition["world_name"], definition["variant"])
        self.current_world_root = world_root
        self.current_definition = definition
        self.log_path = world_root / "audit" / "world_builder_generation.log"

        self.world_state = reconstruct_world_state(world_root)
        for key in STAGE_KEYS:
            self.stage_progress_values[key] = 1.0 if key in self.world_state.completed_stages else 0.0
        self._render_stage_state()
        self._recompute_progress()

        status = self.world_state.latest_status.upper() if self.world_state.latest_status else "READY"
        self.status_var.set(status)
        first_incomplete = self.world_state.first_incomplete_stage
        if self.world_state.frozen:
            self.detail_var.set("World is verified and frozen.")
        elif first_incomplete:
            self.detail_var.set(
                f"Next safe pipeline stage: {STAGE_LABELS[first_incomplete]}."
            )
        else:
            self.detail_var.set("Generation pipeline is complete; finalization may still be pending.")
        self._refresh_identity_text()
        self._update_control_states()

    def _render_stage_state(self) -> None:
        for index, (key, label) in enumerate(STAGES, start=1):
            value = self.stage_progress_values[key]
            if value >= 1.0:
                prefix = "✓"
            elif key == self.active_stage_key:
                prefix = "▶"
            elif value > 0:
                prefix = "◐"
            else:
                prefix = "○"
            self.stage_rows[key].configure(text=f"{prefix}  {index:02d}  {label}")
            self.stage_progress_bars[key].set(value)
            self.stage_percent_labels[key].configure(text=f"{round(value * 100):d}%")

    def _update_control_states(self) -> None:
        running = self.generation_running
        self.generate_button.configure(
            state="disabled" if running else "normal",
            text="GENERATING..." if running else "GENERATE WORLD",
        )
        can_resume = (not running) and (not self.world_state.frozen)
        self.resume_button.configure(state="normal" if can_resume else "disabled")

        first_fourteen = set(STAGE_KEYS[:-1])
        can_finalize = (
            not running
            and first_fourteen.issubset(self.world_state.completed_stages)
            and not self.world_state.frozen
        )
        self.finalize_button.configure(state="normal" if can_finalize else "disabled")
        self.stop_button.configure(state="normal" if running else "disabled")

    # ------------------------------------------------------------------
    # Validation and preparation
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

        smoke = self.execution_mode_var.get() == "Smoke"
        if smoke:
            try:
                smoke_customers = int(self.smoke_customers_var.get())
            except ValueError as exc:
                raise ValueError("Smoke customers must be an integer.") from exc
            if smoke_customers <= 0:
                raise ValueError("Smoke customers must be positive.")
            population = {"customers": smoke_customers}
            canonical = False
        elif self.population_mode_var.get() == "fixed":
            try:
                customers = int(self.population_fixed_var.get())
            except ValueError as exc:
                raise ValueError("Customers must be an integer.") from exc
            if customers <= 0:
                raise ValueError("Customers must be positive.")
            population = {"customers": customers}
            canonical = bool(self.canonical_var.get())
        else:
            try:
                customers_min = int(self.population_min_var.get())
                customers_max = int(self.population_max_var.get())
            except ValueError as exc:
                raise ValueError("Population bounds must be integers.") from exc
            if customers_min <= 0 or customers_max <= 0:
                raise ValueError("Population bounds must be positive.")
            if customers_min > customers_max:
                raise ValueError("Population minimum cannot exceed maximum.")
            population = {
                "customers_min": customers_min,
                "customers_max": customers_max,
            }
            canonical = bool(self.canonical_var.get())

        start_date = self.start_date_var.get().strip()
        end_date = self.end_date_var.get().strip()
        date_pattern = r"\d{4}-\d{2}-\d{2}"
        if not re.fullmatch(date_pattern, start_date):
            raise ValueError("Start date must use YYYY-MM-DD.")
        if not re.fullmatch(date_pattern, end_date):
            raise ValueError("End date must use YYYY-MM-DD.")
        if datetime.fromisoformat(start_date) > datetime.fromisoformat(end_date):
            raise ValueError("Start date cannot be after end date.")

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
            raise ValueError("Pipeline start stage cannot come after end stage.")

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
            "canonical": canonical,
            "execution_mode": "smoke" if smoke else "full",
            "start_key": start_key,
            "end_key": end_key,
            "start_index": start_index,
            "end_index": end_index,
            "auto_finalize": bool(self.auto_finalize_var.get()),
            "keep_log": bool(self.keep_log_var.get()),
            "clean_outputs": bool(self.clean_outputs_var.get()),
        }

    def _prepare_world(self, definition: dict[str, Any]) -> Path:
        world_root = world_root_for(definition["world_name"], definition["variant"])
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

        existing_config = load_json(ACTIVE_CONFIG_PATH, {}) or {}
        existing_world = load_json(world_root / "world.json", {}) or {}
        config_payload = dict(existing_config)

        world_section = dict(config_payload.get("world", {}))
        world_section.update({"name": definition["world_name"], "seed": definition["seed"]})
        config_payload["world"] = world_section

        population_section = dict(config_payload.get("population", {}))
        for key in ("customers", "customers_min", "customers_max"):
            population_section.pop(key, None)
        population_section.update(definition["population"])
        config_payload["population"] = population_section

        observation_section = dict(config_payload.get("observation_period", {}))
        observation_section.update(
            {"start_date": definition["start_date"], "end_date": definition["end_date"]}
        )
        config_payload["observation_period"] = observation_section

        reliability_source = config_payload.get("data_reliability", {})
        if not isinstance(reliability_source, dict):
            raise RuntimeError(
                "world_config.json has an invalid 'data_reliability' section."
            )
        reliability_section = dict(reliability_source)
        reliability_section["level"] = definition["reliability"]
        config_payload["data_reliability"] = reliability_section

        # Execution settings are world-specific. Never inherit a stale
        # smoke-test population from the previously active world.
        execution_section = dict(config_payload.get("execution", {}))
        execution_section["mode"] = (
            "development"
            if definition["execution_mode"] == "smoke"
            else "production"
        )
        if definition["execution_mode"] == "smoke":
            execution_section["smoke_customers"] = int(
                definition["population"]["customers"]
            )
        else:
            resolved_population_floor = int(
                definition["population"].get(
                    "customers",
                    definition["population"].get("customers_min", 1),
                )
            )
            previous_smoke = execution_section.get("smoke_customers", 1)
            try:
                previous_smoke = int(previous_smoke)
            except (TypeError, ValueError):
                previous_smoke = 1
            execution_section["smoke_customers"] = max(
                1,
                min(previous_smoke, resolved_population_floor),
            )
        config_payload["execution"] = execution_section
        config_payload["variant"] = definition["variant"]

        for legacy_key in (
            "world_seed", "world_name", "name", "seed", "start_date", "end_date",
            "customers", "customers_min", "customers_max",
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
                "execution_mode": definition["execution_mode"],
                "start_date": definition["start_date"],
                "end_date": definition["end_date"],
                "data_reliability_level": definition["reliability"],
                "population": definition["population"],
                "updated_at_utc": utc_now_iso(),
            }
        )
        world_payload.setdefault("created_at_utc", utc_now_iso())

        metadata_path = world_root / "metadata.json"
        metadata = load_json(metadata_path, {}) or {}
        metadata.update(
            {
                "world_name": definition["world_name"],
                "variant": definition["variant"],
                "world_id": definition["world_id"],
                "seed": definition["seed"],
                "canonical": definition["canonical"],
                "active": True,
                "updated_at_utc": utc_now_iso(),
            }
        )
        metadata.setdefault("status", "READY")
        metadata.setdefault("created_at_utc", utc_now_iso())

        relative_world_path = str(world_root.relative_to(PROJECT_ROOT))
        active_pointer = {
            "world_name": definition["world_name"],
            "variant": definition["variant"],
            "path": relative_world_path,
        }

        write_json(world_root / "world.json", world_payload)
        write_json(metadata_path, metadata)
        write_json(ACTIVE_CONFIG_PATH, config_payload)
        write_json(ACTIVE_WORLD_PATH, active_pointer)

        self._verify_active_identity(definition, world_root)
        self._update_registry(definition, world_root, metadata.get("status", "READY"))

        self.current_world_root = world_root
        self.current_definition = definition
        self.log_path = world_root / "audit" / "world_builder_generation.log"
        return world_root

    def _verify_active_identity(self, definition: dict[str, Any], world_root: Path) -> None:
        config = load_json(ACTIVE_CONFIG_PATH, {}) or {}
        active = load_json(ACTIVE_WORLD_PATH, {}) or {}
        expected_name = definition["world_name"]
        expected_variant = definition["variant"]
        expected_seed = definition["seed"]
        expected_path = Path(str(world_root.relative_to(PROJECT_ROOT)))

        world_section = config.get("world", {}) if isinstance(config.get("world", {}), dict) else {}
        if world_section.get("name") != expected_name:
            raise RuntimeError("Active config world name is inconsistent with selected identity.")
        if int(world_section.get("seed", -1)) != expected_seed:
            raise RuntimeError("Active config seed is inconsistent with selected identity.")
        execution_section = config.get("execution")
        if not isinstance(execution_section, dict):
            raise RuntimeError(
                "world_config.json is missing the canonical nested 'execution' section."
            )

        expected_mode = (
            "development"
            if definition["execution_mode"] == "smoke"
            else "production"
        )
        if execution_section.get("mode") != expected_mode:
            raise RuntimeError(
                "BTYT Core execution mode is inconsistent with the selected world. "
                f"Expected {expected_mode!r}, "
                f"found {execution_section.get('mode')!r}."
            )

        try:
            configured_smoke_customers = int(execution_section.get("smoke_customers", -1))
        except (TypeError, ValueError) as exc:
            raise RuntimeError(
                "BTYT Core smoke-test customer count is missing or invalid."
            ) from exc

        if expected_mode == "smoke":
            expected_smoke_customers = int(definition["population"]["customers"])
            if configured_smoke_customers != expected_smoke_customers:
                raise RuntimeError(
                    "BTYT Core smoke-test customer count is stale. "
                    f"Expected {expected_smoke_customers}, "
                    f"found {configured_smoke_customers}."
                )
        else:
            minimum_possible_population = int(
                definition["population"].get(
                    "customers",
                    definition["population"].get("customers_min", 1),
                )
            )
            if configured_smoke_customers > minimum_possible_population:
                raise RuntimeError(
                    "BTYT Core smoke-test customer count exceeds the selected "
                    "world's minimum possible population."
                )

        if active.get("world_name") != expected_name:
            raise RuntimeError("active_world.json world_name does not match selected world.")
        if int(active.get("variant", -1)) != expected_variant:
            raise RuntimeError("active_world.json variant does not match selected world.")
        if Path(str(active.get("path", ""))) != expected_path:
            raise RuntimeError("active_world.json path does not match selected world directory.")

    def _update_registry(
        self,
        definition: dict[str, Any],
        world_root: Path,
        status: str,
    ) -> None:
        registry = load_json(WORLD_REGISTRY_PATH, {"worlds": []}) or {"worlds": []}
        worlds = registry.setdefault("worlds", [])
        record = {
            "world_id": definition["world_id"],
            "world_name": definition["world_name"],
            "variant": definition["variant"],
            "seed": definition["seed"],
            "canonical": definition["canonical"],
            "path": str(world_root.relative_to(PROJECT_ROOT)),
            "status": status,
            "updated_at_utc": utc_now_iso(),
        }
        replaced = False
        for index, old in enumerate(worlds):
            if not isinstance(old, dict):
                continue
            if old.get("world_name") == definition["world_name"] and int(old.get("variant", -1)) == definition["variant"]:
                worlds[index] = record
                replaced = True
                break
        if not replaced:
            worlds.append(record)

        if definition["canonical"]:
            for old in worlds:
                if not isinstance(old, dict):
                    continue
                same = (
                    old.get("world_name") == definition["world_name"]
                    and int(old.get("variant", -1)) == definition["variant"]
                )
                if not same:
                    old["canonical"] = False
        write_json(WORLD_REGISTRY_PATH, registry)
        self.after(0, self._refresh_registry_menu)

    def _set_world_status(
        self,
        definition: dict[str, Any],
        status: str,
        detail: str | None = None,
    ) -> None:
        world_root = world_root_for(definition["world_name"], definition["variant"])
        metadata_path = world_root / "metadata.json"
        metadata = load_json(metadata_path, {}) or {}
        metadata["status"] = status
        metadata["updated_at_utc"] = utc_now_iso()
        if status == "GENERATING":
            metadata["generation_started_at_utc"] = utc_now_iso()
        if status in {"GENERATED", "AUDITED", "FROZEN", "FAILED", "STOPPED", "PARTIAL_COMPLETE"}:
            metadata["generation_finished_at_utc"] = utc_now_iso()
        if detail:
            metadata["status_detail"] = detail
        write_json(metadata_path, metadata)
        self._update_registry(definition, world_root, status)

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

        metadata_path = world_root / "metadata.json"
        metadata = load_json(metadata_path, {}) or {}
        metadata.pop("builder_state", None)
        metadata["status"] = "READY"
        write_json(metadata_path, metadata)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _confirm_clean(self, world_root: Path) -> bool:
        if not has_files(world_root / "data"):
            return True
        dialog = ctk.CTkInputDialog(
            text=(
                "This removes generated, interim, operational, database and manifest outputs\n"
                "for this world. Type DELETE to continue."
            ),
            title="Confirm destructive cleanup",
        )
        return (dialog.get_input() or "").strip().upper() == "DELETE"

    def generate_world(self) -> None:
        if self.generation_running:
            return
        try:
            definition = self._validated_inputs()
            world_root = world_root_for(definition["world_name"], definition["variant"])
            if definition["clean_outputs"] and not self._confirm_clean(world_root):
                return
            self._prepare_world(definition)
            if definition["clean_outputs"]:
                self._clean_existing_outputs(world_root)
            materialize_reference_assets(world_root)
        except Exception as exc:
            self.status_var.set("VALIDATION FAILED")
            self.detail_var.set(str(exc))
            return

        self._clear_log()
        self.reload_world_state()

        if definition["clean_outputs"]:
            self.world_state = ReconstructedWorldState()
            for key in STAGE_KEYS:
                self.stage_progress_values[key] = 0.0

        self.selected_keys_for_run = STAGE_KEYS[
            definition["start_index"] : definition["end_index"] + 1
        ]
        for key in self.selected_keys_for_run:
            if key not in self.world_state.completed_stages:
                self.stage_progress_values[key] = 0.0

        self._start_worker(definition, mode="generate")

    def resume_world(self) -> None:
        if self.generation_running:
            return
        try:
            definition = self._validated_inputs()
            world_root = self._prepare_world(definition)
            materialize_reference_assets(world_root)
        except Exception as exc:
            self.status_var.set("RESUME FAILED")
            self.detail_var.set(str(exc))
            return

        self.reload_world_state()
        next_key = self.world_state.first_incomplete_stage
        if next_key is None:
            if self.world_state.frozen:
                self.status_var.set("FROZEN")
                self.detail_var.set("Nothing to resume. The world is already frozen.")
                return
            self.finalize_world()
            return

        start_index = STAGE_KEYS.index(next_key)
        definition["start_key"] = next_key
        definition["start_index"] = start_index
        definition["end_key"] = None
        definition["end_index"] = len(STAGE_KEYS) - 1
        definition["clean_outputs"] = False
        self.pipeline_start_var.set(STAGE_LABELS[next_key])
        self.pipeline_end_var.set("Final")
        self.selected_keys_for_run = STAGE_KEYS[start_index:]

        self._append_log(
            f"=== RESUME FROM LAST SAFE POINT: {next_key} ==="
        )
        self._start_worker(definition, mode="resume")

    def finalize_world(self) -> None:
        if self.generation_running:
            return
        try:
            definition = self._validated_inputs()
            self._prepare_world(definition)
        except Exception as exc:
            self.status_var.set("FINALIZATION FAILED")
            self.detail_var.set(str(exc))
            return

        self.reload_world_state()
        required = set(STAGE_KEYS[:-1])
        missing = [key for key in STAGE_KEYS[:-1] if key not in self.world_state.completed_stages]
        if missing:
            self.status_var.set("FINALIZATION BLOCKED")
            self.detail_var.set(
                "Generation is incomplete. Missing: " + ", ".join(missing)
            )
            return

        self.selected_keys_for_run = ["cross_system_audit"]
        self._start_worker(definition, mode="finalize")

    def _start_worker(self, definition: dict[str, Any], mode: str) -> None:
        self.current_definition = definition
        self.generation_running = True
        self.stop_requested = False
        self.current_phase = "check"
        self.status_var.set("PREPARING WORLD")
        self.detail_var.set("Validating active-world routing and engine structure.")
        self._render_stage_state()
        self._recompute_progress()
        self._update_control_states()

        self.worker_thread = threading.Thread(
            target=self._worker,
            args=(definition, mode),
            daemon=True,
        )
        self.worker_thread.start()

    def _worker(self, definition: dict[str, Any], mode: str) -> None:
        try:
            self._set_world_status(definition, "CHECKING")
            check_code = self._run_command(
                [sys.executable, "-u", "-m", ORCHESTRATOR_MODULE, "--check-only"],
                phase="check",
            )
            if self.stop_requested:
                raise InterruptedError("Run stopped by user.")
            if check_code != 0:
                raise RuntimeError(f"Engine preflight failed with exit code {check_code}.")
            self.event_queue.put(("check_pass", None))

            if mode == "finalize":
                self._set_world_status(definition, "AUDITING")
                if "cross_system_audit" not in self.world_state.completed_stages:
                    code = self._run_command(
                        [
                            sys.executable, "-u", "-m", ORCHESTRATOR_MODULE,
                            "--only", "cross_system_audit",
                        ],
                        phase="generate",
                    )
                    if code != 0:
                        raise RuntimeError(f"Cross-system audit failed with exit code {code}.")
                    self.event_queue.put(("generation_pass", {"finalize_only": True}))
                self._run_finalization(definition)
                return

            self._set_world_status(definition, "GENERATING")
            command = [sys.executable, "-u", "-m", ORCHESTRATOR_MODULE]
            if definition["start_key"] is not None:
                command.extend(["--from-stage", definition["start_key"]])
            if definition["end_key"] is not None:
                command.extend(["--to-stage", definition["end_key"]])

            generation_code = self._run_command(command, phase="generate")
            if self.stop_requested:
                raise InterruptedError("Run stopped by user.")
            if generation_code != 0:
                raise RuntimeError(f"World generation failed with exit code {generation_code}.")

            self.event_queue.put(("generation_pass", {"finalize_only": False}))

            reaches_audit = definition["end_index"] == len(STAGE_KEYS) - 1
            if reaches_audit:
                self._set_world_status(definition, "AUDITED")
                if definition["auto_finalize"]:
                    self._run_finalization(definition)
                else:
                    self.event_queue.put(("complete", {**definition, "final_status": "AUDITED"}))
            else:
                self._set_world_status(definition, "PARTIAL_COMPLETE")
                self.event_queue.put(("complete", {**definition, "final_status": "PARTIAL_COMPLETE"}))

        except InterruptedError as exc:
            self._set_world_status(definition, "STOPPED", detail=str(exc))
            self.event_queue.put(("stopped", str(exc)))
        except Exception as exc:
            self._set_world_status(definition, "FAILED", detail=str(exc))
            self.event_queue.put(("failed", str(exc)))
        finally:
            self.process = None
            self.current_phase = "idle"

    def _run_finalization(self, definition: dict[str, Any]) -> None:
        if self.stop_requested:
            raise InterruptedError("Run stopped by user.")

        self.event_queue.put(("finalization_phase", "manifest"))
        manifest_code = self._run_command(
            [sys.executable, "-u", "-m", MANIFEST_MODULE],
            phase="manifest",
        )
        if manifest_code != 0:
            raise RuntimeError(f"Final manifest failed with exit code {manifest_code}.")
        self.event_queue.put(("manifest_pass", None))

        if self.stop_requested:
            raise InterruptedError("Run stopped by user.")

        self.event_queue.put(("finalization_phase", "verify"))
        verify_code = self._run_command(
            [sys.executable, "-u", "-m", MANIFEST_MODULE, "--verify-only"],
            phase="verify",
        )
        if verify_code != 0:
            raise RuntimeError(f"Manifest verification failed with exit code {verify_code}.")

        manifest = load_json(
            world_root_for(definition["world_name"], definition["variant"])
            / "manifests" / "btyt_part_i_manifest.json",
            {},
        ) or {}
        fingerprint = manifest.get("dataset_fingerprint_sha256")
        self.event_queue.put(("verify_pass", fingerprint))
        self._set_world_status(definition, "FROZEN")
        self.event_queue.put(("complete", {**definition, "final_status": "FROZEN"}))

    # ------------------------------------------------------------------
    # Process execution and stopping
    # ------------------------------------------------------------------

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
            self.event_queue.put(("log", {"phase": phase, "line": line}))
            if self.keep_log_var.get() and self.log_path is not None:
                self.log_path.parent.mkdir(parents=True, exist_ok=True)
                with self.log_path.open("a", encoding="utf-8") as handle:
                    handle.write(f"[{utc_now_iso()}] [{phase.upper()}] {line}\n")

            if phase == "generate":
                match = STAGE_PATTERN.search(line)
                if match:
                    self.event_queue.put(("stage_started", match.group(3).lower()))
                if STAGE_PASS_PATTERN.search(line):
                    self.event_queue.put(("stage_passed", None))
                else:
                    self.event_queue.put(("stage_output", line))

        return self.process.wait()

    def stop_generation(self) -> None:
        if not self.generation_running:
            return
        confirmed = messagebox.askyesno(
            "Stop current run",
            (
                "Stop the active BTYT process?\n\n"
                "Completed stages remain on disk. Checkpoint-aware generators can resume from their own safe point; "
                "other incomplete stages may restart from the beginning."
            ),
        )
        if not confirmed:
            return
        self.stop_requested = True
        self.status_var.set("STOPPING")
        self.detail_var.set("Stopping the current process tree.")
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
                        process.terminate()
                    except psutil.Error:
                        pass
                _, alive = psutil.wait_procs(processes, timeout=4)
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
                ["taskkill", "/PID", str(self.process.pid), "/T", "/F"],
                capture_output=True,
                text=True,
            )
        else:
            try:
                self.process.terminate()
            except OSError:
                pass

    # ------------------------------------------------------------------
    # Progress
    # ------------------------------------------------------------------

    def _set_stage_progress(self, key: str, fraction: float) -> None:
        if key not in self.stage_progress_values:
            return
        fraction = max(0.0, min(float(fraction), 1.0))
        self.stage_progress_values[key] = max(self.stage_progress_values[key], fraction)
        self._render_stage_state()
        self._recompute_progress()

    def _recompute_progress(self) -> None:
        global_fraction = world_progress(
            self.stage_progress_values,
            self.world_state.manifest_pass,
            self.world_state.verification_pass,
        )
        self.world_progress_var.set(global_fraction)
        self.world_percent_var.set(f"{round(global_fraction * 100):d}%")

        selected = self.selected_keys_for_run or STAGE_KEYS
        if selected:
            pipeline_fraction = sum(self.stage_progress_values[key] for key in selected) / len(selected)
        else:
            pipeline_fraction = 0.0
        pipeline_fraction = max(0.0, min(pipeline_fraction, 1.0))
        self.pipeline_progress_var.set(pipeline_fraction)
        self.pipeline_percent_var.set(f"{round(pipeline_fraction * 100):d}%")

    def _month_fraction(self, month: str) -> float | None:
        try:
            start = datetime.fromisoformat(self.start_date_var.get().strip())
            end = datetime.fromisoformat(self.end_date_var.get().strip())
            current = datetime.strptime(month, "%Y-%m")
        except ValueError:
            return None

        total = (end.year - start.year) * 12 + end.month - start.month + 1
        pos = (current.year - start.year) * 12 + current.month - start.month + 1
        if total <= 0:
            return None
        return max(0.0, min(pos / total, 1.0))

    def _extract_internal_progress(self, key: str, line: str) -> float | None:
        if key == "transactions":
            chunk = TX_CHUNK_PATTERN.search(line)
            if chunk:
                current = parse_count(chunk.group(1))
                total = parse_count(chunk.group(2))
                if total > 0:
                    return 0.40 * current / total

            month_match = TX_MONTH_PATTERN.search(line)
            if month_match and ("already replayed" in line.lower() or "transactions=" in line.lower()):
                fraction = self._month_fraction(month_match.group(1))
                if fraction is not None:
                    return 0.40 + 0.55 * fraction

            if "stage 3/3" in line.lower():
                return 0.96

        for pattern in GENERIC_PROGRESS_PATTERNS:
            match = pattern.search(line)
            if match:
                current = parse_count(match.group(1))
                total = parse_count(match.group(2))
                if total > 0:
                    return current / total
        return None

    def _observe_stage_output(self, line: str) -> None:
        key = self.active_stage_key
        if key is None:
            return
        fraction = self._extract_internal_progress(key, line)
        if fraction is not None:
            self._set_stage_progress(key, fraction)

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    def _poll_events(self) -> None:
        while True:
            try:
                event, payload = self.event_queue.get_nowait()
            except queue.Empty:
                break
            self._handle_event(event, payload)
        self.after(100, self._poll_events)

    def _handle_event(self, event: str, payload: Any) -> None:
        if event == "log":
            self._append_log(payload["line"])
            return

        if event == "check_pass":
            self.status_var.set("GENERATING")
            self.detail_var.set("Engine preflight passed.")
            return

        if event == "stage_started":
            key = str(payload)
            self.active_stage_key = key if key in STAGE_KEYS else None
            if self.active_stage_key:
                self.status_var.set("GENERATING")
                self.detail_var.set(f"Running {STAGE_LABELS[self.active_stage_key]}.")
                self._render_stage_state()
            return

        if event == "stage_output":
            self._observe_stage_output(str(payload))
            return

        if event == "stage_passed":
            if self.active_stage_key:
                key = self.active_stage_key
                self._set_stage_progress(key, 1.0)
                self.world_state.completed_stages.add(key)
                if self.current_world_root:
                    persist_builder_state(self.current_world_root, self.world_state)
                self.active_stage_key = None
            return

        if event == "generation_pass":
            self.reload_world_state()
            return

        if event == "finalization_phase":
            if payload == "manifest":
                self.status_var.set("MANIFESTING")
                self.detail_var.set("Building the final inventory and dataset fingerprint.")
            else:
                self.status_var.set("VERIFYING")
                self.detail_var.set("Verifying every inventoried file against the manifest.")
            return

        if event == "manifest_pass":
            self.world_state.manifest_pass = True
            if self.current_world_root:
                persist_builder_state(self.current_world_root, self.world_state)
            self.status_var.set("MANIFESTED")
            self._recompute_progress()
            return

        if event == "verify_pass":
            self.world_state.manifest_pass = True
            self.world_state.verification_pass = True
            self.world_state.frozen = True
            self.world_state.fingerprint = str(payload) if payload else None
            if self.current_world_root:
                persist_builder_state(self.current_world_root, self.world_state)
            self.status_var.set("FROZEN")
            self._recompute_progress()
            return

        if event == "complete":
            final_status = payload.get("final_status", "COMPLETE")
            if final_status == "FROZEN":
                self.status_var.set("FROZEN")
                self.detail_var.set("World generation, audit, manifest and verification are complete.")
            elif final_status == "AUDITED":
                self.status_var.set("AUDITED")
                self.detail_var.set("Generation and cross-system audit passed. Finalization remains pending.")
            else:
                self.status_var.set("PARTIAL COMPLETE")
                self.detail_var.set("Selected pipeline range completed successfully.")
            self._finish_run_state()
            return

        if event == "stopped":
            self.status_var.set("STOPPED")
            self.detail_var.set(str(payload))
            self._finish_run_state()
            return

        if event == "failed":
            self.status_var.set("FAILED")
            self.detail_var.set(str(payload))
            self._finish_run_state()

    def _finish_run_state(self) -> None:
        self.generation_running = False
        self.stop_requested = False
        self.process = None
        self.current_phase = "idle"
        self.active_stage_key = None
        self.reload_world_state()
        self._refresh_identity_text()
        self._update_control_states()

    # ------------------------------------------------------------------
    # Tools and close behavior
    # ------------------------------------------------------------------

    def open_world_folder(self) -> None:
        try:
            definition = self._validated_inputs()
            world_root = world_root_for(definition["world_name"], definition["variant"])
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

    def on_close(self) -> None:
        if self.generation_running:
            confirmed = messagebox.askyesno(
                "Run active",
                "A BTYT process is still running. Stop it and close the World Builder?",
            )
            if not confirmed:
                return
            self.stop_requested = True
            self._terminate_process_tree()
        self.destroy()


def main() -> None:
    app = WorldBuilder()
    app.mainloop()


if __name__ == "__main__":
    main()
