"""Variáveis visuais compartilhadas pela interface do SuporteTools.

Paleta baseada na identidade visual oficial do Anota AI:
- Azul #0098FC como cor principal de marca
- Azul escuro #005C9E para hover e estados pressionados
- Cinza grafite #1F2937 para textos
- Verde #25D366 para resultados positivos
- Fonte Roboto (com fallback para Segoe UI no Windows)
"""

# ---------------------------------------------------------------------------
# Cores de marca (paleta oficial Anota AI)
# ---------------------------------------------------------------------------
PRIMARY_COLOR = "#0098FC"        # azul Anota AI — cabeçalho e destaques
PRIMARY_DARK = "#005C9E"         # azul escuro — hover/pressed
PRIMARY_MID = "#0188E0"          # azul intermediário — bordas e detalhes
PRIMARY_LIGHT = "#E6F4FE"        # azul muito claro — fundos sutis

# ---------------------------------------------------------------------------
# Superfícies
# ---------------------------------------------------------------------------
BG_WHITE = "#FFFFFF"
BG_LIGHT = "#F7F9FB"             # fundo geral da aplicação
BG_CARD = "#FFFFFF"              # cartões
BG_SIDEBAR = "#FAFBFC"           # menu lateral
SHADOW_COLOR = "#E8EDF2"
BORDER_COLOR = "#E1E7ED"

# ---------------------------------------------------------------------------
# Texto
# ---------------------------------------------------------------------------
TEXT_DARK = "#1F2937"            # grafite Anota AI — texto principal
TEXT_MUTED = "#6B7280"           # texto secundário
TEXT_WHITE = "#FFFFFF"

# ---------------------------------------------------------------------------
# Estados
# ---------------------------------------------------------------------------
ACCENT_GREEN = "#25D366"         # verde Anota AI — sucesso
ACCENT_YELLOW = "#F5A623"        # atenção
ACCENT_RED = "#E53935"           # erro
HOVER_COLOR = PRIMARY_DARK

# Aliases semânticos usados pela interface e pela saída dos diagnósticos.
SECONDARY_COLOR = TEXT_WHITE
RESULT_TEXT_COLOR = TEXT_DARK
POSITIVE_COLOR = ACCENT_GREEN
NEGATIVE_COLOR = ACCENT_RED

# ---------------------------------------------------------------------------
# Tipografia
# ---------------------------------------------------------------------------
# Roboto é a fonte oficial do Anota AI. No Windows, Segoe UI serve de
# fallback caso o Roboto não esteja instalado.
FONT_FAMILY = "Roboto"
FONT_FALLBACK = "Segoe UI"
FONT_MONO = "Consolas"

FONT_TITLE = (FONT_FAMILY, 15, "bold")
FONT_HEADING = (FONT_FAMILY, 17, "bold")
FONT_SUBHEADING = (FONT_FAMILY, 12, "bold")
FONT_BUTTON = (FONT_FAMILY, 10)
FONT_BUTTON_BOLD = (FONT_FAMILY, 10, "bold")
FONT_CARD = (FONT_FAMILY, 11, "bold")
FONT_BODY = (FONT_FAMILY, 10)
FONT_TERMINAL = (FONT_MONO, 10)
FONT_STATUS = (FONT_FAMILY, 9, "bold")

# ---------------------------------------------------------------------------
# Métricas
# ---------------------------------------------------------------------------
WINDOW_TITLE = "SuporteTools — Anota AI"
HEADER_HEIGHT = 64
SIDEBAR_WIDTH = 230
PADDING_BODY = (16, 16)
PADDING_CONTENT = (40, 35)

# Estilos das abas internas.
PADX_BUTTONS = 2
PADY_BUTTONS = 2
PADX_SIDEBAR = 14
PADY_SIDEBAR = 14


__all__ = [
    "PRIMARY_COLOR",
    "PRIMARY_DARK",
    "PRIMARY_MID",
    "PRIMARY_LIGHT",
    "BG_WHITE",
    "BG_LIGHT",
    "BG_CARD",
    "BG_SIDEBAR",
    "SHADOW_COLOR",
    "BORDER_COLOR",
    "TEXT_DARK",
    "TEXT_MUTED",
    "TEXT_WHITE",
    "ACCENT_GREEN",
    "ACCENT_YELLOW",
    "ACCENT_RED",
    "HOVER_COLOR",
    "SECONDARY_COLOR",
    "RESULT_TEXT_COLOR",
    "POSITIVE_COLOR",
    "NEGATIVE_COLOR",
    "FONT_FAMILY",
    "FONT_FALLBACK",
    "FONT_MONO",
    "FONT_TITLE",
    "FONT_HEADING",
    "FONT_SUBHEADING",
    "FONT_BUTTON",
    "FONT_BUTTON_BOLD",
    "FONT_CARD",
    "FONT_BODY",
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
