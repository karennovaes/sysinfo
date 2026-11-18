"""Aba Computador."""

from __future__ import annotations

import platform
import subprocess
from contextlib import redirect_stdout
from io import StringIO

try:
    import tkinter as tk
except ImportError:
    tk = None

from modules.config import PRINTERS_COMMAND
from modules.security import log_audit
from modules.theme import *
from .helpers import (
    SystemInfoBase, _clear_print_queue, _creation_flags, _run_command_capture, _startup_info,
)
from modules.datetime_sync import display_datetime_sync
from modules.speedtest import display_speed_test
from modules.temp_cleaner import display_temp_cleaner


class ComputerTabMixin:
    """Métodos e construção da aba correspondente."""

    def _build_computer_frame(self) -> None:
            _, body = self._build_screen_shell(self.computer_frame, "Computador — Anota AI")
            definitions = [
                ("Limpeza de Cache", self._clean_cache),
                ("Sincronização de Hora", self._sync_time),
                ("Compatibilidade", self._check_compatibility),
                ("Teste de Velocidade", self._speed_test),
                ("Monitor de Recursos", self._monitor_cpu),
                ("Verificar Antivírus", self._check_antivirus),
                ("Eventos do Windows", self._check_windows_events),
                ("Windows Update", self._check_windows_update),
            ]
            results_frame = self._build_action_screen(
                body, "computer", definitions, with_progress=True
            )

    def _clean_cache(self) -> None:
            self._start_operation("Limpeza de Cache", [("LIMPEZA DE CACHE", display_temp_cleaner)])

    def _sync_time(self) -> None:
            self._start_operation(
                "Sincronização de Hora", [("SINCRONIZAÇÃO DE HORA", display_datetime_sync)]
            )

    def _check_compatibility(self) -> None:
            from modules.compatibility_check import display_compatibility_check
            self._start_operation("Compatibilidade", [("VERIFICAÇÃO DE COMPATIBILIDADE", display_compatibility_check)])

    def _speed_test(self) -> None:
            self._start_operation(
                "Teste de Velocidade", [("TESTE DE VELOCIDADE", display_speed_test)]
            )

    def _monitor_cpu(self) -> None:
            """Embute o monitor de recursos no painel de resultados da tela Computador."""
            if self._busy or self._command_busy:
                return

            screen = "computer"
            output_frame = self._output_frames.get(screen)
            scrollbar = self._output_scrollbars.get(screen)
            progress_frame = self._progress_frames.get(screen)
            if output_frame is None:
                return

            # Esconde o terminal e a barra de progresso. O monitor ocupa a mesma
            # célula do terminal na tela Computador (row=1 porque há progresso).
            output_frame.grid_remove()
            if scrollbar:
                scrollbar.grid_remove()
            if progress_frame:
                progress_frame.grid_remove()

            results_content = output_frame.master
            monitor_frame = tk.Frame(results_content, bg=BG_WHITE)
            monitor_frame.grid(row=1, column=0, sticky="nsew", padx=0, pady=0)
            results_content.grid_rowconfigure(1, weight=1)
            results_content.grid_columnconfigure(0, weight=1)

            self._set_tool_busy(screen, "Monitor de Recursos")

            def _on_monitor_close() -> None:
                monitor_frame.destroy()
                output_frame.grid(row=1, column=0, sticky="nsew")
                if scrollbar:
                    scrollbar.grid(row=1, column=1, sticky="ns")
                self._resource_monitor = None
                self._set_tool_ready()

            from modules.resource_monitor import create_resource_monitor

            self._resource_monitor = create_resource_monitor(
                monitor_frame, on_close=_on_monitor_close
            )

    def _check_antivirus(self) -> None:
            from modules.maintenance import display_antivirus_status
            self._start_operation("Verificar Antivírus", [("STATUS DO ANTIVÍRUS", display_antivirus_status)])

    def _check_windows_events(self) -> None:
            from modules.windows_events import display_windows_events
            self._start_operation("Eventos do Windows", [("EVENTOS DO WINDOWS", display_windows_events)])

    def _check_windows_update(self) -> None:
            from modules.windows_update import display_windows_update
            self._start_operation("Windows Update", [("WINDOWS UPDATE", display_windows_update)])

    def _open_windows_update_page(self) -> None:
            if platform.system() != "Windows":
                return
            subprocess.Popen(["cmd", "/c", "start", "ms-settings:windowsupdate"], creationflags=_creation_flags(), startupinfo=_startup_info())
