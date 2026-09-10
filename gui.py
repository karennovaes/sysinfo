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
try:
    import tkinter as tk
    from tkinter import ttk
except ImportError:  # Permite usar as rotinas não gráficas em ambientes sem Tk.
    tk = None
    ttk = None

# Permite importar as rotinas em ambientes sem Tk/display.
_FrameBase = tk.Frame if tk is not None else object
import urllib.request
from collections.abc import Callable
from contextlib import redirect_stdout
from io import StringIO

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
from modules.security import calculate_sha256, log_audit, validate_url
from modules.theme import *

Action = Callable[[], None]
Section = tuple[str, Action]
ANSI_RE = re.compile(r"\x1b\[([0-9;]*)m")



def _rounded_shape(
    canvas: tk.Canvas,
    width: int,
    height: int,
    radius: int,
    fill: str,
) -> None:
    """Desenha um botão com cantos arredondados usando primitivas do Canvas."""
    canvas.delete("rounded-shape")
    if width <= 0 or height <= 0:
        return
    radius = max(1, min(radius, width // 2, height // 2))
    diameter = radius * 2
    arc_options = {
        "style": "pieslice",
        "fill": fill,
        "outline": fill,
        "tags": "rounded-shape",
    }
    canvas.create_arc(0, 0, diameter, diameter, start=0, extent=90, **arc_options)
    canvas.create_arc(
        width - diameter, 0, width, diameter, start=90, extent=90, **arc_options
    )
    canvas.create_arc(
        width - diameter, height - diameter, width, height,
        start=180, extent=90, **arc_options
    )
    canvas.create_arc(
        0, height - diameter, diameter, height,
        start=270, extent=90, **arc_options
    )
    canvas.create_rectangle(
        radius, 0, width - radius, height,
        fill=fill, outline=fill, tags="rounded-shape"
    )
    canvas.create_rectangle(
        0, radius, width, height - radius,
        fill=fill, outline=fill, tags="rounded-shape"
    )


class RoundedButton(_FrameBase):
    """Botão com Canvas interno, hover e estado disabled.

    O ``Frame`` é o widget que participa do ``pack(fill="x")``. O Canvas
    ocupa todo o Frame com ``place`` e, assim, acompanha automaticamente a
    largura disponível do sidebar.
    """

    def __init__(
        self,
        parent: tk.Misc,
        text: str,
        command: Action | None = None,
        *,
        width: int = 180,
        height: int = 40,
        radius: int = 12,
        **kwargs: object,
    ) -> None:
        if tk is None:
            raise RuntimeError("Tk não está disponível neste ambiente")
        self._text = text
        self._command = command
        self._radius = radius
        self._disabled = False
        self._hovered = False
        self._pressed = False
        self._font = kwargs.pop("font", FONT_BUTTON)
        background = kwargs.pop("bg", BG_LIGHT)
        cursor = kwargs.pop("cursor", "hand2")

        super().__init__(
            parent,
            width=width,
            height=height,
            bg=background,
            highlightthickness=0,
            bd=0,
            relief="flat",
            cursor=cursor,
            **kwargs,
        )
        self.canvas = tk.Canvas(
            self,
            bg=background,
            highlightthickness=0,
            bd=0,
            relief="flat",
            cursor=cursor,
        )
        self.canvas.place(x=0, y=0, relwidth=1, relheight=1)
        self.canvas.bind("<Configure>", self._on_resize)
        self.canvas.bind("<Enter>", self._on_enter)
        self.canvas.bind("<Leave>", self._on_leave)
        self.canvas.bind("<Button-1>", self._on_press)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self._draw()

    def _draw(self) -> None:
        width = self.canvas.winfo_width()
        if width <= 1:
            width = int(self.cget("width"))
        width = max(1, width)

        height = self.canvas.winfo_height()
        if height <= 1:
            height = int(self.cget("height"))
        height = max(1, height)
        if self._disabled:
            fill = BG_LIGHT
            foreground = "#A8A8A8"
        elif self._hovered or self._pressed:
            fill = HOVER_COLOR
            foreground = TEXT_WHITE
        else:
            fill = PRIMARY_COLOR
            foreground = TEXT_WHITE
        _rounded_shape(self.canvas, width, height, self._radius, fill)
        self.canvas.delete("button-label")
        self.canvas.create_text(
            width // 2,
            height // 2,
            text=self._text,
            fill=foreground,
            font=self._font,
            tags="button-label",
            anchor="center",
        )

    def _on_resize(self, _event: tk.Event) -> None:
        self._draw()

    def _on_enter(self, _event: tk.Event) -> None:
        if not self._disabled:
            self._hovered = True
            self._draw()

    def _on_leave(self, _event: tk.Event) -> None:
        self._hovered = False
        self._pressed = False
        self._draw()

    def _on_press(self, _event: tk.Event) -> None:
        if not self._disabled:
            self._pressed = True
            self._draw()

    def _on_release(self, _event: tk.Event) -> None:
        was_pressed = self._pressed
        self._pressed = False
        self._draw()
        if was_pressed and self._hovered and not self._disabled and self._command:
            self._command()

    def configure(self, cnf: dict[str, object] | None = None, **kwargs: object):
        """Mantém a API de estado/texto usada pela lógica da aplicação."""
        options: dict[str, object] = {}
        if cnf:
            options.update(cnf)
        options.update(kwargs)
        if "text" in options:
            self._text = str(options.pop("text"))
        if "command" in options:
            self._command = options.pop("command")  # type: ignore[assignment]
        if "state" in options:
            state = str(options.pop("state"))
            self._disabled = state == "disabled"
            if self._disabled:
                self._hovered = False
                self._pressed = False
        result = super().configure(**options)
        self._draw()
        return result

    config = configure


def _creation_flags() -> int:
    """Retorna flags que impedem uma janela de console no Windows."""
    creationflags = 0
    if platform.system() == "Windows":
        creationflags = subprocess.CREATE_NO_WINDOW
    return creationflags


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



def _run_command_capture(command: list[str]) -> str:
    """Executa um comando e retorna stdout+stderr como string."""
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
            creationflags=_creation_flags(),
        )
        output = (result.stdout or "") + (result.stderr or "")
        return output.strip() or "Comando executado sem saída."
    except Exception as exc:
        return f"Erro ao executar: {exc}"


def _clear_print_queue() -> str:
    """Para o spooler, limpa a fila e reinicia."""
    commands = [
        ["net", "stop", "spooler"],
        ["del", "/Q", "/F", "/S", r"%systemroot%\System32\Spool\Printers\*.*"],
        ["net", "start", "spooler"],
    ]
    output_lines: list[str] = []
    for command in commands:
        # ``del`` é um comando interno do CMD; shell=True é usado somente
        # nesta rotina, como exige o próprio Windows para esse comando.
        command_text = " ".join(command)
        try:
            if command[0].casefold() == "del":
                # ``del`` é interno ao CMD e exige shell=True.
                result = subprocess.run(
                    command_text,
                    capture_output=True,
                    text=True,
                    timeout=15,
                    check=False,
                    shell=True,
                    creationflags=_creation_flags(),
                )
            else:
                result = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    timeout=15,
                    check=False,
                    creationflags=_creation_flags(),
                )
            output_lines.append(f"> {' '.join(command)}")
            output_lines.append((result.stdout or result.stderr or "OK").strip())
        except Exception as exc:
            output_lines.append(f"> {' '.join(command)}")
            output_lines.append(f"Erro ao executar: {exc}")
    return "\n".join(output_lines)


class SystemDiagnosticsApp:
    """Janela principal com menu inicial e quatro telas de comandos."""

    PRINTERS_COMMAND = "shell:::{A8A91A66-3A7D-4424-8D24-04E180695C7A}"
    DRIVER_URL = (
        "https://raw.githubusercontent.com/Delutto/instalador_universal/main/"
        "Output/Instalador_Universal_0.9.4.exe"
    )
    DRIVER_FILENAME = "Instalador_Universal_0.9.4.exe"
    DESKTOP_URL = "https://app.anota.ai/download-app/anotaai-desktop"
    DESKTOP_FILENAME = "anotaai-desktop.exe"
    NETSTATGUI_URL = (
        "https://raw.githubusercontent.com/Delutto/NetStatGUI/main/bin/NetStatGUI.exe"
    )
    NETSTATGUI_FILENAME = "NetStatGUI.exe"

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(WINDOW_TITLE)
        self.root.geometry("700x500")
        self.root.minsize(500, 400)
        self.root.resizable(True, True)
        self.root.configure(bg=BG_WHITE)
        self._configure_styles()

        self.container = tk.Frame(self.root, bg=BG_WHITE)
        self.container.pack(fill="both", expand=True)
        self.initial_frame = tk.Frame(self.container, bg=BG_WHITE)
        self.tools_frame = tk.Frame(self.container, bg=BG_WHITE)
        self.printer_frame = tk.Frame(self.container, bg=BG_WHITE)
        self.files_frame = tk.Frame(self.container, bg=BG_WHITE)
        self.commands_frame = tk.Frame(self.container, bg=BG_WHITE)
        self._frames = (
            self.initial_frame,
            self.tools_frame,
            self.printer_frame,
            self.files_frame,
            self.commands_frame,
        )

        self._buttons: dict[str, list[ttk.Button | RoundedButton]] = {}
        self._button_labels: dict[ttk.Button | RoundedButton, str] = {}
        self._outputs: dict[str, tk.Text] = {}
        self._statuses: dict[str, tk.Label] = {}
        self._result_queue: queue.Queue[tuple[str, str | None]] = queue.Queue()
        self._command_result_queue: queue.Queue[tuple[str, str | None]] = queue.Queue()
        self._busy = False
        self._command_busy = False
        self._active_screen = ""
        self._pending_tool_output = ""
        self._progress_total = 0
        self._progress_current = 0

        self._build_initial_frame()
        self._build_tools_frame()
        self._build_printer_frame()
        self._build_files_frame()
        self._build_commands_frame()
        self.initial_frame.pack(fill="both", expand=True)

    def _configure_styles(self) -> None:
        """Configura o tema claro e os estilos compartilhados da interface."""
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure(
            "Rounded.TButton",
            background=PRIMARY_COLOR,
            foreground=TEXT_WHITE,
            font=FONT_BUTTON,
            borderwidth=0,
            focusthickness=0,
            padding=(12, 8),
            relief="flat",
        )
        style.map(
            "Rounded.TButton",
            background=[("disabled", BG_LIGHT), ("pressed", HOVER_COLOR), ("active", HOVER_COLOR)],
            foreground=[("disabled", "#A8A8A8"), ("!disabled", TEXT_WHITE)],
        )
        style.configure(
            "Card.TButton",
            background=BG_CARD,
            foreground=TEXT_DARK,
            font=FONT_CARD,
            borderwidth=1,
            bordercolor=BORDER_COLOR,
            focusthickness=0,
            padding=(20, 15),
            relief="solid",
        )
        style.map(
            "Card.TButton",
            background=[("pressed", "#F1F1F2"), ("active", BG_CARD)],
            foreground=[("pressed", HOVER_COLOR), ("active", PRIMARY_COLOR)],
            bordercolor=[("pressed", HOVER_COLOR), ("active", PRIMARY_COLOR)],
        )
        style.configure(
            "Output.TFrame",
            background=BORDER_COLOR,
        )
        style.configure(
            "Anota.Horizontal.TProgressbar",
            troughcolor=BG_LIGHT,
            background=PRIMARY_COLOR,
            lightcolor=PRIMARY_COLOR,
            darkcolor=PRIMARY_COLOR,
            bordercolor=BORDER_COLOR,
        )

    @staticmethod
    def _build_screen_shell(
        parent: tk.Misc, title_text: str
    ) -> tuple[tk.Frame, tk.Frame]:
        """Cria o cabeçalho vermelho e a área de conteúdo compartilhada."""
        header = tk.Frame(parent, bg=PRIMARY_COLOR, height=HEADER_HEIGHT)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(
            header,
            text=title_text,
            bg=PRIMARY_COLOR,
            fg=TEXT_WHITE,
            anchor="w",
            font=FONT_TITLE,
            padx=20,
        ).pack(fill="both", expand=True)
        body = tk.Frame(parent, bg=BG_WHITE)
        body.pack(fill="both", expand=True)
        return header, body

    def _build_initial_frame(self) -> None:
        """Monta a tela inicial com somente os quatro atalhos de abas."""
        _, body = self._build_screen_shell(self.initial_frame, WINDOW_TITLE)
        content = tk.Frame(
            body,
            bg=BG_WHITE,
            padx=PADDING_CONTENT[0],
            pady=PADDING_CONTENT[1],
        )
        content.pack(fill="both", expand=True)
        tk.Label(
            content,
            text="Selecione uma categoria",
            bg=BG_WHITE,
            fg=TEXT_DARK,
            font=FONT_HEADING,
        ).pack(pady=(0, 24))
        definitions = [
            ("🔧  Ferramentas", lambda: self._show_frame(self.tools_frame)),
            ("🖨️  Impressora", lambda: self._show_frame(self.printer_frame)),
            ("📁  Arquivos Úteis", lambda: self._show_frame(self.files_frame)),
            ("⚡  Outros Comandos", lambda: self._show_frame(self.commands_frame)),
        ]
        for label, action in definitions:
            shadow = tk.Frame(content, bg=SHADOW_COLOR)
            shadow.pack(fill="x", pady=6)
            button = self._make_button(shadow, label, action, style_name="Card.TButton")
            button.pack(fill="x", padx=PADX_BUTTONS, pady=(0, PADY_BUTTONS))

    def _build_tools_frame(self) -> None:
        _, body = self._build_screen_shell(self.tools_frame, "Ferramentas — Anota AI")
        definitions = [
            ("Limpeza de Cache", self._clean_cache),
            ("Sincronização de Hora", self._sync_time),
            ("Compatibilidade", self._check_compatibility),
            ("Teste de Velocidade", self._speed_test),
            ("Monitor de CPU", self._monitor_cpu),
            ("Executar Tudo", self._run_all),
        ]
        self._build_action_screen(body, "tools", definitions, with_progress=True)

    def _build_printer_frame(self) -> None:
        _, body = self._build_screen_shell(self.printer_frame, "Impressora — Anota AI")
        definitions = [
            ("Abrir Impressoras", self._open_printers),
            ("Limpar Fila de Impressão", self._clear_printer_queue),
            ("Verificar PID na Porta 5000", self._check_port_5000),
        ]
        self._build_action_screen(body, "printer", definitions)

    def _build_files_frame(self) -> None:
        _, body = self._build_screen_shell(self.files_frame, "Arquivos Úteis — Anota AI")
        definitions = [
            ("Baixar Instalador de Drivers", self._download_driver),
            ("Baixar Anota AI Desktop", self._download_desktop),
            ("Baixar NetStatGUI", self._download_netstatgui),
        ]
        self._build_action_screen(body, "files", definitions)

    def _build_commands_frame(self) -> None:
        _, body = self._build_screen_shell(self.commands_frame, "Outros Comandos — Anota AI")
        definitions = [
            ("Ipconfig", self._ipconfig),
            ("ARP -a", self._arp),
            ("MSCONFIG", self._open_msconfig),
        ]
        self._build_action_screen(body, "commands", definitions)

    def _build_action_screen(
        self,
        body: tk.Frame,
        screen: str,
        definitions: list[tuple[str, Action]],
        with_progress: bool = False,
    ) -> None:
        """Cria a composição horizontal: botões à esquerda e terminal à direita."""
        sidebar = tk.Frame(body, bg=BG_LIGHT, width=SIDEBAR_WIDTH)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        actions = tk.Frame(
            sidebar,
            bg=BG_LIGHT,
            padx=PADX_SIDEBAR,
            pady=PADY_SIDEBAR,
        )
        actions.pack(fill="both", expand=True)
        buttons: list[RoundedButton] = []
        for label, action in definitions:
            button = self._make_button(actions, label, action)
            button.pack(fill="x", pady=3)
            buttons.append(button)
            self._button_labels[button] = label
        self._buttons[screen] = buttons

        self._build_results(body, screen, with_progress)
        footer = tk.Frame(sidebar, bg=BG_LIGHT, padx=12, pady=10)
        footer.pack(side="bottom", fill="x")
        status = tk.Label(
            footer,
            text="Status: Pronto",
            bg=BG_LIGHT,
            fg=ACCENT_GREEN,
            anchor="w",
            font=FONT_STATUS,
        )
        status.pack(fill="x", pady=(0, 7))
        self._statuses[screen] = status
        if with_progress:
            clear_button = self._make_button(
                footer, "Limpar", lambda: self._clear_screen_output(screen)
            )
            clear_button.pack(side="left", fill="x", expand=True, padx=(0, 3))
            self._buttons[screen].append(clear_button)
            self._button_labels[clear_button] = "Limpar"
        back_button = self._make_button(footer, "Voltar", self._back_to_initial)
        back_button.pack(
            side="left" if with_progress else "top", fill="x", expand=with_progress
        )
        self._buttons[screen].append(back_button)
        self._button_labels[back_button] = "Voltar"

    @staticmethod
    def _make_button(
        parent: tk.Misc,
        label: str,
        action: Action,
        style_name: str = "Rounded.TButton",
    ) -> ttk.Button | RoundedButton:
        """Mantém os cards iniciais em ttk e usa Canvas nas abas internas."""
        if style_name == "Card.TButton":
            return ttk.Button(
                parent,
                text=label,
                command=action,
                width=22,
                style=style_name,
                cursor="hand2",
            )
        return RoundedButton(
            parent,
            text=label,
            command=action,
            width=180,
            height=40,
            radius=12,
            bg=BG_LIGHT,
            cursor="hand2",
        )

    def _build_results(self, body: tk.Frame, screen: str, with_progress: bool) -> None:
        results_frame = tk.Frame(
            body,
            bg=BG_WHITE,
            padx=PADDING_BODY[0],
            pady=PADDING_BODY[1],
        )
        results_frame.pack(side="left", fill="both", expand=True)
        row = 0
        progress_frame = None
        progress_label = None
        progress_bar = None
        if with_progress:
            progress_frame = tk.Frame(results_frame, bg=BG_WHITE)
            progress_frame.grid(row=0, column=0, sticky="ew", pady=(0, 8))
            progress_frame.grid_columnconfigure(0, weight=1)
            progress_label = tk.Label(
                progress_frame,
                text="",
                bg=BG_WHITE,
                fg=TEXT_DARK,
                anchor="w",
                font=FONT_STATUS,
            )
            progress_label.grid(row=0, column=0, sticky="ew", pady=(0, 5))
            progress_bar = ttk.Progressbar(
                progress_frame,
                orient="horizontal",
                mode="determinate",
                style="Anota.Horizontal.TProgressbar",
            )
            progress_bar.grid(row=1, column=0, sticky="ew")
            progress_frame.grid_remove()
            row = 1
        results_frame.grid_rowconfigure(row, weight=1)
        results_frame.grid_columnconfigure(0, weight=1)
        output_frame = ttk.Frame(results_frame, style="Output.TFrame", padding=1)
        output_frame.grid(row=row, column=0, sticky="nsew")
        output = tk.Text(
            output_frame,
            wrap="word",
            bg=BG_WHITE,
            fg=TEXT_DARK,
            insertbackground=TEXT_DARK,
            font=FONT_TERMINAL,
            relief="flat",
            borderwidth=0,
            bd=0,
            highlightthickness=0,
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
        output.pack(fill="both", expand=True)
        scrollbar.grid(row=row, column=1, sticky="ns")
        self._outputs[screen] = output
        if with_progress:
            self._output_frame = output_frame
        if with_progress:
            self._progress_frame = progress_frame
            self._progress_label = progress_label
            self._progress_bar = progress_bar
            self._output_scrollbar = scrollbar

    def _show_frame(self, frame: tk.Frame) -> None:
        if self._busy or self._command_busy:
            return
        for current in self._frames:
            current.pack_forget()
        frame.pack(fill="both", expand=True)

    def _back_to_initial(self) -> None:
        """Retorna ao menu inicial sem abrir uma nova janela."""
        self._show_frame(self.initial_frame)

    def _append_output(self, screen: str, text: str) -> None:
        output = self._outputs[screen]
        output.configure(state="normal")
        current = 0
        tag = "normal"
        for match in ANSI_RE.finditer(text):
            output.insert("end", text[current : match.start()], tag)
            codes = match.group(1).split(";")
            if "92" in codes:
                tag = "positive"
            elif "91" in codes:
                tag = "negative"
            elif not match.group(1) or "0" in codes:
                tag = "normal"
            current = match.end()
        output.insert("end", text[current:], tag)
        output.see("end")
        output.configure(state="disabled")

    def _append_command_output(self, text: str) -> None:
        if self._active_screen:
            self._append_output(self._active_screen, text)

    def _clear_screen_output(self, screen: str) -> None:
        if self._busy or self._command_busy:
            return
        output = self._outputs[screen]
        output.configure(state="normal")
        output.delete("1.0", "end")
        output.configure(state="disabled")

    def _show_progress(self, label_text: str, total: int) -> None:
        output = self._outputs["tools"]
        output.configure(state="normal")
        output.delete("1.0", "end")
        output.configure(state="disabled")
        self._output_frame.grid_remove()
        self._output_scrollbar.grid_remove()
        self._progress_total = total
        self._progress_current = 0
        self._progress_label.configure(text=f"Executando: {label_text}...")
        self._progress_frame.grid()
        if total:
            self._progress_bar.stop()
            self._progress_bar.configure(mode="determinate", maximum=total, value=0)
        else:
            self._progress_bar.configure(mode="indeterminate", value=0)
            self._progress_bar.start(10)

    def _hide_progress(self) -> None:
        self._progress_bar.stop()
        self._progress_frame.grid_remove()
        self._output_frame.grid(row=1, column=0, sticky="nsew")
        self._output_scrollbar.grid(row=1, column=1, sticky="ns")

    def _progress_name(self, section_title: str) -> str:
        names = {
            "LIMPEZA DE CACHE": "Limpando cache",
            "SINCRONIZAÇÃO DE HORA": "Sincronizando hora",
            "VERIFICAÇÃO DE COMPATIBILIDADE": "Verificando compatibilidade",
            "TESTE DE VELOCIDADE": "Testando velocidade",
            "MONITOR DE CPU": "Monitorando CPU",
        }
        return names.get(section_title, section_title)

    def _set_tool_busy(self, label: str) -> None:
        self._busy = True
        self._active_screen = "tools"
        self._statuses["tools"].configure(text="Status: Executando...", fg=PRIMARY_COLOR)
        for button in self._buttons["tools"]:
            button.configure(state="disabled")
            if self._button_labels[button] == label:
                button.configure(text="Executando...")

    def _set_tool_ready(self) -> None:
        self._busy = False
        self._statuses["tools"].configure(text="Status: Pronto", fg=ACCENT_GREEN)
        for button in self._buttons["tools"]:
            button.configure(state="normal", text=self._button_labels[button])

    def _start_operation(self, label: str, sections: list[Section]) -> None:
        if self._busy or self._command_busy:
            return
        self._set_tool_busy(label)
        self._pending_tool_output = ""
        progress_name = label if len(sections) > 1 else self._progress_name(sections[0][0])
        self._show_progress(progress_name, len(sections))
        worker = threading.Thread(
            target=self._run_sections,
            args=(sections,),
            daemon=True,
            name="sysinfo-diagnostics",
        )
        worker.start()
        self.root.after(50, self._process_queue)

    def _run_sections(self, sections: list[Section]) -> None:
        for title, action in sections:
            self._result_queue.put(("progress", title))
            captured = StringIO()
            with redirect_stdout(captured):
                try:
                    action()
                except Exception as exc:  # pragma: no cover - proteção da thread
                    print(f"Não foi possível concluir esta seção: {exc}")
            self._result_queue.put(
                (
                    "output",
                    f"\n{'=' * 64}\n{title}\n{'=' * 64}\n"
                    f"{captured.getvalue()}\n{'-' * 64}\n",
                )
            )
        self._result_queue.put(("done", None))

    def _process_queue(self) -> None:
        try:
            message_type, payload = self._result_queue.get_nowait()
        except queue.Empty:
            message_type, payload = None, None
        if message_type == "progress" and payload:
            progress_name = self._progress_name(payload)
            next_step = min(self._progress_current + 1, self._progress_total)
            self._progress_label.configure(
                text=f"Executando: {progress_name}... ({next_step}/{self._progress_total})"
            )
        elif message_type == "output" and payload:
            self._pending_tool_output += payload
            self._progress_current = min(self._progress_current + 1, self._progress_total)
            self._progress_bar.configure(
                mode="determinate", maximum=self._progress_total, value=self._progress_current
            )
        elif message_type == "done":
            self._append_output("tools", self._pending_tool_output)
            self._hide_progress()
            self._set_tool_ready()
            return
        if self._busy:
            self.root.after(50, self._process_queue)

    # ---- Aba Ferramentas -------------------------------------------------

    def _clean_cache(self) -> None:
        self._start_operation("Limpeza de Cache", [("LIMPEZA DE CACHE", display_temp_cleaner)])

    def _sync_time(self) -> None:
        self._start_operation(
            "Sincronização de Hora", [("SINCRONIZAÇÃO DE HORA", display_datetime_sync)]
        )

    def _check_compatibility(self) -> None:
        self._start_operation(
            "Compatibilidade",
            [("VERIFICAÇÃO DE COMPATIBILIDADE", display_compatibility_check)],
        )

    def _speed_test(self) -> None:
        self._start_operation(
            "Teste de Velocidade", [("TESTE DE VELOCIDADE", display_speed_test)]
        )

    def _monitor_cpu(self) -> None:
        self._start_operation(
            "Monitor de CPU",
            [("MONITOR DE CPU", lambda: monitor_cpu(duration=10, interval=1.0))],
        )

    def _run_all(self) -> None:
        self._start_operation(
            "Executar Tudo",
            [
                ("LIMPEZA DE CACHE", display_temp_cleaner),
                ("SINCRONIZAÇÃO DE HORA", display_datetime_sync),
                ("VERIFICAÇÃO DE COMPATIBILIDADE", display_compatibility_check),
                ("TESTE DE VELOCIDADE", display_speed_test),
                ("MONITOR DE CPU", lambda: monitor_cpu(duration=10, interval=1.0)),
            ],
        )

    # ---- Abas Impressora e Outros Comandos -------------------------------

    def _set_command_busy(self, screen: str, label: str) -> None:
        self._command_busy = True
        self._active_screen = screen
        self._statuses[screen].configure(text="Status: Executando...", fg=PRIMARY_COLOR)
        for button in self._buttons[screen]:
            button.configure(state="disabled")
            if self._button_labels[button] == label:
                button.configure(text="Executando...")
        self._append_output(screen, f"{label}\n")

    def _set_command_ready(self) -> None:
        screen = self._active_screen
        self._command_busy = False
        self._statuses[screen].configure(text="Status: Pronto", fg=ACCENT_GREEN)
        for button in self._buttons[screen]:
            button.configure(state="normal", text=self._button_labels[button])

    def _start_command_thread(self, screen: str, label: str, action: Action) -> None:
        if self._busy or self._command_busy:
            return
        self._set_command_busy(screen, label)
        worker = threading.Thread(
            target=self._run_command_action,
            args=(action,),
            daemon=True,
            name="sysinfo-command",
        )
        worker.start()
        self.root.after(50, self._process_command_queue)

    def _run_command_action(self, action: Action) -> None:
        try:
            action()
        except Exception as exc:  # pragma: no cover - proteção da thread
            self._command_result_queue.put(("output", f"Erro: {exc}\n"))
        finally:
            self._command_result_queue.put(("done", None))

    def _queue_command_output(self, text: str) -> None:
        self._command_result_queue.put(("output", f"{text}\n"))

    def _process_command_queue(self) -> None:
        finished = False
        while True:
            try:
                message_type, payload = self._command_result_queue.get_nowait()
            except queue.Empty:
                break
            if message_type == "output" and payload:
                self._append_command_output(payload)
            elif message_type == "done":
                finished = True
        if finished:
            self._set_command_ready()
        elif self._command_busy:
            self.root.after(50, self._process_command_queue)

    def _open_printers(self) -> None:
        log_audit("open_printers", "Abrindo pasta de impressoras do Windows")
        self._start_command_thread("printer", "Abrir Impressoras", self._open_printers_worker)

    def _open_printers_worker(self) -> None:
        if platform.system() != "Windows":
            self._queue_command_output("Disponível apenas no Windows")
            return
        subprocess.Popen(["explorer", self.PRINTERS_COMMAND], creationflags=_creation_flags())
        self._queue_command_output("Abrindo pasta de Impressoras...")

    def _clear_printer_queue(self) -> None:
        self._start_command_thread(
            "printer", "Limpar Fila de Impressão", lambda: self._queue_command_output(_clear_print_queue())
        )

    def _check_port_5000(self) -> None:
        command = ["cmd", "/c", 'netstat -ano | findstr ":5000"']
        self._start_command_thread(
            "printer",
            "Verificar PID na Porta 5000",
            lambda: self._queue_command_output(_run_command_capture(command)),
        )

    def _ipconfig(self) -> None:
        self._start_command_thread(
            "commands", "Ipconfig", lambda: self._queue_command_output(_run_command_capture(["ipconfig", "/all"]))
        )

    def _arp(self) -> None:
        self._start_command_thread(
            "commands", "ARP -a", lambda: self._queue_command_output(_run_command_capture(["arp", "-a"]))
        )

    def _open_msconfig(self) -> None:
        self._start_command_thread("commands", "MSCONFIG", self._open_msconfig_worker)

    def _open_msconfig_worker(self) -> None:
        if platform.system() != "Windows":
            self._queue_command_output("Disponível apenas no Windows")
            return
        subprocess.Popen(["msconfig"], creationflags=_creation_flags())
        self._queue_command_output("Abrindo MSCONFIG...")

    # ---- Aba Arquivos Úteis ----------------------------------------------

    @staticmethod
    def _downloads_path() -> str:
        if platform.system() == "Windows":
            user_profile = os.environ.get("USERPROFILE")
            if user_profile:
                return os.path.join(user_profile, "Downloads")
        return os.path.join(os.path.expanduser("~"), "Downloads")

    def _download_driver(self) -> None:
        self._start_command_thread(
            "files", "Baixar Instalador de Drivers", lambda: self._download_file(
                self.DRIVER_URL, self.DRIVER_FILENAME, "Baixando Instalador de Drivers..."
            )
        )

    def _download_desktop(self) -> None:
        self._start_command_thread(
            "files", "Baixar Anota AI Desktop", lambda: self._download_file(
                self.DESKTOP_URL, self.DESKTOP_FILENAME, "Baixando Anota AI Desktop..."
            )
        )

    def _download_netstatgui(self) -> None:
        self._start_command_thread(
            "files", "Baixar NetStatGUI", lambda: self._download_file(
                self.NETSTATGUI_URL, self.NETSTATGUI_FILENAME, "Baixando NetStatGUI..."
            )
        )

    def _download_file(self, url: str, filename: str, message: str) -> None:
        """Baixa uma origem HTTPS confiável, calcula hash e abre Downloads."""
        if not validate_url(url):
            self._queue_command_output("Erro: URL inválida ou não confiável")
            log_audit("download_failed", f"URL rejeitada: {url}")
            return
        downloads_path = self._downloads_path()
        destination = os.path.join(downloads_path, filename)
        log_audit("download_start", f"Baixando de {url} para {destination}")
        try:
            os.makedirs(downloads_path, exist_ok=True)
        except OSError as error:
            log_audit("download_failed", f"Erro: {error}")
            self._queue_command_output(f"Erro ao baixar: {error}")
            return
        self._queue_command_output(message)

        def reporthook(block_number: int, block_size: int, total_size: int) -> None:
            downloaded = block_number * block_size
            if total_size > 0:
                percent = min(100, int(downloaded * 100 / total_size))
                total_mb = total_size / (1024 * 1024)
                downloaded_mb = min(downloaded, total_size) / (1024 * 1024)
                self._queue_command_output(
                    f"Baixando... {percent}% ({downloaded_mb:.1f} MB / {total_mb:.1f} MB)"
                )
            else:
                self._queue_command_output("Baixando...")

        try:
            urllib.request.urlretrieve(url, destination, reporthook=reporthook)
            sha256 = calculate_sha256(destination)
        except Exception as error:
            log_audit("download_failed", f"Erro: {error}")
            self._queue_command_output(f"Erro ao baixar: {error}")
            return
        log_audit("download_complete", f"Arquivo: {destination}, SHA-256: {sha256}")
        self._queue_command_output(f"Download concluído: {destination}")
        self._queue_command_output(f"SHA-256: {sha256}")
        if platform.system() == "Windows":
            subprocess.Popen(["explorer", downloads_path], creationflags=_creation_flags())


_ICON_B64 = (
    """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"""
)


def _set_window_icon(root: tk.Tk) -> None:
    """Define o icone da janela e da barra de tarefas no Windows.

    O icone esta embutido no codigo (base64) para nao depender de
    arquivos externos ao lado do .exe.
    """
    if platform.system() != "Windows":
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "AnotaAI.DiagnosticoSistema"
        )
    except (OSError, AttributeError):
        pass
    try:
        import tempfile
        import base64 as _b64
        icon_data = _b64.b64decode("".join(_ICON_B64.split()))
        with tempfile.NamedTemporaryFile(suffix=".ico", delete=False) as tmp:
            tmp.write(icon_data)
            tmp_path = tmp.name
        root.iconbitmap(tmp_path)
        os.unlink(tmp_path)
    except Exception:
        pass


def main() -> None:
    """Inicia a interface gráfica e registra o ciclo de vida do programa."""
    _ensure_admin()
    log_audit("program_start", "Diagnóstico do Sistema iniciado")
    root = tk.Tk()
    _set_window_icon(root)
    root.protocol(
        "WM_DELETE_WINDOW",
        lambda: (log_audit("program_end", "Programa encerrado"), root.destroy()),
    )
    SystemDiagnosticsApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
