"""Visualizador de logs do Anota AI em formato de tabela com filtros."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from modules.anota_logs import find_latest_log
from modules.theme import (
    BG_LIGHT,
    BG_WHITE,
    FONT_BUTTON,
    FONT_STATUS,
    FONT_TERMINAL,
    PRIMARY_COLOR,
    TEXT_DARK,
)

# Cores dos tipos de log.
COLOR_INFO = "#F9A825"  # amarelo
COLOR_ERROR = "#EA1D2F"  # vermelho (mesmo PRIMARY_COLOR)
COLOR_OTHER = "#3F3E3E"  # cinza escuro

ERROR_TERMS = ("error", "exception", "fail", "fatal", "crash")
INFO_TERMS = ("info", "log", "started", "connected", "success", "loaded", "ready")


def _classify_line(line: str) -> str:
    """Classifica uma linha como ``error``, ``info`` ou ``other``."""
    lower = line.casefold()
    if any(term in lower for term in ERROR_TERMS):
        return "error"
    if any(term in lower for term in INFO_TERMS):
        return "info"
    return "other"


class LogViewerWidget:
    """Widget embutido com tabela de logs e filtros por tipo."""

    MAX_LINES = 200

    def __init__(
        self, container: tk.Frame, on_close: Callable[[], None] | None = None
    ) -> None:
        self.container = container
        self._on_close = on_close
        self._filter: str = "all"  # "all", "error", "info"
        self._all_rows: list[tuple[str, str, str]] = []  # tipo, linha, texto
        self._build_ui()
        self._load_logs()

    def _build_ui(self) -> None:
        """Constrói a barra de ações e a tabela de logs."""
        top_bar = tk.Frame(self.container, bg=BG_WHITE)
        top_bar.pack(fill="x", padx=10, pady=(10, 5))

        title = tk.Label(
            top_bar,
            text="Logs do Anota AI",
            bg=BG_WHITE,
            fg=TEXT_DARK,
            font=("Segoe UI", 12, "bold"),
        )
        title.pack(side="left")

        filter_frame = tk.Frame(top_bar, bg=BG_WHITE)
        filter_frame.pack(side="left", padx=(15, 0))

        self._configure_filter_styles()
        self._btn_all = ttk.Button(
            filter_frame,
            text="Todos",
            command=lambda: self._set_filter("all"),
            style="LogAll.TButton",
        )
        self._btn_all.pack(side="left", padx=(0, 5))
        self._btn_info = ttk.Button(
            filter_frame,
            text="Info",
            command=lambda: self._set_filter("info"),
            style="LogInfo.TButton",
        )
        self._btn_info.pack(side="left", padx=(0, 5))
        self._btn_error = ttk.Button(
            filter_frame,
            text="Erro",
            command=lambda: self._set_filter("error"),
            style="LogError.TButton",
        )
        self._btn_error.pack(side="left")

        close_btn = ttk.Button(
            top_bar,
            text="Fechar",
            command=self._close,
            style="Rounded.TButton",
        )
        close_btn.pack(side="right")

        self._file_label = tk.Label(
            self.container,
            text="",
            bg=BG_WHITE,
            fg=TEXT_DARK,
            font=FONT_STATUS,
            anchor="w",
        )
        self._file_label.pack(fill="x", padx=10, pady=(0, 5))

        columns = ("line", "type", "message")
        style = ttk.Style()
        style.configure("Log.Treeview", font=FONT_TERMINAL, rowheight=22)
        style.configure("Log.Treeview.Heading", font=FONT_BUTTON)
        self._tree = ttk.Treeview(
            self.container,
            columns=columns,
            show="headings",
            style="Log.Treeview",
            selectmode="browse",
        )
        self._tree.heading("line", text="Linha")
        self._tree.heading("type", text="Tipo")
        self._tree.heading("message", text="Mensagem")
        self._tree.column("line", width=60, stretch=False, anchor="center")
        self._tree.column("type", width=80, stretch=False, anchor="center")
        self._tree.column("message", width=400, stretch=True, anchor="w")

        self._tree.tag_configure("error", foreground=COLOR_ERROR, background="#FFF5F5")
        self._tree.tag_configure("info", foreground=COLOR_INFO, background="#FFFDF5")
        self._tree.tag_configure("other", foreground=COLOR_OTHER, background=BG_WHITE)

        tree_scroll = tk.Scrollbar(
            self.container,
            orient="vertical",
            command=self._tree.yview,
            troughcolor=BG_LIGHT,
            relief="flat",
            borderwidth=0,
        )
        self._tree.configure(yscrollcommand=tree_scroll.set)

        self._tree.pack(
            side="left", fill="both", expand=True, padx=(10, 0), pady=(0, 10)
        )
        tree_scroll.pack(side="right", fill="y", padx=(0, 10), pady=(0, 10))

        self._empty_label = tk.Label(
            self.container,
            text="",
            bg=BG_WHITE,
            fg=TEXT_DARK,
            font=FONT_STATUS,
        )

    @staticmethod
    def _configure_filter_styles() -> None:
        """Configura cores distintas para os filtros da tabela."""
        style = ttk.Style()
        style.configure(
            "LogAll.TButton",
            background=BG_LIGHT,
            foreground=TEXT_DARK,
            font=FONT_BUTTON,
            borderwidth=0,
            focusthickness=0,
            padding=(10, 7),
            relief="flat",
        )
        style.configure(
            "LogInfo.TButton",
            background="#FFF3CD",
            foreground="#8A5A00",
            font=FONT_BUTTON,
            borderwidth=0,
            focusthickness=0,
            padding=(10, 7),
            relief="flat",
        )
        style.configure(
            "LogError.TButton",
            background=PRIMARY_COLOR,
            foreground="#FFFFFF",
            font=FONT_BUTTON,
            borderwidth=0,
            focusthickness=0,
            padding=(10, 7),
            relief="flat",
        )
        style.map("LogAll.TButton", background=[("active", "#E8E8E8")])
        style.map("LogInfo.TButton", background=[("active", "#FFE69C")])
        style.map("LogError.TButton", background=[("active", "#C41523")])

    def _load_logs(self) -> None:
        """Carrega as últimas ``MAX_LINES`` linhas do log mais recente."""
        log_path = find_latest_log()
        if log_path is None:
            self._file_label.configure(text="Nenhum arquivo de log encontrado.")
            self._show_empty_message("Nenhum arquivo de log encontrado.")
            return

        self._file_label.configure(text=f"Arquivo: {log_path}")
        try:
            lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError as exc:
            message = f"Erro ao ler o arquivo: {exc}"
            self._file_label.configure(text=message)
            self._show_empty_message(message)
            return

        tail = lines[-self.MAX_LINES :]
        start_line = max(1, len(lines) - self.MAX_LINES + 1)
        self._all_rows = []
        for index, line in enumerate(tail):
            line_type = _classify_line(line)
            self._all_rows.append((line_type, str(start_line + index), line.strip()))

        self._apply_filter()

    def _set_filter(self, filter_type: str) -> None:
        """Seleciona ``Todos``, ``Info`` ou ``Erro`` e atualiza a tabela."""
        self._filter = filter_type
        self._apply_filter()

    def _apply_filter(self) -> None:
        """Reaplica o filtro atual à tabela."""
        self._tree.delete(*self._tree.get_children())
        visible_rows = 0
        labels = {"error": "Erro", "info": "Info", "other": "Outro"}
        for row_type, line_num, text in self._all_rows:
            if self._filter == "all" or row_type == self._filter:
                self._tree.insert(
                    "",
                    "end",
                    values=(line_num, labels.get(row_type, "Outro"), text),
                    tags=(row_type,),
                )
                visible_rows += 1

        if visible_rows:
            self._empty_label.pack_forget()
        else:
            message = {
                "error": "Nenhuma linha de erro encontrada.",
                "info": "Nenhuma linha informativa encontrada.",
            }.get(self._filter, "Nenhuma linha de log encontrada.")
            self._show_empty_message(message)

    def _show_empty_message(self, message: str) -> None:
        """Exibe uma mensagem quando o arquivo ou filtro não tem linhas."""
        self._empty_label.configure(text=message)
        self._empty_label.pack(fill="x", padx=10, pady=(0, 10))

    def _close(self) -> None:
        """Fecha o visualizador por meio do callback do painel principal."""
        if self._on_close is not None:
            self._on_close()
        else:
            self.container.destroy()


def create_log_viewer(
    container: tk.Frame, on_close: Callable[[], None] | None = None
) -> LogViewerWidget:
    """Cria o visualizador de logs dentro do container fornecido."""
    return LogViewerWidget(container, on_close)
