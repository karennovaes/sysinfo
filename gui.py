"""Interface gráfica do Diagnóstico do Sistema — Anota AI.

A interface reutiliza as rotinas de diagnóstico do pacote ``modules``. O
arquivo ``main.py`` continua disponível como alternativa de terminal.
"""

from __future__ import annotations

import ctypes
import io
import os
import platform
import queue
import re
import subprocess
import sys
import threading
import tkinter as tk
import urllib.request
from collections.abc import Callable
from contextlib import redirect_stdout
from io import StringIO
from tkinter import ttk

if sys.stdout is None:
    sys.stdout = io.StringIO()
if sys.stderr is None:
    sys.stderr = io.StringIO()

from modules.compatibility_check import display_compatibility_check
from modules.cpu_monitor import monitor_cpu
from modules.datetime_sync import display_datetime_sync
from modules.speedtest import display_speed_test
from modules.temp_cleaner import display_temp_cleaner
from modules.system_info import collect_system_info, display_system_info

# Paleta Anota AI.
PRIMARY_COLOR = "#EA1D2F"
BG_WHITE = "#FFFFFF"
BG_LIGHT = "#F5F5F5"
TEXT_DARK = "#3F3E3E"
TEXT_WHITE = "#FFFFFF"
ACCENT_GREEN = "#2E7D32"
HOVER_COLOR = "#C41523"
BORDER_COLOR = "#E0E0E0"

# Aliases usados pela saída da aplicação.
SECONDARY_COLOR = TEXT_WHITE
RESULT_TEXT_COLOR = TEXT_DARK
POSITIVE_COLOR = ACCENT_GREEN
NEGATIVE_COLOR = PRIMARY_COLOR
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
        self.root.geometry("700x500")
        self.root.minsize(500, 400)
        self.root.resizable(True, True)
        self.root.configure(bg=BG_WHITE)

        self.container = tk.Frame(self.root, bg=BG_WHITE)
        self.container.pack(fill="both", expand=True)
        self.main_frame = tk.Frame(self.container, bg=BG_WHITE)
        self.commands_frame = tk.Frame(self.container, bg=BG_WHITE)

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
        """Monta a tela principal com ações à esquerda e resultados à direita."""
        _, body = self._build_screen_shell(self.main_frame, WINDOW_TITLE)
        self._build_main_sidebar(body)
        self._build_results(body, "main")

    def _build_commands_frame(self) -> None:
        """Monta a tela de comandos no mesmo layout horizontal."""
        _, body = self._build_screen_shell(
            self.commands_frame, "Comandos — Anota AI"
        )
        self._build_commands_sidebar(body)
        self._build_results(body, "commands")

    @staticmethod
    def _build_screen_shell(
        parent: tk.Misc, title_text: str
    ) -> tuple[tk.Frame, tk.Frame]:
        """Cria cabeçalho e corpo compartilhados pelas duas telas."""
        header = tk.Frame(parent, bg=PRIMARY_COLOR, height=70)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(
            header,
            text=title_text,
            bg=PRIMARY_COLOR,
            fg=TEXT_WHITE,
            anchor="w",
            font=("Arial", 14, "bold"),
            padx=20,
        ).pack(fill="both", expand=True)

        body = tk.Frame(parent, bg=BG_WHITE)
        body.pack(fill="both", expand=True)
        return header, body

    def _build_main_sidebar(self, body: tk.Frame) -> None:
        sidebar = tk.Frame(body, bg=BG_LIGHT, width=200)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        actions = tk.Frame(sidebar, bg=BG_LIGHT, padx=12, pady=12)
        actions.pack(fill="both", expand=True)
        definitions: list[tuple[str, Action]] = [
            ("Verificar Compatibilidade", self._check_compatibility),
            ("Informações do Sistema", self._show_system_info),
            ("Monitor de CPU", self._monitor_cpu),
            ("Data/Hora e Sincronização", self._show_datetime),
            ("Teste de Velocidade", self._speed_test),
            ("Limpar Temporários", self._clean_temporaries),
            ("Executar Tudo", self._run_all),
            ("Comandos", self._open_commands),
        ]
        for label, action in definitions:
            button = self._make_button(actions, label, action)
            button.pack(fill="x", pady=3)
            self._buttons.append(button)
            self._button_labels[button] = label

        self._build_main_footer(sidebar)

    def _build_commands_sidebar(self, body: tk.Frame) -> None:
        sidebar = tk.Frame(body, bg=BG_LIGHT, width=200)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        actions = tk.Frame(sidebar, bg=BG_LIGHT, padx=12, pady=12)
        actions.pack(fill="both", expand=True)
        definitions: list[tuple[str, Action]] = [
            ("Abrir Impressoras", self._open_printers),
            ("Baixar Instalador de Drivers", self._download_driver),
            ("Baixar Anota AI Desktop", self._download_desktop),
        ]
        for label, action in definitions:
            button = self._make_button(actions, label, action)
            button.pack(fill="x", pady=3)
            self._command_buttons.append(button)
            self._command_button_labels[button] = label

        self._build_commands_footer(sidebar)

    @staticmethod
    def _make_button(
        parent: tk.Misc, label: str, action: Action
    ) -> tk.Button:
        """Cria um botão Tk nativo, sem desenho customizado ou cantos arredondados."""
        button = tk.Button(
            parent,
            text=label,
            command=action,
            width=22,
            padx=12,
            pady=8,
            bg=PRIMARY_COLOR,
            fg=TEXT_WHITE,
            activebackground=HOVER_COLOR,
            activeforeground=TEXT_WHITE,
            font=("Segoe UI", 9, "bold"),
            borderwidth=0,
            relief="flat",
            highlightthickness=0,
            cursor="hand2",
            anchor="center",
        )

        def on_enter(event: tk.Event) -> None:
            if event.widget.cget("state") != tk.DISABLED:
                event.widget.configure(bg=HOVER_COLOR)

        def on_leave(event: tk.Event) -> None:
            if event.widget.cget("state") != tk.DISABLED:
                event.widget.configure(bg=PRIMARY_COLOR)

        button.bind("<Enter>", on_enter)
        button.bind("<Leave>", on_leave)
        return button

    def _build_results(self, body: tk.Frame, screen: str) -> None:
        """Cria o painel de resultados branco com texto e rolagem."""
        results_frame = tk.Frame(body, bg=BG_WHITE, padx=12, pady=12)
        results_frame.pack(side="left", fill="both", expand=True)
        results_frame.grid_rowconfigure(1, weight=1)
        results_frame.grid_columnconfigure(0, weight=1)

        progress_frame = tk.Frame(results_frame, bg=BG_WHITE)
        progress_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        progress_frame.grid_columnconfigure(0, weight=1)
        progress_label = tk.Label(
            progress_frame,
            text="",
            bg=BG_WHITE,
            fg=TEXT_DARK,
            anchor="w",
            font=("Segoe UI", 9, "bold"),
        )
        progress_label.grid(row=0, column=0, sticky="ew", pady=(0, 5))

        progress_style = ttk.Style(self.root)
        progress_style.configure(
            "Anota.Horizontal.TProgressbar",
            troughcolor=BG_LIGHT,
            background=PRIMARY_COLOR,
            lightcolor=PRIMARY_COLOR,
            darkcolor=PRIMARY_COLOR,
            bordercolor=BORDER_COLOR,
        )
        progress_bar = ttk.Progressbar(
            progress_frame,
            orient="horizontal",
            mode="determinate",
            style="Anota.Horizontal.TProgressbar",
        )
        progress_bar.grid(row=1, column=0, sticky="ew")
        progress_frame.grid_remove()

        output = tk.Text(
            results_frame,
            wrap="word",
            bg=BG_WHITE,
            fg=TEXT_DARK,
            insertbackground=TEXT_DARK,
            font=("Consolas", 10),
            relief="solid",
            borderwidth=1,
            bd=1,
            highlightbackground=BORDER_COLOR,
            highlightcolor=BORDER_COLOR,
            padx=10,
            pady=10,
            state="disabled",
            selectbackground=PRIMARY_COLOR,
            selectforeground=TEXT_WHITE,
        )
        scrollbar = tk.Scrollbar(
            results_frame,
            orient="vertical",
            command=output.yview,
            troughcolor=BG_LIGHT,
            activebackground=PRIMARY_COLOR,
            relief="flat",
            borderwidth=0,
        )
        output.configure(yscrollcommand=scrollbar.set)
        output.grid(row=1, column=0, sticky="nsew")
        scrollbar.grid(row=1, column=1, sticky="ns")

        if screen == "main":
            output.tag_configure("positive", foreground=ACCENT_GREEN)
            output.tag_configure("negative", foreground=PRIMARY_COLOR)
            output.tag_configure("normal", foreground=TEXT_DARK)
            self.output = output
            self.progress_frame = progress_frame
            self.progress_label = progress_label
            self.progress_bar = progress_bar
            self._output_scrollbar = scrollbar
            self._progress_total = 0
            self._progress_current = 0
        else:
            self.command_output = output

    def _build_main_footer(self, sidebar: tk.Frame) -> None:
        footer = tk.Frame(sidebar, bg=BG_LIGHT, padx=12, pady=10)
        footer.pack(side="bottom", fill="x")
        self.status = tk.Label(
            footer,
            text="Status: Pronto",
            bg=BG_LIGHT,
            fg=ACCENT_GREEN,
            anchor="w",
            font=("Segoe UI", 9, "bold"),
        )
        self.status.pack(fill="x", pady=(0, 7))

        buttons = tk.Frame(footer, bg=BG_LIGHT)
        buttons.pack(fill="x")
        clear_button = self._make_button(buttons, "Limpar", self.clear_output)
        clear_button.pack(side="left", fill="x", expand=True, padx=(0, 3))
        exit_button = self._make_button(buttons, "Sair", self.root.destroy)
        exit_button.pack(side="left", fill="x", expand=True, padx=(3, 0))
        self._buttons.extend((clear_button, exit_button))
        self._button_labels[clear_button] = "Limpar"
        self._button_labels[exit_button] = "Sair"

    def _build_commands_footer(self, sidebar: tk.Frame) -> None:
        footer = tk.Frame(sidebar, bg=BG_LIGHT, padx=12, pady=10)
        footer.pack(side="bottom", fill="x")
        self.command_status = tk.Label(
            footer,
            text="Status: Pronto",
            bg=BG_LIGHT,
            fg=ACCENT_GREEN,
            anchor="w",
            font=("Segoe UI", 9, "bold"),
        )
        self.command_status.pack(fill="x", pady=(0, 7))
        back_button = self._make_button(footer, "Voltar", self._back_to_main)
        back_button.pack(fill="x")
        self._command_buttons.append(back_button)
        self._command_button_labels[back_button] = "Voltar"

    def _append_output(self, text: str) -> None:
        """Adiciona texto à área de resultados na thread da interface."""
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
        """Adiciona status à área de comandos."""
        self.command_output.configure(state="normal")
        self.command_output.insert("end", text)
        self.command_output.see("end")
        self.command_output.configure(state="disabled")

    def clear_output(self) -> None:
        """Limpa os resultados principais quando não há operação em curso."""
        if self._busy:
            return
        self._clear_output()

    def _clear_output(self) -> None:
        self.output.configure(state="normal")
        self.output.delete("1.0", "end")
        self.output.configure(state="disabled")

    def _show_progress(self, label_text: str, total: int = 0) -> None:
        """Mostra a barra no painel direito e oculta o relatório até terminar."""
        self._clear_output()
        self.output.grid_remove()
        self._output_scrollbar.grid_remove()
        self._progress_total = total
        self._progress_current = 0
        self._active_progress_name = label_text
        self.progress_label.configure(text=f"Executando: {label_text}...")
        self.progress_frame.grid()
        if total > 0:
            self.progress_bar.stop()
            self.progress_bar.configure(mode="determinate", maximum=total, value=0)
        else:
            self.progress_bar.configure(mode="indeterminate", value=0)
            self.progress_bar.start(10)

    def _hide_progress(self) -> None:
        """Para a animação e reexibe o relatório principal."""
        self.progress_bar.stop()
        self.progress_frame.grid_remove()
        self.output.grid(row=1, column=0, sticky="nsew")
        self._output_scrollbar.grid(row=1, column=1, sticky="ns")

    def _update_progress(self, current: int, total: int, label: str) -> None:
        self.progress_bar.configure(mode="determinate", maximum=total, value=current)
        self.progress_label.configure(
            text=f"Executando: {label}... ({current}/{total})"
        )

    def _progress_name(self, section_title: str) -> str:
        names = {
            "VERIFICAÇÃO DE COMPATIBILIDADE — ANOTA AI": "Verificando compatibilidade",
            "INFORMAÇÕES DO SISTEMA": "Coletando informações do sistema",
            "MONITOR DE CPU": "Monitorando CPU",
            "DATA, HORA E SINCRONIZAÇÃO": "Sincronizando data e hora",
            "TESTE DE VELOCIDADE DA INTERNET": "Testando velocidade",
            "LIMPEZA DE ARQUIVOS TEMPORÁRIOS": "Limpando temporários",
        }
        return names.get(section_title, section_title)

    def _set_busy(self, label: str) -> None:
        self._busy = True
        self.status.configure(text="Status: Executando...", fg=PRIMARY_COLOR)
        for button in self._buttons:
            button.configure(state="disabled")
        for button, button_label in self._button_labels.items():
            if button_label == label:
                button.configure(text="Executando...")
                break

    def _set_ready(self) -> None:
        self._busy = False
        self.status.configure(text="Status: Pronto", fg=ACCENT_GREEN)
        for button in self._buttons:
            button.configure(state="normal", text=self._button_labels[button])

    def _start_operation(self, label: str, sections: list[Section]) -> None:
        """Inicia uma ou mais seções em uma thread de trabalho."""
        if self._busy:
            return
        self._set_busy(label)
        progress_name = (
            self._progress_name(sections[0][0]) if len(sections) == 1 else label
        )
        self._show_progress(
            progress_name,
            total=len(sections) if len(sections) > 1 else 0,
        )
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
            self._result_queue.put(("progress", title))
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
        try:
            message_type, payload = self._result_queue.get_nowait()
        except queue.Empty:
            message_type, payload = None, None

        if message_type == "progress" and payload is not None:
            progress_name = self._progress_name(payload)
            self._active_progress_name = progress_name
            if self._progress_total > 0:
                next_step = min(self._progress_current + 1, self._progress_total)
                self.progress_bar.configure(
                    mode="determinate",
                    maximum=self._progress_total,
                    value=self._progress_current,
                )
                self.progress_label.configure(
                    text=(
                        f"Executando: {progress_name}... "
                        f"({next_step}/{self._progress_total})"
                    )
                )
            else:
                self.progress_label.configure(
                    text=f"Executando: {progress_name}..."
                )
        elif message_type == "output" and payload is not None:
            # O texto é acumulado enquanto a barra está visível e só aparece
            # quando todas as seções terminarem.
            self._append_output(payload)
            if self._progress_total > 0:
                self._progress_current = min(
                    self._progress_current + 1, self._progress_total
                )
                self._update_progress(
                    self._progress_current,
                    self._progress_total,
                    self._active_progress_name,
                )
        elif message_type == "done":
            finished = True

        if finished:
            self._hide_progress()
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
            "Data/Hora e Sincronização",
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
        self.command_status.configure(text="Status: Executando...", fg=PRIMARY_COLOR)
        for button in self._command_buttons:
            button.configure(state="disabled")
        self._append_command_output(f"{label}\n")

    def _set_command_ready(self) -> None:
        self._command_busy = False
        self.command_status.configure(text="Status: Pronto", fg=ACCENT_GREEN)
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
