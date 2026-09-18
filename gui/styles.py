"""Tema ttk compartilhado pela interface."""

from __future__ import annotations

try:
    from tkinter import ttk
except ImportError:
    ttk = None

from modules.theme import (
    BG_CARD, BG_LIGHT, BORDER_COLOR, FONT_BUTTON, FONT_CARD, HOVER_COLOR,
    PRIMARY_COLOR, TEXT_DARK, TEXT_WHITE,
)

def setup_styles(style: ttk.Style) -> None:
    """Configura todos os estilos ttk da aplicação."""
    style.theme_use("clam")
    style.theme_use("clam")
    style.configure(
        "Rounded.TButton",
        background=PRIMARY_COLOR,
        foreground=TEXT_WHITE,
        font=FONT_BUTTON,
        borderwidth=0,
        focusthickness=0,
        padding=(12, 10),
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
