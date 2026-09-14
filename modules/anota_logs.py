"""Leitura segura dos erros mais recentes dos logs do Anota AI."""

from __future__ import annotations

import os
from pathlib import Path


def _log_directories() -> list[Path]:
    """Lista os diretórios de logs em APPDATA e LOCALAPPDATA.

    O caminho AnotaAIResponde/logs é verificado em ambas as raízes.
    """
    roots = [os.environ.get("APPDATA"), os.environ.get("LOCALAPPDATA")]
    # APPDATA e LOCALAPPDATA podem conter AnotaAIResponde/logs.
    directories: list[Path] = []
    for root in roots:
        if root:
            base = Path(root)
            directories.extend((
                base / "AnotaAIResponde" / "logs",
                base / "anotaairesponde" / "logs",
                base / "anotaai" / "logs",
                base / "anota ai" / "logs",
            ))
    return directories


def find_latest_log() -> Path | None:
    """Retorna o log modificado mais recentemente nos diretórios conhecidos."""
    candidates: list[Path] = []
    for directory in _log_directories():
        if not directory.is_dir():
            continue
        try:
            candidates.extend(item for item in directory.iterdir() if item.is_file())
        except OSError:
            continue
    if not candidates:
        return None
    return max(candidates, key=lambda item: item.stat().st_mtime)


def recent_error_lines(limit: int = 10) -> tuple[Path | None, list[str]]:
    """Lê as últimas linhas com error, exception ou fail de um log."""
    log_path = find_latest_log()
    if log_path is None:
        return None, []
    try:
        lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-50:]
    except OSError:
        return log_path, []
    errors = [line for line in lines if any(term in line.casefold() for term in ("error", "exception", "fail"))]
    return log_path, errors[-limit:]
