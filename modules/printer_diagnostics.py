"""Diagnóstico completo de impressoras no Windows."""

from __future__ import annotations

import csv as csv_mod
import io
import platform
import re
import socket
import subprocess
from typing import Any


def _creation_flags() -> int:
    """Retorna a flag que evita abrir uma janela de console no Windows."""
    return getattr(subprocess, "CREATE_NO_WINDOW", 0) if platform.system() == "Windows" else 0


def _startup_info() -> "subprocess.STARTUPINFO | None":
    """Configura STARTUPINFO para ocultar a janela do PowerShell."""
    if platform.system() != "Windows":
        return None
    startup_info_type = getattr(subprocess, "STARTUPINFO", None)
    if startup_info_type is None:
        return None
    try:
        startup_info = startup_info_type()
        startup_info.dwFlags |= getattr(subprocess, "STARTF_USESHOWWINDOW", 0)
        startup_info.wShowWindow = getattr(subprocess, "SW_HIDE", 0)
    except (AttributeError, OSError, TypeError):
        return None
    return startup_info


def _run_ps(command: str) -> str:
    """Executa PowerShell sem exibir console e devolve somente a saída padrão."""
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
            creationflags=_creation_flags(),
            startupinfo=_startup_info(),
        )
        return (result.stdout or "").strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def _ps_string(value: str) -> str:
    """Escapa um texto para uso como string literal entre aspas simples no PS."""
    return "'" + value.replace("'", "''") + "'"


def _test_network_printer(port_name: str) -> dict[str, Any]:
    """Testa conectividade TCP com uma impressora de rede."""
    # Portas padrão do Windows podem aparecer como IP_10.0.0.5, enquanto
    # outras configurações usam 10.0.0.5:9100 ou 10.0.0.5_9100.
    match = re.search(
        r"(?<!\d)(\d{1,3}(?:\.\d{1,3}){3})(?:(?::|_)(\d{1,5}))?",
        port_name,
    )
    if not match:
        return {"reachable": False, "error": "formato de porta inválido"}

    ip = match.group(1)
    tcp_port = int(match.group(2)) if match.group(2) else 9100
    if any(int(octet) > 255 for octet in ip.split(".")) or not 1 <= tcp_port <= 65535:
        return {"reachable": False, "error": "formato de porta inválido"}

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(2)
            result = sock.connect_ex((ip, tcp_port))
        if result == 0:
            return {"reachable": True, "error": ""}
        return {"reachable": False, "error": "connection_failed"}
    except (OSError, socket.error):
        return {"reachable": False, "error": "connection_error"}


def _get_health_score(
    is_online: bool,
    queued_jobs: int,
    has_generic_driver: bool,
    has_error: bool,
    is_paused: bool,
    is_network_reachable: bool,
) -> int:
    """Calcula uma pontuação de saúde entre 0 e 100."""
    score = 100
    if not is_online:
        score -= 50
    if queued_jobs > 0:
        score -= 10
    if queued_jobs > 5:
        score -= 20
    if has_generic_driver:
        score -= 15
    if has_error:
        score -= 30
    if is_paused:
        score -= 25
    if not is_network_reachable:
        score -= 40
    return max(0, score)


def _printer_rows(csv_output: str) -> list[dict[str, str]]:
    """Converte a saída CSV do PowerShell em linhas, sem quebrar diagnóstico."""
    try:
        return list(csv_mod.DictReader(io.StringIO(csv_output)))
    except (csv_mod.Error, TypeError, ValueError):
        return []


def _get_queue_counts(printer_name: str) -> tuple[int, int]:
    """Obtém total de jobs e total de jobs em estado de erro."""
    safe_name = _ps_string(printer_name)
    total_output = _run_ps(
        f"(Get-PrintJob -PrinterName {safe_name} -ErrorAction SilentlyContinue).Count"
    )
    error_output = _run_ps(
        "(Get-PrintJob -PrinterName "
        f"{safe_name} -ErrorAction SilentlyContinue | "
        "Where-Object { $_.JobStatus -match "
        "'Error|Blocked|Offline|PaperOut|UserIntervention|Paused' } | "
        "Measure-Object).Count"
    )

    try:
        queued_jobs = int(total_output) if total_output else 0
    except ValueError:
        queued_jobs = 0
    try:
        error_jobs = int(error_output) if error_output else 0
    except ValueError:
        error_jobs = 0
    return max(0, queued_jobs), max(0, error_jobs)


def get_printer_diagnostics() -> list[dict[str, Any]]:
    """Coleta diagnóstico de todas as impressoras físicas instaladas."""
    if platform.system() != "Windows":
        return []

    # Impressoras virtuais não representam o hardware que o suporte precisa
    # diagnosticar. O filtro também remove portas reservadas pelo Windows.
    ps_script = r"""
    $virtual = 'Microsoft Print to PDF|Microsoft XPS|Fax|OneNote|PORTPROMPT|nul:|SHRFAX'
    Get-Printer | Where-Object {
        $_.PortName -notmatch $virtual -and $_.Name -notmatch $virtual
    } | Select-Object Name,PortName,DriverName,PrinterStatus,WorkflowPolicy,Location | ConvertTo-Csv -NoTypeInformation
    """
    csv_output = _run_ps(ps_script)
    if not csv_output:
        return []

    rows = _printer_rows(csv_output)
    if not rows:
        return []

    default_name = _run_ps(
        "(Get-WmiObject -Query 'SELECT * FROM Win32_Printer WHERE Default = TRUE').Name"
    ).strip()
    printers: list[dict[str, Any]] = []

    for row in rows:
        name = (row.get("Name") or "").strip()
        if not name:
            continue
        port_name = (row.get("PortName") or "").strip()
        driver_name = (row.get("DriverName") or "").strip()
        try:
            status_code = int((row.get("PrinterStatus") or "0").strip())
        except (AttributeError, ValueError):
            status_code = 0

        status_map = {
            1: "outro",
            2: "desconhecida",
            3: "ociosa",
            4: "imprimindo",
            5: "aquecendo",
            6: "pronta",
            7: "erro",
        }
        status_text = status_map.get(status_code, "desconhecida")
        is_online = status_code not in (2, 7)
        is_paused = (row.get("WorkflowPolicy") or "0").strip() == "1"
        has_error = status_code in (2, 7)
        is_default = name == default_name
        has_generic_driver = bool(
            re.search(r"Generic|Text Only|Microsoft", driver_name, re.IGNORECASE)
        )

        queued_jobs, error_jobs = _get_queue_counts(name)

        is_network = bool(re.search(r"\d{1,3}(?:\.\d{1,3}){3}", port_name))
        network_test = (
            _test_network_printer(port_name)
            if is_network
            else {"reachable": True, "error": ""}
        )
        health = _get_health_score(
            is_online,
            queued_jobs,
            has_generic_driver,
            has_error or error_jobs > 0,
            is_paused,
            network_test["reachable"],
        )

        printers.append(
            {
                "name": name,
                "port": port_name,
                "driver": driver_name,
                "status": status_text,
                "is_online": is_online,
                "is_default": is_default,
                "is_paused": is_paused,
                "has_error": has_error,
                "queued_jobs": queued_jobs,
                "error_jobs": error_jobs,
                "has_generic_driver": has_generic_driver,
                "is_network": is_network,
                "network_reachable": network_test["reachable"],
                "network_error": network_test["error"],
                "health_score": health,
            }
        )
    return printers


def get_spooler_status() -> dict[str, Any]:
    """Verifica se o processo do spooler está rodando, além de CPU e memória."""
    try:
        import psutil
    except ImportError:
        return {"running": False, "pid": 0, "cpu_percent": 0.0, "memory_mb": 0.0}

    try:
        for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_info"]):
            info = proc.info
            process_name = info.get("name") or ""
            if "spoolsv" not in process_name.casefold():
                continue

            cpu_percent = info.get("cpu_percent")
            if cpu_percent is None:
                try:
                    cpu_percent = proc.cpu_percent(interval=0.1)
                except (psutil.Error, OSError):
                    cpu_percent = 0.0
            memory_info = info.get("memory_info")
            memory_mb = 0.0
            if memory_info is not None:
                memory_mb = round(memory_info.rss / (1024 * 1024), 2)
            return {
                "running": True,
                "pid": info.get("pid", 0),
                "cpu_percent": round(float(cpu_percent or 0), 2),
                "memory_mb": memory_mb,
            }
    except (OSError, psutil.Error):
        pass
    return {"running": False, "pid": 0, "cpu_percent": 0.0, "memory_mb": 0.0}


def display_printer_diagnostics() -> None:
    """Exibe o diagnóstico em formato adequado para o painel de suporte."""
    printers = get_printer_diagnostics()
    if not printers:
        print("Nenhuma impressora física encontrada.")
        spooler = get_spooler_status()
        if spooler["running"]:
            print(
                "Spooler: rodando "
                f"(PID {spooler['pid']}, {spooler['cpu_percent']:.1f}% CPU, "
                f"{spooler['memory_mb']:.1f} MB)"
            )
        else:
            print("Spooler: NÃO está rodando. AVISO: Reinicie o serviço.")
        return

    for printer in printers:
        print(f"Impressora: {printer['name']}")
        print(
            f"  Status: {printer['status']} | "
            f"{'Padrão' if printer['is_default'] else 'Não padrão'}"
        )
        driver_warning = " (GENÉRICO - AVISO)" if printer["has_generic_driver"] else ""
        print(f"  Driver: {printer['driver']}{driver_warning}")
        print(
            f"  Fila: {printer['queued_jobs']} job(s) "
            f"({printer['error_jobs']} com erro)"
        )
        if printer["is_network"]:
            reachable = "alcançável" if printer["network_reachable"] else "INALCANÇÁVEL - AVISO"
            print(f"  Rede: {reachable} ({printer['port']})")
        if printer["is_paused"]:
            print("  AVISO: Impressora pausada.")
        if printer["has_error"] or printer["error_jobs"]:
            print("  AVISO: Impressora ou fila com erro.")
        print(f"  Health Score: {printer['health_score']}/100")
        if printer["health_score"] < 70:
            print("  AVISO: Health score baixo. Verifique os problemas acima.")
        print()

    spooler = get_spooler_status()
    if spooler["running"]:
        print(
            f"Spooler: rodando (PID {spooler['pid']}, "
            f"{spooler['cpu_percent']:.1f}% CPU, {spooler['memory_mb']:.1f} MB)"
        )
    else:
        print("Spooler: NÃO está rodando. AVISO: Reinicie o serviço.")
