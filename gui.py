"""Interface gráfica do Diagnóstico do Sistema — Anota AI.

A interface reutiliza as rotinas de diagnóstico do pacote ``modules``. O
arquivo ``main.py`` continua disponível como alternativa de terminal.
"""

from __future__ import annotations

import io
import os
import sys

if sys.stdout is None:
    sys.stdout = io.StringIO()
if sys.stderr is None:
    sys.stderr = io.StringIO()

import ctypes
import platform
import queue
import re
import subprocess
import threading
import tkinter as tk
import urllib.request
from collections.abc import Callable
from contextlib import redirect_stdout
from io import StringIO

from modules.compatibility_check import display_compatibility_check
from modules.cpu_monitor import monitor_cpu
from modules.datetime_sync import display_datetime_sync
from modules.speedtest import display_speed_test
from modules.temp_cleaner import display_temp_cleaner
from modules.system_info import collect_system_info, display_system_info

# Paleta Anota AI / iFood.
PRIMARY_COLOR = "#EA1D2F"
SECONDARY_COLOR = "#FFFFFF"
RESULT_TEXT_COLOR = "#3F3E3E"
POSITIVE_COLOR = "#2E7D32"
NEGATIVE_COLOR = "#C62828"
WINDOW_TITLE = "Diagnóstico do Sistema — Anota AI"

Action = Callable[[], None]
Section = tuple[str, Action]
ANSI_RE = re.compile(r"\x1b\[([0-9;]*)m")


def _ensure_admin() -> None:
    """Reinicia o programa com privilégios de administrador no Windows."""
    if platform.system() != "Windows":
        return
    if ctypes.windll.shell32.IsUserAnAdmin():
        return

    # ShellExecuteW com ``runas`` solicita a confirmação do UAC. list2cmdline
    # preserva argumentos que contenham espaços ao relançar a aplicação.
    parameters = subprocess.list2cmdline(sys.argv)
    ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, parameters, None, 1
    )
    sys.exit(0)


class SystemDiagnosticsApp:
    """Janela principal com telas internas de diagnóstico e comandos."""

    PRINTERS_COMMAND = "shell:::{A8A91A66-3A7D-4424-8D24-04E180695C7A}"
    DRIVER_URL = (
        "https://raw.githubusercontent.com/Delutto/instalador_universal/main/"
        "Output/Instalador_Universal_0.9.4.exe"
    )
    DRIVER_FILENAME = "Instalador_Universal_0.9.4.exe"
    DESKTOP_URL = "https://app.anota.ai/download-app/anotaai-desktop"
    DESKTOP_FILENAME = "anotaai-desktop.exe"

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(WINDOW_TITLE)
        self.root.geometry("800x600")
        self.root.minsize(640, 480)
        self.root.configure(bg=SECONDARY_COLOR)

        # As duas telas compartilham este container e nunca criam uma janela
        # adicional. Apenas uma delas fica empacotada por vez.
        self.container = tk.Frame(self.root, bg=SECONDARY_COLOR)
        self.container.pack(fill="both", expand=True)
        self.main_frame = tk.Frame(self.container, bg=SECONDARY_COLOR)
        self.commands_frame = tk.Frame(self.container, bg=SECONDARY_COLOR)

        self._buttons: list[tk.Button] = []
        self._button_labels: dict[tk.Button, str] = {}
        self._result_queue: queue.Queue[tuple[str, str | None]] = queue.Queue()
        self._busy = False

        self._command_buttons: list[tk.Button] = []
        self._command_button_labels: dict[tk.Button, str] = {}
        self._command_result_queue: queue.Queue[tuple[str, str | None]] = queue.Queue()
        self._command_busy = False

        self._build_main_frame()
        self._build_commands_frame()
        self.main_frame.pack(fill="both", expand=True)

    def _build_main_frame(self) -> None:
        """Monta a tela principal dentro de ``main_frame``."""
        self._build_header(self.main_frame, WINDOW_TITLE.upper(), 76, 15, 24)
        self._build_actions(self.main_frame)
        self._build_results(self.main_frame, "main")
        self._build_main_footer(self.main_frame)

    def _build_commands_frame(self) -> None:
        """Monta a tela de comandos dentro de ``commands_frame``."""
        self._build_header(self.commands_frame, "COMANDOS — ANOTA AI", 58, 13, 18)
        self._build_command_actions(self.commands_frame)
        self._build_results(self.commands_frame, "commands")
        self._build_commands_footer(self.commands_frame)

    @staticmethod
    def _build_header(
        parent: tk.Misc,
        title_text: str,
        height: int,
        font_size: int,
        padx: int,
    ) -> None:
        header = tk.Frame(parent, bg=PRIMARY_COLOR, height=height)
        header.pack(fill="x")
        header.pack_propagate(False)
        title = tk.Label(
            header,
            text=title_text,
            bg=PRIMARY_COLOR,
            fg=SECONDARY_COLOR,
            font=("Arial", font_size, "bold"),
            anchor="w",
            padx=padx,
        )
        title.pack(fill="both", expand=True)

    def _build_actions(self, parent: tk.Misc) -> None:
        actions = tk.Frame(parent, bg=SECONDARY_COLOR, padx=24, pady=20)
        actions.pack(fill="x")
        for column in range(2):
            actions.grid_columnconfigure(column, weight=1)

        definitions: list[tuple[str, Action]] = [
            ("Verificar Compatibilidade", self._check_compatibility),
            ("Informações do Sistema", self._show_system_info),
            ("Monitor de CPU", self._monitor_cpu),
            ("Data, Hora e Sincronização", self._show_datetime),
            ("Teste de Velocidade", self._speed_test),
            ("Limpar Temporários", self._clean_temporaries),
            ("Executar Tudo", self._run_all),
            ("Comandos", self._open_commands),
        ]
        for index, (label, action) in enumerate(definitions):
            button = self._make_button(actions, label, action, padx=10, pady=9)
            button.grid(
                row=index // 2,
                column=index % 2,
                padx=6,
                pady=5,
                sticky="ew",
            )
            self._buttons.append(button)
            self._button_labels[button] = label

    def _build_command_actions(self, parent: tk.Misc) -> None:
        actions = tk.Frame(parent, bg=SECONDARY_COLOR, padx=18, pady=12)
        actions.pack(fill="x")
        definitions: list[tuple[str, Action]] = [
            ("Abrir Impressoras", self._open_printers),
            ("Baixar Instalador de Drivers", self._download_driver),
            ("Baixar Anota AI Desktop", self._download_desktop),
        ]
        for label, action in definitions:
            button = self._make_button(actions, label, action, padx=10, pady=7)
            button.pack(fill="x", pady=3)
            self._command_buttons.append(button)
            self._command_button_labels[button] = label

    @staticmethod
    def _make_button(
        parent: tk.Misc,
        label: str,
        action: Action,
        *,
        padx: int,
        pady: int,
    ) -> tk.Button:
        return tk.Button(
            parent,
            text=label,
            command=action,
            bg=PRIMARY_COLOR,
            fg=SECONDARY_COLOR,
            activebackground=PRIMARY_COLOR,
            activeforeground=SECONDARY_COLOR,
            relief="flat",
            cursor="hand2",
            font=("Arial", 10, "bold"),
            padx=padx,
            pady=pady,
        )

    def _build_results(self, parent: tk.Misc, screen: str) -> None:
        horizontal_pad = 24 if screen == "main" else 18
        results_frame = tk.Frame(parent, bg=SECONDARY_COLOR, padx=horizontal_pad)
        results_frame.pack(fill="both", expand=True)
        results_frame.grid_rowconfigure(0, weight=1)
        results_frame.grid_columnconfigure(0, weight=1)

        output = tk.Text(
            results_frame,
            wrap="word",
            bg=SECONDARY_COLOR,
            fg=RESULT_TEXT_COLOR,
            insertbackground=RESULT_TEXT_COLOR,
            font=("Consolas", 10 if screen == "main" else 9),
            relief="solid",
            borderwidth=1,
            padx=12 if screen == "main" else 10,
            pady=10 if screen == "main" else 8,
            state="disabled",
        )
        scrollbar = tk.Scrollbar(
            results_frame, orient="vertical", command=output.yview
        )
        output.configure(yscrollcommand=scrollbar.set)
        if screen == "main":
            output.tag_configure("positive", foreground=POSITIVE_COLOR)
            output.tag_configure("negative", foreground=NEGATIVE_COLOR)
            output.tag_configure("normal", foreground=RESULT_TEXT_COLOR)
            self.output = output
        else:
            self.command_output = output
        output.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

    def _build_main_footer(self, parent: tk.Misc) -> None:
        footer = tk.Frame(parent, bg=SECONDARY_COLOR, padx=24, pady=12)
        footer.pack(fill="x")
        self.status = tk.Label(
            footer,
            text="Pronto",
            bg=SECONDARY_COLOR,
            fg=RESULT_TEXT_COLOR,
            anchor="w",
            font=("Arial", 9),
        )
        self.status.pack(side="left", fill="x", expand=True)

        clear_button = self._make_button(
            footer, "Limpar", self.clear_output, padx=16, pady=6
        )
        clear_button.pack(side="right", padx=(6, 0))
        exit_button = self._make_button(
            footer, "Sair", self.root.destroy, padx=16, pady=6
        )
        exit_button.pack(side="right")
        self._buttons.extend((clear_button, exit_button))
        self._button_labels[clear_button] = "Limpar"
        self._button_labels[exit_button] = "Sair"

    def _build_commands_footer(self, parent: tk.Misc) -> None:
        footer = tk.Frame(parent, bg=SECONDARY_COLOR, padx=18, pady=10)
        footer.pack(fill="x")
        self.command_status = tk.Label(
            footer,
            text="Pronto",
            bg=SECONDARY_COLOR,
            fg=RESULT_TEXT_COLOR,
            anchor="w",
            font=("Arial", 9),
        )
        self.command_status.pack(side="left", fill="x", expand=True)

        close_button = self._make_button(
            footer, "Fechar", self.root.destroy, padx=16, pady=5
        )
        close_button.pack(side="right", padx=(6, 0))
        back_button = self._make_button(
            footer, "Voltar", self._back_to_main, padx=16, pady=5
        )
        back_button.pack(side="right")
        self._command_buttons.extend((close_button, back_button))
        self._command_button_labels[close_button] = "Fechar"
        self._command_button_labels[back_button] = "Voltar"

    def _append_output(self, text: str) -> None:
        """Adiciona texto à área de resultados principal na thread da interface."""
        self.output.configure(state="normal")
        current = 0
        tag = "normal"
        for match in ANSI_RE.finditer(text):
            self.output.insert("end", text[current : match.start()], tag)
            codes = match.group(1).split(";")
            if "92" in codes:
                tag = "positive"
            elif "91" in codes:
                tag = "negative"
            elif not match.group(1) or "0" in codes:
                tag = "normal"
            current = match.end()
        self.output.insert("end", text[current:], tag)
        self.output.see("end")
        self.output.configure(state="disabled")

    def _append_command_output(self, text: str) -> None:
        """Adiciona status à área de comandos independente da principal."""
        self.command_output.configure(state="normal")
        self.command_output.insert("end", text)
        self.command_output.see("end")
        self.command_output.configure(state="disabled")

    def clear_output(self) -> None:
        """Limpa os resultados principais quando não há operação em curso."""
        if self._busy:
            return
        self.output.configure(state="normal")
        self.output.delete("1.0", "end")
        self.output.configure(state="disabled")

    def _set_busy(self, label: str) -> None:
        """Bloqueia os controles principais durante um diagnóstico."""
        self._busy = True
        self.status.configure(text="Executando...", fg=PRIMARY_COLOR)
        for button in self._buttons:
            button.configure(state="disabled")
        for button, button_label in self._button_labels.items():
            if button_label == label:
                button.configure(text="Executando...")
                break

    def _set_ready(self) -> None:
        """Libera os controles principais após o diagnóstico."""
        self._busy = False
        self.status.configure(text="Pronto", fg=RESULT_TEXT_COLOR)
        for button in self._buttons:
            button.configure(state="normal", text=self._button_labels[button])

    def _start_operation(self, label: str, sections: list[Section]) -> None:
        """Inicia uma ou mais seções em uma thread de trabalho."""
        if self._busy:
            return
        self._set_busy(label)
        worker = threading.Thread(
            target=self._run_sections,
            args=(sections,),
            daemon=True,
            name="sysinfo-diagnostics",
        )
        worker.start()
        self.root.after(50, self._process_queue)

    def _run_sections(self, sections: list[Section]) -> None:
        """Executa as seções fora da thread principal e captura seus prints."""
        for title, action in sections:
            captured = StringIO()
            with redirect_stdout(captured):
                try:
                    action()
                except Exception as exc:  # pragma: no cover - proteção da thread
                    print(f"Não foi possível concluir esta seção: {exc}")
            result = (
                f"\n{'=' * 64}\n{title}\n{'=' * 64}\n"
                f"{captured.getvalue()}"
                f"\n{'-' * 64}\n"
            )
            self._result_queue.put(("output", result))
        self._result_queue.put(("done", None))

    def _process_queue(self) -> None:
        """Entrega os resultados do diagnóstico à interface via ``after``."""
        finished = False
        while True:
            try:
                message_type, payload = self._result_queue.get_nowait()
            except queue.Empty:
                break
            if message_type == "output" and payload is not None:
                self._append_output(payload)
            elif message_type == "done":
                finished = True
        if finished:
            self._set_ready()
        elif self._busy:
            self.root.after(50, self._process_queue)

    def _open_commands(self) -> None:
        """Troca a tela principal pela tela de comandos no mesmo root."""
        if self._busy:
            return
        self.main_frame.pack_forget()
        self.commands_frame.pack(fill="both", expand=True)

    def _back_to_main(self) -> None:
        """Retorna à tela principal sem criar ou destruir uma janela."""
        if self._command_busy:
            return
        self.commands_frame.pack_forget()
        self.main_frame.pack(fill="both", expand=True)

    def _check_compatibility(self) -> None:
        self._start_operation(
            "Verificar Compatibilidade",
            [
                (
                    "VERIFICAÇÃO DE COMPATIBILIDADE — ANOTA AI",
                    display_compatibility_check,
                )
            ],
        )

    def _show_system_info(self) -> None:
        self._start_operation(
            "Informações do Sistema",
            [
                (
                    "INFORMAÇÕES DO SISTEMA",
                    lambda: display_system_info(collect_system_info()),
                )
            ],
        )

    def _monitor_cpu(self) -> None:
        self._start_operation(
            "Monitor de CPU",
            [("MONITOR DE CPU", lambda: monitor_cpu(duration=10, interval=1.0))],
        )

    def _show_datetime(self) -> None:
        self._start_operation(
            "Data, Hora e Sincronização",
            [("DATA, HORA E SINCRONIZAÇÃO", display_datetime_sync)],
        )

    def _speed_test(self) -> None:
        self._start_operation(
            "Teste de Velocidade",
            [("TESTE DE VELOCIDADE DA INTERNET", display_speed_test)],
        )

    def _clean_temporaries(self) -> None:
        self._start_operation(
            "Limpar Temporários",
            [("LIMPEZA DE ARQUIVOS TEMPORÁRIOS", display_temp_cleaner)],
        )

    def _run_all(self) -> None:
        self._start_operation(
            "Executar Tudo",
            [
                (
                    "VERIFICAÇÃO DE COMPATIBILIDADE — ANOTA AI",
                    display_compatibility_check,
                ),
                (
                    "INFORMAÇÕES DO SISTEMA",
                    lambda: display_system_info(collect_system_info()),
                ),
                ("MONITOR DE CPU", lambda: monitor_cpu(duration=10, interval=1.0)),
                ("DATA, HORA E SINCRONIZAÇÃO", display_datetime_sync),
                ("TESTE DE VELOCIDADE DA INTERNET", display_speed_test),
                ("LIMPEZA DE ARQUIVOS TEMPORÁRIOS", display_temp_cleaner),
            ],
        )

    # ---- Comandos utilitários -------------------------------------------------

    def _set_command_busy(self, label: str) -> None:
        self._command_busy = True
        self.command_status.configure(text="Executando...", fg=PRIMARY_COLOR)
        for button in self._command_buttons:
            button.configure(state="disabled")
        self._append_command_output(f"{label}\n")

    def _set_command_ready(self) -> None:
        self._command_busy = False
        self.command_status.configure(text="Pronto", fg=RESULT_TEXT_COLOR)
        for button in self._command_buttons:
            button.configure(
                state="normal", text=self._command_button_labels[button]
            )

    def _start_command_thread(
        self,
        label: str,
        action: Action,
        error_prefix: str = "Erro",
    ) -> None:
        if self._command_busy:
            return
        self._set_command_busy(label)
        worker = threading.Thread(
            target=self._run_command_action,
            args=(action, error_prefix),
            daemon=True,
            name="sysinfo-command",
        )
        worker.start()
        self.root.after(50, self._process_command_queue)

    def _run_command_action(self, action: Action, error_prefix: str) -> None:
        try:
            action()
        except Exception as exc:  # pragma: no cover - proteção da thread
            self._command_result_queue.put(("output", f"{error_prefix}: {exc}\n"))
        finally:
            self._command_result_queue.put(("done", None))

    def _process_command_queue(self) -> None:
        finished = False
        while True:
            try:
                message_type, payload = self._command_result_queue.get_nowait()
            except queue.Empty:
                break
            if message_type == "output" and payload is not None:
                self._append_command_output(payload)
            elif message_type == "done":
                finished = True
        if finished:
            self._set_command_ready()
        elif self._command_busy:
            self.root.after(50, self._process_command_queue)

    @staticmethod
    def _downloads_path() -> str:
        """Retorna a pasta Downloads do usuário, priorizando o Windows."""
        if platform.system() == "Windows":
            user_profile = os.environ.get("USERPROFILE")
            if user_profile:
                return os.path.join(user_profile, "Downloads")
        return os.path.join(os.path.expanduser("~"), "Downloads")

    def _open_printers(self) -> None:
        self._start_command_thread("Abrir Impressoras", self._open_printers_worker)

    def _open_printers_worker(self) -> None:
        if platform.system() != "Windows":
            self._command_result_queue.put(
                ("output", "Disponível apenas no Windows\n")
            )
            return
        subprocess.Popen(["explorer", self.PRINTERS_COMMAND])
        self._command_result_queue.put(("output", "Abrindo pasta de Impressoras...\n"))

    def _download_driver(self) -> None:
        self._start_command_thread(
            "Baixar Instalador de Drivers",
            lambda: self._download_file(
                self.DRIVER_URL,
                self.DRIVER_FILENAME,
                "Baixando Instalador de Drivers...",
            ),
            error_prefix="Erro ao baixar",
        )

    def _download_desktop(self) -> None:
        self._start_command_thread(
            "Baixar Anota AI Desktop",
            lambda: self._download_file(
                self.DESKTOP_URL,
                self.DESKTOP_FILENAME,
                "Baixando Anota AI Desktop...",
            ),
            error_prefix="Erro ao baixar",
        )

    def _download_file(self, url: str, filename: str, message: str) -> None:
        downloads_path = self._downloads_path()
        os.makedirs(downloads_path, exist_ok=True)
        destination = os.path.join(downloads_path, filename)
        self._command_result_queue.put(("output", f"{message}\n"))

        def reporthook(block_number: int, block_size: int, total_size: int) -> None:
            downloaded = block_number * block_size
            if total_size > 0:
                percent = min(100, int(downloaded * 100 / total_size))
                total_mb = total_size / (1024 * 1024)
                downloaded_mb = min(downloaded, total_size) / (1024 * 1024)
                progress = (
                    f"Baixando... {percent}% "
                    f"({downloaded_mb:.1f} MB / {total_mb:.1f} MB)\n"
                )
            else:
                progress = "Baixando...\n"
            self._command_result_queue.put(("output", progress))

        urllib.request.urlretrieve(url, destination, reporthook=reporthook)
        self._command_result_queue.put(
            ("output", f"Download concluído: {destination}\n")
        )
        if platform.system() == "Windows":
            subprocess.Popen(["explorer", downloads_path])


if __name__ == "__main__":
    _ensure_admin()
    root = tk.Tk()
    app = SystemDiagnosticsApp(root)
    root.mainloop()
