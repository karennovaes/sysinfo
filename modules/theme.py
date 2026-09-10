"""Variáveis visuais compartilhadas pela interface do Diagnóstico do Sistema."""

# Cores da interface.
PRIMARY_COLOR = "#EA1D2F"
BG_WHITE = "#FFFFFF"
BG_LIGHT = "#F7F7F8"
BG_CARD = "#FAFAFA"
SHADOW_COLOR = "#E0E0E0"
TEXT_DARK = "#3F3E3E"
TEXT_WHITE = "#FFFFFF"
ACCENT_GREEN = "#2E7D32"
HOVER_COLOR = "#C41523"
BORDER_COLOR = "#E8E8E8"

# Aliases semânticos usados pela interface e pela saída dos diagnósticos.
SECONDARY_COLOR = TEXT_WHITE
RESULT_TEXT_COLOR = TEXT_DARK
POSITIVE_COLOR = ACCENT_GREEN
NEGATIVE_COLOR = PRIMARY_COLOR

# Fontes da interface.
FONT_TITLE = ("Arial", 14, "bold")
FONT_HEADING = ("Segoe UI", 16, "bold")
FONT_BUTTON = ("Segoe UI", 9, "bold")
FONT_CARD = ("Segoe UI", 11, "bold")
FONT_TERMINAL = ("Consolas", 10)
FONT_STATUS = ("Segoe UI", 9, "bold")

# Estilos da tela principal.
WINDOW_TITLE = "Diagnóstico do Sistema — Anota AI"
HEADER_HEIGHT = 70
SIDEBAR_WIDTH = 220
PADDING_BODY = (12, 12)
PADDING_CONTENT = (40, 35)

# Estilos das abas internas.
PADX_BUTTONS = 2
PADY_BUTTONS = 2
PADX_SIDEBAR = 12
PADY_SIDEBAR = 12


__all__ = [
    "PRIMARY_COLOR",
    "BG_WHITE",
    "BG_LIGHT",
    "BG_CARD",
    "SHADOW_COLOR",
    "TEXT_DARK",
    "TEXT_WHITE",
    "ACCENT_GREEN",
    "HOVER_COLOR",
    "BORDER_COLOR",
    "SECONDARY_COLOR",
    "RESULT_TEXT_COLOR",
    "POSITIVE_COLOR",
    "NEGATIVE_COLOR",
    "FONT_TITLE",
    "FONT_HEADING",
    "FONT_BUTTON",
    "FONT_CARD",
    "FONT_TERMINAL",
    "FONT_STATUS",
    "WINDOW_TITLE",
    "HEADER_HEIGHT",
    "SIDEBAR_WIDTH",
    "PADDING_BODY",
    "PADDING_CONTENT",
    "PADX_BUTTONS",
    "PADY_BUTTONS",
    "PADX_SIDEBAR",
    "PADY_SIDEBAR",
]
