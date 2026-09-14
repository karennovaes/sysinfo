"""Verificações e reparos de manutenção do Windows para o Anota AI."""

from __future__ import annotations

import platform
import subprocess


def _creation_flags() -> int:
    return subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0


def _startup_info() -> "subprocess.STARTUPINFO | None":
    """Configura STARTUPINFO para ocultar a janela do console no Windows."""
    if platform.system() != "Windows":
        return None
    startupinfo_type = getattr(subprocess, "STARTUPINFO", None)
    if startupinfo_type is None:
        return None
    try:
        startupinfo = startupinfo_type()
        startupinfo.dwFlags |= getattr(subprocess, "STARTF_USESHOWWINDOW", 0)
        startupinfo.wShowWindow = getattr(subprocess, "SW_HIDE", 0)
    except (AttributeError, OSError, TypeError):
        return None
    return startupinfo


def _powershell(command: str, args: list[str] | None = None, timeout: int = 30) -> str:
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", command, *(args or [])],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            creationflags=_creation_flags(),
            startupinfo=_startup_info(),
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return f"Erro ao executar PowerShell: {exc}"
    return (result.stdout or result.stderr or "Sem saída.").strip()


def display_antivirus_status() -> None:
    if platform.system() != "Windows":
        print("Disponível apenas no Windows.")
        return
    output = _powershell("Get-MpComputerStatus | Select-Object AntivirusEnabled, RealTimeProtectionEnabled | Format-List")
    print(output)
    lowered = output.casefold()
    antivirus_on = "antivirusenabled : true" in lowered
    realtime_on = "realtimeprotectionenabled : true" in lowered
    print(f"Antivírus: {'ATIVO' if antivirus_on else 'INATIVO ou não identificado'}")
    print(f"Proteção em tempo real: {'ATIVA' if realtime_on else 'INATIVA ou não identificada'}")
    if not antivirus_on or not realtime_on:
        print("Aviso: a proteção pode estar desativada ou outro antivírus pode estar interferindo.")



def display_startup_programs() -> None:
    if platform.system() != "Windows":
        print("Disponível apenas no Windows.")
        return
    try:
        result = subprocess.run(
            ["wmic", "startup", "get", "Caption,Command,Location"],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
            creationflags=_creation_flags(),
            startupinfo=_startup_info(),
        )
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"Não foi possível consultar a inicialização: {exc}")
        return
    output = (result.stdout or result.stderr or "Sem dados.").strip()
    print(output)
