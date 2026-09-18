"""Infraestrutura compartilhada da interface gráfica do SuporteTools."""

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
import urllib.request
from collections.abc import Callable
from contextlib import redirect_stdout
from io import StringIO

try:
    import tkinter as tk
    from tkinter import ttk
except ImportError:
    tk = None
    ttk = None

from modules.config import (
    DESKTOP_FILENAME, DESKTOP_URL, DRIVER_FILENAME, DRIVER_URL,
    NETSTATGUI_FILENAME, NETSTATGUI_URL,
)
from modules.security import calculate_sha256, log_audit, validate_url
from modules.theme import *

Action = Callable[[], None]
Section = tuple[str, Action]
ANSI_RE = re.compile(r"\x1b\[([0-9;]*)m")

if sys.stdout is None:
    sys.stdout = io.StringIO()
if sys.stderr is None:
    sys.stderr = io.StringIO()

def _creation_flags() -> int:
    """Retorna flags que impedem uma janela de console no Windows."""
    creationflags = 0
    if platform.system() == "Windows":
        creationflags = subprocess.CREATE_NO_WINDOW
    return creationflags

def _startup_info() -> "subprocess.STARTUPINFO | None":
    """Configura STARTUPINFO para ocultar a janela do console no Windows."""
    if platform.system() != "Windows":
        return None
    startupinfo_type = getattr(subprocess, "STARTUPINFO", None)
    if startupinfo_type is None:
        return None
    try:
        startupinfo = startupinfo_type()
        startupinfo.dwFlags |= getattr(subprocess, "STARTF_USESHOWWINDOW", 0)
        startupinfo.wShowWindow = getattr(subprocess, "SW_HIDE", 0)
    except (AttributeError, OSError, TypeError):
        return None
    return startupinfo

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
            startupinfo=_startup_info(),
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
        try:
            if command[0].casefold() == "del":
                # ``del`` é interno ao CMD; usa cmd /c para evitar shell=True.
                cmd = ["cmd", "/c"] + command
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=15,
                    check=False,
                    creationflags=_creation_flags(),
                    startupinfo=_startup_info(),
                )
            else:
                result = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    timeout=15,
                    check=False,
                    creationflags=_creation_flags(),
                    startupinfo=_startup_info(),
                )
            output_lines.append(f"> {' '.join(command)}")
            output_lines.append((result.stdout or result.stderr or "OK").strip())
        except Exception as exc:
            output_lines.append(f"> {' '.join(command)}")
            output_lines.append(f"Erro ao executar: {exc}")
    return "\n".join(output_lines)

class SystemInfoBase:
    """Classe base com estado, widgets e operações compartilhados."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.container = tk.Frame(self.root, bg=BG_WHITE)
        self.container.pack(fill="both", expand=True)
        self.initial_frame = tk.Frame(self.container, bg=BG_WHITE)
        self.computer_frame = tk.Frame(self.container, bg=BG_WHITE)
        self.program_frame = tk.Frame(self.container, bg=BG_WHITE)
        self.printer_frame = tk.Frame(self.container, bg=BG_WHITE)
        self.network_frame = tk.Frame(self.container, bg=BG_WHITE)
        self._frames = (self.initial_frame, self.computer_frame, self.program_frame, self.printer_frame, self.network_frame)
        self._buttons: dict[str, list[ttk.Button]] = {}
        self._button_labels: dict[ttk.Button, str] = {}
        self._outputs: dict[str, tk.Text] = {}
        self._output_frames: dict[str, ttk.Frame] = {}
        self._output_scrollbars: dict[str, tk.Scrollbar] = {}
        self._progress_bars: dict[str, ttk.Progressbar] = {}
        self._progress_labels: dict[str, tk.Label] = {}
        self._progress_frames: dict[str, tk.Frame] = {}
        self._statuses: dict[str, tk.Label] = {}
        self._result_queue: queue.Queue[tuple[str, str | None]] = queue.Queue()
        self._command_result_queue: queue.Queue[tuple[str, object | None]] = queue.Queue()
        self._scan_result_queue: queue.Queue[tuple[bool, str, str]] = queue.Queue()
        self._scan_button: ttk.Button | None = None
        self._scan_status: tk.Label | None = None
        self._scan_busy = False
        self._busy = False
        self._command_busy = False
        self._card_queue: queue.Queue = queue.Queue()
        self._card_busy = False
        self._active_screen = ""
        self._pending_tool_output = ""
        self._progress_total = 0
        self._progress_current = 0
        self._resource_monitor = None

    def _build_screen_shell(
            self, parent: tk.Misc, title_text: str
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

    def _build_action_screen(
            self,
            body: tk.Frame,
            screen: str,
            definitions: list[tuple[str, Action]],
            with_progress: bool = False,
        ) -> tk.Frame:
            """Cria a composição horizontal: botões à esquerda e terminal à direita."""
            sidebar = tk.Frame(body, bg=BG_LIGHT, width=SIDEBAR_WIDTH)
            sidebar.pack(side="left", fill="y")
            sidebar.pack_propagate(False)
            # O menu lateral pode conter mais ações do que a altura disponível.
            # O canvas mantém os botões acessíveis sem aumentar a janela inteira.
            actions_view = tk.Frame(sidebar, bg=BG_LIGHT)
            actions_view.pack(fill="both", expand=True)
            actions_canvas = tk.Canvas(
                actions_view,
                bg=BG_LIGHT,
                highlightthickness=0,
                borderwidth=0,
            )
            actions_scrollbar = tk.Scrollbar(
                actions_view,
                orient="vertical",
                command=actions_canvas.yview,
                troughcolor=BG_LIGHT,
                activebackground=PRIMARY_COLOR,
                relief="flat",
                borderwidth=0,
            )
            actions_canvas.configure(yscrollcommand=actions_scrollbar.set)
            actions_canvas.pack(side="left", fill="both", expand=True)
            actions_scrollbar.pack(side="right", fill="y")
            actions = tk.Frame(
                actions_canvas,
                bg=BG_LIGHT,
                padx=PADX_SIDEBAR,
                pady=PADY_SIDEBAR,
            )
            actions_window = actions_canvas.create_window(
                (0, 0), window=actions, anchor="nw"
            )

            def _on_canvas_configure(event: tk.Event) -> None:
                """Mantém o frame interno com a largura visível do canvas."""
                actions_canvas.itemconfigure(actions_window, width=event.width)
                actions_canvas.configure(scrollregion=actions_canvas.bbox("all"))

            def _on_frame_configure(_event: tk.Event) -> None:
                """Recalcula a área rolável sempre que um botão é adicionado."""
                actions_canvas.configure(scrollregion=actions_canvas.bbox("all"))

            def _on_mousewheel(event: tk.Event) -> None:
                """Rola o sidebar enquanto o cursor estiver sobre a área de ações."""
                delta = getattr(event, "delta", 0)
                if delta:
                    actions_canvas.yview_scroll(int(-1 * (delta / 120)), "units")

            def _enable_mousewheel(_event: tk.Event) -> None:
                actions_canvas.bind_all("<MouseWheel>", _on_mousewheel)

            def _disable_mousewheel(_event: tk.Event) -> None:
                actions_canvas.unbind_all("<MouseWheel>")

            # A largura do frame acompanha o canvas e sua altura alimenta o
            # scrollregion. Isso também cobre mudanças de tamanho da janela.
            actions_canvas.bind("<Configure>", _on_canvas_configure)
            actions.bind("<Configure>", _on_frame_configure)
            # O canvas recebe os eventos quando o cursor está sobre a área rolável;
            # os binds no sidebar cobrem também suas áreas auxiliares.
            actions_canvas.bind("<Enter>", _enable_mousewheel)
            actions_canvas.bind("<Leave>", _disable_mousewheel)
            sidebar.bind("<Enter>", _enable_mousewheel)
            sidebar.bind("<Leave>", _disable_mousewheel)
            buttons: list[ttk.Button] = []
            for label, action in definitions:
                button = self._make_button(actions, label, action)
                button.pack(fill="x", pady=3)
                buttons.append(button)
                self._button_labels[button] = label
            # Garante a região inicial mesmo antes do primeiro <Configure> do
            # frame interno (importante quando a tela é construída já visível).
            actions_canvas.configure(scrollregion=actions_canvas.bbox("all"))
            self._buttons[screen] = buttons

            results_frame = self._build_results(body, screen, with_progress)
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
            return results_frame

    def _make_button(
            self, parent: tk.Misc,
            label: str,
            action: Action,
            style_name: str = "Rounded.TButton",
        ) -> ttk.Button:
            """Cria botões ttk, preservando o estilo especial dos cards iniciais."""
            if style_name == "Card.TButton":
                return ttk.Button(
                    parent,
                    text=label,
                    command=action,
                    width=22,
                    style=style_name,
                    cursor="hand2",
                )
            return ttk.Button(
                parent,
                text=label,
                command=action,
                style="Rounded.TButton",
                cursor="hand2",
            )

    def _build_results(self, body: tk.Frame, screen: str, with_progress: bool) -> tk.Frame:
            results_frame = tk.Frame(
                body,
                bg=BG_WHITE,
                padx=PADDING_BODY[0],
                pady=PADDING_BODY[1],
            )
            results_frame.pack(side="left", fill="both", expand=True)
            # Mantém o scanner (que usa pack) separado dos widgets de resultados,
            # que usam grid. Assim o card pode ser inserido no topo depois que a
            # tela for montada sem conflito entre gerenciadores de geometria.
            results_content = tk.Frame(results_frame, bg=BG_WHITE)
            results_content.pack(fill="both", expand=True)
            row = 0
            progress_frame = None
            progress_label = None
            progress_bar = None
            if with_progress:
                progress_frame = tk.Frame(results_content, bg=BG_WHITE)
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
            results_content.grid_rowconfigure(row, weight=1)
            results_content.grid_columnconfigure(0, weight=1)
            output_frame = ttk.Frame(results_content, style="Output.TFrame", padding=1)
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
                results_content,
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
            self._output_frames[screen] = output_frame
            self._output_scrollbars[screen] = scrollbar
            if with_progress:
                # Cada tela mantém seus próprios widgets para que um download não
                # reutilize a barra da tela Computador por engano.
                self._progress_frames[screen] = progress_frame
                self._progress_labels[screen] = progress_label
                self._progress_bars[screen] = progress_bar
            return results_frame

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
            screen = self._active_screen
            output = self._outputs[screen]
            output.configure(state="normal")
            output.delete("1.0", "end")
            output.configure(state="disabled")
            output_frame = self._output_frames.get(screen)
            output_scrollbar = self._output_scrollbars.get(screen)
            progress_frame = self._progress_frames.get(screen)
            progress_label = self._progress_labels.get(screen)
            progress_bar = self._progress_bars.get(screen)
            if not all((output_frame, progress_frame, progress_label, progress_bar)):
                return
            output_frame.grid_remove()
            if output_scrollbar:
                output_scrollbar.grid_remove()
            self._progress_total = total
            self._progress_current = 0
            progress_label.configure(text=f"Executando: {label_text}...")
            progress_frame.grid()
            if total:
                progress_bar.stop()
                progress_bar.configure(mode="determinate", maximum=total, value=0)
            else:
                progress_bar.configure(mode="indeterminate", value=0)
                progress_bar.start(10)

    def _hide_progress(self) -> None:
            screen = self._active_screen
            progress_bar = self._progress_bars.get(screen)
            progress_frame = self._progress_frames.get(screen)
            output_frame = self._output_frames.get(screen)
            output_scrollbar = self._output_scrollbars.get(screen)
            if progress_bar:
                progress_bar.stop()
            if progress_frame:
                progress_frame.grid_remove()
            if output_frame:
                output_frame.grid(row=1, column=0, sticky="nsew")
            if output_scrollbar:
                output_scrollbar.grid(row=1, column=1, sticky="ns")

    def _progress_name(self, section_title: str) -> str:
            names = {
                "LIMPEZA DE CACHE": "Limpando cache",
                "SINCRONIZAÇÃO DE HORA": "Sincronizando hora",
                "VERIFICAÇÃO DE COMPATIBILIDADE": "Verificando compatibilidade",
                "TESTE DE VELOCIDADE": "Testando velocidade",
                "PROCESSOS ATIVOS DO ANOTA AI": "Verificando processos do Anota AI",
                "VERSÃO INSTALADA DO ANOTA AI": "Verificando versão instalada",
                "STATUS DO ANTIVÍRUS": "Verificando antivírus",
            }
            return names.get(section_title, section_title)

    def _set_tool_busy(self, screen: str, label: str) -> None:
            self._busy = True
            self._active_screen = screen
            self._statuses[screen].configure(text="Status: Executando...", fg=PRIMARY_COLOR)
            for button in self._buttons[screen]:
                button.configure(state="disabled")
                if self._button_labels[button] == label:
                    button.configure(text="Executando...")

    def _set_tool_ready(self) -> None:
            screen = self._active_screen
            self._busy = False
            self._statuses[screen].configure(text="Status: Pronto", fg=ACCENT_GREEN)
            for button in self._buttons[screen]:
                button.configure(state="normal", text=self._button_labels[button])

    def _start_operation(
            self, label: str, sections: list[Section], screen: str = "computer"
        ) -> None:
            if self._busy or self._command_busy or self._scan_busy:
                return
            self._set_tool_busy(screen, label)
            self._pending_tool_output = ""
            if screen == "computer":
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
                        f"\n{'=' * 59}\n{title}\n{'=' * 59}\n"
                        f"{captured.getvalue()}\n{'-' * 59}\n",
                    )
                )
            self._result_queue.put(("done", None))

    def _process_queue(self) -> None:
            try:
                message_type, payload = self._result_queue.get_nowait()
            except queue.Empty:
                message_type, payload = None, None
            if message_type == "progress" and payload:
                if self._active_screen == "computer":
                    progress_name = self._progress_name(payload)
                    next_step = min(self._progress_current + 1, self._progress_total)
                    progress_label = self._progress_labels.get(self._active_screen)
                    if progress_label:
                        progress_label.configure(
                            text=f"Executando: {progress_name}... ({next_step}/{self._progress_total})"
                        )
            elif message_type == "output" and payload:
                self._pending_tool_output += payload
                if self._active_screen == "computer":
                    self._progress_current = min(self._progress_current + 1, self._progress_total)
                    progress_bar = self._progress_bars.get(self._active_screen)
                    if progress_bar:
                        progress_bar.configure(
                            mode="determinate",
                            maximum=self._progress_total,
                            value=self._progress_current,
                        )
            elif message_type == "done":
                self._append_output(self._active_screen, self._pending_tool_output)
                if self._active_screen == "computer":
                    self._hide_progress()
                self._set_tool_ready()
                return
            if self._busy:
                self.root.after(50, self._process_queue)

    def _show_cards_async(
            self,
            screen: str,
            label: str,
            data_func: Callable,
            action_label: str | None = None,
            action_callback=None,
        ) -> None:
            """Executa a coleta numa thread e mostra os cards via _card_queue."""
            if self._busy or self._command_busy:
                return
            self._set_tool_busy(screen, label)
            # Limpa a fila de cards
            try:
                while True:
                    self._card_queue.get_nowait()
            except queue.Empty:
                pass
            self._card_busy = True

            def _worker():
                try:
                    cards = data_func()
                    self._card_queue.put(("cards", cards))
                except Exception as exc:
                    self._card_queue.put(("error", str(exc)))

            worker = threading.Thread(target=_worker, daemon=True, name="card-data")
            worker.start()
            self.root.after(50, lambda: self._process_card_result(screen, action_label, action_callback))

    def _process_card_result(self, screen: str, action_label: str | None, action_callback) -> None:
            """Processa o resultado da coleta de cards na thread principal."""
            try:
                msg_type, payload = self._card_queue.get_nowait()
            except queue.Empty:
                if self._card_busy:
                    self.root.after(50, lambda: self._process_card_result(screen, action_label, action_callback))
                return

            self._card_busy = False

            if msg_type == "cards":
                output_frame = self._output_frames.get(screen)
                scrollbar = self._output_scrollbars.get(screen)
                progress_frame = self._progress_frames.get(screen)
                if output_frame is None:
                    self._set_tool_ready()
                    return
                output_frame.grid_remove()
                if scrollbar:
                    scrollbar.grid_remove()
                if progress_frame:
                    progress_frame.grid_remove()
                results_content = output_frame.master
                cards_frame = tk.Frame(results_content, bg=BG_WHITE)
                cards_frame.grid(row=1, column=0, sticky="nsew", padx=0, pady=0)
                results_content.grid_rowconfigure(1, weight=1)
                results_content.grid_columnconfigure(0, weight=1)

                def _on_cards_close() -> None:
                    cards_frame.destroy()
                    output_frame.grid(row=1, column=0, sticky="nsew")
                    if scrollbar:
                        scrollbar.grid(row=1, column=1, sticky="ns")
                    self._set_tool_ready()

                from modules.result_cards import create_result_cards

                create_result_cards(
                    cards_frame,
                    payload,
                    on_close=_on_cards_close,
                    action_label=action_label,
                    action_callback=action_callback,
                )
            elif msg_type == "error":
                self._append_output(screen, f"Erro ao coletar dados: {payload}\n")
                self._set_tool_ready()

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
            if self._busy or self._command_busy or self._scan_busy:
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
                elif message_type == "progress_start":
                    screen = self._active_screen
                    output_frame = self._output_frames.get(screen)
                    scrollbar = self._output_scrollbars.get(screen)
                    frame = self._progress_frames.get(screen)
                    bar = self._progress_bars.get(screen)
                    label = self._progress_labels.get(screen)
                    if frame and bar and label:
                        if output_frame:
                            output_frame.grid_remove()
                        if scrollbar:
                            scrollbar.grid_remove()
                        frame.grid()
                        bar.stop()
                        bar.configure(mode="determinate", maximum=100, value=0)
                        label.configure(text="Baixando... 0%")
                elif message_type == "progress" and isinstance(payload, dict):
                    screen = self._active_screen
                    bar = self._progress_bars.get(screen)
                    label = self._progress_labels.get(screen)
                    frame = self._progress_frames.get(screen)
                    output_frame = self._output_frames.get(screen)
                    scrollbar = self._output_scrollbars.get(screen)
                    if bar and label and frame:
                        if output_frame:
                            output_frame.grid_remove()
                        if scrollbar:
                            scrollbar.grid_remove()
                        frame.grid()
                        percent = int(payload.get("percent", 0))
                        downloaded_mb = float(payload.get("downloaded_mb", 0))
                        total_mb = float(payload.get("total_mb", 0))
                        bar.configure(mode="determinate", maximum=100, value=percent)
                        label.configure(
                            text=(
                                f"Baixando... {percent}% "
                                f"({downloaded_mb:.1f} MB / {total_mb:.1f} MB)"
                            )
                        )
                elif message_type == "progress_done":
                    self._hide_progress()
                elif message_type == "done":
                    finished = True
            if finished:
                self._set_command_ready()
            elif self._command_busy:
                self.root.after(50, self._process_command_queue)

    def _queue_command_output_capture(self, action: Action) -> None:
            """Captura funções de diagnóstico que imprimem na saída padrão."""
            captured = StringIO()
            with redirect_stdout(captured):
                action()
            self._queue_command_output(captured.getvalue())

    def _downloads_path(self) -> str:
            if platform.system() == "Windows":
                user_profile = os.environ.get("USERPROFILE")
                if user_profile:
                    return os.path.join(user_profile, "Downloads")
            return os.path.join(os.path.expanduser("~"), "Downloads")

    def _download_driver(self) -> None:
            self._start_command_thread(
                "printer", "Baixar Instalador de Drivers", lambda: self._download_file(
                    DRIVER_URL, DRIVER_FILENAME, "Baixando Instalador de Drivers..."
                )
            )

    def _download_desktop(self) -> None:
            self._start_command_thread(
                "program", "Baixar Anota AI Desktop", lambda: self._download_file(
                    DESKTOP_URL, DESKTOP_FILENAME, "Baixando Anota AI Desktop..."
                )
            )

    def _download_netstatgui(self) -> None:
            self._start_command_thread(
                "printer", "Baixar NetStatGUI", lambda: self._download_file(
                    NETSTATGUI_URL, NETSTATGUI_FILENAME, "Baixando NetStatGUI..."
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
            self._command_result_queue.put(("progress_start", None))

            def reporthook(block_number: int, block_size: int, total_size: int) -> None:
                downloaded = block_number * block_size
                if total_size > 0:
                    percent = min(100, int(downloaded * 100 / total_size))
                    total_mb = total_size / (1024 * 1024)
                    downloaded_mb = min(downloaded, total_size) / (1024 * 1024)
                else:
                    percent = 0
                    total_mb = 0
                    downloaded_mb = 0
                self._command_result_queue.put(
                    ("progress", {
                        "percent": percent,
                        "downloaded_mb": downloaded_mb,
                        "total_mb": total_mb,
                        "label": message,
                    })
                )

            try:
                urllib.request.urlretrieve(url, destination, reporthook=reporthook)
                sha256 = calculate_sha256(destination)
            except Exception as error:
                log_audit("download_failed", f"Erro: {error}")
                self._command_result_queue.put(("progress_done", None))
                self._queue_command_output(f"Erro ao baixar: {error}")
                return
            self._command_result_queue.put(("progress_done", None))
            log_audit("download_complete", f"Arquivo: {destination}, SHA-256: {sha256}")
            self._queue_command_output(f"Download concluído: {destination}")
            self._queue_command_output(f"SHA-256: {sha256}")
            if platform.system() == "Windows":
                subprocess.Popen(["explorer", downloads_path], creationflags=_creation_flags(), startupinfo=_startup_info())

    def _scan_anota_installation(self) -> None:
            """Executa o scanner em segundo plano e atualiza o cartão de status."""
            if self._busy or self._command_busy or self._scan_busy or self._scan_button is None:
                return
            self._scan_busy = True
            self._scan_button.configure(state="disabled", text="Scanear...")
            if self._scan_status is not None:
                self._scan_status.configure(text="Procurando a instalação do Anota AI...", fg=TEXT_DARK)
            threading.Thread(
                target=self._run_anota_scan,
                daemon=True,
                name="anota-installation-scan",
            ).start()
            self.root.after(50, self._process_scan_queue)

    def _run_anota_scan(self) -> None:
            try:
                from modules.anota_process import scan_anota_installation

                result = scan_anota_installation()
            except Exception:  # pragma: no cover - proteção da thread
                result = (False, "", "")
            self._scan_result_queue.put(result)

    def _process_scan_queue(self) -> None:
            try:
                found, path, version = self._scan_result_queue.get_nowait()
            except queue.Empty:
                self.root.after(50, self._process_scan_queue)
                return
            if self._scan_status is not None:
                if found:
                    self._scan_status.configure(
                        text=f"Anota AI instalado — versão {version}",
                        fg=ACCENT_GREEN,
                    )
                else:
                    self._scan_status.configure(
                        text="Anota AI não encontrado",
                        fg=PRIMARY_COLOR,
                    )
            self._scan_busy = False
            if self._scan_button is not None:
                self._scan_button.configure(state="normal", text="⌕ Scanear")
