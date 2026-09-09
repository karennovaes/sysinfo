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
import tkinter.font as tkfont
import urllib.request
from tkinter import ttk
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
BG_DARK = "#1A1A2E"
BG_DARKER = "#16213E"
TEXT_LIGHT = "#E0E0E0"
TEXT_WHITE = "#FFFFFF"
ACCENT_GREEN = "#00FF94"
HOVER_COLOR = "#C41523"
BORDER_COLOR = PRIMARY_COLOR

# Aliases mantidos para os nomes usados pela lógica de saída.
SECONDARY_COLOR = TEXT_WHITE
RESULT_TEXT_COLOR = TEXT_LIGHT
POSITIVE_COLOR = ACCENT_GREEN
NEGATIVE_COLOR = PRIMARY_COLOR
WINDOW_TITLE = "Diagnóstico do Sistema — Anota AI"

Action = Callable[[], None]
Section = tuple[str, Action]
ANSI_RE = re.compile(r"\x1b\[([0-9;]*)m")


class RoundedButton(tk.Canvas):
    """Botão leve desenhado em canvas para obter cantos realmente arredondados.

    A classe expõe ``configure(state=..., text=...)`` como um ``tk.Button``
    para que o bloqueio dos controles durante as threads continue intacto.
    O desenho é recalculado quando o widget muda de largura, mantendo o
    preenchimento arredondado também em layouts redimensionáveis.
    """

    def __init__(
        self,
        parent: tk.Misc,
        *,
        text: str,
        command: Action,
        bg: str = PRIMARY_COLOR,
        hover_bg: str = HOVER_COLOR,
        fg: str = TEXT_WHITE,
        font: tuple[str, int, str],
        padx: int = 16,
        pady: int = 10,
    ) -> None:
        self._button_bg = bg
        self._hover_bg = hover_bg
        self._foreground = fg
        self._font = tkfont.Font(font=font)
        self._text = text
        self._command = command
        self._button_state = tk.NORMAL
        self._radius = 12
        self._padx = padx
        self._height = max(42, self._font.metrics("linespace") + (pady * 2))

        parent_bg = parent.cget("bg")
        super().__init__(
            parent,
            height=self._height,
            bg=parent_bg,
            bd=0,
            highlightthickness=0,
            relief="flat",
            cursor="hand2",
        )
        self._font.configure(weight="bold")
        self.bind("<Configure>", self._redraw)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click)
        self._redraw()

    @staticmethod
    def _rounded_rectangle(
        canvas: tk.Canvas,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        radius: int,
        **kwargs: object,
    ) -> None:
        """Desenha um retângulo arredondado usando arcos e retângulos do canvas."""
        diameter = radius * 2
        canvas.create_arc(x1, y1, x1 + diameter, y1 + diameter, start=90, extent=90, **kwargs)
        canvas.create_arc(x2 - diameter, y1, x2, y1 + diameter, start=0, extent=90, **kwargs)
        canvas.create_arc(x1, y2 - diameter, x1 + diameter, y2, start=180, extent=90, **kwargs)
        canvas.create_arc(x2 - diameter, y2 - diameter, x2, y2, start=270, extent=90, **kwargs)
        canvas.create_rectangle(x1 + radius, y1, x2 - radius, y2, **kwargs)
        canvas.create_rectangle(x1, y1 + radius, x2, y2 - radius, **kwargs)

    def _redraw(self, _event: tk.Event | None = None) -> None:
        self.delete("all")
        width = max(self.winfo_width(), 80)
        inset = 2
        radius = min(self._radius, max(6, (self._height - inset * 2) // 2))
        color = self._button_bg if self._button_state == tk.NORMAL else "#5B2730"

        # Sombra discreta e o botão deslocado um pixel dão profundidade sem
        # depender de efeitos nativos diferentes entre plataformas.
        self._rounded_rectangle(
            self, inset + 1, inset + 3, width - inset + 1, self._height + 1,
            radius, fill="#0D0D1A", outline="",
        )
        self._rounded_rectangle(
            self, inset, inset, width - inset, self._height - inset,
            radius, fill=color, outline="",
        )
        self.create_text(
            width // 2, self._height // 2, text=self._text, fill=self._foreground,
            font=self._font, anchor="center",
        )

    def _on_enter(self, _event: tk.Event) -> None:
        if self._button_state == tk.NORMAL:
            self._button_bg, self._current_bg = self._hover_bg, self._button_bg
            self._redraw()

    def _on_leave(self, _event: tk.Event) -> None:
        if self._button_state == tk.NORMAL and hasattr(self, "_current_bg"):
            self._button_bg, self._current_bg = self._current_bg, self._button_bg
            self._redraw()

    def _on_click(self, _event: tk.Event) -> None:
        if self._button_state == tk.NORMAL:
            self._command()

    def configure(self, cnf: dict[str, object] | None = None, **kwargs: object) -> None:
        if cnf:
            kwargs.update(cnf)
        state = kwargs.pop("state", None)
        text = kwargs.pop("text", None)
        if state is not None:
            self._button_state = state
            self.configure_cursor()
        if text is not None:
            self._text = str(text)
        if kwargs:
            super().configure(**kwargs)
        if state is not None or text is not None:
            self._redraw()

    def configure_cursor(self) -> None:
        self.configure_cursor_value = "hand2" if self._button_state == tk.NORMAL else ""
        super().configure(cursor=self.configure_cursor_value)


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
        self.root.geometry("860x680")
        self.root.minsize(700, 560)
        self.root.configure(bg=BG_DARK)

        # As duas telas compartilham este container e nunca criam uma janela
        # adicional. Apenas uma delas fica empacotada por vez.
        self.container = tk.Frame(self.root, bg=BG_DARK)
        self.container.pack(fill="both", expand=True)
        self.main_frame = tk.Frame(self.container, bg=BG_DARK)
        self.commands_frame = tk.Frame(self.container, bg=BG_DARK)

        self._buttons: list[RoundedButton] = []
        self._button_labels: dict[tk.Button, str] = {}
        self._result_queue: queue.Queue[tuple[str, str | None]] = queue.Queue()
        self._busy = False

        self._command_buttons: list[RoundedButton] = []
        self._command_button_labels: dict[tk.Button, str] = {}
        self._command_result_queue: queue.Queue[tuple[str, str | None]] = queue.Queue()
        self._command_busy = False

        self._build_main_frame()
        self._build_commands_frame()
        self.main_frame.pack(fill="both", expand=True)

    def _build_main_frame(self) -> None:
        """Monta a tela principal dentro de ``main_frame``."""
        self._build_header(self.main_frame, WINDOW_TITLE.upper(), 90, 16, 24)
        self._build_actions(self.main_frame)
        self._build_results(self.main_frame, "main")
        self._build_main_footer(self.main_frame)

    def _build_commands_frame(self) -> None:
        """Monta a tela de comandos dentro de ``commands_frame``."""
        self._build_header(self.commands_frame, "COMANDOS — ANOTA AI", 76, 16, 24)
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
        """Cria um cabeçalho escuro com cápsula vermelha e linha de glow."""
        header = tk.Canvas(
            parent, height=height, bg=BG_DARK, bd=0, highlightthickness=0
        )
        header.pack(fill="x", padx=16, pady=(14, 4))

        def redraw(_event: tk.Event | None = None) -> None:
            header.delete("all")
            width = max(header.winfo_width(), 120)
            header.create_arc(
                0, 0, 28, height, start=90, extent=90, fill=PRIMARY_COLOR, outline=""
            )
            header.create_arc(
                width - 28, 0, width, height, start=0, extent=90,
                fill=PRIMARY_COLOR, outline=""
            )
            header.create_rectangle(14, 0, width - 14, height, fill=PRIMARY_COLOR, outline="")
            header.create_rectangle(0, 14, width, height - 14, fill=PRIMARY_COLOR, outline="")
            header.create_text(
                padx + 4, height // 2 - 5, text=title_text, anchor="w",
                fill=TEXT_WHITE, font=("Arial", font_size, "bold")
            )
            header.create_line(
                padx + 4, height - 17, width - padx - 4, height - 17,
                fill=TEXT_WHITE, width=1
            )

        header.bind("<Configure>", redraw)
        redraw()

    def _build_actions(self, parent: tk.Misc) -> None:
        actions = tk.Frame(parent, bg=BG_DARK, padx=24, pady=20)
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
        actions = tk.Frame(parent, bg=BG_DARK, padx=22, pady=16)
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
    ) -> RoundedButton:
        return RoundedButton(
            parent, text=label, command=action, padx=padx, pady=pady,
            font=("Segoe UI", 10, "bold"),
        )

    def _build_results(self, parent: tk.Misc, screen: str) -> None:
        horizontal_pad = 24 if screen == "main" else 22
        results_frame = tk.Frame(
            parent, bg=BG_DARKER, padx=16, pady=12,
            highlightbackground=BORDER_COLOR, highlightcolor=BORDER_COLOR,
            highlightthickness=2,
        )
        results_frame.pack(fill="both", expand=True, padx=horizontal_pad, pady=(2, 8))
        results_frame.grid_rowconfigure(1, weight=1)
        results_frame.grid_columnconfigure(0, weight=1)

        # A área de progresso ocupa o topo do painel de resultados. Ela fica
        # escondida até uma operação começar; assim o relatório não aparece
        # enquanto o diagnóstico ainda está sendo executado.
        progress_frame = tk.Frame(results_frame, bg=BG_DARKER)
        progress_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        progress_frame.grid_columnconfigure(0, weight=1)
        progress_label = tk.Label(
            progress_frame, text="", bg=BG_DARKER, fg=TEXT_LIGHT,
            font=("Segoe UI", 10, "bold"),
        )
        progress_label.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        progress_style = ttk.Style(self.root)
        progress_style.configure(
            "Futuristic.Horizontal.TProgressbar",
            troughcolor=BG_DARK, background=PRIMARY_COLOR,
            lightcolor=PRIMARY_COLOR, darkcolor=PRIMARY_COLOR, bordercolor=BG_DARK,
        )
        progress_bar = ttk.Progressbar(
            progress_frame, orient="horizontal",
            style="Futuristic.Horizontal.TProgressbar",
        )
        progress_bar.grid(row=1, column=0, sticky="ew", padx=32)
        progress_frame.grid_remove()

        output = tk.Text(
            results_frame, wrap="word", bg=BG_DARKER, fg=TEXT_LIGHT,
            insertbackground=TEXT_LIGHT, font=("Consolas", 10),
            relief="flat", borderwidth=0, padx=16, pady=12,
            state="disabled", selectbackground=PRIMARY_COLOR,
        )
        scrollbar = tk.Scrollbar(
            results_frame, orient="vertical", command=output.yview,
            bg=BG_DARK, troughcolor=BG_DARKER, activebackground=PRIMARY_COLOR,
            relief="flat", borderwidth=0, width=12,
        )
        output.configure(yscrollcommand=scrollbar.set)
        if screen == "main":
            output.tag_configure("positive", foreground=ACCENT_GREEN)
            output.tag_configure("negative", foreground=PRIMARY_COLOR)
            output.tag_configure("normal", foreground=TEXT_LIGHT)
            self.output = output
            self.progress_frame = progress_frame
            self.progress_label = progress_label
            self.progress_bar = progress_bar
            self._progress_total = 0
            self._progress_current = 0
        else:
            self.command_output = output
        output.grid(row=1, column=0, sticky="nsew")
        scrollbar.grid(row=1, column=1, sticky="ns", padx=(8, 0))
        if screen == "main":
            self._output_scrollbar = scrollbar

    def _build_main_footer(self, parent: tk.Misc) -> None:
        footer = tk.Frame(parent, bg=BG_DARK, padx=24, pady=16)
        footer.pack(fill="x")
        self.status = tk.Label(
            footer,
            text="Pronto",
            bg=BG_DARK,
            fg=ACCENT_GREEN,
            anchor="w",
            font=("Segoe UI", 9),
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
        footer = tk.Frame(parent, bg=BG_DARK, padx=22, pady=16)
        footer.pack(fill="x")
        self.command_status = tk.Label(
            footer,
            text="Pronto",
            bg=BG_DARK,
            fg=ACCENT_GREEN,
            anchor="w",
            font=("Segoe UI", 9),
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

    def _clear_output(self) -> None:
        """Limpa o relatório principal sem considerar o estado de ocupação."""
        self.output.configure(state="normal")
        self.output.delete("1.0", "end")
        self.output.configure(state="disabled")

    def _show_progress(self, label_text: str, total: int = 0) -> None:
        """Mostra o progresso e oculta o relatório durante uma operação."""
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
        """Para a animação e volta a exibir o relatório principal."""
        self.progress_bar.stop()
        self.progress_frame.grid_remove()
        self.output.grid(row=1, column=0, sticky="nsew")
        self._output_scrollbar.grid(row=1, column=1, sticky="ns")

    def _update_progress(self, current: int, total: int, label: str) -> None:
        """Atualiza a etapa atual do diagnóstico geral."""
        self.progress_bar.configure(mode="determinate", maximum=total, value=current)
        self.progress_label.configure(
            text=f"Executando: {label}... ({current}/{total})"
        )

    def _progress_name(self, section_title: str) -> str:
        """Converte o título do relatório no nome amigável da etapa."""
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
        self.status.configure(text="Pronto", fg=ACCENT_GREEN)
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
                # A etapa atual aparece no texto, mas a barra só avança
                # quando o resultado dessa etapa chega à fila.
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
            self._append_output(payload)
            # No modo geral, o relatório é preenchido e exibido à medida
            # que cada etapa termina, sem esperar a última seção.
            if self._progress_total > 0:
                self._progress_current = min(
                    self._progress_current + 1, self._progress_total
                )
                self._update_progress(
                    self._progress_current,
                    self._progress_total,
                    self._active_progress_name,
                )
                self.output.grid(row=1, column=0, sticky="nsew")
                self._output_scrollbar.grid(row=1, column=1, sticky="ns")
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
        self.command_status.configure(text="Pronto", fg=ACCENT_GREEN)
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
