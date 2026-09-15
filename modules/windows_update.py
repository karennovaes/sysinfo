"""Verificação de atualizações pendentes do Windows Update."""

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


def get_pending_updates() -> dict:
    """Verifica atualizações pendentes do Windows Update."""
    if platform.system() != "Windows":
        return {"available": False, "pending_count": 0, "reboot_required": False, "updates": []}

    # Usar o módulo PSWindowsUpdate se disponível, senão usar WMI/COM
    # Método 1: Verificar se há reinicialização pendente
    reboot_key = _run_ps(
        "(Get-ItemProperty -Path 'HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\WindowsUpdate\\Auto Update\\RebootRequired' "
        "-ErrorAction SilentlyContinue).PSChildName"
    )
    reboot_required = bool(reboot_key)

    # Método 2: Usar COM object para verificar updates pendentes
    ps_script = """
    try {
        $session = New-Object -ComObject Microsoft.Update.Session
        $searcher = $session.CreateUpdateSearcher()
        $result = $searcher.Search("IsInstalled=0 and Type='Software'")
        $pending = @()
        foreach ($update in $result.Updates) {
            $pending += $update.Title
        }
        $pending -join "|"
    } catch {
        Write-Output "ERROR"
    }
    """
    output = _run_ps(ps_script, timeout=60)

    if output == "ERROR" or not output:
        return {"available": False, "pending_count": 0, "reboot_required": reboot_required, "updates": []}

    updates = [update.strip() for update in output.split("|") if update.strip()]
    return {
        "available": len(updates) > 0,
        "pending_count": len(updates),
        "reboot_required": reboot_required,
        "updates": updates,
    }


def display_windows_update() -> None:
    result = get_pending_updates()
    if not result.get("available") and not result.get("reboot_required"):
        print("Windows Update: nenhuma atualização pendente.")
        return

    if result["reboot_required"]:
        print("AVISO: Reinicialização pendente do Windows Update.")
        print("  O computador pode reiniciar automaticamente. Salve seus trabalhos.")

    if result["pending_count"] > 0:
        print(f"Atualizações pendentes: {result['pending_count']}")
        for i, update in enumerate(result["updates"][:10], 1):
            print(f"  {i}. {update}")
        if result["pending_count"] > 10:
            print(f"  ... e mais {result['pending_count'] - 10} atualização(ões).")
        print("AVISO: Atualizações pendentes podem causar reinícios inesperados.")
