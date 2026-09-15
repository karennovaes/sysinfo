"""Verificação do status do WhatsApp no Anota AI."""

from __future__ import annotations

import os
import platform
from pathlib import Path


def get_whatsapp_status() -> dict[str, str | bool | int]:
    """Lê o status do WhatsApp a partir do arquivo wpp_status.txt."""
    if platform.system() != "Windows":
        return {
            "available": False,
            "connected": False,
            "status": "disponível apenas no Windows",
            "raw_value": -1,
        }

    appdata = os.environ.get("APPDATA", "")
    possible_paths = [
        Path(appdata) / "AnotaAIResponde" / "wpp_status.txt",
        Path(appdata) / "anotaairesponde" / "wpp_status.txt",
    ]

    status_file = next((path for path in possible_paths if path.is_file()), None)

    if status_file is None:
        return {
            "available": False,
            "connected": False,
            "status": "arquivo de status não encontrado — WhatsApp não configurado",
            "raw_value": -1,
        }

    try:
        raw = status_file.read_text(encoding="utf-8", errors="replace").strip()
        value = int(raw)
    except (ValueError, OSError):
        return {
            "available": True,
            "connected": False,
            "status": "não foi possível ler o status",
            "raw_value": -1,
        }

    if value == 1:
        status_text = "conectado"
        connected = True
    elif value == 0:
        status_text = "desconectado"
        connected = False
    else:
        status_text = f"status desconhecido (valor: {value})"
        connected = False

    return {
        "available": True,
        "connected": connected,
        "status": status_text,
        "raw_value": value,
    }


def display_whatsapp_status() -> None:
    """Exibe o status do WhatsApp no terminal."""
    result = get_whatsapp_status()
    print(f"WhatsApp: {result['status']}")
    if result["connected"]:
        print("O WhatsApp está funcionando normalmente.")
    elif result["available"]:
        print("AVISO: O WhatsApp pode estar desconectado. Verifique a conexão no Anota AI.")
