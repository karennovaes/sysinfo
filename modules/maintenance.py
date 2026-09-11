"""Verificações e reparos de manutenção do Windows para o Anota AI."""

from __future__ import annotations

import os
import platform
import subprocess
from pathlib import Path

from .anota_process import find_anota_executable


def _creation_flags() -> int:
    return subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0


def _powershell(command: str, args: list[str] | None = None, timeout: int = 30) -> str:
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", command, *(args or [])],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            creationflags=_creation_flags(),
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return f"Erro ao executar PowerShell: {exc}"
    return (result.stdout or result.stderr or "Sem saída.").strip()


def display_antivirus_status() -> None:
    print("STATUS DO ANTIVÍRUS")
    print("-" * 64)
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


def repair_shortcut() -> str:
    """Cria/recria o atalho Anota AI na área de trabalho."""
    if platform.system() != "Windows":
        return "Disponível apenas no Windows."
    executable = find_anota_executable()
    if executable is None:
        return "Não foi possível reparar o atalho: executável do Anota AI não encontrado."
    desktop = Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Desktop"
    shortcut = desktop / "Anota AI.lnk"
    command = (
        "$ws = New-Object -ComObject WScript.Shell; "
        "$s = $ws.CreateShortcut($args[0]); "
        "$s.TargetPath = $args[1]; $s.WorkingDirectory = Split-Path $args[1]; $s.Save()"
    )
    result = _powershell(command, [str(shortcut), str(executable)])
    if result.startswith("Erro ao executar"):
        return result
    return f"Atalho reparado: {shortcut}\nDestino: {executable}"


def display_repair_shortcut() -> None:
    print("REPARAR ATALHO")
    print("-" * 64)
    print(repair_shortcut())


def display_startup_programs() -> None:
    print("PROGRAMAS NA INICIALIZAÇÃO DO WINDOWS")
    print("-" * 64)
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
        )
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"Não foi possível consultar a inicialização: {exc}")
        return
    output = (result.stdout or result.stderr or "Sem dados.").strip()
    print(output)
