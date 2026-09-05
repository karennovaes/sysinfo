"""Interface gráfica do Diagnóstico do Sistema — Anota AI.

A interface reutiliza as rotinas de diagnóstico do pacote ``modules``. O
arquivo ``main.py`` continua disponível como alternativa de terminal.
"""

from __future__ import annotations

import ctypes
import platform
import queue
import re
import subprocess
import sys
import threading
import tkinter as tk
from contextlib import redirect_stdout
from io import StringIO
from collections.abc import Callable

from modules.compatibility_check import display_compatibility_check
from modules.cpu_monitor import monitor_cpu
from modules.datetime_sync import display_datetime_sync
from modules.speedtest import display_speed_test
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
    """Janela principal da aplicação gráfica."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(WINDOW_TITLE)
        self.root.geometry("800x600")
        self.root.minsize(640, 480)
        self.root.configure(bg=SECONDARY_COLOR)

        self._buttons: list[tk.Button] = []
        self._button_labels: dict[tk.Button, str] = {}
        self._result_queue: queue.Queue[tuple[str, str | None]] = queue.Queue()
        self._busy = False
        self._build_header()
        self._build_actions()
        self._build_results()
        self._build_footer()

    def _build_header(self) -> None:
        header = tk.Frame(self.root, bg=PRIMARY_COLOR, height=76)
        header.pack(fill="x")
        header.pack_propagate(False)
        title = tk.Label(
            header,
            text=WINDOW_TITLE.upper(),
            bg=PRIMARY_COLOR,
            fg=SECONDARY_COLOR,
            font=("Arial", 15, "bold"),
            anchor="w",
            padx=24,
        )
        title.pack(fill="both", expand=True)

    def _build_actions(self) -> None:
        actions = tk.Frame(self.root, bg=SECONDARY_COLOR, padx=24, pady=20)
        actions.pack(fill="x")
        for column in range(2):
            actions.grid_columnconfigure(column, weight=1)

        definitions: list[tuple[str, Action]] = [
            ("Verificar Compatibilidade", self._check_compatibility),
            ("Informações do Sistema", self._show_system_info),
            ("Monitor de CPU", self._monitor_cpu),
            ("Data, Hora e Sincronização", self._show_datetime),
            ("Teste de Velocidade", self._speed_test),
            ("Executar Tudo", self._run_all),
        ]
        for index, (label, action) in enumerate(definitions):
            button = tk.Button(
                actions,
                text=label,
                command=action,
                bg=PRIMARY_COLOR,
                fg=SECONDARY_COLOR,
                activebackground=PRIMARY_COLOR,
                activeforeground=SECONDARY_COLOR,
                relief="flat",
                cursor="hand2",
                font=("Arial", 10, "bold"),
                padx=10,
                pady=9,
            )
            button.grid(
                row=index // 2,
                column=index % 2,
                padx=6,
                pady=5,
                sticky="ew",
            )
            self._buttons.append(button)
            self._button_labels[button] = label

    def _build_results(self) -> None:
        results_frame = tk.Frame(self.root, bg=SECONDARY_COLOR, padx=24)
        results_frame.pack(fill="both", expand=True)
        results_frame.grid_rowconfigure(0, weight=1)
        results_frame.grid_columnconfigure(0, weight=1)

        self.output = tk.Text(
            results_frame,
            wrap="word",
            bg=SECONDARY_COLOR,
            fg=RESULT_TEXT_COLOR,
            insertbackground=RESULT_TEXT_COLOR,
            font=("Consolas", 10),
            relief="solid",
            borderwidth=1,
            padx=12,
            pady=10,
            state="disabled",
        )
        scrollbar = tk.Scrollbar(
            results_frame, orient="vertical", command=self.output.yview
        )
        self.output.configure(yscrollcommand=scrollbar.set)
        self.output.tag_configure("positive", foreground=POSITIVE_COLOR)
        self.output.tag_configure("negative", foreground=NEGATIVE_COLOR)
        self.output.tag_configure("normal", foreground=RESULT_TEXT_COLOR)
        self.output.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

    def _build_footer(self) -> None:
        footer = tk.Frame(self.root, bg=SECONDARY_COLOR, padx=24, pady=12)
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

        clear_button = tk.Button(
            footer,
            text="Limpar",
            command=self.clear_output,
            bg=PRIMARY_COLOR,
            fg=SECONDARY_COLOR,
            activebackground=PRIMARY_COLOR,
            activeforeground=SECONDARY_COLOR,
            relief="flat",
            padx=16,
            pady=6,
        )
        clear_button.pack(side="right", padx=(6, 0))
        exit_button = tk.Button(
            footer,
            text="Sair",
            command=self.root.destroy,
            bg=PRIMARY_COLOR,
            fg=SECONDARY_COLOR,
            activebackground=PRIMARY_COLOR,
            activeforeground=SECONDARY_COLOR,
            relief="flat",
            padx=16,
            pady=6,
        )
        exit_button.pack(side="right")
        self._buttons.extend((clear_button, exit_button))
        self._button_labels[clear_button] = "Limpar"
        self._button_labels[exit_button] = "Sair"

    def _append_output(self, text: str) -> None:
        """Adiciona texto à área de resultados na thread principal."""
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

    def clear_output(self) -> None:
        """Limpa os resultados exibidos quando não há operação em curso."""
        if self._busy:
            return
        self.output.configure(state="normal")
        self.output.delete("1.0", "end")
        self.output.configure(state="disabled")

    def _set_busy(self, label: str) -> None:
        """Bloqueia os controles e identifica a operação em andamento."""
        self._busy = True
        self.status.configure(text="Executando...", fg=PRIMARY_COLOR)
        for button in self._buttons:
            button.configure(state="disabled")
        for button, button_label in self._button_labels.items():
            if button_label == label:
                button.configure(text="Executando...")
                break

    def _set_ready(self) -> None:
        """Libera os controles após o término da operação."""
        self._busy = False
        self.status.configure(text="Pronto", fg=RESULT_TEXT_COLOR)
        for button in self._buttons:
            button.configure(state="normal")
            button.configure(text=self._button_labels[button])

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
        """Entrega os resultados da thread à interface usando ``after``."""
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

    def _check_compatibility(self) -> None:
        self._start_operation(
            "Verificar Compatibilidade",
            [("VERIFICAÇÃO DE COMPATIBILIDADE — ANOTA AI", display_compatibility_check)],
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

    def _run_all(self) -> None:
        self._start_operation(
            "Executar Tudo",
            [
                ("VERIFICAÇÃO DE COMPATIBILIDADE — ANOTA AI", display_compatibility_check),
                (
                    "INFORMAÇÕES DO SISTEMA",
                    lambda: display_system_info(collect_system_info()),
                ),
                ("MONITOR DE CPU", lambda: monitor_cpu(duration=10, interval=1.0)),
                ("DATA, HORA E SINCRONIZAÇÃO", display_datetime_sync),
                ("TESTE DE VELOCIDADE DA INTERNET", display_speed_test),
            ],
        )



def main() -> None:
    """Inicia a interface gráfica com elevação UAC quando necessário."""
    _ensure_admin()
    root = tk.Tk()
    SystemDiagnosticsApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
