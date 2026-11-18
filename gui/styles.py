"""Tema ttk compartilhado pela interface do SuporteTools."""

from __future__ import annotations

try:
    from tkinter import ttk
except ImportError:
    ttk = None

from modules.theme import (
    BG_CARD, BG_LIGHT, BG_SIDEBAR, BORDER_COLOR, FONT_BODY, FONT_BUTTON,
    FONT_BUTTON_BOLD, FONT_CARD, FONT_FALLBACK, FONT_FAMILY, HOVER_COLOR,
    PRIMARY_COLOR, PRIMARY_DARK, PRIMARY_LIGHT, TEXT_DARK, TEXT_MUTED,
    TEXT_WHITE,
)


def resolve_font_family(root) -> str:
    """Retorna Roboto se instalada; caso contrário, Segoe UI."""
    try:
        from tkinter import font as tkfont

        available = set(tkfont.families(root))
        if FONT_FAMILY in available:
            return FONT_FAMILY
        if FONT_FALLBACK in available:
            return FONT_FALLBACK
    except Exception:
        pass
    return FONT_FALLBACK


def setup_styles(style: ttk.Style) -> None:
    """Configura todos os estilos ttk da aplicação."""
    style.theme_use("clam")

    # --- Botões principais (ações do menu lateral) -------------------------
    style.configure(
        "Rounded.TButton",
        background=BG_CARD,
        foreground=TEXT_DARK,
        font=FONT_BUTTON,
        borderwidth=1,
        bordercolor=BORDER_COLOR,
        focusthickness=0,
        padding=(14, 11),
        relief="flat",
        anchor="w",
    )
    style.map(
        "Rounded.TButton",
        background=[
            ("disabled", BG_LIGHT),
            ("pressed", PRIMARY_LIGHT),
            ("active", PRIMARY_LIGHT),
        ],
        foreground=[
            ("disabled", TEXT_MUTED),
            ("pressed", PRIMARY_DARK),
            ("active", PRIMARY_DARK),
            ("!disabled", TEXT_DARK),
        ],
        bordercolor=[
            ("pressed", PRIMARY_COLOR),
            ("active", PRIMARY_COLOR),
        ],
    )

    # --- Botões de destaque (ações primárias) ------------------------------
    style.configure(
        "Primary.TButton",
        background=PRIMARY_COLOR,
        foreground=TEXT_WHITE,
        font=FONT_BUTTON_BOLD,
        borderwidth=0,
        focusthickness=0,
        padding=(16, 11),
        relief="flat",
    )
    style.map(
        "Primary.TButton",
        background=[
            ("disabled", BG_LIGHT),
            ("pressed", PRIMARY_DARK),
            ("active", PRIMARY_DARK),
        ],
        foreground=[("disabled", TEXT_MUTED), ("!disabled", TEXT_WHITE)],
    )

    # --- Cards da tela inicial --------------------------------------------
    style.configure(
        "Card.TButton",
        background=BG_CARD,
        foreground=TEXT_DARK,
        font=FONT_CARD,
        borderwidth=1,
        bordercolor=BORDER_COLOR,
        focusthickness=0,
        padding=(22, 18),
        relief="solid",
    )
    style.map(
        "Card.TButton",
        background=[("pressed", PRIMARY_LIGHT), ("active", PRIMARY_LIGHT)],
        foreground=[("pressed", PRIMARY_DARK), ("active", PRIMARY_DARK)],
        bordercolor=[("pressed", PRIMARY_COLOR), ("active", PRIMARY_COLOR)],
    )

    # --- Área de saída -----------------------------------------------------
    style.configure("Output.TFrame", background=BORDER_COLOR)
    style.configure("Sidebar.TFrame", background=BG_SIDEBAR)
    style.configure("Body.TFrame", background=BG_LIGHT)

    # --- Barra de progresso ------------------------------------------------
    style.configure(
        "Anota.Horizontal.TProgressbar",
        troughcolor=BG_LIGHT,
        background=PRIMARY_COLOR,
        lightcolor=PRIMARY_COLOR,
        darkcolor=PRIMARY_COLOR,
        bordercolor=BORDER_COLOR,
        thickness=8,
    )

    # --- Rótulos -----------------------------------------------------------
    style.configure("Body.TLabel", background=BG_LIGHT, foreground=TEXT_DARK, font=FONT_BODY)
    style.configure("Muted.TLabel", background=BG_LIGHT, foreground=TEXT_MUTED, font=FONT_BODY)
