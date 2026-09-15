"""Cards visuais de resultados de diagnóstico."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from modules.theme import (
    ACCENT_GREEN,
    BG_LIGHT,
    BG_WHITE,
    BORDER_COLOR,
    FONT_BUTTON,
    FONT_CARD,
    FONT_STATUS,
    PRIMARY_COLOR,
    TEXT_DARK,
    TEXT_WHITE,
)

# Cores de fundo e texto para cada estado do diagnóstico.
COLOR_PASS_BG = "#E8F5E9"      # verde claro
COLOR_PASS_FG = ACCENT_GREEN   # verde
COLOR_FAIL_BG = "#FFEBEE"      # vermelho claro
COLOR_FAIL_FG = PRIMARY_COLOR  # vermelho
COLOR_WARN_BG = "#FFF8E1"     # amarelo claro
COLOR_WARN_FG = "#F9A825"      # amarelo

STATUS_ICONS = {"pass": "✅", "fail": "❌", "warn": "⚠️"}
STATUS_COLORS = {
    "pass": (COLOR_PASS_BG, COLOR_PASS_FG),
    "fail": (COLOR_FAIL_BG, COLOR_FAIL_FG),
    "warn": (COLOR_WARN_BG, COLOR_WARN_FG),
}


class Card:
    """Definição de um card de resultado."""

    def __init__(self, title: str, detail: str, status: str = "pass") -> None:
        self.title = title
        self.detail = detail
        self.status = status


class ResultCardsWidget:
    """Widget embutido com cards visuais de resultados."""

    def __init__(
        self,
        container: tk.Frame,
        cards: list[Card],
        on_close: Callable[[], None] | None = None,
        action_label: str | None = None,
        action_callback: Callable[[], None] | None = None,
    ) -> None:
        self.container = container
        self._on_close = on_close
        self._cards = cards
        self._action_label = action_label
        self._action_callback = action_callback
        self._build_ui()

    def _build_ui(self) -> None:
        """Constrói a área rolável, os cards e os controles do widget."""
        canvas = tk.Canvas(
            self.container,
            bg=BG_WHITE,
            highlightthickness=0,
            bd=0,
        )
        scrollbar = tk.Scrollbar(
            self.container,
            orient="vertical",
            command=canvas.yview,
            troughcolor=BG_LIGHT,
            relief="flat",
            borderwidth=0,
        )
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        canvas.configure(yscrollcommand=scrollbar.set)

        inner = tk.Frame(canvas, bg=BG_WHITE)
        inner_window = canvas.create_window((0, 0), window=inner, anchor="nw")

        def _configure_scroll_region(event: tk.Event) -> None:
            del event
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _configure_inner_width(event: tk.Event) -> None:
            canvas.itemconfig(inner_window, width=event.width)

        inner.bind("<Configure>", _configure_scroll_region)
        canvas.bind("<Configure>", _configure_inner_width)

        header = tk.Frame(inner, bg=BG_WHITE, padx=15, pady=(15, 5))
        header.pack(fill="x")
        tk.Label(
            header,
            text="Resultados do Diagnóstico",
            bg=BG_WHITE,
            fg=TEXT_DARK,
            font=("Segoe UI", 14, "bold"),
            anchor="w",
        ).pack(side="left")

        for card in self._cards:
            self._build_card(inner, card)

        if self._action_label and self._action_callback:
            action_frame = tk.Frame(inner, bg=BG_WHITE, padx=15, pady=(10, 5))
            action_frame.pack(fill="x")
            action_btn = ttk.Button(
                action_frame,
                text=self._action_label,
                command=self._action_callback,
                style="Rounded.TButton",
            )
            action_btn.pack(side="left")

        close_frame = tk.Frame(inner, bg=BG_WHITE, padx=15, pady=(10, 15))
        close_frame.pack(fill="x")
        close_btn = ttk.Button(
            close_frame,
            text="Fechar",
            command=self._close,
            style="Rounded.TButton",
        )
        close_btn.pack(side="left")

    def _build_card(self, parent: tk.Frame, card: Card) -> None:
        """Cria um card individual com a cor correspondente ao status."""
        bg, fg = STATUS_COLORS.get(card.status, (BG_LIGHT, TEXT_DARK))
        icon = STATUS_ICONS.get(card.status, "•")

        card_frame = tk.Frame(
            parent,
            bg=bg,
            highlightbackground=BORDER_COLOR,
            highlightthickness=1,
        )
        card_frame.pack(fill="x", padx=15, pady=5)

        content = tk.Frame(card_frame, bg=bg, padx=12, pady=10)
        content.pack(fill="x")

        header = tk.Frame(content, bg=bg)
        header.pack(fill="x")

        tk.Label(
            header,
            text=icon,
            bg=bg,
            fg=fg,
            font=("Segoe UI", 14),
        ).pack(side="left", padx=(0, 8))

        tk.Label(
            header,
            text=card.title,
            bg=bg,
            fg=TEXT_DARK,
            font=FONT_CARD,
            anchor="w",
        ).pack(side="left")

        tk.Label(
            content,
            text=card.detail,
            bg=bg,
            fg=fg,
            font=FONT_STATUS,
            anchor="w",
            wraplength=800,
            justify="left",
        ).pack(fill="x", pady=(4, 0))

    def _close(self) -> None:
        """Chama o callback de encerramento ou destrói o container."""
        if self._on_close is not None:
            self._on_close()
        else:
            self.container.destroy()


def create_result_cards(
    container: tk.Frame,
    cards: list[Card],
    on_close: Callable[[], None] | None = None,
    action_label: str | None = None,
    action_callback: Callable[[], None] | None = None,
) -> ResultCardsWidget:
    """Cria o widget de cards dentro do container fornecido."""
    return ResultCardsWidget(
        container,
        cards,
        on_close,
        action_label,
        action_callback,
    )
