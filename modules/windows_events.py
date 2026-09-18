"""Eventos críticos do Windows da última hora."""

from __future__ import annotations

import platform
import subprocess


def _creation_flags() -> int:
    return getattr(subprocess, "CREATE_NO_WINDOW", 0) if platform.system() == "Windows" else 0


def _startup_info() -> "subprocess.STARTUPINFO | None":
    if platform.system() != "Windows":
        return None
    t = getattr(subprocess, "STARTUPINFO", None)
    if t is None:
        return None
    try:
        si = t()
        si.dwFlags |= getattr(subprocess, "STARTF_USESHOWWINDOW", 0)
        si.wShowWindow = getattr(subprocess, "SW_HIDE", 0)
    except (AttributeError, OSError, TypeError):
        return None
    return si


def _run_ps(command: str, timeout: int = 30) -> str:
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            creationflags=_creation_flags(),
            startupinfo=_startup_info(),
        )
        return (result.stdout or "").strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def get_windows_events() -> dict[str, int]:
    """Coleta contadores de eventos críticos da última hora."""
    if platform.system() != "Windows":
        return {}

    # Erros de aplicação
    app_errors = _run_ps(
        "(Get-WinEvent -FilterHashtable @{LogName='Application'; Level=2; "
        "StartTime=(Get-Date).AddHours(-1)} -MaxEvents 100 "
        "-ErrorAction SilentlyContinue).Count"
    )
    app_error_count = int(app_errors) if app_errors and app_errors.isdigit() else 0

    # Erros do AnotaAIResponde
    anotaai_errors = _run_ps(
        "(Get-WinEvent -FilterHashtable @{LogName='Application'; Level=2; "
        "StartTime=(Get-Date).AddHours(-1)} -ErrorAction SilentlyContinue | "
        "Where-Object {$_.Message -match 'AnotaAIResponde'}).Count"
    )
    anotaai_count = int(anotaai_errors) if anotaai_errors and anotaai_errors.isdigit() else 0

    # Erros de sistema
    sys_errors = _run_ps(
        "(Get-WinEvent -FilterHashtable @{LogName='System'; Level=2; "
        "StartTime=(Get-Date).AddHours(-1)} -MaxEvents 100 "
        "-ErrorAction SilentlyContinue).Count"
    )
    sys_error_count = int(sys_errors) if sys_errors and sys_errors.isdigit() else 0

    # Spooler crashes
    spooler_crashes = _run_ps(
        "(Get-WinEvent -FilterHashtable @{LogName='System'; Level=2; "
        "StartTime=(Get-Date).AddHours(-1)} -ErrorAction SilentlyContinue | "
        "Where-Object {$_.Id -eq 7031 -and $_.Message -match 'Spooler'}).Count"
    )
    spooler_count = int(spooler_crashes) if spooler_crashes and spooler_crashes.isdigit() else 0

    # Erros de disco
    disk_errors = _run_ps(
        "(Get-WinEvent -FilterHashtable @{LogName='System'; Level=2; "
        "StartTime=(Get-Date).AddHours(-1)} -ErrorAction SilentlyContinue | "
        "Where-Object {$_.ProviderName -match 'Disk|NTFS' -or $_.Id -eq 7}).Count"
    )
    disk_count = int(disk_errors) if disk_errors and disk_errors.isdigit() else 0

    # Quedas de energia
    power_events = _run_ps(
        "(Get-WinEvent -FilterHashtable @{LogName='System'; "
        "StartTime=(Get-Date).AddHours(-1)} -ErrorAction SilentlyContinue | "
        "Where-Object {$_.Id -eq 41}).Count"
    )
    power_count = int(power_events) if power_events and power_events.isdigit() else 0

    # Erros de rede
    network_events = _run_ps(
        "(Get-WinEvent -FilterHashtable @{LogName='System'; Level=2; "
        "StartTime=(Get-Date).AddHours(-1)} -ErrorAction SilentlyContinue | "
        "Where-Object {$_.Id -eq 4201 -or $_.Id -eq 4202 -or "
        "$_.ProviderName -match 'Tcpip'}).Count"
    )
    network_count = int(network_events) if network_events and network_events.isdigit() else 0

    # Erros de SSL/TLS
    ssl_errors = _run_ps(
        "(Get-WinEvent -FilterHashtable @{LogName='System'; "
        "StartTime=(Get-Date).AddHours(-1)} -MaxEvents 50 "
        "-ErrorAction SilentlyContinue | Where-Object {$_.Message -match "
        "'certificate|SSL|TLS'}).Count"
    )
    ssl_count = int(ssl_errors) if ssl_errors and ssl_errors.isdigit() else 0

    # Crashes do Chrome/Electron
    chrome_crashes = _run_ps(
        "(Get-WinEvent -FilterHashtable @{LogName='Application'; Level=2; "
        "StartTime=(Get-Date).AddHours(-1)} -ErrorAction SilentlyContinue | "
        "Where-Object {$_.Message -match 'chrome|electron|renderer'}).Count"
    )
    chrome_count = int(chrome_crashes) if chrome_crashes and chrome_crashes.isdigit() else 0

    return {
        "app_errors": app_error_count,
        "anotaai_errors": anotaai_count,
        "system_errors": sys_error_count,
        "spooler_crashes": spooler_count,
        "disk_errors": disk_count,
        "power_events": power_count,
        "network_events": network_count,
        "ssl_errors": ssl_count,
        "chrome_crashes": chrome_count,
    }


def display_windows_events() -> None:
    events = get_windows_events()
    if not events:
        print("Disponível apenas no Windows.")
        return

    print("Eventos críticos (última hora):")
    print(f"  Erros de aplicação: {events['app_errors']}")
    if events["anotaai_errors"] > 0:
        print(
            f"  Erros do AnotaAIResponde: {events['anotaai_errors']} — "
            "AVISO: verificar erros do app"
        )
    print(f"  Erros de sistema: {events['system_errors']}")
    if events["spooler_crashes"] > 0:
        print(
            f"  Crashes do spooler: {events['spooler_crashes']} — "
            "AVISO: reiniciar spooler"
        )
    if events["disk_errors"] > 0:
        print(
            f"  Erros de disco: {events['disk_errors']} — "
            "AVISO: verificar saúde do disco"
        )
    if events["power_events"] > 0:
        print(
            f"  Quedas de energia: {events['power_events']} — "
            "AVISO: máquina reiniciou inesperadamente"
        )
    if events["network_events"] > 0:
        print(
            f"  Eventos de rede: {events['network_events']} — "
            "AVISO: problemas de conectividade"
        )
    if events["ssl_errors"] > 0:
        print(
            f"  Erros de SSL/TLS: {events['ssl_errors']} — "
            "AVISO: certificados ou TLS"
        )
    if events["chrome_crashes"] > 0:
        print(
            f"  Crashes do Electron/Chrome: {events['chrome_crashes']} — "
            "AVISO: app pode ter fechado sozinho"
        )
    if all(value == 0 for value in events.values()):
        print("  Nenhum evento crítico encontrado. Tudo normal.")
