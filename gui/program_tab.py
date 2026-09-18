"""Aba Programa."""

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


class ProgramTabMixin:
    """Métodos e construção da aba correspondente."""

    def _build_program_frame(self) -> None:
            _, body = self._build_screen_shell(self.program_frame, "Programa — Anota AI")
            definitions = [
                ("Verificar Processos Ativos", self._check_anota_processes),
                ("Status do WhatsApp", self._check_whatsapp),
                ("Desinstalar Anota AI", self._uninstall_anota),
                ("Baixar Anota AI Desktop", self._download_desktop),
            ]
            results_frame = self._build_action_screen(
                body, "program", definitions, with_progress=True
            )
            self._build_scan_card(results_frame)

    def _build_scan_card(self, body: tk.Frame) -> None:
            """Cria o cartão destacado que apresenta o scanner do Anota AI."""
            card = tk.Frame(body, bg=BG_CARD, highlightbackground=BORDER_COLOR, highlightthickness=1)
            pack_options = {"fill": "x", "pady": (0, 8)}
            # O conteúdo dos resultados já foi criado. Insere o scanner antes dele
            # para que o cartão fique no topo sem misturar pack e grid no mesmo
            # container (o conteúdo usa grid internamente).
            children = body.winfo_children()
            if children:
                pack_options["before"] = children[0]
            card.pack(**pack_options)
            content = tk.Frame(card, bg=BG_CARD, padx=12, pady=10)
            content.pack(fill="x")
            title_row = tk.Frame(content, bg=BG_CARD)
            title_row.pack(fill="x")
            tk.Label(
                title_row,
                text="Scanner de instalação do Anota AI",
                bg=BG_CARD,
                fg=TEXT_DARK,
                font=FONT_CARD,
                anchor="w",
            ).pack(side="left", fill="x", expand=True)
            self._scan_button = self._make_button(
                title_row, "⌕ Scanear", self._scan_anota_installation
            )
            self._scan_button.pack(side="right")
            self._scan_status = tk.Label(
                content,
                text="Ainda não escaneado",
                bg=BG_CARD,
                fg=TEXT_DARK,
                font=FONT_STATUS,
                anchor="w",
                justify="left",
                wraplength=900,
            )
            self._scan_status.pack(fill="x", pady=(8, 0))

    def _download_desktop(self) -> None:
        """Mantém a ação de download localizada na aba Programa."""
        super()._download_desktop()

    def _check_anota_processes(self) -> None:
            from modules.anota_process import display_anota_processes

            self._start_operation(
                "Verificar Processos Ativos", [("PROCESSOS ATIVOS DO ANOTA AI", display_anota_processes)], "program"
            )

    def _check_whatsapp(self) -> None:
            from modules.whatsapp_status import display_whatsapp_status
            self._start_command_thread("program", "Status do WhatsApp", lambda: self._queue_command_output_capture(display_whatsapp_status))

    def _uninstall_anota(self) -> None:
            """Confirma a desinstalação na thread principal antes do trabalho pesado."""
            from tkinter import messagebox

            if not messagebox.askyesno(
                "Desinstalar Anota AI",
                "Tem certeza que deseja desinstalar completamente o Anota AI? "
                "Esta ação não pode ser desfeita.",
            ):
                return
            from modules.uninstaller import display_uninstall

            self._start_operation(
                "Desinstalar Anota AI",
                [("DESINSTALAÇÃO COMPLETA DO ANOTA AI", display_uninstall)],
                "program",
            )
