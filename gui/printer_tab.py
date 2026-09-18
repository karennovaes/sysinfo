"""Aba Impressora."""

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
from modules.printer_diagnostics import display_printer_diagnostics


class PrinterTabMixin:
    """Métodos e construção da aba correspondente."""

    def _build_printer_frame(self) -> None:
            _, body = self._build_screen_shell(self.printer_frame, "Impressora — Anota AI")
            definitions = [
                ("Abrir Impressoras", self._open_printers),
                ("Limpar Fila de Impressão", self._clear_printer_queue),
                ("Diagnóstico de Impressoras", self._check_printer_diag),
                ("Verificar PID na Porta 5000", self._check_port_5000),
                ("Baixar Instalador de Drivers", self._download_driver),
                ("Baixar NetStatGUI", self._download_netstatgui),
            ]
            self._build_action_screen(body, "printer", definitions, with_progress=True)

    def _open_printers(self) -> None:
            log_audit("open_printers", "Abrindo pasta de impressoras do Windows")
            self._start_command_thread("printer", "Abrir Impressoras", self._open_printers_worker)

    def _open_printers_worker(self) -> None:
            if platform.system() != "Windows":
                self._queue_command_output("Disponível apenas no Windows")
                return
            subprocess.Popen(["explorer", PRINTERS_COMMAND], creationflags=_creation_flags(), startupinfo=_startup_info())
            self._queue_command_output("Abrindo pasta de Impressoras...")

    def _clear_printer_queue(self) -> None:
            self._start_command_thread(
                "printer", "Limpar Fila de Impressão", lambda: self._queue_command_output(_clear_print_queue())
            )

    def _check_printer_diag(self) -> None:
            self._start_command_thread(
                "printer", "Diagnóstico de Impressoras", lambda: self._queue_command_output_capture(display_printer_diagnostics)
            )

    def _check_port_5000(self) -> None:
            command = ["cmd", "/c", 'netstat -ano | findstr ":5000"']
            self._start_command_thread(
                "printer",
                "Verificar PID na Porta 5000",
                lambda: self._queue_command_output(_run_command_capture(command)),
            )
