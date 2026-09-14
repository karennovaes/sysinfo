"""Variáveis de configuração compartilhadas pelo Diagnóstico do Sistema."""

# Comando para abrir a pasta de Impressoras do Windows.
PRINTERS_COMMAND = "shell:::{A8A91A66-3A7D-4424-8D24-04E180695C7A}"

# Downloads de instaladores e utilitários.
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

__all__ = [
    "PRINTERS_COMMAND",
    "DRIVER_URL",
    "DRIVER_FILENAME",
    "DESKTOP_URL",
    "DESKTOP_FILENAME",
    "NETSTATGUI_URL",
    "NETSTATGUI_FILENAME",
]
