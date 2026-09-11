"""Exportação e cópia do relatório exibido no terminal da interface."""

from __future__ import annotations

import os
import platform
import subprocess
from datetime import datetime
from pathlib import Path


def downloads_path() -> Path:
    if platform.system() == "Windows" and os.environ.get("USERPROFILE"):
        return Path(os.environ["USERPROFILE"]) / "Downloads"
    return Path.home() / "Downloads"


def _creation_flags() -> int:
    return subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0


def open_downloads() -> None:
    """Abre a pasta Downloads, sem criar janela de console no Windows."""
    folder = downloads_path()
    if platform.system() == "Windows":
        subprocess.Popen(["explorer", str(folder)], creationflags=_creation_flags())
    elif platform.system() == "Darwin":
        subprocess.Popen(["open", str(folder)], creationflags=_creation_flags())
    else:
        subprocess.Popen(["xdg-open", str(folder)], creationflags=_creation_flags())


def export_report(content: str, open_folder: bool = True, now: datetime | None = None) -> str:
    """Salva o conteúdo completo em Downloads e retorna o caminho criado."""
    folder = downloads_path()
    folder.mkdir(parents=True, exist_ok=True)
    timestamp = now or datetime.now()
    filename = f"Diagnostico_AnotaAI_{timestamp:%Y-%m-%d_%H%M}.txt"
    destination = folder / filename
    destination.write_text(content, encoding="utf-8")
    if open_folder:
        try:
            open_downloads()
        except OSError:
            # O relatório já foi salvo; abrir a pasta é apenas uma conveniência.
            pass
    return f"Relatório salvo em: {destination}"


def copy_report_to_clipboard(content: str, root: object) -> str:
    """Copia o relatório para o clipboard de uma janela Tk já existente."""
    try:
        root.clipboard_clear()  # type: ignore[attr-defined]
        root.clipboard_append(content)  # type: ignore[attr-defined]
        root.update()  # type: ignore[attr-defined]
    except (AttributeError, OSError, RuntimeError) as exc:
        return f"Não foi possível copiar o relatório: {exc}"
    return "Relatório copiado para a área de transferência!"
